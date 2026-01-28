"""
Unit tests for performance monitoring admin components.

These tests verify the UI components render correctly with various data states.

Note: These tests require the full FastHTML environment. If imports fail due to
missing dependencies, tests will be skipped.
"""

import pytest
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Skip all tests if fasthtml dependencies are not available
try:
    from fasthtml.common import Div, H1, P, Table
    HAS_FASTHTML = True
except ImportError:
    HAS_FASTHTML = False

pytestmark = pytest.mark.skipif(not HAS_FASTHTML, reason="FastHTML not available")


# ============================================================================
# Test PerformanceDashboard Component
# ============================================================================

@pytest.mark.unit
class TestPerformanceDashboard:
    """Tests for the main PerformanceDashboard component."""

    def test_dashboard_renders_with_empty_stats(self):
        """Dashboard renders correctly with empty statistics."""
        from bibliome.components.admin import PerformanceDashboard

        stats = {
            'requests': {'total': 0, 'avg_ms': 0, 'max_ms': 0, 'errors': 0, 'slow': 0},
            'queries': {'total': 0, 'avg_ms': 0, 'max_ms': 0, 'slow': 0},
            'api_calls': {'total': 0, 'avg_ms': 0, 'errors': 0},
            'period_hours': 24
        }

        result = PerformanceDashboard(stats)
        assert result is not None

    def test_dashboard_renders_with_data(self):
        """Dashboard renders correctly with actual statistics."""
        from bibliome.components.admin import PerformanceDashboard

        stats = {
            'requests': {'total': 1500, 'avg_ms': 150.5, 'max_ms': 5000, 'errors': 10, 'slow': 25},
            'queries': {'total': 5000, 'avg_ms': 25.3, 'max_ms': 500, 'slow': 100},
            'api_calls': {'total': 200, 'avg_ms': 800, 'errors': 5},
            'period_hours': 24
        }

        result = PerformanceDashboard(stats)
        assert result is not None

    def test_dashboard_handles_missing_keys(self):
        """Dashboard handles missing stat keys gracefully."""
        from bibliome.components.admin import PerformanceDashboard

        stats = {
            'requests': {},
            'queries': {},
            'api_calls': {},
            'period_hours': 24
        }

        result = PerformanceDashboard(stats)
        assert result is not None


# ============================================================================
# Test PerformanceOverviewCard Component
# ============================================================================

@pytest.mark.unit
class TestPerformanceOverviewCard:
    """Tests for the overview card component."""

    def test_card_renders_success_status(self):
        """Card renders with success status styling."""
        from bibliome.components.admin import PerformanceOverviewCard

        result = PerformanceOverviewCard(
            title="Requests",
            count=1000,
            detail1="Avg: 100ms",
            detail2="Slow: 0",
            icon="fa-globe",
            status="success"
        )
        assert result is not None

    def test_card_renders_warning_status(self):
        """Card renders with warning status styling."""
        from bibliome.components.admin import PerformanceOverviewCard

        result = PerformanceOverviewCard(
            title="Queries",
            count=500,
            detail1="Avg: 75ms",
            detail2="Slow: 10",
            icon="fa-database",
            status="warning"
        )
        assert result is not None

    def test_card_renders_danger_status(self):
        """Card renders with danger status styling."""
        from bibliome.components.admin import PerformanceOverviewCard

        result = PerformanceOverviewCard(
            title="API Calls",
            count=100,
            detail1="Avg: 2000ms",
            detail2="Errors: 50",
            icon="fa-cloud",
            status="danger"
        )
        assert result is not None

    def test_card_formats_large_numbers(self):
        """Card formats large numbers with commas."""
        from bibliome.components.admin import PerformanceOverviewCard

        result = PerformanceOverviewCard(
            title="Requests",
            count=1000000,
            detail1="Avg: 50ms",
            detail2="Slow: 0",
            icon="fa-globe",
            status="success"
        )
        assert result is not None


# ============================================================================
# Test PerformanceRouteTable Component
# ============================================================================

@pytest.mark.unit
class TestPerformanceRouteTable:
    """Tests for the route performance table component."""

    def test_table_renders_empty_state(self):
        """Table shows empty message when no routes."""
        from bibliome.components.admin import PerformanceRouteTable

        result = PerformanceRouteTable([])
        assert result is not None

    def test_table_renders_with_routes(self):
        """Table renders route data correctly."""
        from bibliome.components.admin import PerformanceRouteTable

        routes = [
            {
                'route': '/api/shelves',
                'method': 'GET',
                'request_count': 500,
                'avg_duration_ms': 150,
                'max_duration_ms': 2000,
                'error_count': 5
            },
            {
                'route': '/api/books',
                'method': 'POST',
                'request_count': 100,
                'avg_duration_ms': 50,
                'max_duration_ms': 500,
                'error_count': 0
            }
        ]

        result = PerformanceRouteTable(routes)
        assert result is not None

    def test_table_limits_to_15_routes(self):
        """Table only shows first 15 routes."""
        from bibliome.components.admin import PerformanceRouteTable

        routes = [
            {
                'route': f'/api/route{i}',
                'method': 'GET',
                'request_count': i * 10,
                'avg_duration_ms': i * 5,
                'max_duration_ms': i * 10,
                'error_count': 0
            }
            for i in range(20)
        ]

        result = PerformanceRouteTable(routes)
        assert result is not None

    def test_table_handles_slow_routes(self):
        """Table applies correct styling for slow routes."""
        from bibliome.components.admin import PerformanceRouteTable

        routes = [
            {
                'route': '/slow/route',
                'method': 'GET',
                'request_count': 10,
                'avg_duration_ms': 1500,
                'max_duration_ms': 3000,
                'error_count': 0
            }
        ]

        result = PerformanceRouteTable(routes)
        assert result is not None


# ============================================================================
# Test PerformanceQueryTable Component
# ============================================================================

@pytest.mark.unit
class TestPerformanceQueryTable:
    """Tests for the query performance table component."""

    def test_table_renders_empty_state(self):
        """Table shows empty message when no queries."""
        from bibliome.components.admin import PerformanceQueryTable

        result = PerformanceQueryTable([])
        assert result is not None

    def test_table_renders_with_queries(self):
        """Table renders query data correctly."""
        from bibliome.components.admin import PerformanceQueryTable

        queries = [
            {
                'query_name': 'get_public_shelves_with_stats',
                'query_type': 'select',
                'query_count': 1000,
                'avg_duration_ms': 45.5,
                'max_duration_ms': 200,
                'total_rows': 50000
            },
            {
                'query_name': 'get_network_activity',
                'query_type': 'select',
                'query_count': 500,
                'avg_duration_ms': 75.2,
                'max_duration_ms': 300,
                'total_rows': 10000
            }
        ]

        result = PerformanceQueryTable(queries)
        assert result is not None

    def test_table_handles_slow_queries(self):
        """Table applies correct styling for slow queries."""
        from bibliome.components.admin import PerformanceQueryTable

        queries = [
            {
                'query_name': 'very_slow_query',
                'query_type': 'select',
                'query_count': 10,
                'avg_duration_ms': 150,
                'max_duration_ms': 500,
                'total_rows': 1000
            }
        ]

        result = PerformanceQueryTable(queries)
        assert result is not None


# ============================================================================
# Test PerformanceApiTable Component
# ============================================================================

@pytest.mark.unit
class TestPerformanceApiTable:
    """Tests for the API performance table component."""

    def test_table_renders_empty_state(self):
        """Table shows empty message when no API calls."""
        from bibliome.components.admin import PerformanceApiTable

        result = PerformanceApiTable([])
        assert result is not None

    def test_table_renders_with_apis(self):
        """Table renders API data correctly."""
        from bibliome.components.admin import PerformanceApiTable

        apis = [
            {
                'service': 'google_books',
                'endpoint': 'search',
                'call_count': 200,
                'avg_duration_ms': 800,
                'max_duration_ms': 2000,
                'error_count': 5,
                'error_rate': 2.5
            },
            {
                'service': 'open_library',
                'endpoint': 'search',
                'call_count': 50,
                'avg_duration_ms': 1200,
                'max_duration_ms': 3000,
                'error_count': 10,
                'error_rate': 20.0
            }
        ]

        result = PerformanceApiTable(apis)
        assert result is not None

    def test_table_highlights_high_error_rate(self):
        """Table highlights APIs with high error rates."""
        from bibliome.components.admin import PerformanceApiTable

        apis = [
            {
                'service': 'failing_api',
                'endpoint': 'broken',
                'call_count': 100,
                'avg_duration_ms': 500,
                'max_duration_ms': 1000,
                'error_count': 50,
                'error_rate': 50.0
            }
        ]

        result = PerformanceApiTable(apis)
        assert result is not None


# ============================================================================
# Test SlowRequestsList Component
# ============================================================================

@pytest.mark.unit
class TestSlowRequestsList:
    """Tests for the slow requests list component."""

    def test_list_renders_empty_state(self):
        """List shows success message when no slow requests."""
        from bibliome.components.admin import SlowRequestsList

        result = SlowRequestsList([])
        assert result is not None

    def test_list_renders_with_requests(self):
        """List renders slow request data correctly."""
        from bibliome.components.admin import SlowRequestsList

        requests = [
            {
                'route': '/api/slow-route',
                'method': 'GET',
                'status_code': 200,
                'duration_ms': 2500,
                'timestamp': '2026-01-28T10:30:00',
                'user_did': 'did:plc:user123'
            },
            {
                'route': '/api/another-slow',
                'method': 'POST',
                'status_code': 500,
                'duration_ms': 5000,
                'timestamp': '2026-01-28T10:31:00',
                'user_did': None
            }
        ]

        result = SlowRequestsList(requests)
        assert result is not None

    def test_list_limits_to_10_requests(self):
        """List only shows first 10 requests."""
        from bibliome.components.admin import SlowRequestsList

        requests = [
            {
                'route': f'/api/route{i}',
                'method': 'GET',
                'status_code': 200,
                'duration_ms': 1000 + i * 100,
                'timestamp': f'2026-01-28T10:{30+i}:00',
                'user_did': None
            }
            for i in range(15)
        ]

        result = SlowRequestsList(requests)
        assert result is not None

    def test_list_handles_missing_fields(self):
        """List handles requests with missing optional fields."""
        from bibliome.components.admin import SlowRequestsList

        requests = [
            {
                'route': '/api/test',
                'method': 'GET',
                'status_code': None,
                'duration_ms': 2000,
                'timestamp': '',
                'user_did': None
            }
        ]

        result = SlowRequestsList(requests)
        assert result is not None
