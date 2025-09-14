"""Automatic database cleanup service for Bibliome."""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from process_monitor import ProcessMonitor, ProcessStatus, LogLevel, EventType

class DatabaseCleanupMonitor:
    """Automatic database cleanup service that monitors and cleans old log entries."""
    
    def __init__(self, db_tables=None, process_monitor=None):
        self.db_tables = db_tables
        self.process_monitor = process_monitor
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._cleanup_thread = None
        
        # Configuration from environment variables
        self.enabled = os.getenv('AUTO_CLEANUP_ENABLED', 'true').lower() == 'true'
        self.check_interval = int(os.getenv('AUTO_CLEANUP_CHECK_INTERVAL', '3600'))  # 1 hour
        self.max_process_logs = int(os.getenv('MAX_PROCESS_LOGS', '10000'))
        self.max_process_metrics = int(os.getenv('MAX_PROCESS_METRICS', '50000'))
        self.max_activity_records = int(os.getenv('MAX_ACTIVITY_RECORDS', '25000'))
        self.max_sync_log_records = int(os.getenv('MAX_SYNC_LOG_RECORDS', '15000'))
        self.max_database_size_mb = int(os.getenv('MAX_DATABASE_SIZE_MB', '100'))
        
        # Retention periods (minimum age before cleanup)
        self.min_retention_days = {
            'process_logs': int(os.getenv('MIN_RETENTION_PROCESS_LOGS', '7')),
            'process_metrics': int(os.getenv('MIN_RETENTION_PROCESS_METRICS', '3')),
            'activity': int(os.getenv('MIN_RETENTION_ACTIVITY', '30')),
            'sync_log': int(os.getenv('MIN_RETENTION_SYNC_LOG', '7'))
        }
        
        # Emergency cleanup thresholds (more aggressive cleanup)
        self.emergency_multiplier = 2.0  # Trigger emergency cleanup at 2x normal thresholds
        
        self.last_cleanup_time = None
        self.last_cleanup_stats = {}
        
        if self.process_monitor:
            self.process_monitor.register_process("database_cleanup", "database_cleanup", {
                "description": "Automatic database cleanup service",
                "expected_activity_interval": self.check_interval,
                "restart_policy": "always"
            })
    
    def start(self):
        """Start the automatic cleanup monitoring."""
        if not self.enabled:
            self.logger.info("Database auto-cleanup is disabled")
            return
        
        if self._running:
            self.logger.warning("Database cleanup monitor already running")
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
        
        if self.process_monitor:
            self.process_monitor.update_process_status("database_cleanup", ProcessStatus.RUNNING)
            self.process_monitor.log_event("database_cleanup", LogLevel.INFO, EventType.START,
                                         "Database cleanup monitor started")
        
        self.logger.info(f"Database cleanup monitor started (check interval: {self.check_interval}s)")
    
    def stop(self):
        """Stop the automatic cleanup monitoring."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)
        
        if self.process_monitor:
            self.process_monitor.update_process_status("database_cleanup", ProcessStatus.STOPPED)
            self.process_monitor.log_event("database_cleanup", LogLevel.INFO, EventType.STOP,
                                         "Database cleanup monitor stopped")
        
        self.logger.info("Database cleanup monitor stopped")
    
    def _cleanup_loop(self):
        """Main cleanup monitoring loop."""
        while self._running:
            try:
                # Send heartbeat
                if self.process_monitor:
                    self.process_monitor.heartbeat("database_cleanup")
                
                # Check if cleanup is needed
                if self._should_cleanup():
                    self._perform_cleanup()
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                if self.process_monitor:
                    self.process_monitor.log_event("database_cleanup", LogLevel.ERROR, EventType.ERROR,
                                                 f"Cleanup loop error: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying on error
    
    def _should_cleanup(self) -> bool:
        """Check if cleanup is needed based on thresholds."""
        if not self.db_tables:
            return False
        
        try:
            # Check row counts for each table
            table_counts = self._get_table_counts()
            
            # Check against thresholds
            thresholds = {
                'process_logs': self.max_process_logs,
                'process_metrics': self.max_process_metrics,
                'activity': self.max_activity_records,
                'sync_log': self.max_sync_log_records
            }
            
            for table_name, threshold in thresholds.items():
                if table_name in table_counts:
                    count = table_counts[table_name]
                    if count > threshold:
                        self.logger.info(f"Cleanup needed: {table_name} has {count} records (threshold: {threshold})")
                        return True
            
            # Check database file size if possible
            db_size_mb = self._get_database_size_mb()
            if db_size_mb and db_size_mb > self.max_database_size_mb:
                self.logger.info(f"Cleanup needed: database size is {db_size_mb}MB (threshold: {self.max_database_size_mb}MB)")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking cleanup thresholds: {e}")
            return False
    
    def _get_table_counts(self) -> Dict[str, int]:
        """Get row counts for all monitored tables."""
        counts = {}
        
        tables_to_check = ['process_logs', 'process_metrics', 'activity', 'sync_log']
        
        for table_name in tables_to_check:
            try:
                if table_name in self.db_tables:
                    count = len(self.db_tables[table_name]())
                    counts[table_name] = count
            except Exception as e:
                self.logger.warning(f"Could not get count for table {table_name}: {e}")
        
        return counts
    
    def _get_database_size_mb(self) -> Optional[float]:
        """Get database file size in MB."""
        try:
            # Try to get database file path
            db_path = None
            if hasattr(self.db_tables, 'db') and hasattr(self.db_tables.db, 'db'):
                # FastLite database path
                db_path = self.db_tables.db.db
            elif hasattr(self.db_tables, 'db'):
                db_path = str(self.db_tables.db)
            
            if db_path and os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                size_mb = size_bytes / (1024 * 1024)
                return round(size_mb, 2)
            
        except Exception as e:
            self.logger.debug(f"Could not get database size: {e}")
        
        return None
    
    def _perform_cleanup(self):
        """Perform the actual cleanup operation."""
        try:
            self.logger.info("Starting automatic database cleanup")
            
            if self.process_monitor:
                self.process_monitor.log_event("database_cleanup", LogLevel.INFO, EventType.ACTIVITY,
                                             "Starting automatic cleanup")
            
            cleanup_stats = {}
            total_deleted = 0
            
            # Get current counts and determine if emergency cleanup is needed
            table_counts = self._get_table_counts()
            is_emergency = self._is_emergency_cleanup_needed(table_counts)
            
            if is_emergency:
                self.logger.warning("Emergency cleanup mode activated - database is critically full")
                if self.process_monitor:
                    self.process_monitor.log_event("database_cleanup", LogLevel.WARNING, EventType.ACTIVITY,
                                                 "Emergency cleanup mode activated")
            
            # Clean each table
            for table_name in ['process_logs', 'process_metrics', 'activity', 'sync_log']:
                if table_name not in self.db_tables:
                    continue
                
                try:
                    deleted_count = self._cleanup_table(table_name, is_emergency)
                    cleanup_stats[table_name] = deleted_count
                    total_deleted += deleted_count
                    
                    if deleted_count > 0:
                        self.logger.info(f"Cleaned {deleted_count} records from {table_name}")
                        
                except Exception as e:
                    self.logger.error(f"Error cleaning table {table_name}: {e}")
                    cleanup_stats[table_name] = 0
            
            # Record cleanup completion
            self.last_cleanup_time = datetime.now()
            self.last_cleanup_stats = cleanup_stats
            
            # Log results
            if total_deleted > 0:
                self.logger.info(f"Automatic cleanup completed: {total_deleted} total records deleted")
                if self.process_monitor:
                    self.process_monitor.log_event("database_cleanup", LogLevel.INFO, EventType.ACTIVITY,
                                                 f"Cleanup completed: {total_deleted} records deleted",
                                                 cleanup_stats)
                    self.process_monitor.record_metric("database_cleanup", "records_cleaned", total_deleted)
            else:
                self.logger.info("Automatic cleanup completed: no records needed cleaning")
            
        except Exception as e:
            self.logger.error(f"Error during automatic cleanup: {e}", exc_info=True)
            if self.process_monitor:
                self.process_monitor.log_event("database_cleanup", LogLevel.ERROR, EventType.ERROR,
                                             f"Cleanup failed: {str(e)}")
    
    def _is_emergency_cleanup_needed(self, table_counts: Dict[str, int]) -> bool:
        """Check if emergency cleanup is needed (more aggressive thresholds)."""
        emergency_thresholds = {
            'process_logs': int(self.max_process_logs * self.emergency_multiplier),
            'process_metrics': int(self.max_process_metrics * self.emergency_multiplier),
            'activity': int(self.max_activity_records * self.emergency_multiplier),
            'sync_log': int(self.max_sync_log_records * self.emergency_multiplier)
        }
        
        for table_name, threshold in emergency_thresholds.items():
            if table_name in table_counts and table_counts[table_name] > threshold:
                return True
        
        # Also check database size
        db_size_mb = self._get_database_size_mb()
        if db_size_mb and db_size_mb > (self.max_database_size_mb * self.emergency_multiplier):
            return True
        
        return False
    
    def _cleanup_table(self, table_name: str, is_emergency: bool = False) -> int:
        """Clean up old records from a specific table."""
        try:
            # Determine retention period
            base_retention_days = self.min_retention_days.get(table_name, 7)
            
            if is_emergency:
                # More aggressive cleanup in emergency mode
                retention_days = max(1, base_retention_days // 2)
            else:
                retention_days = base_retention_days
            
            # Calculate cutoff date
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            # Count records before deletion
            if table_name == 'activity':
                before_count = len(self.db_tables[table_name](f"created_at < ?", (cutoff_date,)))
            elif table_name == 'process_metrics':
                before_count = len(self.db_tables[table_name](f"recorded_at < ?", (cutoff_date,)))
            else:
                before_count = len(self.db_tables[table_name](f"timestamp < ?", (cutoff_date,)))
            
            if before_count == 0:
                return 0
            
            # Delete old records
            if table_name == 'activity':
                self.db_tables[table_name].delete_where("created_at < ?", (cutoff_date,))
            elif table_name == 'process_metrics':
                self.db_tables[table_name].delete_where("recorded_at < ?", (cutoff_date,))
            else:
                self.db_tables[table_name].delete_where("timestamp < ?", (cutoff_date,))
            
            return before_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning table {table_name}: {e}")
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current cleanup status for admin dashboard."""
        try:
            table_counts = self._get_table_counts()
            db_size_mb = self._get_database_size_mb()
            
            # Calculate how close we are to thresholds
            threshold_status = {}
            thresholds = {
                'process_logs': self.max_process_logs,
                'process_metrics': self.max_process_metrics,
                'activity': self.max_activity_records,
                'sync_log': self.max_sync_log_records
            }
            
            for table_name, threshold in thresholds.items():
                if table_name in table_counts:
                    count = table_counts[table_name]
                    percentage = (count / threshold) * 100
                    threshold_status[table_name] = {
                        'count': count,
                        'threshold': threshold,
                        'percentage': round(percentage, 1),
                        'needs_cleanup': count > threshold
                    }
            
            return {
                'enabled': self.enabled,
                'running': self._running,
                'last_cleanup': self.last_cleanup_time.isoformat() if self.last_cleanup_time else None,
                'last_cleanup_stats': self.last_cleanup_stats,
                'table_counts': table_counts,
                'database_size_mb': db_size_mb,
                'threshold_status': threshold_status,
                'check_interval': self.check_interval,
                'next_check_in': self.check_interval if self._running else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cleanup status: {e}")
            return {
                'enabled': self.enabled,
                'running': self._running,
                'error': str(e)
            }

# Global cleanup monitor instance
_cleanup_monitor: Optional[DatabaseCleanupMonitor] = None

def get_cleanup_monitor(db_tables=None, process_monitor=None) -> DatabaseCleanupMonitor:
    """Get the global cleanup monitor instance."""
    global _cleanup_monitor
    if _cleanup_monitor is None:
        _cleanup_monitor = DatabaseCleanupMonitor(db_tables, process_monitor)
    elif db_tables and not _cleanup_monitor.db_tables:
        _cleanup_monitor.db_tables = db_tables
        _cleanup_monitor.process_monitor = process_monitor
    return _cleanup_monitor

def init_database_cleanup(db_tables, process_monitor):
    """Initialize the database cleanup monitor."""
    cleanup_monitor = get_cleanup_monitor(db_tables, process_monitor)
    cleanup_monitor.start()
    return cleanup_monitor
