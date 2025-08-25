"""Process monitoring service for tracking background processes in Bibliome."""

import os
import time
import json
import logging
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

class ProcessStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class EventType(Enum):
    START = "start"
    STOP = "stop"
    HEARTBEAT = "heartbeat"
    ACTIVITY = "activity"
    ERROR = "error"
    RESTART = "restart"

@dataclass
class ProcessInfo:
    """Information about a monitored process."""
    name: str
    process_type: str
    status: ProcessStatus
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    restart_count: int = 0
    error_message: Optional[str] = None
    config_data: Optional[Dict[str, Any]] = None

class ProcessMonitor:
    """Central process monitoring and management service."""
    
    def __init__(self, db_tables=None):
        self.db_tables = db_tables
        self.logger = logging.getLogger(__name__)
        self._processes: Dict[str, ProcessInfo] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None
        
        # Load existing process status from database
        self._load_process_status()
    
    def _load_process_status(self):
        """Load process status from database on startup."""
        if not self.db_tables:
            return
        
        try:
            # Add process_status table to db_tables if it doesn't exist
            if 'process_status' not in self.db_tables:
                from fastlite import Table
                self.db_tables['process_status'] = Table(self.db_tables['db'], 'process_status')
                self.db_tables['process_logs'] = Table(self.db_tables['db'], 'process_logs')
                self.db_tables['process_metrics'] = Table(self.db_tables['db'], 'process_metrics')
            
            # Load existing processes
            processes = self.db_tables['process_status']()
            for process_row in processes:
                config_data = {}
                if process_row['config_data']:
                    try:
                        config_data = json.loads(process_row['config_data'])
                    except json.JSONDecodeError:
                        pass
                
                # Check if process is actually running by PID
                actual_status = ProcessStatus.STOPPED
                if process_row['pid']:
                    try:
                        if psutil.pid_exists(process_row['pid']):
                            proc = psutil.Process(process_row['pid'])
                            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                                actual_status = ProcessStatus.RUNNING
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Convert string datetime fields back to datetime objects
                started_at = None
                if process_row['started_at']:
                    if isinstance(process_row['started_at'], str):
                        started_at = datetime.fromisoformat(process_row['started_at'].replace('Z', '+00:00'))
                    else:
                        started_at = process_row['started_at']
                
                last_heartbeat = None
                if process_row['last_heartbeat']:
                    if isinstance(process_row['last_heartbeat'], str):
                        last_heartbeat = datetime.fromisoformat(process_row['last_heartbeat'].replace('Z', '+00:00'))
                    else:
                        last_heartbeat = process_row['last_heartbeat']
                
                last_activity = None
                if process_row['last_activity']:
                    if isinstance(process_row['last_activity'], str):
                        last_activity = datetime.fromisoformat(process_row['last_activity'].replace('Z', '+00:00'))
                    else:
                        last_activity = process_row['last_activity']
                
                self._processes[process_row['process_name']] = ProcessInfo(
                    name=process_row['process_name'],
                    process_type=process_row['process_type'],
                    status=actual_status,
                    pid=process_row['pid'] if actual_status == ProcessStatus.RUNNING else None,
                    started_at=started_at,
                    last_heartbeat=last_heartbeat,
                    last_activity=last_activity,
                    restart_count=process_row['restart_count'] or 0,
                    error_message=process_row['error_message'],
                    config_data=config_data
                )
                
                # Update database with actual status if different
                if actual_status != ProcessStatus(process_row['status']):
                    self._update_process_status(process_row['process_name'], actual_status)
                    
        except Exception as e:
            self.logger.error(f"Error loading process status from database: {e}")
    
    def _update_process_status(self, process_name: str, status: ProcessStatus, 
                             pid: Optional[int] = None, error_message: Optional[str] = None):
        """Update process status in database."""
        if not self.db_tables:
            return
        
        try:
            update_data = {
                'status': status.value,
                'updated_at': datetime.now()
            }
            
            if pid is not None:
                update_data['pid'] = pid
            elif status in [ProcessStatus.STOPPED, ProcessStatus.FAILED]:
                update_data['pid'] = None
            
            if status == ProcessStatus.RUNNING and pid:
                update_data['started_at'] = datetime.now()
            elif status in [ProcessStatus.STOPPED, ProcessStatus.FAILED]:
                update_data['started_at'] = None
            
            if error_message:
                update_data['error_message'] = error_message
            elif status == ProcessStatus.RUNNING:
                update_data['error_message'] = None
            
            # Update database
            update_data['process_name'] = process_name
            self.db_tables['process_status'].update(update_data)
            
        except Exception as e:
            self.logger.error(f"Error updating process status for {process_name}: {e}")
    
    def log_event(self, process_name: str, log_level: LogLevel, event_type: EventType, 
                  message: str, details: Optional[Dict[str, Any]] = None):
        """Log a process event."""
        if not self.db_tables:
            self.logger.log(getattr(logging, log_level.value), f"[{process_name}] {message}")
            return
        
        try:
            log_entry = {
                'process_name': process_name,
                'log_level': log_level.value,
                'event_type': event_type.value,
                'message': message,
                'details': json.dumps(details) if details else None,
                'timestamp': datetime.now()
            }
            
            self.db_tables['process_logs'].insert(log_entry)
            
            # Also log to regular logger
            self.logger.log(getattr(logging, log_level.value), f"[{process_name}] {message}")
            
        except Exception as e:
            self.logger.error(f"Error logging event for {process_name}: {e}")
    
    def record_metric(self, process_name: str, metric_name: str, metric_value: int, 
                     metric_type: str = "counter"):
        """Record a process metric."""
        if not self.db_tables:
            return
        
        try:
            metric_entry = {
                'process_name': process_name,
                'metric_name': metric_name,
                'metric_value': metric_value,
                'metric_type': metric_type,
                'recorded_at': datetime.now()
            }
            
            self.db_tables['process_metrics'].insert(metric_entry)
            
        except Exception as e:
            self.logger.error(f"Error recording metric {metric_name} for {process_name}: {e}")
    
    def register_process(self, name: str, process_type: str, config: Optional[Dict[str, Any]] = None):
        """Register a new process for monitoring."""
        with self._lock:
            if name not in self._processes:
                self._processes[name] = ProcessInfo(
                    name=name,
                    process_type=process_type,
                    status=ProcessStatus.STOPPED,
                    config_data=config or {}
                )
                
                # Add to database if it doesn't exist
                if self.db_tables:
                    try:
                        existing = self.db_tables['process_status'](f"process_name='{name}'")
                        if not existing:
                            self.db_tables['process_status'].insert({
                                'process_name': name,
                                'process_type': process_type,
                                'status': ProcessStatus.STOPPED.value,
                                'config_data': json.dumps(config) if config else None,
                                'created_at': datetime.now(),
                                'updated_at': datetime.now()
                            })
                    except Exception as e:
                        self.logger.error(f"Error adding process {name} to database: {e}")
                
                self.log_event(name, LogLevel.INFO, EventType.START, f"Process {name} registered for monitoring")
    
    def update_process_status(self, name: str, status: ProcessStatus, pid: Optional[int] = None, 
                            error_message: Optional[str] = None):
        """Update the status of a monitored process."""
        with self._lock:
            if name in self._processes:
                old_status = self._processes[name].status
                self._processes[name].status = status
                
                if pid:
                    self._processes[name].pid = pid
                elif status in [ProcessStatus.STOPPED, ProcessStatus.FAILED]:
                    self._processes[name].pid = None
                
                if status == ProcessStatus.RUNNING:
                    self._processes[name].started_at = datetime.now()
                    self._processes[name].error_message = None
                elif status in [ProcessStatus.STOPPED, ProcessStatus.FAILED]:
                    self._processes[name].started_at = None
                    if error_message:
                        self._processes[name].error_message = error_message
                
                # Update database
                self._update_process_status(name, status, pid, error_message)
                
                # Log status change
                if old_status != status:
                    if status == ProcessStatus.FAILED and error_message:
                        self.log_event(name, LogLevel.ERROR, EventType.ERROR, 
                                     f"Process status changed from {old_status.value} to {status.value}", 
                                     {"error": error_message})
                    else:
                        self.log_event(name, LogLevel.INFO, EventType.START if status == ProcessStatus.RUNNING else EventType.STOP,
                                     f"Process status changed from {old_status.value} to {status.value}")
    
    def heartbeat(self, name: str, activity_info: Optional[Dict[str, Any]] = None):
        """Record a heartbeat for a process."""
        with self._lock:
            if name in self._processes:
                now = datetime.now()
                self._processes[name].last_heartbeat = now
                
                if activity_info:
                    self._processes[name].last_activity = now
                    # Record specific metrics if provided
                    if 'messages_processed' in activity_info:
                        self.record_metric(name, 'messages_processed', activity_info['messages_processed'])
                    if 'posts_sent' in activity_info:
                        self.record_metric(name, 'posts_sent', activity_info['posts_sent'])
                    if 'errors_count' in activity_info:
                        self.record_metric(name, 'errors_count', activity_info['errors_count'])
                
                # Update database heartbeat
                if self.db_tables:
                    try:
                        update_data = {'last_heartbeat': now}
                        if activity_info:
                            update_data['last_activity'] = now
                        
                        update_data['process_name'] = name
                        self.db_tables['process_status'].update(update_data)
                    except Exception as e:
                        self.logger.error(f"Error updating heartbeat for {name}: {e}")
                
                # Log detailed heartbeat for debugging
                self.log_event(name, LogLevel.DEBUG, EventType.HEARTBEAT, 
                             "Process heartbeat", activity_info)
    
    def get_process_status(self, name: str) -> Optional[ProcessInfo]:
        """Get current status of a process."""
        with self._lock:
            return self._processes.get(name)
    
    def get_all_processes(self) -> Dict[str, ProcessInfo]:
        """Get status of all monitored processes."""
        with self._lock:
            return self._processes.copy()
    
    def is_process_healthy(self, name: str, max_heartbeat_age: timedelta = timedelta(minutes=5)) -> bool:
        """Check if a process is considered healthy based on recent heartbeat."""
        process = self.get_process_status(name)
        if not process:
            return False
        
        if process.status != ProcessStatus.RUNNING:
            return False
        
        if not process.last_heartbeat:
            return False
        
        return (datetime.now() - process.last_heartbeat) <= max_heartbeat_age
    
    def get_process_metrics(self, name: str, metric_name: str = None, hours: int = 24) -> list:
        """Get metrics for a process within the specified time range."""
        if not self.db_tables:
            return []
        
        try:
            since = datetime.now() - timedelta(hours=hours)
            
            if metric_name:
                metrics = self.db_tables['process_metrics'](
                    "process_name=? AND metric_name=? AND recorded_at>=?",
                    (name, metric_name, since),
                    order_by="recorded_at ASC"
                )
            else:
                metrics = self.db_tables['process_metrics'](
                    "process_name=? AND recorded_at>=?",
                    (name, since),
                    order_by="recorded_at ASC"
                )
            
            return list(metrics)
            
        except Exception as e:
            self.logger.error(f"Error getting metrics for {name}: {e}")
            return []
    
    def get_recent_logs(self, name: str = None, hours: int = 24, log_level: LogLevel = None) -> list:
        """Get recent logs for a process or all processes."""
        if not self.db_tables:
            return []
        
        try:
            since = datetime.now() - timedelta(hours=hours)
            since_str = since.strftime('%Y-%m-%d %H:%M:%S')
            
            conditions = ["timestamp>=?"]
            params = [since_str]
            
            if name:
                conditions.append("process_name=?")
                params.append(name)
            
            if log_level:
                conditions.append("log_level=?")
                params.append(log_level.value)
            
            where_clause = " AND ".join(conditions)
            logs = self.db_tables['process_logs'](
                where_clause,
                params,
                order_by="timestamp DESC",
                limit=100
            )
            
            return list(logs)
            
        except Exception as e:
            self.logger.error(f"Error getting recent logs: {e}")
            return []
    
    def start_monitoring(self, check_interval: int = 60):
        """Start the background monitoring thread."""
        if self._running:
            self.logger.warning("Process monitor already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(check_interval,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info("Process monitor started")
    
    def stop_monitoring(self):
        """Stop the background monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Process monitor stopped")
    
    def _monitor_loop(self, check_interval: int):
        """Main monitoring loop that runs in background thread."""
        while self._running:
            try:
                self._check_all_processes()
                time.sleep(check_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(check_interval)
    
    def _check_all_processes(self):
        """Check the health of all monitored processes."""
        with self._lock:
            for name, process in self._processes.items():
                try:
                    self._check_process_health(name, process)
                except Exception as e:
                    self.logger.error(f"Error checking health of process {name}: {e}")
    
    def _check_process_health(self, name: str, process: ProcessInfo):
        """Check the health of a specific process."""
        if process.status != ProcessStatus.RUNNING:
            return
        
        # Check if PID is still valid
        if process.pid:
            try:
                if not psutil.pid_exists(process.pid):
                    self.logger.warning(f"Process {name} (PID {process.pid}) no longer exists")
                    self.update_process_status(name, ProcessStatus.FAILED, 
                                             error_message="Process terminated unexpectedly")
                    return
                
                proc = psutil.Process(process.pid)
                if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                    self.logger.warning(f"Process {name} (PID {process.pid}) is not running")
                    self.update_process_status(name, ProcessStatus.FAILED,
                                             error_message="Process in non-running state")
                    return
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                self.logger.warning(f"Cannot access process {name} (PID {process.pid}): {e}")
                self.update_process_status(name, ProcessStatus.FAILED,
                                         error_message=f"Process access error: {e}")
                return
        
        # Check heartbeat age
        if process.last_heartbeat:
            heartbeat_age = datetime.now() - process.last_heartbeat
            if heartbeat_age > timedelta(minutes=10):  # 10 minutes without heartbeat = unhealthy
                self.logger.warning(f"Process {name} has stale heartbeat (age: {heartbeat_age})")
                self.log_event(name, LogLevel.WARNING, EventType.ERROR,
                             f"Stale heartbeat detected (age: {heartbeat_age})",
                             {"heartbeat_age_seconds": heartbeat_age.total_seconds()})
                
                # Don't mark as failed yet, just warn
                # If heartbeat is > 30 minutes old, then mark as failed
                if heartbeat_age > timedelta(minutes=30):
                    self.update_process_status(name, ProcessStatus.FAILED,
                                             error_message=f"No heartbeat for {heartbeat_age}")

# Global process monitor instance
_process_monitor: Optional[ProcessMonitor] = None

def get_process_monitor(db_tables=None) -> ProcessMonitor:
    """Get the global process monitor instance."""
    global _process_monitor
    if _process_monitor is None:
        _process_monitor = ProcessMonitor(db_tables)
    elif db_tables and not _process_monitor.db_tables:
        _process_monitor.db_tables = db_tables
        _process_monitor._load_process_status()
    return _process_monitor

def init_process_monitoring(db_tables):
    """Initialize process monitoring with database tables."""
    monitor = get_process_monitor(db_tables)
    
    # Register known processes
    monitor.register_process("firehose_ingester", "firehose", {
        "description": "AT-Proto firehose monitor for Bibliome records",
        "expected_activity_interval": 300,  # 5 minutes
        "restart_policy": "always"
    })
    
    monitor.register_process("bluesky_automation", "bluesky_automation", {
        "description": "Automated Bluesky posting service",
        "expected_activity_interval": 3600,  # 1 hour
        "restart_policy": "on_failure"
    })
    
    # Start monitoring
    monitor.start_monitoring()
    
    return monitor

# Convenience functions for process monitoring
def log_process_event(process_name: str, message: str, level: str = "INFO", 
                     event_type: str = "activity", details: Dict[str, Any] = None, db_tables=None):
    """Convenience function to log process events from background processes."""
    try:
        if not db_tables:
            from models import get_database
            db_tables = get_database()
        
        monitor = get_process_monitor(db_tables)
        
        log_level = LogLevel(level.upper())
        event_type_enum = EventType(event_type.lower())
        
        monitor.log_event(process_name, log_level, event_type_enum, message, details)
        
    except Exception as e:
        # Fallback to regular logging if database is unavailable
        logger = logging.getLogger(f"process.{process_name}")
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

def record_process_metric(process_name: str, metric_name: str, value: int, metric_type: str = "counter", db_tables=None):
    """Convenience function to record process metrics from background processes."""
    try:
        if not db_tables:
            from models import get_database
            db_tables = get_database()
        
        monitor = get_process_monitor(db_tables)
        monitor.record_metric(process_name, metric_name, value, metric_type)
        
    except Exception as e:
        # Fail silently for metrics if database is unavailable
        pass

def process_heartbeat(process_name: str, activity_info: Dict[str, Any] = None, db_tables=None):
    """Send a heartbeat for a process."""
    try:
        if not db_tables:
            from models import get_database
            db_tables = get_database()
        
        monitor = get_process_monitor(db_tables)
        monitor.heartbeat(process_name, activity_info)
        
    except Exception as e:
        # Fail silently for heartbeats if database is unavailable
        pass

def update_process_status(process_name: str, status: str, pid: int = None, error_message: str = None, db_tables=None):
    """Update the status of a process."""
    try:
        if not db_tables:
            from models import get_database
            db_tables = get_database()
        
        monitor = get_process_monitor(db_tables)
        status_enum = ProcessStatus(status.lower())
        monitor.update_process_status(process_name, status_enum, pid, error_message)
        
    except Exception as e:
        # Fallback to regular logging
        logger = logging.getLogger(f"process.{process_name}")
        logger.error(f"Failed to update process status: {e}")
