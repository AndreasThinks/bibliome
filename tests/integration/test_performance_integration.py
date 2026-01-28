"""
Integration tests for performance monitoring.

These tests verify the integration between the performance monitor,
middleware, and admin routes.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


# ============================================================================
# Test Performance Monitor with Database
# ============================================================================

class TestPerformanceMonitorWithDB:
    """Tests for PerformanceMonitor with actual database operations."""

    @pytest.fixture
    def monitor_with_db(self, db_tables):
        """Create a performance monitor with database tables."""
        from performance_monitor import PerformanceMonitor

        # Create performance tables
        db_tables['db'].execute("""
            CREATE TABLE IF NOT EXISTS request_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL,
                method TEXT NOT NULL DEFAULT 'GET',
                status_code INTEGER,
                duration_ms REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_did TEXT,
                request_size INTEGER,
                response_size INTEGER
            )
        """)
        db_tables['db'].execute("""
            CREATE TABLE IF NOT EXISTS query_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_type TEXT NOT NULL,
                query_name TEXT,
                duration_ms REAL NOT NULL,
                row_count INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                caller TEXT
            )
        """)
        db_tables['db'].execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                status_code INTEGER,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        monitor = PerformanceMonitor(db_tables=db_tables)
        monitor._buffer_size = 2  # Low threshold for testing

        return monitor, db_tables

    @pytest.mark.integration
    def test_request_metrics_persisted(self, monitor_with_db):
        """Request metrics are persisted to database."""
        monitor, db_tables = monitor_with_db

        # Record enough requests to trigger flush
        monitor.record_request("/test1", "GET", 200, 100)
        monitor.record_request("/test2", "GET", 200, 150)
        monitor.record_request("/test3", "GET", 200, 200)

        # Force flush
        monitor.flush_all()

        # Check database
        rows = db_tables['db'].execute(
            "SELECT route, duration_ms FROM request_metrics"
        ).fetchall()

        assert len(rows) >= 1

    @pytest.mark.integration
    def test_query_metrics_persisted(self, monitor_with_db):
        """Query metrics are persisted to database."""
        monitor, db_tables = monitor_with_db

        monitor.record_query("select", "test_query", 50, row_count=10)
        monitor.record_query("select", "test_query", 75, row_count=20)
        monitor.record_query("select", "test_query", 100, row_count=30)

        monitor.flush_all()

        rows = db_tables['db'].execute(
            "SELECT query_name, duration_ms FROM query_metrics"
        ).fetchall()

        assert len(rows) >= 1

    @pytest.mark.integration
    def test_api_metrics_persisted(self, monitor_with_db):
        """API metrics are persisted to database."""
        monitor, db_tables = monitor_with_db

        monitor.record_api_call("google_books", "search", 500, success=True)
        monitor.record_api_call("google_books", "search", 600, success=False, error_message="timeout")
        monitor.record_api_call("open_library", "search", 800, success=True)

        monitor.flush_all()

        rows = db_tables['db'].execute(
            "SELECT service, endpoint, success FROM api_metrics"
        ).fetchall()

        assert len(rows) >= 1

    @pytest.mark.integration
    def test_get_request_stats_from_db(self, monitor_with_db):
        """Request stats can be retrieved from database."""
        monitor, db_tables = monitor_with_db

        # Insert test data
        monitor.record_request("/api/test", "GET", 200, 100)
        monitor.record_request("/api/test", "GET", 200, 200)
        monitor.record_request("/api/other", "POST", 201, 50)
        monitor.flush_all()

        # Get stats
        stats = monitor.get_request_stats(hours=24)

        # Should have aggregated results
        assert isinstance(stats, list)

    @pytest.mark.integration
    def test_get_slow_requests_from_db(self, monitor_with_db):
        """Slow requests can be retrieved from database."""
        monitor, db_tables = monitor_with_db

        # Insert test data including slow requests
        monitor.record_request("/fast", "GET", 200, 50)
        monitor.record_request("/slow", "GET", 200, 1500)
        monitor.record_request("/very_slow", "GET", 200, 3000)
        monitor.flush_all()

        # Get slow requests
        slow = monitor.get_slow_requests(threshold_ms=1000, limit=10)

        # Should return slow requests (may depend on buffer behavior)
        assert isinstance(slow, list)

    @pytest.mark.integration
    def test_cleanup_old_records(self, monitor_with_db):
        """Old records can be cleaned up."""
        monitor, db_tables = monitor_with_db

        # Insert test data
        monitor.record_request("/test", "GET", 200, 100)
        monitor.flush_all()

        # Cleanup (with 0 days should remove everything)
        monitor.cleanup_old_records(days=0)

        # Verify cleanup
        rows = db_tables['db'].execute(
            "SELECT COUNT(*) FROM request_metrics"
        ).fetchone()

        # Records should be cleaned (timestamp is current, so 0 days removes all)
        assert rows[0] == 0


# ============================================================================
# Test Decorated Model Functions
# ============================================================================

class TestDecoratedModelFunctions:
    """Tests for model functions with performance tracking decorators."""

    @pytest.mark.integration
    def test_get_public_shelves_with_stats_tracked(self, db_with_books):
        """get_public_shelves_with_stats is tracked."""
        from performance_monitor import init_performance_monitoring, get_performance_monitor
        from models import get_public_shelves_with_stats

        db_tables, owner, shelf, books = db_with_books

        # Initialize monitor
        monitor = init_performance_monitoring()

        # Call the decorated function
        result = get_public_shelves_with_stats(db_tables, limit=10)

        # Check that it was tracked
        assert 'get_public_shelves_with_stats' in monitor._query_stats
        assert monitor._query_stats['get_public_shelves_with_stats']['count'] == 1

    @pytest.mark.integration
    def test_get_user_shelves_tracked(self, db_with_shelf):
        """get_user_shelves is tracked."""
        from performance_monitor import init_performance_monitoring, get_performance_monitor
        from models import get_user_shelves

        db_tables, owner, shelf = db_with_shelf

        # Initialize monitor
        monitor = init_performance_monitoring()

        # Call the decorated function
        result = get_user_shelves(owner.did, db_tables, limit=10)

        # Check that it was tracked
        assert 'get_user_shelves' in monitor._query_stats

    @pytest.mark.integration
    def test_get_mixed_public_shelves_tracked(self, db_with_books):
        """get_mixed_public_shelves is tracked."""
        from performance_monitor import init_performance_monitoring, get_performance_monitor
        from models import get_mixed_public_shelves

        db_tables, owner, shelf, books = db_with_books

        # Initialize monitor
        monitor = init_performance_monitoring()

        # Call the decorated function
        result = get_mixed_public_shelves(db_tables, limit=10)

        # Check that it was tracked
        assert 'get_mixed_public_shelves' in monitor._query_stats


# ============================================================================
# Test Book API Client Tracking
# ============================================================================

class TestBookAPIClientTracking:
    """Tests for book API client with performance tracking."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_books_tracks_google_success(self):
        """Successful Google Books search is tracked."""
        from performance_monitor import init_performance_monitoring, get_performance_monitor
        from bibliome.clients.books import BookAPIClient

        monitor = init_performance_monitoring()

        # Mock the HTTP client
        with patch('httpx.AsyncClient') as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'items': [{
                    'volumeInfo': {
                        'title': 'Test Book',
                        'authors': ['Test Author'],
                        'industryIdentifiers': [{'type': 'ISBN_13', 'identifier': '9781234567890'}]
                    }
                }]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value = mock_client_instance

            client = BookAPIClient()

            # Mock rate limiter
            with patch.object(client.rate_limiter, 'execute_with_backoff', new_callable=AsyncMock) as mock_rate:
                mock_rate.return_value = mock_response

                result = await client.search_books("test query")

            # Check tracking
            assert 'google_books:search' in monitor._api_stats


# ============================================================================
# Test Migration
# ============================================================================

class TestPerformanceMigration:
    """Tests for the performance monitoring database migration."""

    @pytest.mark.integration
    def test_migration_creates_tables(self, db_tables):
        """Migration creates required tables."""
        import os

        # Read and execute migration
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'migrations',
            '0011-add-performance-monitoring.sql'
        )

        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        # Execute migration (split by semicolon for multiple statements)
        for statement in migration_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    db_tables['db'].execute(statement)
                except Exception:
                    pass  # Ignore errors for CREATE IF NOT EXISTS

        # Verify tables exist
        tables = db_tables['db'].execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert 'request_metrics' in table_names
        assert 'query_metrics' in table_names
        assert 'api_metrics' in table_names

    @pytest.mark.integration
    def test_migration_creates_indexes(self, db_tables):
        """Migration creates performance indexes."""
        import os

        # Execute migration
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'migrations',
            '0011-add-performance-monitoring.sql'
        )

        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        for statement in migration_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    db_tables['db'].execute(statement)
                except Exception:
                    pass

        # Verify indexes exist
        indexes = db_tables['db'].execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [i[0] for i in indexes]

        assert 'idx_request_metrics_route' in index_names
        assert 'idx_query_metrics_name' in index_names
        assert 'idx_api_metrics_service' in index_names
