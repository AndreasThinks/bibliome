"""Admin dashboard components for Bibliome."""

from fasthtml.common import *
from typing import Dict, Any


def AdminDashboard(stats: Dict[str, Any]):
    """Admin dashboard component with error handling."""
    # Check if there was an error loading stats
    if stats.get("error"):
        error_section = Div(
            H3("⚠️ Stats Loading Error", style="color: #ffc107;"),
            P(f"Error: {stats['error']}", style="color: #dc3545;"),
            P("Basic database connectivity may be impacted. Check the debug page for more information."),
            A("View Debug Info", href="/admin/debug", cls="btn btn-secondary"),
            cls="admin-error-section",
            style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem;"
        )
    else:
        error_section = None
    
    # Maintenance & Cleanup section
    maintenance_section = Section(
        H2("Maintenance & Cleanup"),
        P("Manage system maintenance and database cleanup operations."),
        
        # Maintenance Mode Card
        Div(
            H3("🔧 Maintenance Mode"),
            P("Stop all background processes for safe database operations."),
            Div(
                Div(
                    Span("Status: ", style="font-weight: bold;"),
                    Span("Loading...", id="maintenance-status", style="color: #6c757d;"),
                    cls="maintenance-status-display"
                ),
                # Load the maintenance toggle button via HTMX
                Div(
                    Span("Loading controls...", style="color: #6c757d;"),
                    id="maintenance-controls",
                    hx_get="/admin/maintenance-mode/toggle-button",
                    hx_trigger="load delay:500ms",
                    hx_swap="innerHTML"
                ),
                cls="maintenance-controls-container"
            ),
            cls="admin-maintenance-card",
            style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1rem; background: #ffffff;"
        ),
        
        # Log Cleanup Card
        Div(
            H3("🧹 Database Cleanup"),
            P("Remove old log entries to keep the database size manageable."),
            Div(
                Div(
                    Span("Estimated log entries: ", style="font-weight: bold;"),
                    Span("Loading...", id="log-count-display", style="color: #6c757d;"),
                    cls="log-count-display"
                ),
                Div(
                    Button(
                        "Preview Cleanup",
                        id="cleanup-preview-btn",
                        hx_get="/admin/cleanup-logs/preview",
                        hx_target="#cleanup-preview",
                        hx_swap="innerHTML",
                        cls="btn btn-secondary",
                        style="margin-right: 0.5rem;"
                    ),
                    Button(
                        "Clean Old Logs",
                        id="cleanup-execute-btn",
                        hx_post="/admin/cleanup-logs",
                        hx_target="#cleanup-results",
                        hx_swap="innerHTML",
                        hx_confirm="Are you sure you want to delete old log entries? This cannot be undone.",
                        cls="btn btn-danger"
                    ),
                    cls="cleanup-buttons"
                ),
                Div(id="cleanup-preview", cls="cleanup-preview-container"),
                Div(id="cleanup-results", cls="cleanup-results-container"),
                cls="cleanup-controls-container"
            ),
            cls="admin-cleanup-card",
            style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1rem; background: #ffffff;"
        ),
        
        # Auto-Cleanup Card
        Div(
            H3("🤖 Automatic Cleanup"),
            P("Monitor automatic database cleanup that runs in the background."),
            Div(
                Div(
                    Span("Status: ", style="font-weight: bold;"),
                    Span("Loading...", id="auto-cleanup-status", style="color: #6c757d;"),
                    cls="auto-cleanup-status-display"
                ),
                cls="auto-cleanup-controls-container"
            ),
            cls="admin-auto-cleanup-card",
            style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1rem; background: #ffffff;"
        ),
        
        # Auto-load maintenance status, log count, and auto-cleanup status using HTMX
        Div(
            hx_get="/admin/maintenance-mode/status-display",
            hx_target="#maintenance-status",
            hx_trigger="load",
            hx_swap="innerHTML"
        ),
        Div(
            hx_get="/admin/cleanup-logs/count-display", 
            hx_target="#log-count-display",
            hx_trigger="load",
            hx_swap="innerHTML"
        ),
        Div(
            hx_get="/admin/auto-cleanup/status-display",
            hx_target="#auto-cleanup-status",
            hx_trigger="load",
            hx_swap="innerHTML"
        ),
        
        style="margin: 2rem 0; padding: 1.5rem; border: 1px solid #dee2e6; border-radius: 0.5rem; background: #f8f9fa;"
    )
    
    return Div(
        H1("Admin Dashboard"),
        error_section,
        Div(
            AdminStatsCard("Total Users", stats.get("total_users", "Error"), "fa-users"),
            AdminStatsCard("Total Bookshelves", stats.get("total_bookshelves", "Error"), "fa-book-bookmark"),
            AdminStatsCard("Total Books", stats.get("total_books", "Error"), "fa-book"),
            AdminStatsCard("Total Comments", stats.get("total_comments", "Error"), "fa-comments"),
            cls="admin-stats-grid"
        ),
        # Activity stats section with time-based data
        AdminActivitySection(stats) if not stats.get("error") else None,
        maintenance_section,
        cls="admin-dashboard"
    )


def AdminStatsCard(title: str, value, icon: str):
    """A card for displaying a single stat on the admin dashboard."""
    return Div(
        Div(
            I(cls=f"fas {icon} fa-2x"),
            cls="admin-stats-card-icon"
        ),
        Div(
            H3(value, cls="admin-stats-card-value"),
            P(title, cls="admin-stats-card-title"),
            cls="admin-stats-card-info"
        ),
        cls="admin-stats-card"
    )


def AdminActivitySection(stats: Dict[str, Any]):
    """Activity section showing time-based activity counts."""
    activity_7d = stats.get("activity_7d", {})
    activity_30d = stats.get("activity_30d", {})
    
    if not activity_7d and not activity_30d:
        return None
    
    return Section(
        H2("Recent Activity"),
        P("Activity counts for the last 7 and 30 days", cls="activity-section-subtitle"),
        
        # 7-day activity cards
        Div(
            H3("📅 Last 7 Days", cls="activity-period-title"),
            Div(
                AdminActivityCard("Active Users", activity_7d.get("users", 0), "fa-user-clock", "Users who logged in or joined"),
                AdminActivityCard("New Shelves", activity_7d.get("bookshelves", 0), "fa-plus-circle", "Bookshelves created"),
                AdminActivityCard("Books Added", activity_7d.get("books", 0), "fa-book-medical", "Books added to shelves"),
                AdminActivityCard("Comments", activity_7d.get("comments", 0), "fa-comment-dots", "Comments posted"),
                cls="admin-activity-cards-grid"
            ),
            cls="activity-period-section"
        ),
        
        # 30-day activity cards
        Div(
            H3("📅 Last 30 Days", cls="activity-period-title"),
            Div(
                AdminActivityCard("Active Users", activity_30d.get("users", 0), "fa-user-clock", "Users who logged in or joined"),
                AdminActivityCard("New Shelves", activity_30d.get("bookshelves", 0), "fa-plus-circle", "Bookshelves created"),
                AdminActivityCard("Books Added", activity_30d.get("books", 0), "fa-book-medical", "Books added to shelves"),
                AdminActivityCard("Comments", activity_30d.get("comments", 0), "fa-comment-dots", "Comments posted"),
                cls="admin-activity-cards-grid"
            ),
            cls="activity-period-section"
        ),
        
        cls="admin-activity-section",
        style="margin: 2rem 0; padding: 1.5rem; border: 1px solid #dee2e6; border-radius: 0.5rem; background: #f8f9fa;"
    )


def AdminActivityCard(title: str, value: int, icon: str, description: str):
    """A smaller card for displaying activity stats with descriptions."""
    return Div(
        Div(
            I(cls=f"fas {icon}"),
            cls="admin-activity-card-icon"
        ),
        Div(
            H4(str(value), cls="admin-activity-card-value"),
            P(title, cls="admin-activity-card-title"),
            P(description, cls="admin-activity-card-description"),
            cls="admin-activity-card-info"
        ),
        cls="admin-activity-card"
    )


def AdminDatabaseSection():
    """Section for database management in the admin dashboard."""
    return Div(
        H2("Database Management"),
        Card(
            DatabaseUploadForm(),
            BackupHistoryCard(),
            A("Download Backup", href="/admin/backup-database", cls="button primary"),
            cls="admin-card"
        ),
        cls="admin-database-section"
    )


def DatabaseUploadForm():
    """Form for uploading a new database file."""
    return Form(
        H3("Upload & Restore Database"),
        P("Replace the current database with a backup file. The current database will be backed up before replacement."),
        Input(type="file", name="db_file", id="db_file", required=True),
        Button("Upload & Restore", type="submit", cls="primary"),
        Div(id="upload-status"),
        hx_post="/admin/upload-database",
        hx_encoding="multipart/form-data",
        hx_target="#upload-status",
        hx_swap="innerHTML",
        cls="database-upload-form"
    )


def BackupHistoryCard():
    """Card to display database backup history."""
    return Div(
        H3("Backup History"),
        Button("Refresh Backups", hx_get="/admin/list-backups", hx_target="#backup-list", hx_swap="innerHTML"),
        Div(id="backup-list", hx_get="/admin/list-backups", hx_trigger="load", hx_swap="innerHTML"),
        cls="backup-history-card"
    )


def PerformanceDashboard(stats: Dict[str, Any]):
    """Performance monitoring dashboard component."""
    requests = stats.get('requests', {})
    queries = stats.get('queries', {})
    api_calls = stats.get('api_calls', {})
    period = stats.get('period_hours', 24)

    return Div(
        H1("Performance Monitor"),
        P(f"Metrics for the last {period} hours", cls="subtitle"),

        # Overview cards
        Div(
            PerformanceOverviewCard(
                "Requests",
                requests.get('total', 0),
                f"Avg: {requests.get('avg_ms', 0):.0f}ms",
                f"Slow: {requests.get('slow', 0)}",
                "fa-globe",
                "success" if requests.get('slow', 0) == 0 else "warning"
            ),
            PerformanceOverviewCard(
                "DB Queries",
                queries.get('total', 0),
                f"Avg: {queries.get('avg_ms', 0):.0f}ms",
                f"Slow: {queries.get('slow', 0)}",
                "fa-database",
                "success" if queries.get('slow', 0) == 0 else "warning"
            ),
            PerformanceOverviewCard(
                "API Calls",
                api_calls.get('total', 0),
                f"Avg: {api_calls.get('avg_ms', 0):.0f}ms",
                f"Errors: {api_calls.get('errors', 0)}",
                "fa-cloud",
                "success" if api_calls.get('errors', 0) == 0 else "danger"
            ),
            cls="performance-overview-grid",
            style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;"
        ),

        # Detailed sections loaded via HTMX
        Div(
            # Slowest Routes Section
            Section(
                H2("Slowest Routes"),
                Div(
                    "Loading...",
                    id="slowest-routes",
                    hx_get="/admin/performance/routes",
                    hx_trigger="load",
                    hx_swap="innerHTML"
                ),
                cls="performance-section"
            ),

            # Slowest Queries Section
            Section(
                H2("Slowest Queries"),
                Div(
                    "Loading...",
                    id="slowest-queries",
                    hx_get="/admin/performance/queries",
                    hx_trigger="load",
                    hx_swap="innerHTML"
                ),
                cls="performance-section"
            ),

            # External API Performance Section
            Section(
                H2("External API Performance"),
                Div(
                    "Loading...",
                    id="api-performance",
                    hx_get="/admin/performance/apis",
                    hx_trigger="load",
                    hx_swap="innerHTML"
                ),
                cls="performance-section"
            ),

            # Recent Slow Requests Section
            Section(
                H2("Recent Slow Requests"),
                Div(
                    "Loading...",
                    id="slow-requests",
                    hx_get="/admin/performance/slow-requests",
                    hx_trigger="load",
                    hx_swap="innerHTML"
                ),
                cls="performance-section"
            ),

            style="display: flex; flex-direction: column; gap: 2rem;"
        ),

        cls="performance-dashboard"
    )


def PerformanceOverviewCard(title: str, count: int, detail1: str, detail2: str, icon: str, status: str = "success"):
    """Card showing overview stats for performance section."""
    status_colors = {
        "success": "#28a745",
        "warning": "#ffc107",
        "danger": "#dc3545"
    }
    border_color = status_colors.get(status, "#dee2e6")

    return Div(
        Div(
            I(cls=f"fas {icon} fa-2x", style=f"color: {border_color};"),
            cls="performance-card-icon"
        ),
        Div(
            H3(f"{count:,}", cls="performance-card-value", style="margin: 0; font-size: 1.5rem;"),
            P(title, cls="performance-card-title", style="margin: 0.25rem 0; font-weight: 600;"),
            P(detail1, cls="performance-card-detail", style="margin: 0; font-size: 0.85rem; color: #6c757d;"),
            P(detail2, cls="performance-card-detail", style="margin: 0; font-size: 0.85rem; color: #6c757d;"),
            cls="performance-card-info"
        ),
        cls="performance-overview-card",
        style=f"border: 1px solid {border_color}; border-radius: 0.5rem; padding: 1rem; background: #fff; display: flex; align-items: center; gap: 1rem;"
    )


def PerformanceRouteTable(routes):
    """Table showing route performance metrics."""
    if not routes:
        return P("No request data available yet.", style="color: #6c757d; text-align: center; padding: 1rem;")

    rows = []
    for route in routes[:15]:
        avg_ms = route.get('avg_duration_ms', 0)
        # Color code based on response time
        if avg_ms > 1000:
            time_style = "color: #dc3545; font-weight: bold;"
        elif avg_ms > 500:
            time_style = "color: #ffc107; font-weight: bold;"
        else:
            time_style = "color: #28a745;"

        rows.append(Tr(
            Td(Code(route.get('method', 'GET')), style="width: 60px;"),
            Td(route.get('route', ''), style="font-family: monospace; font-size: 0.85rem;"),
            Td(f"{route.get('request_count', 0):,}", style="text-align: right;"),
            Td(f"{avg_ms:.0f}ms", style=f"text-align: right; {time_style}"),
            Td(f"{route.get('max_duration_ms', 0):.0f}ms", style="text-align: right;"),
            Td(f"{route.get('error_count', 0)}", style="text-align: right; color: #dc3545;" if route.get('error_count', 0) > 0 else "text-align: right;"),
        ))

    return Table(
        Thead(Tr(
            Th("Method"),
            Th("Route"),
            Th("Count", style="text-align: right;"),
            Th("Avg Time", style="text-align: right;"),
            Th("Max Time", style="text-align: right;"),
            Th("Errors", style="text-align: right;"),
        )),
        Tbody(*rows),
        cls="performance-table",
        style="width: 100%; border-collapse: collapse; font-size: 0.9rem;"
    )


def PerformanceQueryTable(queries):
    """Table showing query performance metrics."""
    if not queries:
        return P("No query data available yet.", style="color: #6c757d; text-align: center; padding: 1rem;")

    rows = []
    for query in queries[:15]:
        avg_ms = query.get('avg_duration_ms', 0)
        if avg_ms > 100:
            time_style = "color: #dc3545; font-weight: bold;"
        elif avg_ms > 50:
            time_style = "color: #ffc107; font-weight: bold;"
        else:
            time_style = "color: #28a745;"

        rows.append(Tr(
            Td(query.get('query_name', 'unknown'), style="font-family: monospace; font-size: 0.85rem;"),
            Td(f"{query.get('query_count', 0):,}", style="text-align: right;"),
            Td(f"{avg_ms:.1f}ms", style=f"text-align: right; {time_style}"),
            Td(f"{query.get('max_duration_ms', 0):.1f}ms", style="text-align: right;"),
            Td(f"{query.get('total_rows', 0):,}", style="text-align: right;"),
        ))

    return Table(
        Thead(Tr(
            Th("Query"),
            Th("Count", style="text-align: right;"),
            Th("Avg Time", style="text-align: right;"),
            Th("Max Time", style="text-align: right;"),
            Th("Total Rows", style="text-align: right;"),
        )),
        Tbody(*rows),
        cls="performance-table",
        style="width: 100%; border-collapse: collapse; font-size: 0.9rem;"
    )


def PerformanceApiTable(apis):
    """Table showing external API performance metrics."""
    if not apis:
        return P("No API call data available yet.", style="color: #6c757d; text-align: center; padding: 1rem;")

    rows = []
    for api in apis[:15]:
        avg_ms = api.get('avg_duration_ms', 0)
        error_rate = api.get('error_rate', 0)

        if avg_ms > 2000:
            time_style = "color: #dc3545; font-weight: bold;"
        elif avg_ms > 1000:
            time_style = "color: #ffc107; font-weight: bold;"
        else:
            time_style = "color: #28a745;"

        rows.append(Tr(
            Td(api.get('service', ''), style="font-weight: 600;"),
            Td(api.get('endpoint', ''), style="font-family: monospace; font-size: 0.85rem;"),
            Td(f"{api.get('call_count', 0):,}", style="text-align: right;"),
            Td(f"{avg_ms:.0f}ms", style=f"text-align: right; {time_style}"),
            Td(f"{api.get('error_count', 0)}", style="text-align: right; color: #dc3545;" if api.get('error_count', 0) > 0 else "text-align: right;"),
            Td(f"{error_rate:.1f}%", style="text-align: right; color: #dc3545;" if error_rate > 5 else "text-align: right;"),
        ))

    return Table(
        Thead(Tr(
            Th("Service"),
            Th("Endpoint"),
            Th("Calls", style="text-align: right;"),
            Th("Avg Time", style="text-align: right;"),
            Th("Errors", style="text-align: right;"),
            Th("Error Rate", style="text-align: right;"),
        )),
        Tbody(*rows),
        cls="performance-table",
        style="width: 100%; border-collapse: collapse; font-size: 0.9rem;"
    )


def SlowRequestsList(requests):
    """List of recent slow requests."""
    if not requests:
        return P("No slow requests in this period.", style="color: #28a745; text-align: center; padding: 1rem;")

    items = []
    for req in requests[:10]:
        duration = req.get('duration_ms', 0)
        items.append(
            Div(
                Div(
                    Code(f"{req.get('method', 'GET')} {req.get('route', '')}"),
                    Span(f"{duration:.0f}ms", style="color: #dc3545; font-weight: bold; margin-left: 1rem;"),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),
                Div(
                    Span(f"Status: {req.get('status_code', '-')}", style="margin-right: 1rem; font-size: 0.85rem; color: #6c757d;"),
                    Span(req.get('timestamp', ''), style="font-size: 0.85rem; color: #6c757d;"),
                    style="margin-top: 0.25rem;"
                ),
                style="padding: 0.75rem; border-bottom: 1px solid #dee2e6;"
            )
        )

    return Div(*items, style="border: 1px solid #dee2e6; border-radius: 0.5rem; background: #fff;")
