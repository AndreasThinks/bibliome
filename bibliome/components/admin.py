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
