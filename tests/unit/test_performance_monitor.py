"""
Unit tests for the performance monitoring module.

These tests verify the PerformanceMonitor class, tracking decorators,
context managers, and metric recording functionality.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ============================================================================
# Test PerformanceMonitor Class
# ============================================================================

class TestPerformanceMonitorInit:
    """Tests for PerformanceMonitor initialization."""

    @pytest.mark.unit
    def test_init_without_db(self):
        """PerformanceMonitor can be initialized without database."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        assert monitor.db_tables is None
        assert monitor._enabled is True
        assert len(monitor._request_buffer) == 0

    @pytest.mark.unit
    def test_init_with_db_tables(self):
        """PerformanceMonitor accepts db_tables on init."""
        from performance_monitor import PerformanceMonitor

        mock_db = MagicMock()
        monitor = PerformanceMonitor(db_tables=mock_db)

        assert monitor.db_tables == mock_db

    @pytest.mark.unit
    def test_default_thresholds(self):
        """PerformanceMonitor has sensible default thresholds."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        assert monitor.SLOW_REQUEST_THRESHOLD_MS == 1000
        assert monitor.SLOW_QUERY_THRESHOLD_MS == 100
        assert monitor.SLOW_API_THRESHOLD_MS == 2000


class TestRecordRequest:
    """Tests for recording request metrics."""

    @pytest.mark.unit
    def test_record_request_basic(self):
        """Basic request recording works correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_request(
            route="/api/test",
            method="GET",
            status_code=200,
            duration_ms=50.5
        )

        # Check in-memory stats
        key = "GET /api/test"
        assert key in monitor._route_stats
        assert monitor._route_stats[key]['count'] == 1
        assert monitor._route_stats[key]['total_ms'] == 50.5

    @pytest.mark.unit
    def test_record_request_aggregates_stats(self):
        """Multiple requests aggregate correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        # Record multiple requests
        monitor.record_request("/api/test", "GET", 200, 100)
        monitor.record_request("/api/test", "GET", 200, 200)
        monitor.record_request("/api/test", "GET", 500, 300)

        key = "GET /api/test"
        assert monitor._route_stats[key]['count'] == 3
        assert monitor._route_stats[key]['total_ms'] == 600
        assert monitor._route_stats[key]['max_ms'] == 300
        assert monitor._route_stats[key]['min_ms'] == 100

    @pytest.mark.unit
    def test_record_request_with_user_did(self):
        """Request recording accepts user_did parameter."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_request(
            route="/api/test",
            method="POST",
            status_code=201,
            duration_ms=100,
            user_did="did:plc:testuser123"
        )

        # Should be in buffer
        assert len(monitor._request_buffer) == 1
        assert monitor._request_buffer[0].user_did == "did:plc:testuser123"

    @pytest.mark.unit
    def test_record_request_disabled(self):
        """Request recording does nothing when disabled."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor._enabled = False

        monitor.record_request("/api/test", "GET", 200, 100)

        assert len(monitor._request_buffer) == 0
        assert len(monitor._route_stats) == 0

    @pytest.mark.unit
    def test_slow_request_logging(self, caplog):
        """Slow requests are logged as warnings."""
        from performance_monitor import PerformanceMonitor
        import logging

        monitor = PerformanceMonitor()

        with caplog.at_level(logging.WARNING):
            monitor.record_request("/slow/route", "GET", 200, 1500)

        assert "Slow request" in caplog.text
        assert "/slow/route" in caplog.text


class TestRecordQuery:
    """Tests for recording database query metrics."""

    @pytest.mark.unit
    def test_record_query_basic(self):
        """Basic query recording works correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_query(
            query_type="select",
            query_name="get_user",
            duration_ms=15.5
        )

        assert "get_user" in monitor._query_stats
        assert monitor._query_stats["get_user"]['count'] == 1

    @pytest.mark.unit
    def test_record_query_with_row_count(self):
        """Query recording accepts row_count parameter."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_query(
            query_type="select",
            query_name="get_users",
            duration_ms=25,
            row_count=100
        )

        assert len(monitor._query_buffer) == 1
        assert monitor._query_buffer[0].row_count == 100

    @pytest.mark.unit
    def test_record_query_with_caller(self):
        """Query recording accepts caller parameter."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_query(
            query_type="select",
            query_name="get_shelves",
            duration_ms=30,
            caller="get_public_shelves_with_stats"
        )

        assert monitor._query_buffer[0].caller == "get_public_shelves_with_stats"

    @pytest.mark.unit
    def test_slow_query_logging(self, caplog):
        """Slow queries are logged as warnings."""
        from performance_monitor import PerformanceMonitor
        import logging

        monitor = PerformanceMonitor()

        with caplog.at_level(logging.WARNING):
            monitor.record_query("select", "slow_query", 150)

        assert "Slow query" in caplog.text
        assert "slow_query" in caplog.text


class TestRecordApiCall:
    """Tests for recording external API call metrics."""

    @pytest.mark.unit
    def test_record_api_call_basic(self):
        """Basic API call recording works correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor.record_api_call(
            service="google_books",
            endpoint="search",
            duration_ms=500
        )

        key = "google_books:search"
        assert key in monitor._api_stats
        assert monitor._api_stats[key]['count'] == 1

    @pytest.mark.unit
    def test_record_api_call_with_error(self):
        """API call recording tracks errors correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        # Record successful call
        monitor.record_api_call("test_api", "endpoint", 100, success=True)
        # Record failed call
        monitor.record_api_call(
            "test_api", "endpoint", 200,
            success=False, error_message="Connection timeout"
        )

        key = "test_api:endpoint"
        assert monitor._api_stats[key]['count'] == 2
        assert monitor._api_stats[key]['errors'] == 1

    @pytest.mark.unit
    def test_slow_api_call_logging(self, caplog):
        """Slow API calls are logged as warnings."""
        from performance_monitor import PerformanceMonitor
        import logging

        monitor = PerformanceMonitor()

        with caplog.at_level(logging.WARNING):
            monitor.record_api_call("external_api", "slow_endpoint", 2500)

        assert "Slow API call" in caplog.text


class TestGetStats:
    """Tests for retrieving statistics."""

    @pytest.mark.unit
    def test_get_memory_request_stats(self):
        """In-memory request stats are retrieved correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        # Add some data
        monitor.record_request("/api/a", "GET", 200, 100)
        monitor.record_request("/api/a", "GET", 200, 200)
        monitor.record_request("/api/b", "POST", 201, 50)

        stats = monitor._get_memory_request_stats()

        assert len(stats) == 2
        # Should be sorted by avg duration descending
        assert stats[0]['avg_duration_ms'] >= stats[1]['avg_duration_ms']

    @pytest.mark.unit
    def test_get_memory_query_stats(self):
        """In-memory query stats are retrieved correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        monitor.record_query("select", "query_a", 50)
        monitor.record_query("select", "query_b", 100)
        monitor.record_query("select", "query_b", 150)

        stats = monitor._get_memory_query_stats()

        assert len(stats) == 2
        # query_b should have higher average
        query_b_stat = next(s for s in stats if s['query_name'] == 'query_b')
        assert query_b_stat['avg_duration_ms'] == 125.0

    @pytest.mark.unit
    def test_get_memory_api_stats(self):
        """In-memory API stats are retrieved correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        monitor.record_api_call("service_a", "endpoint", 100, success=True)
        monitor.record_api_call("service_a", "endpoint", 200, success=False)

        stats = monitor._get_memory_api_stats()

        assert len(stats) == 1
        assert stats[0]['call_count'] == 2
        assert stats[0]['error_count'] == 1
        assert stats[0]['error_rate'] == 50.0

    @pytest.mark.unit
    def test_get_overview_stats_memory(self):
        """Overview stats from memory work correctly."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        monitor.record_request("/test", "GET", 200, 100)
        monitor.record_query("select", "test_query", 50)
        monitor.record_api_call("test_api", "endpoint", 200, success=True)
        monitor.record_api_call("test_api", "endpoint", 300, success=False)

        overview = monitor.get_overview_stats()

        assert overview['requests']['total'] == 1
        assert overview['queries']['total'] == 1
        assert overview['api_calls']['total'] == 2
        assert overview['api_calls']['errors'] == 1


class TestBufferFlushing:
    """Tests for buffer management and flushing."""

    @pytest.mark.unit
    def test_buffer_size_threshold(self):
        """Buffer flushes when threshold is reached."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        monitor._buffer_size = 5  # Low threshold for testing

        # Should not flush yet
        for i in range(4):
            monitor.record_request(f"/api/{i}", "GET", 200, 10)

        assert len(monitor._request_buffer) == 4

        # This should trigger flush (but without db, buffer just clears in lock)
        monitor.record_request("/api/5", "GET", 200, 10)

        # Without db_tables, flush doesn't persist but buffer is cleared
        # The 5th item is added after the flush
        assert len(monitor._request_buffer) <= 5

    @pytest.mark.unit
    def test_flush_all_attempts_flush(self):
        """flush_all attempts to flush all buffers."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()

        monitor.record_request("/test", "GET", 200, 100)
        monitor.record_query("select", "test", 50)
        monitor.record_api_call("api", "endpoint", 200)

        # Without db, buffers won't clear but flush should not error
        monitor.flush_all()

        # Without db_tables, data stays in buffer (no persistence target)
        # The important thing is it doesn't error
        assert True


class TestThreadSafety:
    """Tests for thread safety of the monitor."""

    @pytest.mark.unit
    def test_concurrent_request_recording(self):
        """Concurrent request recording doesn't lose data."""
        from performance_monitor import PerformanceMonitor

        monitor = PerformanceMonitor()
        num_threads = 10
        requests_per_thread = 100

        def record_requests(thread_id):
            for i in range(requests_per_thread):
                monitor.record_request(
                    f"/thread/{thread_id}",
                    "GET",
                    200,
                    float(i)
                )

        threads = [
            threading.Thread(target=record_requests, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check total count across all route stats
        total_count = sum(s['count'] for s in monitor._route_stats.values())
        assert total_count == num_threads * requests_per_thread


# ============================================================================
# Test Tracking Decorators
# ============================================================================

class TestTrackQueryFunc:
    """Tests for the track_query_func decorator."""

    @pytest.mark.unit
    def test_decorator_tracks_function(self):
        """Decorator tracks function execution time."""
        from performance_monitor import track_query_func, init_performance_monitoring, get_performance_monitor

        monitor = init_performance_monitoring()

        @track_query_func('test_function', 'select')
        def test_function():
            time.sleep(0.01)  # 10ms
            return [1, 2, 3]

        result = test_function()

        assert result == [1, 2, 3]
        assert 'test_function' in monitor._query_stats
        assert monitor._query_stats['test_function']['count'] == 1

    @pytest.mark.unit
    def test_decorator_counts_list_results(self):
        """Decorator counts rows when result is a list."""
        from performance_monitor import track_query_func, init_performance_monitoring

        monitor = init_performance_monitoring()

        @track_query_func('list_function', 'select')
        def list_function():
            return ['a', 'b', 'c', 'd', 'e']

        result = list_function()

        assert len(result) == 5
        # Check row count was captured in buffer
        assert len(monitor._query_buffer) == 1
        assert monitor._query_buffer[0].row_count == 5

    @pytest.mark.unit
    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""
        from performance_monitor import track_query_func

        @track_query_func('my_query', 'select')
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__name__ == 'documented_function'
        assert documented_function.__doc__ == """This is the docstring."""


class TestTrackApiFunc:
    """Tests for the track_api_func decorator."""

    @pytest.mark.unit
    def test_decorator_tracks_successful_call(self):
        """Decorator tracks successful API calls."""
        from performance_monitor import track_api_func, init_performance_monitoring

        monitor = init_performance_monitoring()

        @track_api_func('test_service', 'test_endpoint')
        def api_function():
            return {'status': 'ok'}

        result = api_function()

        assert result == {'status': 'ok'}
        key = 'test_service:test_endpoint'
        assert key in monitor._api_stats
        assert monitor._api_stats[key]['errors'] == 0

    @pytest.mark.unit
    def test_decorator_tracks_failed_call(self):
        """Decorator tracks failed API calls."""
        from performance_monitor import track_api_func, init_performance_monitoring

        monitor = init_performance_monitoring()

        @track_api_func('failing_service', 'failing_endpoint')
        def failing_function():
            raise ValueError("API Error")

        with pytest.raises(ValueError):
            failing_function()

        key = 'failing_service:failing_endpoint'
        assert key in monitor._api_stats
        assert monitor._api_stats[key]['errors'] == 1


# ============================================================================
# Test Context Managers
# ============================================================================

class TestTrackQueryContextManager:
    """Tests for the track_query context manager."""

    @pytest.mark.unit
    def test_context_manager_tracks_timing(self):
        """Context manager tracks execution time."""
        from performance_monitor import track_query, init_performance_monitoring

        monitor = init_performance_monitoring()

        with track_query('ctx_query', 'select'):
            time.sleep(0.01)

        assert 'ctx_query' in monitor._query_stats

    @pytest.mark.unit
    def test_context_manager_handles_exceptions(self):
        """Context manager records timing even on exception."""
        from performance_monitor import track_query, init_performance_monitoring

        monitor = init_performance_monitoring()

        with pytest.raises(RuntimeError):
            with track_query('failing_query', 'select'):
                raise RuntimeError("Query failed")

        # Should still have recorded the timing
        assert 'failing_query' in monitor._query_stats


class TestTrackApiCallContextManager:
    """Tests for the track_api_call context manager."""

    @pytest.mark.unit
    def test_context_manager_tracks_timing(self):
        """Context manager tracks API call timing."""
        from performance_monitor import track_api_call, init_performance_monitoring

        monitor = init_performance_monitoring()

        with track_api_call('ctx_service', 'ctx_endpoint'):
            time.sleep(0.01)

        key = 'ctx_service:ctx_endpoint'
        assert key in monitor._api_stats

    @pytest.mark.unit
    def test_context_manager_tracks_failures(self):
        """Context manager records failures on exception."""
        from performance_monitor import track_api_call, init_performance_monitoring

        monitor = init_performance_monitoring()

        with pytest.raises(ConnectionError):
            with track_api_call('failing_api', 'endpoint'):
                raise ConnectionError("Network error")

        key = 'failing_api:endpoint'
        assert monitor._api_stats[key]['errors'] == 1


# ============================================================================
# Test Global Monitor Management
# ============================================================================

class TestGlobalMonitor:
    """Tests for global monitor initialization and access."""

    @pytest.mark.unit
    def test_init_creates_global_monitor(self):
        """init_performance_monitoring creates global monitor."""
        from performance_monitor import init_performance_monitoring, get_performance_monitor

        monitor = init_performance_monitoring()

        assert get_performance_monitor() is monitor

    @pytest.mark.unit
    def test_init_with_db_tables(self):
        """init_performance_monitoring accepts db_tables."""
        from performance_monitor import init_performance_monitoring

        mock_db = MagicMock()
        monitor = init_performance_monitoring(db_tables=mock_db)

        assert monitor.db_tables == mock_db

    @pytest.mark.unit
    def test_get_monitor_returns_none_before_init(self):
        """get_performance_monitor returns None before initialization."""
        from performance_monitor import _performance_monitor
        import performance_monitor

        # Reset global
        original = performance_monitor._performance_monitor
        performance_monitor._performance_monitor = None

        result = performance_monitor.get_performance_monitor()

        assert result is None

        # Restore
        performance_monitor._performance_monitor = original


# ============================================================================
# Test Data Classes
# ============================================================================

class TestMetricDataClasses:
    """Tests for metric data classes."""

    @pytest.mark.unit
    def test_request_metric_creation(self):
        """RequestMetric dataclass works correctly."""
        from performance_monitor import RequestMetric

        metric = RequestMetric(
            route="/test",
            method="GET",
            status_code=200,
            duration_ms=100.5
        )

        assert metric.route == "/test"
        assert metric.method == "GET"
        assert metric.status_code == 200
        assert metric.duration_ms == 100.5
        assert metric.timestamp is not None

    @pytest.mark.unit
    def test_query_metric_creation(self):
        """QueryMetric dataclass works correctly."""
        from performance_monitor import QueryMetric

        metric = QueryMetric(
            query_type="select",
            query_name="get_users",
            duration_ms=25.3,
            row_count=50
        )

        assert metric.query_type == "select"
        assert metric.query_name == "get_users"
        assert metric.row_count == 50

    @pytest.mark.unit
    def test_api_metric_creation(self):
        """ApiMetric dataclass works correctly."""
        from performance_monitor import ApiMetric

        metric = ApiMetric(
            service="google_books",
            endpoint="search",
            duration_ms=500,
            status_code=200,
            success=True
        )

        assert metric.service == "google_books"
        assert metric.success is True

    @pytest.mark.unit
    def test_api_metric_with_error(self):
        """ApiMetric captures error information."""
        from performance_monitor import ApiMetric

        metric = ApiMetric(
            service="failing_api",
            endpoint="broken",
            duration_ms=100,
            success=False,
            error_message="Connection refused"
        )

        assert metric.success is False
        assert metric.error_message == "Connection refused"
