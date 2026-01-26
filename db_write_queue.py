"""
Centralized database write queue for handling concurrent writes to SQLite.

This module provides a thread-safe write queue that batches database writes
and uses retry logic with exponential backoff to handle SQLite lock contention
when multiple processes are writing to the same database file.
"""

import logging
import threading
import queue
import time
import sqlite3
from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class WriteOperation(Enum):
    """Types of database write operations."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UPSERT = "upsert"  # INSERT OR REPLACE


@dataclass
class WriteRequest:
    """Represents a single database write request."""
    table_name: str
    operation: WriteOperation
    data: Dict[str, Any]
    primary_key: Optional[str] = None  # For UPDATE/UPSERT operations
    callback: Optional[Callable[[bool, Optional[Exception]], None]] = None


class DatabaseWriteQueue:
    """
    Thread-safe database write queue with batching and retry logic.
    
    This class serializes all database writes through a single background thread,
    eliminating concurrent write contention that causes "database is locked" errors.
    
    Features:
    - Batching: Groups writes together (up to batch_size at a time)
    - Retry logic: Exponential backoff for locked database scenarios
    - Non-blocking: Callers enqueue and continue without waiting
    - Graceful shutdown: Flushes remaining writes before stopping
    """
    
    def __init__(
        self,
        db_tables: Dict = None,
        batch_size: int = 50,
        flush_interval: float = 2.0,
        max_retries: int = 5,
        base_retry_delay: float = 0.1
    ):
        """
        Initialize the write queue.
        
        Args:
            db_tables: Dictionary of database tables from setup_database()
            batch_size: Maximum number of writes to process in one batch
            flush_interval: Maximum seconds to wait before flushing partial batch
            max_retries: Maximum retry attempts for locked database
            base_retry_delay: Initial delay for exponential backoff (seconds)
        """
        self.db_tables = db_tables
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        
        self._queue: queue.Queue[WriteRequest] = queue.Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Statistics
        self._writes_processed = 0
        self._writes_failed = 0
        self._retries_total = 0
    
    def set_db_tables(self, db_tables: Dict):
        """Set or update the database tables reference."""
        with self._lock:
            self.db_tables = db_tables
    
    def start(self):
        """Start the background worker thread."""
        with self._lock:
            if self._running:
                logger.warning("Write queue already running")
                return
            
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="DatabaseWriteQueue",
                daemon=True
            )
            self._worker_thread.start()
            logger.info("Database write queue started")
    
    def stop(self, timeout: float = 10.0):
        """
        Stop the background worker thread and flush remaining writes.
        
        Args:
            timeout: Maximum seconds to wait for queue to drain
        """
        with self._lock:
            if not self._running:
                return
            
            self._running = False
        
        # Wait for worker to finish processing remaining items
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("Write queue worker did not stop cleanly within timeout")
            else:
                logger.info(f"Database write queue stopped. Processed: {self._writes_processed}, Failed: {self._writes_failed}")
    
    def enqueue(self, request: WriteRequest):
        """
        Add a write request to the queue.
        
        This method is non-blocking - it returns immediately after queuing.
        
        Args:
            request: The WriteRequest to queue
        """
        if not self._running:
            logger.warning("Write queue not running, starting it automatically")
            self.start()
        
        self._queue.put(request)
    
    def _worker_loop(self):
        """Main worker loop that processes queued writes."""
        batch: list[WriteRequest] = []
        last_flush = time.time()
        
        while self._running or not self._queue.empty():
            try:
                # Try to get an item with a short timeout
                try:
                    request = self._queue.get(timeout=0.1)
                    batch.append(request)
                except queue.Empty:
                    pass
                
                # Check if we should flush the batch
                should_flush = (
                    len(batch) >= self.batch_size or
                    (len(batch) > 0 and time.time() - last_flush >= self.flush_interval) or
                    (not self._running and len(batch) > 0)  # Flush on shutdown
                )
                
                if should_flush:
                    self._process_batch(batch)
                    batch = []
                    last_flush = time.time()
                    
            except Exception as e:
                logger.error(f"Error in write queue worker loop: {e}", exc_info=True)
        
        # Final flush of any remaining items
        if batch:
            self._process_batch(batch)
    
    def _process_batch(self, batch: list[WriteRequest]):
        """Process a batch of write requests with retry logic."""
        if not self.db_tables:
            logger.error("No database tables configured, dropping batch of %d writes", len(batch))
            for request in batch:
                if request.callback:
                    request.callback(False, RuntimeError("No database tables configured"))
            return
        
        for request in batch:
            success = False
            last_error = None
            
            for attempt in range(self.max_retries):
                try:
                    self._execute_write(request)
                    success = True
                    self._writes_processed += 1
                    break
                    
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if 'database is locked' in error_msg or 'database is busy' in error_msg:
                        self._retries_total += 1
                        delay = self.base_retry_delay * (2 ** attempt)
                        logger.debug(
                            f"Database locked on {request.table_name} {request.operation.value}, "
                            f"retry {attempt + 1}/{self.max_retries} in {delay:.2f}s"
                        )
                        time.sleep(delay)
                        last_error = e
                    else:
                        # Non-retryable database error
                        logger.error(f"Database error on {request.table_name}: {e}")
                        last_error = e
                        break
                        
                except Exception as e:
                    # Non-retryable error
                    logger.error(f"Error executing write on {request.table_name}: {e}")
                    last_error = e
                    break
            
            if not success:
                self._writes_failed += 1
                logger.error(
                    f"Failed to write to {request.table_name} after {self.max_retries} attempts: {last_error}"
                )
            
            # Call the callback if provided
            if request.callback:
                request.callback(success, last_error if not success else None)
    
    def _execute_write(self, request: WriteRequest):
        """Execute a single write operation."""
        table = self.db_tables.get(request.table_name)
        if not table:
            raise ValueError(f"Unknown table: {request.table_name}")
        
        if request.operation == WriteOperation.INSERT:
            table.insert(request.data)
            
        elif request.operation == WriteOperation.UPDATE:
            if not request.primary_key:
                raise ValueError("UPDATE operation requires primary_key")
            table.update(request.data, request.primary_key)
            
        elif request.operation == WriteOperation.DELETE:
            if not request.primary_key:
                raise ValueError("DELETE operation requires primary_key")
            table.delete(request.primary_key)
            
        elif request.operation == WriteOperation.UPSERT:
            # UPSERT for process_status table (keyed by process_name)
            if request.table_name == 'process_status':
                self._upsert_process_status(request.data, request.primary_key)
            else:
                # For other tables, try update first, then insert
                try:
                    if request.primary_key:
                        table.update(request.data, request.primary_key)
                    else:
                        table.insert(request.data)
                except Exception:
                    table.insert(request.data)
    
    def _upsert_process_status(self, data: Dict[str, Any], process_name: str):
        """
        UPSERT operation for process_status table.
        
        Checks if record exists first:
        - If exists: UPDATE only the provided fields (preserves NOT NULL fields like process_type)
        - If not exists: INSERT (requires all NOT NULL fields to be present)
        """
        db = self.db_tables.get('db')
        if not db:
            raise ValueError("Database connection not available")
        
        # Convert datetime objects to ISO format strings for SQLite
        processed_data = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value
        
        # Check if record exists
        cursor = db.execute(
            "SELECT 1 FROM process_status WHERE process_name = ?",
            [process_name]
        )
        exists = cursor.fetchone() is not None
        
        if exists:
            # UPDATE only the provided fields (preserves process_type and other NOT NULL fields)
            # Remove process_name from update data since it's the key
            update_data = {k: v for k, v in processed_data.items() if k != 'process_name'}
            
            if update_data:
                set_clause = ', '.join([f"{col} = ?" for col in update_data.keys()])
                values = list(update_data.values()) + [process_name]
                
                query = f"UPDATE process_status SET {set_clause} WHERE process_name = ?"
                db.execute(query, values)
        else:
            # INSERT - requires all NOT NULL fields (process_name, process_type, status)
            # Ensure process_name is in the data
            processed_data['process_name'] = process_name
            
            columns = list(processed_data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            
            query = f"INSERT INTO process_status ({column_names}) VALUES ({placeholders})"
            values = [processed_data.get(col) for col in columns]
            
            db.execute(query, values)
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return {
            'writes_processed': self._writes_processed,
            'writes_failed': self._writes_failed,
            'retries_total': self._retries_total,
            'queue_size': self._queue.qsize()
        }


# Global write queue instance
_write_queue: Optional[DatabaseWriteQueue] = None
_queue_lock = threading.Lock()


def get_write_queue(db_tables: Dict = None) -> DatabaseWriteQueue:
    """
    Get or create the global write queue instance.
    
    Args:
        db_tables: Database tables dictionary (optional, can be set later)
    
    Returns:
        The global DatabaseWriteQueue instance
    """
    global _write_queue
    
    with _queue_lock:
        if _write_queue is None:
            _write_queue = DatabaseWriteQueue(db_tables)
            _write_queue.start()
        elif db_tables and not _write_queue.db_tables:
            _write_queue.set_db_tables(db_tables)
        
        return _write_queue


def init_write_queue(db_tables: Dict) -> DatabaseWriteQueue:
    """
    Initialize the write queue with database tables.
    
    This should be called early in process startup.
    
    Args:
        db_tables: Database tables dictionary from setup_database()
    
    Returns:
        The initialized DatabaseWriteQueue instance
    """
    queue = get_write_queue(db_tables)
    queue.set_db_tables(db_tables)
    return queue


def shutdown_write_queue(timeout: float = 10.0):
    """
    Shutdown the global write queue gracefully.
    
    Args:
        timeout: Maximum seconds to wait for queue to drain
    """
    global _write_queue
    
    with _queue_lock:
        if _write_queue:
            _write_queue.stop(timeout)
            _write_queue = None


# ============================================================================
# Convenience Functions for Process Monitoring
# ============================================================================

def queue_process_heartbeat(
    process_name: str,
    activity_info: Dict[str, Any] = None,
    db_tables: Dict = None
):
    """
    Queue a process heartbeat update.
    
    Uses UPSERT semantics - creates the process record if it doesn't exist,
    updates it if it does.
    
    Args:
        process_name: Name of the process
        activity_info: Optional activity metrics (messages_processed, etc.)
        db_tables: Database tables (optional if queue already initialized)
    """
    queue = get_write_queue(db_tables)
    
    now = datetime.now()
    
    # Build the heartbeat data
    data = {
        'process_name': process_name,
        'last_heartbeat': now,
        'updated_at': now,
        'status': 'running'
    }
    
    if activity_info:
        data['last_activity'] = now
    
    # Queue the UPSERT operation
    request = WriteRequest(
        table_name='process_status',
        operation=WriteOperation.UPSERT,
        data=data,
        primary_key=process_name
    )
    
    queue.enqueue(request)
    
    # Also queue metrics if activity_info provided
    if activity_info:
        for metric_name, metric_value in activity_info.items():
            if isinstance(metric_value, (int, float)):
                queue_process_metric(process_name, metric_name, int(metric_value), db_tables=db_tables)


def queue_process_log(
    process_name: str,
    message: str,
    level: str = "INFO",
    event_type: str = "activity",
    details: Dict[str, Any] = None,
    db_tables: Dict = None
):
    """
    Queue a process log entry.
    
    Args:
        process_name: Name of the process
        message: Log message
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        event_type: Event type (start, stop, heartbeat, activity, error, restart)
        details: Optional additional details as a dictionary
        db_tables: Database tables (optional if queue already initialized)
    """
    import json
    
    queue = get_write_queue(db_tables)
    
    data = {
        'process_name': process_name,
        'log_level': level.upper(),
        'event_type': event_type.lower(),
        'message': message,
        'details': json.dumps(details) if details else None,
        'timestamp': datetime.now()
    }
    
    request = WriteRequest(
        table_name='process_logs',
        operation=WriteOperation.INSERT,
        data=data
    )
    
    queue.enqueue(request)
    
    # Also log to standard logger
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, f"[{process_name}] {message}")


def queue_process_metric(
    process_name: str,
    metric_name: str,
    value: int,
    metric_type: str = "counter",
    db_tables: Dict = None
):
    """
    Queue a process metric record.
    
    Args:
        process_name: Name of the process
        metric_name: Name of the metric
        value: Metric value (integer)
        metric_type: Type of metric (counter, gauge, etc.)
        db_tables: Database tables (optional if queue already initialized)
    """
    queue = get_write_queue(db_tables)
    
    data = {
        'process_name': process_name,
        'metric_name': metric_name,
        'metric_value': value,
        'metric_type': metric_type,
        'recorded_at': datetime.now()
    }
    
    request = WriteRequest(
        table_name='process_metrics',
        operation=WriteOperation.INSERT,
        data=data
    )
    
    queue.enqueue(request)


# ============================================================================
# Synchronous Write with Retry (for critical operations)
# ============================================================================

def write_with_retry(
    db_tables: Dict,
    table_name: str,
    operation: WriteOperation,
    data: Dict[str, Any],
    primary_key: str = None,
    max_retries: int = 5,
    base_delay: float = 0.1
) -> bool:
    """
    Execute a synchronous database write with retry logic.
    
    Use this for critical operations that need immediate confirmation,
    such as user creation or bookshelf creation.
    
    Args:
        db_tables: Database tables dictionary
        table_name: Name of the table to write to
        operation: Type of write operation
        data: Data to write
        primary_key: Primary key for UPDATE/DELETE operations
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay for exponential backoff
    
    Returns:
        True if write succeeded, False otherwise
    """
    table = db_tables.get(table_name)
    if not table:
        logger.error(f"Unknown table: {table_name}")
        return False
    
    for attempt in range(max_retries):
        try:
            if operation == WriteOperation.INSERT:
                table.insert(data)
            elif operation == WriteOperation.UPDATE:
                if not primary_key:
                    raise ValueError("UPDATE operation requires primary_key")
                table.update(data, primary_key)
            elif operation == WriteOperation.DELETE:
                if not primary_key:
                    raise ValueError("DELETE operation requires primary_key")
                table.delete(primary_key)
            elif operation == WriteOperation.UPSERT:
                # Try update first, then insert
                try:
                    if primary_key:
                        table.update(data, primary_key)
                    else:
                        table.insert(data)
                except Exception:
                    table.insert(data)
            
            return True
            
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if 'database is locked' in error_msg or 'database is busy' in error_msg:
                delay = base_delay * (2 ** attempt)
                logger.debug(
                    f"Database locked on {table_name} {operation.value}, "
                    f"retry {attempt + 1}/{max_retries} in {delay:.2f}s"
                )
                time.sleep(delay)
            else:
                logger.error(f"Database error on {table_name}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing write on {table_name}: {e}")
            return False
    
    logger.error(f"Failed to write to {table_name} after {max_retries} attempts")
    return False
