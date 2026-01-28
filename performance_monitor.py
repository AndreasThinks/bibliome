"""Performance monitoring for tracking request, query, and API metrics."""

import time
import logging
import threading
import functools
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global performance monitor instance
_performance_monitor = None


@dataclass
class RequestMetric:
    """Metric for a single HTTP request."""
    route: str
    method: str
    status_code: Optional[int]
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_did: Optional[str] = None
    request_size: Optional[int] = None
    response_size: Optional[int] = None


@dataclass
class QueryMetric:
    """Metric for a database query."""
    query_type: str
    query_name: Optional[str]
    duration_ms: float
    row_count: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    caller: Optional[str] = None


@dataclass
class ApiMetric:
    """Metric for an external API call."""
    service: str
    endpoint: str
    duration_ms: float
    status_code: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PerformanceMonitor:
    """Central performance monitoring service."""

    # Threshold in ms for logging slow operations
    SLOW_REQUEST_THRESHOLD_MS = 1000  # 1 second
    SLOW_QUERY_THRESHOLD_MS = 100     # 100ms
    SLOW_API_THRESHOLD_MS = 2000      # 2 seconds

    # Maximum records to keep in database (for cleanup)
    MAX_REQUEST_RECORDS = 50000
    MAX_QUERY_RECORDS = 50000
    MAX_API_RECORDS = 25000

    def __init__(self, db_tables=None):
        self.db_tables = db_tables
        self._lock = threading.Lock()
        self._request_buffer: List[RequestMetric] = []
        self._query_buffer: List[QueryMetric] = []
        self._api_buffer: List[ApiMetric] = []
        self._buffer_size = 50  # Flush after this many records
        self._enabled = True

        # In-memory aggregates for quick stats
        self._route_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0, 'total_ms': 0, 'max_ms': 0, 'min_ms': float('inf')
        })
        self._query_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0, 'total_ms': 0, 'max_ms': 0, 'min_ms': float('inf')
        })
        self._api_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0, 'total_ms': 0, 'max_ms': 0, 'errors': 0
        })

        logger.info("Performance monitor initialized")

    def set_db_tables(self, db_tables):
        """Set database tables after initialization."""
        self.db_tables = db_tables
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure performance tables exist in db_tables."""
        if not self.db_tables:
            return

        try:
            from fastlite import Table
            if 'request_metrics' not in self.db_tables:
                self.db_tables['request_metrics'] = Table(
                    self.db_tables['db'], 'request_metrics'
                )
            if 'query_metrics' not in self.db_tables:
                self.db_tables['query_metrics'] = Table(
                    self.db_tables['db'], 'query_metrics'
                )
            if 'api_metrics' not in self.db_tables:
                self.db_tables['api_metrics'] = Table(
                    self.db_tables['db'], 'api_metrics'
                )
        except Exception as e:
            logger.warning(f"Could not ensure performance tables: {e}")

    def record_request(self, route: str, method: str, status_code: int,
                       duration_ms: float, user_did: Optional[str] = None,
                       request_size: Optional[int] = None,
                       response_size: Optional[int] = None):
        """Record a request metric."""
        if not self._enabled:
            return

        metric = RequestMetric(
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            user_did=user_did,
            request_size=request_size,
            response_size=response_size
        )

        # Update in-memory stats
        key = f"{method} {route}"
        with self._lock:
            stats = self._route_stats[key]
            stats['count'] += 1
            stats['total_ms'] += duration_ms
            stats['max_ms'] = max(stats['max_ms'], duration_ms)
            stats['min_ms'] = min(stats['min_ms'], duration_ms)

            self._request_buffer.append(metric)
            if len(self._request_buffer) >= self._buffer_size:
                self._flush_request_buffer()

        # Log slow requests
        if duration_ms >= self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(f"Slow request: {method} {route} took {duration_ms:.0f}ms")

    def record_query(self, query_type: str, query_name: Optional[str],
                     duration_ms: float, row_count: Optional[int] = None,
                     caller: Optional[str] = None):
        """Record a database query metric."""
        if not self._enabled:
            return

        metric = QueryMetric(
            query_type=query_type,
            query_name=query_name,
            duration_ms=duration_ms,
            row_count=row_count,
            caller=caller
        )

        # Update in-memory stats
        key = query_name or query_type
        with self._lock:
            stats = self._query_stats[key]
            stats['count'] += 1
            stats['total_ms'] += duration_ms
            stats['max_ms'] = max(stats['max_ms'], duration_ms)
            stats['min_ms'] = min(stats['min_ms'], duration_ms)

            self._query_buffer.append(metric)
            if len(self._query_buffer) >= self._buffer_size:
                self._flush_query_buffer()

        # Log slow queries
        if duration_ms >= self.SLOW_QUERY_THRESHOLD_MS:
            logger.warning(f"Slow query: {query_name or query_type} took {duration_ms:.0f}ms")

    def record_api_call(self, service: str, endpoint: str, duration_ms: float,
                        status_code: Optional[int] = None, success: bool = True,
                        error_message: Optional[str] = None):
        """Record an external API call metric."""
        if not self._enabled:
            return

        metric = ApiMetric(
            service=service,
            endpoint=endpoint,
            duration_ms=duration_ms,
            status_code=status_code,
            success=success,
            error_message=error_message
        )

        # Update in-memory stats
        key = f"{service}:{endpoint}"
        with self._lock:
            stats = self._api_stats[key]
            stats['count'] += 1
            stats['total_ms'] += duration_ms
            stats['max_ms'] = max(stats['max_ms'], duration_ms)
            if not success:
                stats['errors'] += 1

            self._api_buffer.append(metric)
            if len(self._api_buffer) >= self._buffer_size:
                self._flush_api_buffer()

        # Log slow API calls
        if duration_ms >= self.SLOW_API_THRESHOLD_MS:
            logger.warning(f"Slow API call: {service} {endpoint} took {duration_ms:.0f}ms")

    def _flush_request_buffer(self):
        """Flush request metrics to database."""
        if not self.db_tables or not self._request_buffer:
            return

        try:
            self._ensure_tables()
            buffer = self._request_buffer
            self._request_buffer = []

            for metric in buffer:
                self.db_tables['db'].execute(
                    """INSERT INTO request_metrics
                       (route, method, status_code, duration_ms, timestamp,
                        user_did, request_size, response_size)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (metric.route, metric.method, metric.status_code,
                     metric.duration_ms, metric.timestamp.isoformat(),
                     metric.user_did, metric.request_size, metric.response_size)
                )
            self.db_tables['db'].execute("COMMIT")
        except Exception as e:
            logger.error(f"Error flushing request metrics: {e}")

    def _flush_query_buffer(self):
        """Flush query metrics to database."""
        if not self.db_tables or not self._query_buffer:
            return

        try:
            self._ensure_tables()
            buffer = self._query_buffer
            self._query_buffer = []

            for metric in buffer:
                self.db_tables['db'].execute(
                    """INSERT INTO query_metrics
                       (query_type, query_name, duration_ms, row_count, timestamp, caller)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (metric.query_type, metric.query_name, metric.duration_ms,
                     metric.row_count, metric.timestamp.isoformat(), metric.caller)
                )
            self.db_tables['db'].execute("COMMIT")
        except Exception as e:
            logger.error(f"Error flushing query metrics: {e}")

    def _flush_api_buffer(self):
        """Flush API metrics to database."""
        if not self.db_tables or not self._api_buffer:
            return

        try:
            self._ensure_tables()
            buffer = self._api_buffer
            self._api_buffer = []

            for metric in buffer:
                self.db_tables['db'].execute(
                    """INSERT INTO api_metrics
                       (service, endpoint, duration_ms, status_code, success,
                        error_message, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (metric.service, metric.endpoint, metric.duration_ms,
                     metric.status_code, 1 if metric.success else 0,
                     metric.error_message, metric.timestamp.isoformat())
                )
            self.db_tables['db'].execute("COMMIT")
        except Exception as e:
            logger.error(f"Error flushing API metrics: {e}")

    def flush_all(self):
        """Flush all buffers to database."""
        with self._lock:
            self._flush_request_buffer()
            self._flush_query_buffer()
            self._flush_api_buffer()

    def get_request_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get request statistics for the given time period."""
        if not self.db_tables:
            return self._get_memory_request_stats()

        try:
            self._ensure_tables()
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            rows = self.db_tables['db'].execute(
                """SELECT route, method,
                          COUNT(*) as request_count,
                          AVG(duration_ms) as avg_duration_ms,
                          MAX(duration_ms) as max_duration_ms,
                          MIN(duration_ms) as min_duration_ms,
                          SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
                   FROM request_metrics
                   WHERE timestamp > ?
                   GROUP BY route, method
                   ORDER BY avg_duration_ms DESC
                   LIMIT 50""",
                (cutoff,)
            ).fetchall()

            return [
                {
                    'route': row[0],
                    'method': row[1],
                    'request_count': row[2],
                    'avg_duration_ms': round(row[3], 1) if row[3] else 0,
                    'max_duration_ms': round(row[4], 1) if row[4] else 0,
                    'min_duration_ms': round(row[5], 1) if row[5] else 0,
                    'error_count': row[6] or 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting request stats: {e}")
            return self._get_memory_request_stats()

    def _get_memory_request_stats(self) -> List[Dict[str, Any]]:
        """Get request stats from in-memory aggregates."""
        results = []
        with self._lock:
            for key, stats in self._route_stats.items():
                parts = key.split(' ', 1)
                method = parts[0] if len(parts) > 0 else 'GET'
                route = parts[1] if len(parts) > 1 else key
                results.append({
                    'route': route,
                    'method': method,
                    'request_count': stats['count'],
                    'avg_duration_ms': round(stats['total_ms'] / stats['count'], 1) if stats['count'] > 0 else 0,
                    'max_duration_ms': round(stats['max_ms'], 1),
                    'min_duration_ms': round(stats['min_ms'], 1) if stats['min_ms'] != float('inf') else 0,
                    'error_count': 0
                })
        return sorted(results, key=lambda x: x['avg_duration_ms'], reverse=True)[:50]

    def get_query_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get query statistics for the given time period."""
        if not self.db_tables:
            return self._get_memory_query_stats()

        try:
            self._ensure_tables()
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            rows = self.db_tables['db'].execute(
                """SELECT query_name, query_type,
                          COUNT(*) as query_count,
                          AVG(duration_ms) as avg_duration_ms,
                          MAX(duration_ms) as max_duration_ms,
                          SUM(row_count) as total_rows
                   FROM query_metrics
                   WHERE timestamp > ?
                   GROUP BY query_name, query_type
                   ORDER BY avg_duration_ms DESC
                   LIMIT 50""",
                (cutoff,)
            ).fetchall()

            return [
                {
                    'query_name': row[0] or row[1],
                    'query_type': row[1],
                    'query_count': row[2],
                    'avg_duration_ms': round(row[3], 1) if row[3] else 0,
                    'max_duration_ms': round(row[4], 1) if row[4] else 0,
                    'total_rows': row[5] or 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting query stats: {e}")
            return self._get_memory_query_stats()

    def _get_memory_query_stats(self) -> List[Dict[str, Any]]:
        """Get query stats from in-memory aggregates."""
        results = []
        with self._lock:
            for key, stats in self._query_stats.items():
                results.append({
                    'query_name': key,
                    'query_type': 'select',
                    'query_count': stats['count'],
                    'avg_duration_ms': round(stats['total_ms'] / stats['count'], 1) if stats['count'] > 0 else 0,
                    'max_duration_ms': round(stats['max_ms'], 1),
                    'total_rows': 0
                })
        return sorted(results, key=lambda x: x['avg_duration_ms'], reverse=True)[:50]

    def get_api_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get external API statistics for the given time period."""
        if not self.db_tables:
            return self._get_memory_api_stats()

        try:
            self._ensure_tables()
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            rows = self.db_tables['db'].execute(
                """SELECT service, endpoint,
                          COUNT(*) as call_count,
                          AVG(duration_ms) as avg_duration_ms,
                          MAX(duration_ms) as max_duration_ms,
                          SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                   FROM api_metrics
                   WHERE timestamp > ?
                   GROUP BY service, endpoint
                   ORDER BY avg_duration_ms DESC
                   LIMIT 50""",
                (cutoff,)
            ).fetchall()

            return [
                {
                    'service': row[0],
                    'endpoint': row[1],
                    'call_count': row[2],
                    'avg_duration_ms': round(row[3], 1) if row[3] else 0,
                    'max_duration_ms': round(row[4], 1) if row[4] else 0,
                    'error_count': row[5] or 0,
                    'error_rate': round((row[5] or 0) / row[2] * 100, 1) if row[2] > 0 else 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting API stats: {e}")
            return self._get_memory_api_stats()

    def _get_memory_api_stats(self) -> List[Dict[str, Any]]:
        """Get API stats from in-memory aggregates."""
        results = []
        with self._lock:
            for key, stats in self._api_stats.items():
                parts = key.split(':', 1)
                service = parts[0]
                endpoint = parts[1] if len(parts) > 1 else ''
                results.append({
                    'service': service,
                    'endpoint': endpoint,
                    'call_count': stats['count'],
                    'avg_duration_ms': round(stats['total_ms'] / stats['count'], 1) if stats['count'] > 0 else 0,
                    'max_duration_ms': round(stats['max_ms'], 1),
                    'error_count': stats['errors'],
                    'error_rate': round(stats['errors'] / stats['count'] * 100, 1) if stats['count'] > 0 else 0
                })
        return sorted(results, key=lambda x: x['avg_duration_ms'], reverse=True)[:50]

    def get_slow_requests(self, threshold_ms: float = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent slow requests."""
        threshold = threshold_ms or self.SLOW_REQUEST_THRESHOLD_MS

        if not self.db_tables:
            return []

        try:
            self._ensure_tables()
            rows = self.db_tables['db'].execute(
                """SELECT route, method, status_code, duration_ms, timestamp, user_did
                   FROM request_metrics
                   WHERE duration_ms >= ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (threshold, limit)
            ).fetchall()

            return [
                {
                    'route': row[0],
                    'method': row[1],
                    'status_code': row[2],
                    'duration_ms': round(row[3], 1),
                    'timestamp': row[4],
                    'user_did': row[5]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting slow requests: {e}")
            return []

    def get_overview_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get an overview of performance stats for the dashboard."""
        if not self.db_tables:
            return self._get_memory_overview_stats()

        try:
            self._ensure_tables()
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            # Request stats
            req_row = self.db_tables['db'].execute(
                """SELECT COUNT(*) as total,
                          AVG(duration_ms) as avg_ms,
                          MAX(duration_ms) as max_ms,
                          SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors,
                          SUM(CASE WHEN duration_ms >= ? THEN 1 ELSE 0 END) as slow
                   FROM request_metrics WHERE timestamp > ?""",
                (self.SLOW_REQUEST_THRESHOLD_MS, cutoff)
            ).fetchone()

            # Query stats
            query_row = self.db_tables['db'].execute(
                """SELECT COUNT(*) as total,
                          AVG(duration_ms) as avg_ms,
                          MAX(duration_ms) as max_ms,
                          SUM(CASE WHEN duration_ms >= ? THEN 1 ELSE 0 END) as slow
                   FROM query_metrics WHERE timestamp > ?""",
                (self.SLOW_QUERY_THRESHOLD_MS, cutoff)
            ).fetchone()

            # API stats
            api_row = self.db_tables['db'].execute(
                """SELECT COUNT(*) as total,
                          AVG(duration_ms) as avg_ms,
                          SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
                   FROM api_metrics WHERE timestamp > ?""",
                (cutoff,)
            ).fetchone()

            return {
                'requests': {
                    'total': req_row[0] or 0,
                    'avg_ms': round(req_row[1], 1) if req_row[1] else 0,
                    'max_ms': round(req_row[2], 1) if req_row[2] else 0,
                    'errors': req_row[3] or 0,
                    'slow': req_row[4] or 0
                },
                'queries': {
                    'total': query_row[0] or 0,
                    'avg_ms': round(query_row[1], 1) if query_row[1] else 0,
                    'max_ms': round(query_row[2], 1) if query_row[2] else 0,
                    'slow': query_row[3] or 0
                },
                'api_calls': {
                    'total': api_row[0] or 0,
                    'avg_ms': round(api_row[1], 1) if api_row[1] else 0,
                    'errors': api_row[2] or 0
                },
                'period_hours': hours
            }
        except Exception as e:
            logger.error(f"Error getting overview stats: {e}")
            return self._get_memory_overview_stats()

    def _get_memory_overview_stats(self) -> Dict[str, Any]:
        """Get overview stats from in-memory data."""
        with self._lock:
            req_count = sum(s['count'] for s in self._route_stats.values())
            req_total_ms = sum(s['total_ms'] for s in self._route_stats.values())

            query_count = sum(s['count'] for s in self._query_stats.values())
            query_total_ms = sum(s['total_ms'] for s in self._query_stats.values())

            api_count = sum(s['count'] for s in self._api_stats.values())
            api_total_ms = sum(s['total_ms'] for s in self._api_stats.values())
            api_errors = sum(s['errors'] for s in self._api_stats.values())

            return {
                'requests': {
                    'total': req_count,
                    'avg_ms': round(req_total_ms / req_count, 1) if req_count > 0 else 0,
                    'max_ms': max((s['max_ms'] for s in self._route_stats.values()), default=0),
                    'errors': 0,
                    'slow': 0
                },
                'queries': {
                    'total': query_count,
                    'avg_ms': round(query_total_ms / query_count, 1) if query_count > 0 else 0,
                    'max_ms': max((s['max_ms'] for s in self._query_stats.values()), default=0),
                    'slow': 0
                },
                'api_calls': {
                    'total': api_count,
                    'avg_ms': round(api_total_ms / api_count, 1) if api_count > 0 else 0,
                    'errors': api_errors
                },
                'period_hours': 24
            }

    def cleanup_old_records(self, days: int = 7):
        """Remove old performance records to prevent database bloat."""
        if not self.db_tables:
            return

        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            self.db_tables['db'].execute(
                "DELETE FROM request_metrics WHERE timestamp < ?", (cutoff,)
            )
            self.db_tables['db'].execute(
                "DELETE FROM query_metrics WHERE timestamp < ?", (cutoff,)
            )
            self.db_tables['db'].execute(
                "DELETE FROM api_metrics WHERE timestamp < ?", (cutoff,)
            )
            self.db_tables['db'].execute("COMMIT")

            logger.info(f"Cleaned up performance records older than {days} days")
        except Exception as e:
            logger.error(f"Error cleaning up performance records: {e}")


# Context manager for timing operations
@contextmanager
def track_query(query_name: str, query_type: str = 'select'):
    """Context manager to track database query timing."""
    monitor = get_performance_monitor()
    start = time.perf_counter()
    row_count = None
    try:
        yield lambda count: setattr(track_query, '_row_count', count)
        row_count = getattr(track_query, '_row_count', None)
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        if monitor:
            monitor.record_query(query_type, query_name, duration_ms, row_count)


@contextmanager
def track_api_call(service: str, endpoint: str):
    """Context manager to track external API call timing."""
    monitor = get_performance_monitor()
    start = time.perf_counter()
    success = True
    error_msg = None
    status_code = None
    try:
        yield lambda code: setattr(track_api_call, '_status_code', code)
        status_code = getattr(track_api_call, '_status_code', None)
    except Exception as e:
        success = False
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        if monitor:
            monitor.record_api_call(service, endpoint, duration_ms,
                                     status_code, success, error_msg)


def track_query_func(query_name: str, query_type: str = 'select'):
    """Decorator to track function that performs a database query."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000

            # Try to get row count from result
            row_count = None
            if isinstance(result, (list, tuple)):
                row_count = len(result)

            if monitor:
                monitor.record_query(query_type, query_name, duration_ms,
                                      row_count, func.__name__)
            return result
        return wrapper
    return decorator


def track_api_func(service: str, endpoint: str):
    """Decorator to track function that makes an external API call."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start = time.perf_counter()
            success = True
            error_msg = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                if monitor:
                    monitor.record_api_call(service, endpoint, duration_ms,
                                             None, success, error_msg)
        return wrapper
    return decorator


def init_performance_monitoring(db_tables=None) -> PerformanceMonitor:
    """Initialize the global performance monitor."""
    global _performance_monitor
    _performance_monitor = PerformanceMonitor(db_tables)
    return _performance_monitor


def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get the global performance monitor instance."""
    return _performance_monitor
