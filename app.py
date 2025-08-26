"""Main FastHTML application for Bibliome."""

from fasthtml.common import *
from models import (
    setup_database, can_view_bookshelf, can_edit_bookshelf,
    get_public_shelves_with_stats, get_user_shelves, get_shelf_by_slug,
    get_public_shelves, get_recent_community_books
)
from api_clients import BookAPIClient
from components import (
    NavBar, LandingPageHero, FeaturesSection, CommunityReadingSection,
    HowItWorksSection, PublicShelvesPreview, UniversalFooter, NetworkActivityFeed,
    NetworkActivityPreview, BookshelfCard, EmptyState, CreateBookshelfForm, SearchPageHero,
    SearchForm, SearchResultsGrid, ExplorePageHero, PublicShelvesGrid,
    BookSearchForm, SearchResultCard, ShareInterface, InviteCard, MemberCard, AddBooksToggle,
    EnhancedEmptyState, ShelfHeader, ContactModal, ContactForm, ContactFormSuccess, ContactFormError
)
from meta_utils import create_homepage_meta_tags, create_explore_meta_tags, create_bookshelf_meta_tags, create_user_profile_meta_tags, get_sample_book_titles
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from auth import BlueskyAuth, get_current_user_did, auth_beforeware, is_admin, require_admin
from bluesky_automation import trigger_automation
from admin_operations import get_database_path, backup_database, upload_database
from process_monitor import init_process_monitoring, get_process_monitor

load_dotenv()

# Get log level from environment, default to INFO
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, log_level_str, logging.INFO)

# Set up logging
logging.basicConfig(
    level=level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bibliome.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Silence the noisy watchfiles logger
logging.getLogger('watchfiles.main').setLevel(logging.WARNING)

# Initialize database with fastmigrate
db_tables = setup_database()

# Initialize process monitoring
process_monitor = init_process_monitoring(db_tables)

# Initialize external services
bluesky_auth = BlueskyAuth()
book_api = BookAPIClient()


# Beforeware function that includes database tables
def before_handler(req, sess):
    return auth_beforeware(req, sess, db_tables)

# Initialize FastHTML app with persistent sessions
app, rt = fast_app(
    before=Beforeware(before_handler, skip=[r'/static/.*', r'/favicon\.ico']),
    htmlkw={'data-theme':'light'},
    # Session configuration for persistent login
    max_age=30*24*60*60,  # 30 days in seconds
    session_cookie='bibliome_session',
    same_site='lax',  # Good balance of security and functionality
    sess_https_only=False,  # Set to True in production with HTTPS
    hdrs=(
        picolink,
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap"),
        Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css"),
        Link(rel="stylesheet", href="/static/css/styles.css"),
        Script(src="https://unpkg.com/htmx.org@1.9.10")
    )
)

# Static file serving
@rt("/{fname:path}.{ext:static}")
def static_files(fname: str, ext: str):
    return FileResponse(f'static/{fname}.{ext}')

# Home page
@rt("/")
def index(auth, req):
    """Homepage - beautiful landing page for visitors, dashboard for logged-in users."""
    if not auth:
        # Show beautiful landing page for anonymous users
        public_shelves = get_public_shelves_with_stats(db_tables, limit=6)
        recent_books = get_recent_community_books(db_tables, limit=15)
        
        # Generate meta tags for homepage
        meta_tags = create_homepage_meta_tags(req)
        
        return (
            Title("Bibliome - Building the very best reading lists, together"),
            *meta_tags,
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            LandingPageHero(),
            FeaturesSection(),
            CommunityReadingSection(recent_books),
            HowItWorksSection(),
            PublicShelvesPreview(public_shelves),
            UniversalFooter()
        )
    else:
        # Show user's dashboard
        current_auth_did = get_current_user_did(auth)
        logger.debug(f"Loading dashboard for user DID: {current_auth_did}")
        user_shelves = get_user_shelves(current_auth_did, db_tables, limit=12)

        content = [
            Div(
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
            )
        ]
        
        # Add network activity preview with background loading
        from components import NetworkActivityPreviewLoading
        content.append(NetworkActivityPreviewLoading())
        
        # Add user's shelves with proper permission checking
        if user_shelves:
            shelf_cards = []
            for shelf in user_shelves:
                is_owner = getattr(shelf, 'user_relationship', 'owner') == 'owner'
                can_edit = can_edit_bookshelf(shelf, current_auth_did, db_tables)
                shelf_cards.append(BookshelfCard(shelf, is_owner=is_owner, can_edit=can_edit))
            content.append(Div(*shelf_cards, cls="bookshelf-grid"))
        else:
            content.append(EmptyState(
                "You haven't created any bookshelves yet",
                "Start building your first collection of books!",
                "Create Your First Shelf",
                "/shelf/new"
            ))
        
        # Generate meta tags for dashboard
        meta_tags = create_homepage_meta_tags(req)
        
        return (
            Title("Dashboard - Bibliome"),
            *meta_tags,
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )

# Admin route
@rt("/admin")
def admin_page(auth):
    """Admin dashboard page with enhanced progressive loading."""
    if not is_admin(auth):
        return RedirectResponse('/', status_code=303)
    
    from components import AdminDashboard, AdminDatabaseSection, AdminProcessSectionProgressive
    
    # Fast stats calculation using efficient COUNT queries
    try:
        # Use SQL COUNT queries instead of loading all records
        total_users = db_tables['db'].execute("SELECT COUNT(*) FROM user").fetchone()[0]
        total_bookshelves = db_tables['db'].execute("SELECT COUNT(*) FROM bookshelf").fetchone()[0]
        total_books = db_tables['db'].execute("SELECT COUNT(*) FROM book").fetchone()[0]
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        # Fallback to 0 if queries fail
        total_users = total_bookshelves = total_books = 0
    
    stats = {
        "total_users": total_users,
        "total_bookshelves": total_bookshelves,
        "total_books": total_books
    }
    
    # Process monitoring section with enhanced progressive loading
    process_section = AdminProcessSectionProgressive()
    
    return (
        Title("Admin Dashboard - Bibliome"),
        Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
        NavBar(auth),
        Container(AdminDashboard(stats), process_section, AdminDatabaseSection()),
        UniversalFooter()
    )

@rt("/admin/backup-database")
def download_db_backup(auth):
    """Route to trigger a database backup and download."""
    if not is_admin(auth):
        return RedirectResponse('/', status_code=303)
    
    try:
        db_path = get_database_path()
        backup_path = backup_database(db_path)
        return FileResponse(backup_path, media_type='application/octet-stream', filename=os.path.basename(backup_path))
    except Exception as e:
        return Div(f"Error creating backup: {e}", cls="alert alert-danger")

@rt("/admin/upload-database", methods=["POST"])
async def upload_db(auth, req):
    """Route to handle database file upload."""
    if not is_admin(auth):
        return Div("Permission denied.", cls="alert alert-danger")
    
    try:
        form = await req.form()
        db_file = form.get("db_file")
        if not db_file or not db_file.filename:
            return Div("No file selected.", cls="alert alert-warning")
        
        file_content = await db_file.read()
        db_path = get_database_path()
        upload_database(db_path, file_content)
        
        return Div("Database restored successfully. The application will now restart.", 
                   cls="alert-success", 
                   hx_trigger="load", 
                   hx_oob="true", 
                   hx_on_load="setTimeout(() => window.location.reload(), 2000)")

    except Exception as e:
        return Div(f"Error uploading database: {e}", cls="alert alert-danger")

@rt("/admin/list-backups")
def list_backups(auth):
    """HTMX route to list available database backups."""
    if not is_admin(auth):
        return ""
    
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return P("No backups found.")
    
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith(".bak")],
        reverse=True
    )
    
    if not backups:
        return P("No backups found.")
    
    return Ul(*[Li(A(backup, href=f"/admin/download-backup/{backup}")) for backup in backups])

@rt("/admin/download-backup/{backup_file:path}")
def download_backup_file(auth, backup_file: str):
    """Route to download a specific backup file."""
    if not is_admin(auth):
        return RedirectResponse('/', status_code=303)
    
    backup_path = os.path.join("backups", backup_file)
    if not os.path.exists(backup_path):
        return "File not found."
    
    return FileResponse(backup_path, media_type='application/octet-stream', filename=backup_file)

# Process monitoring admin routes
@rt("/admin/processes")
def admin_processes_page(auth):
    """Admin page for process monitoring."""
    if not is_admin(auth):
        return RedirectResponse('/', status_code=303)
    
    monitor = get_process_monitor(db_tables)
    all_processes = monitor.get_all_processes()
    
    # Process status cards
    process_cards = []
    for name, process_info in all_processes.items():
        status_color = {
            "running": "#28a745",
            "stopped": "#6c757d", 
            "starting": "#ffc107",
            "failed": "#dc3545"
        }.get(process_info.status.value, "#6c757d")
        
        # Calculate uptime if running and started_at exists
        uptime_display = "N/A"
        if process_info.started_at is not None and process_info.status.value == "running":
            try:
                # Handle both datetime objects and string representations
                if isinstance(process_info.started_at, str):
                    from datetime import datetime
                    started_at = datetime.fromisoformat(process_info.started_at.replace('Z', '+00:00'))
                else:
                    started_at = process_info.started_at
                
                uptime = datetime.now() - started_at
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                uptime_display = f"{hours}h {minutes}m"
            except (ValueError, TypeError) as e:
                uptime_display = "N/A"
        
        # Last heartbeat age
        heartbeat_display = "Never"
        heartbeat_color = "#dc3545"
        if process_info.last_heartbeat:
            try:
                # Handle both datetime objects and string representations
                if isinstance(process_info.last_heartbeat, str):
                    last_heartbeat = datetime.fromisoformat(process_info.last_heartbeat.replace('Z', '+00:00'))
                else:
                    last_heartbeat = process_info.last_heartbeat
                
                heartbeat_age = datetime.now() - last_heartbeat
                
                if heartbeat_age.total_seconds() < 300:  # 5 minutes
                    heartbeat_display = "< 5m ago"
                    heartbeat_color = "#28a745"
                elif heartbeat_age.total_seconds() < 1800:  # 30 minutes
                    heartbeat_display = f"{int(heartbeat_age.total_seconds() / 60)}m ago"
                    heartbeat_color = "#ffc107"
                else:
                    heartbeat_display = f"{int(heartbeat_age.total_seconds() / 3600)}h ago"
                    heartbeat_color = "#dc3545"
            except (ValueError, TypeError) as e:
                heartbeat_display = "Invalid"
                heartbeat_color = "#dc3545"
        
        process_cards.append(
            Div(
                H3(name.replace('_', ' ').title()),
                P(f"Type: {process_info.process_type}"),
                P(f"Status: ", Span(process_info.status.value.title(), style=f"color: {status_color}; font-weight: bold;")),
                P(f"PID: {process_info.pid or 'N/A'}"),
                P(f"Uptime: {uptime_display}"),
                P(f"Last Heartbeat: ", Span(heartbeat_display, style=f"color: {heartbeat_color}; font-weight: bold;")),
                P(f"Restart Count: {process_info.restart_count}"),
                process_info.error_message and P(f"Error: {process_info.error_message}", style="color: #dc3545;") or "",
                cls="card",
                style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem;"
            )
        )
    
    content = [
        H1("Process Monitoring"),
        P("Monitor the health and status of background processes."),
        Div(*process_cards),
        Div(
            H2("Quick Actions"),
            Div(
                Button("Refresh Status", 
                       hx_get="/admin/processes/refresh",
                       hx_target="body",
                       hx_swap="outerHTML",
                       cls="btn btn-primary"),
                style="margin: 1rem 0;"
            )
        )
    ]
    
    return (
        Title("Process Monitoring - Admin - Bibliome"),
        Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
        NavBar(auth),
        Container(*content),
        UniversalFooter()
    )


@rt("/api/admin/process-status")
def admin_process_status_api(auth):
    """HTMX endpoint to load process status asynchronously with optimized performance."""
    if not is_admin(auth):
        return ""
    
    try:
        # Get process monitoring data
        monitor = get_process_monitor(db_tables)
        all_processes = monitor.get_all_processes()
        
        # Build optimized process status cards
        process_summary_cards = []
        current_time = datetime.now()
        
        for name, process_info in all_processes.items():
            status_color = {
                "running": "#28a745",
                "stopped": "#6c757d", 
                "starting": "#ffc107",
                "failed": "#dc3545"
            }.get(process_info.status.value, "#6c757d")
            
            # Optimized heartbeat age calculation
            heartbeat_display = "Never"
            heartbeat_color = "#dc3545"
            if process_info.last_heartbeat:
                try:
                    # Handle both datetime objects and string representations
                    if isinstance(process_info.last_heartbeat, str):
                        last_heartbeat = datetime.fromisoformat(process_info.last_heartbeat.replace('Z', '+00:00'))
                    else:
                        last_heartbeat = process_info.last_heartbeat
                    
                    # Remove timezone for consistent comparison
                    if last_heartbeat.tzinfo is not None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=None)
                    
                    heartbeat_age = current_time - last_heartbeat
                    age_seconds = heartbeat_age.total_seconds()
                    
                    if age_seconds < 300:  # 5 minutes
                        heartbeat_display = "< 5m ago"
                        heartbeat_color = "#28a745"
                    elif age_seconds < 1800:  # 30 minutes
                        heartbeat_display = f"{int(age_seconds / 60)}m ago"
                        heartbeat_color = "#ffc107"
                    else:
                        heartbeat_display = f"{int(age_seconds / 3600)}h ago"
                        heartbeat_color = "#dc3545"
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing heartbeat time for {name}: {e}")
                    heartbeat_display = "Invalid"
                    heartbeat_color = "#dc3545"
            
            process_summary_cards.append(
                Div(
                    Div(
                        H4(name.replace('_', ' ').title(), style="margin: 0 0 0.5rem 0;"),
                        P(f"Status: ", Span(process_info.status.value.title(), style=f"color: {status_color}; font-weight: bold;")),
                        P(f"PID: {process_info.pid or 'N/A'}"),
                        P(f"Heartbeat: ", Span(heartbeat_display, style=f"color: {heartbeat_color}; font-weight: bold;")),
                        process_info.error_message and P(f"Error: {process_info.error_message}", style="color: #dc3545; font-size: 0.85rem;") or "",
                    ),
                    cls="admin-process-card",
                    style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1rem; background: #f8f9fa;"
                )
            )
        
        # Return the complete process monitoring section
        return Div(
            *process_summary_cards,
            style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin: 1rem 0;"
        ), Div(
            A("Full Process Monitor", href="/admin/processes", cls="btn btn-primary"),
            style="text-align: center; margin-top: 1rem;"
        )
        
    except Exception as e:
        logger.error(f"Error loading admin process status: {e}", exc_info=True)
        return Div(
            P("Error loading process status. Please refresh the page.", cls="error-text"),
            Button(
                "Retry",
                hx_get="/api/admin/process-status",
                hx_target="#process-section",
                hx_swap="innerHTML",
                cls="retry-btn secondary"
            ),
            style="display: flex; flex-direction: column; align-items: center; padding: 2rem;"
        )

@rt("/api/admin/process-status-progressive")
def admin_process_status_progressive_api(auth):
    """Enhanced HTMX endpoint for progressive loading of process status with improved error handling."""
    if not is_admin(auth):
        return ""
    
    try:
        # Get process monitoring data with enhanced error handling
        monitor = get_process_monitor(db_tables)
        all_processes = monitor.get_all_processes()
        
        # Build optimized process status cards with enhanced formatting
        process_summary_cards = []
        current_time = datetime.now()
        
        for name, process_info in all_processes.items():
            status_color = {
                "running": "#28a745",
                "stopped": "#6c757d", 
                "starting": "#ffc107",
                "failed": "#dc3545"
            }.get(process_info.status.value, "#6c757d")
            
            # Enhanced heartbeat age calculation with better error handling
            heartbeat_display = "Never"
            heartbeat_color = "#dc3545"
            if process_info.last_heartbeat:
                try:
                    # Handle both datetime objects and string representations
                    if isinstance(process_info.last_heartbeat, str):
                        last_heartbeat = datetime.fromisoformat(process_info.last_heartbeat.replace('Z', '+00:00'))
                    else:
                        last_heartbeat = process_info.last_heartbeat
                    
                    # Remove timezone for consistent comparison
                    if last_heartbeat.tzinfo is not None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=None)
                    
                    heartbeat_age = current_time - last_heartbeat
                    age_seconds = heartbeat_age.total_seconds()
                    
                    if age_seconds < 300:  # 5 minutes
                        heartbeat_display = "< 5m ago"
                        heartbeat_color = "#28a745"
                    elif age_seconds < 1800:  # 30 minutes
                        heartbeat_display = f"{int(age_seconds / 60)}m ago"
                        heartbeat_color = "#ffc107"
                    else:
                        heartbeat_display = f"{int(age_seconds / 3600)}h ago"
                        heartbeat_color = "#dc3545"
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing heartbeat time for {name}: {e}")
                    heartbeat_display = "Parse Error"
                    heartbeat_color = "#dc3545"
            
            # Enhanced status display with more information
            process_summary_cards.append(
                Div(
                    Div(
                        H4(name.replace('_', ' ').title(), style="margin: 0 0 0.5rem 0;"),
                        P(f"Status: ", Span(process_info.status.value.title(), style=f"color: {status_color}; font-weight: bold;")),
                        P(f"PID: {process_info.pid or 'N/A'}"),
                        P(f"Type: {process_info.process_type}"),
                        P(f"Heartbeat: ", Span(heartbeat_display, style=f"color: {heartbeat_color}; font-weight: bold;")),
                        P(f"Restarts: {process_info.restart_count}"),
                        process_info.error_message and P(f"Error: {process_info.error_message}", style="color: #dc3545; font-size: 0.85rem; margin-top: 0.5rem;") or "",
                    ),
                    cls="admin-process-card",
                    style="border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1rem; background: #f8f9fa;"
                )
            )
        
        # Return enhanced process monitoring section with additional controls
        return Section(
            H2("Background Processes"),
            P("Monitor the health of background services and system processes..."),
            Div(
                *process_summary_cards,
                style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin: 1rem 0;"
            ),
            Div(
                A("Full Process Monitor", href="/admin/processes", cls="btn btn-primary"),
                Button(
                    "Refresh",
                    hx_get="/api/admin/process-status-progressive",
                    hx_target="#process-loading-container",
                    hx_swap="outerHTML",
                    cls="btn secondary",
                    style="margin-left: 0.5rem;"
                ),
                style="text-align: center; margin-top: 1rem; display: flex; justify-content: center; gap: 0.5rem;"
            ),
            style="margin: 2rem 0;"
        )
        
    except Exception as e:
        logger.error(f"Error loading progressive admin process status: {e}", exc_info=True)
        
        # Enhanced fallback content for the progressive loading system
        from components import AdminProcessSectionFallback
        return AdminProcessSectionFallback()

@rt("/admin/processes/refresh")
def admin_processes_refresh(auth):
    """HTMX endpoint to refresh process status."""
    if not is_admin(auth):
        return RedirectResponse('/', status_code=303)
    
    return RedirectResponse('/admin/processes', status_code=303)

# Authentication routes
@app.get("/auth/login")
def login_page(sess):
    """Display login form."""
    error_msg = sess.pop('error', None)
    return bluesky_auth.create_login_form(error_msg)

@app.post("/auth/login")
async def login_handler(handle: str, password: str, sess):
    """Handle login form submission."""
    logger.info(f"Login attempt for handle: {handle}")
    
    user_data = await bluesky_auth.authenticate_user(handle, password)
    
    if user_data:
        logger.info(f"Authentication successful for user: {user_data['handle']}")
        
        # Prepare database data (exclude JWT fields)
        db_user_data = {
            'did': user_data['did'],
            'handle': user_data['handle'],
            'display_name': user_data['display_name'],
            'avatar_url': user_data['avatar_url'],
            'created_at': datetime.now(),
            'last_login': datetime.now()
        }
        
        # Store user in database - check if user exists first to avoid constraint errors
        try:
            existing_user = db_tables['users'][user_data['did']]
            # User exists, update their info and last login
            update_data = {
                'handle': user_data['handle'],
                'display_name': user_data['display_name'],
                'avatar_url': user_data['avatar_url'],
                'last_login': datetime.now()
            }
            db_tables['users'].update(update_data, user_data['did'])
            logger.debug(f"Existing user updated in database: {user_data['handle']}")
        except (IndexError, Exception):
            # User doesn't exist, create them
            # Note: FastLite can throw different exceptions when records aren't found
            db_tables['users'].insert(**db_user_data)
            logger.info(f"New user created in database: {user_data['handle']}")
        
        # Store full auth data (including JWTs) in session
        sess['auth'] = user_data
        
        # Check for pending redirect (like invite links)
        next_url = sess.pop('next_url', None)
        if next_url:
            logger.info(f"Redirecting user {user_data['handle']} to pending URL: {next_url}")
            return RedirectResponse(next_url, status_code=303)
        else:
            return RedirectResponse('/', status_code=303)
    else:
        logger.warning(f"Authentication failed for handle: {handle}")
        sess['error'] = "Invalid handle or app password. Please check your credentials and try again."
        return RedirectResponse('/auth/login', status_code=303)

@rt("/auth/logout")
def logout_handler(sess):
    """Handle logout."""
    sess.clear()
    return RedirectResponse('/', status_code=303)

# Bookshelf routes
@rt("/shelf/new")
def new_shelf_page(auth):
    """Display create bookshelf form."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    return (
        Title("Create New Bookshelf - Bibliome"),
        Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
        NavBar(auth),
        Container(CreateBookshelfForm()),
        UniversalFooter()
    )

@rt("/shelf/create", methods=["POST"])
def create_shelf(name: str, description: str, privacy: str, auth, sess, self_join: bool = False):
    """Handle bookshelf creation."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    atproto_uri = None
    try:
        from models import Bookshelf, generate_slug, create_bookshelf_record
        from datetime import datetime
        
        try:
            client = bluesky_auth.get_client_from_session(auth)
            # 1. Write to AT Protocol
            atproto_uri = create_bookshelf_record(client, name, description, privacy)
        except Exception as e:
            logger.error(f"Failed to write bookshelf to AT Protocol: {e}", exc_info=True)
            # Don't fail the whole request, just log the error and continue
        
        # 2. Write to local DB
        shelf = Bookshelf(
            name=name.strip(),
            slug=generate_slug(),
            description=description.strip(),
            owner_did=auth['did'],
            privacy=privacy,
            self_join=self_join,
            atproto_uri=atproto_uri, # Store the canonical URI
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        created_shelf = db_tables['bookshelves'].insert(shelf)
        
        # Log activity for social feed
        try:
            from models import log_activity
            log_activity(auth['did'], 'bookshelf_created', db_tables, bookshelf_id=created_shelf.id)
        except Exception as e:
            logger.warning(f"Could not log bookshelf creation activity: {e}")
        
        return RedirectResponse(f'/shelf/{created_shelf.slug}', status_code=303)
    except Exception as e:
        sess['error'] = f"Error creating bookshelf: {str(e)}"
        return RedirectResponse('/shelf/new', status_code=303)


@rt("/explore")
def explore_page(auth, req, query: str = "", privacy: str = "public", sort_by: str = "smart_mix", page: int = 1, open_to_contributions: str = "", book_title: str = "", book_author: str = "", book_isbn: str = ""):
    """Unified explore page - simple discovery for anonymous users, enhanced search for logged-in users."""
    from models import search_shelves_enhanced, get_mixed_public_shelves
    from components import UnifiedExploreHero, ExploreSearchForm, SearchResultsGrid
    
    page = int(page)
    limit = 12
    offset = (page - 1) * limit
    viewer_did = get_current_user_did(auth)
    
    # Convert open_to_contributions string to boolean or None
    open_to_contributions_filter = None
    if open_to_contributions == "true":
        open_to_contributions_filter = True
    elif open_to_contributions == "false":
        open_to_contributions_filter = False
    
    if auth:
        # Logged-in users get enhanced explore with search functionality
        if query or sort_by != "smart_mix" or open_to_contributions or book_title or book_author or book_isbn:
            # User is actively searching/filtering - use enhanced search
            shelves = search_shelves_enhanced(
                db_tables,
                query=query,
                book_title=book_title,
                book_author=book_author,
                book_isbn=book_isbn,
                privacy=privacy,
                sort_by=sort_by,
                limit=limit,
                offset=offset,
                open_to_contributions=open_to_contributions_filter
            )
        else:
            # Default view - show smart mix of active and newest shelves
            shelves = get_mixed_public_shelves(db_tables, limit=limit, offset=offset)
        
        # Build content for logged-in users
        content = [
            UnifiedExploreHero(auth=auth),
            ExploreSearchForm(
                query=query,
                privacy=privacy,
                sort_by=sort_by,
                open_to_contributions=open_to_contributions,
                book_title=book_title,
                book_author=book_author,
                book_isbn=book_isbn
            ),
            SearchResultsGrid(
                shelves,
                users=[],  # No user search in explore page
                search_type="shelves",
                page=page,
                query=query,
                privacy=privacy,
                sort_by=sort_by,
                open_to_contributions=open_to_contributions
            )
        ]
    else:
        # Anonymous users get simple discovery experience
        if query:
            # Anonymous users can still search, but with limited functionality
            from models import search_shelves
            shelves = search_shelves(
                db_tables,
                query=query,
                privacy="public",  # Force public for anonymous users
                sort_by="updated_at",
                limit=limit,
                offset=offset
            )
        else:
            # Default view for anonymous users - mixed public shelves
            shelves = get_mixed_public_shelves(db_tables, limit=limit, offset=offset)
        
        # Simple search form for anonymous users (just a search box)
        simple_search = Form(
            Div(
                Input(
                    name="query",
                    type="search",
                    placeholder="Search public bookshelves...",
                    value=query,
                    cls="explore-search-input"
                ),
                Button("🔍 Search", type="submit", cls="explore-search-btn primary"),
                cls="simple-search-row"
            ),
            action="/explore",
            method="get",
            cls="simple-explore-search-form"
        )
        
        content = [
            UnifiedExploreHero(auth=None),
            simple_search,
            PublicShelvesGrid(shelves, page=page, total_pages=1)  # Simplified pagination for anonymous users
        ]
    
    # Generate meta tags for explore page
    meta_tags = create_explore_meta_tags(req)
    
    return (
        Title("Explore - Bibliome"),
        *meta_tags,
        Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
        NavBar(auth),
        Container(*content),
        UniversalFooter()
    )

# Redirect /search to /explore
@rt("/search")
def search_redirect(query: str = "", privacy: str = "public", sort_by: str = "smart_mix", open_to_contributions: str = "", book_title: str = "", book_author: str = "", book_isbn: str = ""):
    """Redirect /search to /explore with query parameters preserved."""
    from urllib.parse import urlencode
    
    # Collect all query parameters into a dictionary
    params = {
        "query": query,
        "privacy": privacy,
        "sort_by": sort_by,
        "open_to_contributions": open_to_contributions,
        "book_title": book_title,
        "book_author": book_author,
        "book_isbn": book_isbn
    }
    
    # Filter out empty values
    filtered_params = {k: v for k, v in params.items() if v}
    
    # Build query string
    query_string = urlencode(filtered_params)
    redirect_url = f"/explore?{query_string}" if query_string else "/explore"
    
    return RedirectResponse(redirect_url, status_code=301)  # Permanent redirect

@rt("/network")
def network_page(auth, activity_type: str = "all", date_filter: str = "all", page: int = 1):
    """Display the full network activity page with filtering and pagination."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        from models import get_network_activity, get_network_activity_count
        from components import NetworkPageHero, NetworkActivityFilters, FullNetworkActivityFeed, EmptyNetworkStateFullPage
        
        # Pagination settings
        limit = 20
        offset = (page - 1) * limit
        
        # Get network activities with filtering
        logger.info(f"Loading network activity for user: {auth.get('handle')} with filters: type={activity_type}, date={date_filter}, page={page}")
        network_activities = get_network_activity(
            auth, db_tables, bluesky_auth, 
            limit=limit, offset=offset, 
            activity_type=activity_type, date_filter=date_filter
        )
        
        # Get total count for pagination
        total_count = get_network_activity_count(
            auth, db_tables, bluesky_auth,
            activity_type=activity_type, date_filter=date_filter
        )
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
        
        logger.info(f"Network activities loaded: {len(network_activities)} activities found, {total_count} total")
        
        # Build page content
        content = [
            NetworkPageHero(),
            NetworkActivityFilters(activity_type=activity_type, date_filter=date_filter),
            FullNetworkActivityFeed(
                network_activities, 
                page=page, 
                total_pages=total_pages,
                activity_type=activity_type,
                date_filter=date_filter
            ) if network_activities else EmptyNetworkStateFullPage()
        ]
        
        return (
            Title("Your Network - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )
        
    except Exception as e:
        logger.error(f"Error loading network page: {e}", exc_info=True)
        # Show empty state even if there's an error
        content = [
            NetworkPageHero(),
            NetworkActivityFilters(activity_type=activity_type, date_filter=date_filter),
            EmptyNetworkStateFullPage()
        ]
        
        return (
            Title("Your Network - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )

@rt("/user/{handle}")
def user_profile(handle: str, auth, req):
    """Display a user's profile page."""
    try:
        from models import get_user_by_handle, get_user_public_shelves, get_user_activity
        from components import UserProfileHeader, UserPublicShelves, UserActivityFeed
        
        # Get user by handle
        user = get_user_by_handle(handle, db_tables)
        if not user:
            return NavBar(auth), Container(
                H1("User Not Found"),
                P(f"The user @{handle} doesn't exist or hasn't joined Bibliome yet."),
                A("← Back to Home", href="/")
            )
        
        # Check if this is the user's own profile
        viewer_did = get_current_user_did(auth)
        is_own_profile = viewer_did == user.did
        
        # If it's their own profile, redirect to dashboard
        if is_own_profile:
            return RedirectResponse('/', status_code=303)
        
        # Get user's public content (filtered based on viewer permissions)
        public_shelves = get_user_public_shelves(user.did, db_tables, viewer_did=viewer_did, limit=12)
        user_activities = get_user_activity(user.did, db_tables, viewer_did=viewer_did, limit=15)
        
        # Generate meta tags for user profile
        shelf_count = len(public_shelves)
        meta_tags = create_user_profile_meta_tags(user, req, shelf_count=shelf_count)
        
        # Build page content
        content = [
            UserProfileHeader(user, is_own_profile=is_own_profile, public_shelves_count=len(public_shelves)),
            UserPublicShelves(public_shelves, user.handle),
            UserActivityFeed(user_activities, user.handle, viewer_is_logged_in=bool(viewer_did))
        ]
        
        return (
            Title(f"@{user.handle} - Bibliome"),
            *meta_tags,
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )
        
    except Exception as e:
        logger.error(f"Error loading user profile for {handle}: {e}", exc_info=True)
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            ),
            UniversalFooter()
        )

@rt("/shelf/{slug}")
def view_shelf(slug: str, auth, req, view: str = "grid"):
    """Display a bookshelf."""
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return NavBar(auth), Container(
                H1("Bookshelf Not Found"),
                P("The bookshelf you're looking for doesn't exist."),
                A("← Back to Home", href="/")
            )
        
        # Check permissions
        user_did = get_current_user_did(auth)
        if not can_view_bookshelf(shelf, user_did, db_tables):
            return NavBar(auth), Container(
                H1("Access Denied"),
                P("This bookshelf is private and you don't have permission to view it."),
                A("← Back to Home", href="/")
            )
        
        # Import the new permission functions
        from models import (can_add_books, can_vote_books, can_remove_books, 
                           can_edit_bookshelf, can_manage_members, can_generate_invites)
        
        can_add = can_add_books(shelf, user_did, db_tables)
        can_vote = can_vote_books(shelf, user_did, db_tables)
        can_remove = can_remove_books(shelf, user_did, db_tables)
        can_edit = can_edit_bookshelf(shelf, user_did, db_tables)
        can_manage = can_manage_members(shelf, user_did, db_tables)
        can_share = can_generate_invites(shelf, user_did, db_tables)
        
        # Get creator information
        creator = None
        try:
            creator = db_tables['users'][shelf.owner_did]
        except Exception as e:
            logger.debug(f"Could not find creator for shelf {shelf.slug}: {e}")
        
        # Get books with upvote counts using the new helper function
        from models import get_books_with_upvotes
        shelf_books = get_books_with_upvotes(shelf.id, user_did, db_tables)
        
        # Generate meta tags for bookshelf with dynamic content
        book_count = len(shelf_books)
        sample_books = get_sample_book_titles(shelf_books, max_titles=3)
        meta_tags = create_bookshelf_meta_tags(shelf, req, book_count=book_count, sample_books=sample_books)
        
        # Determine user authentication status
        user_auth_status = "anonymous" if not auth else "logged_in"
        
        # Build action buttons
        action_buttons = []
        if can_edit or can_share:
            action_buttons.append(A("Manage", href=f"/shelf/{shelf.slug}/manage", cls="secondary"))
        
        # New Shelf Header with view toggle and share button
        shelf_header = ShelfHeader(shelf, action_buttons, current_view=view, can_share=can_share, user_is_logged_in=bool(auth), creator=creator)
        
        # Show self-join button if applicable (logged in user, public shelf with self-join enabled, not already a member)
        self_join_section = None
        if (auth and shelf.privacy == 'public' and shelf.self_join and user_did and 
            not can_add and shelf.owner_did != user_did):
            # Check if user is already a member
            existing_permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, user_did))
            if not existing_permission:
                from components import SelfJoinButton
                self_join_section = Section(SelfJoinButton(shelf.slug), cls="self-join-section")
        
        # Show book search form if user can add books
        add_books_section = Section(AddBooksToggle(shelf.id), cls="add-books-section") if can_add else None
        
        # Always create a books-container div with book-grid inside for consistent HTMX targeting
        if shelf_books:
            if view == "list":
                from components import BookListView
                books_content = BookListView(shelf_books, can_upvote=can_vote, can_remove=can_remove, user_auth_status=user_auth_status)
            else:  # grid view (default)
                books_content = Div(*[book.as_interactive_card(
                    can_upvote=can_vote, 
                    user_has_upvoted=book.user_has_upvoted,
                    upvote_count=book.upvote_count,
                    can_remove=can_remove,
                    user_auth_status=user_auth_status
                ) for book in shelf_books], cls="book-grid", id="book-grid")
            
            books_section = Section(
                Div(books_content, id="books-container"),
                cls=f"books-section {view}-view",
                id="books-section"
            )
        else:
            books_section = Section(
                Div(
                    EnhancedEmptyState(can_add=can_add, shelf_id=shelf.id, user_auth_status=user_auth_status),
                    # Always include an empty book-grid div for HTMX targeting
                    Div(id="book-grid", cls="book-grid"),
                    id="books-container"
                ),
                cls=f"books-section {view}-view",
                id="books-section"
            )
        
        content = [
            shelf_header,
            self_join_section,
            add_books_section,
            books_section,
            # Share modal container
            Div(id="share-modal-container")
        ]
        
        # Add JavaScript for book removal confirmation if user can remove books
        if can_remove:
            content.append(
                Script("""
                function confirmRemoveBook(bookId, bookTitle, voteCount) {
                    let message = `Are you sure you want to remove "${bookTitle}" from this shelf?`;
                    if (voteCount > 1) {
                        message += `\n\nThis book has ${voteCount} votes and will be permanently removed for all users.`;
                    }
                    
                    if (confirm(message)) {
                        // Use HTMX to make the removal request
                        htmx.ajax('POST', `/book/${bookId}/remove`, {
                            target: `#book-${bookId}`,
                            swap: 'outerHTML'
                        });
                    }
                }
                """)
            )
        
        # Add JavaScript for share functionality
        content.append(
            Script("""
            // Copy to clipboard functionality
            async function copyToClipboard(text, buttonElement) {
                try {
                    await navigator.clipboard.writeText(text);
                    
                    // Update button to show success
                    const originalText = buttonElement.innerHTML;
                    buttonElement.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    buttonElement.classList.add('copied');
                    
                    // Reset after 2 seconds
                    setTimeout(() => {
                        buttonElement.innerHTML = originalText;
                        buttonElement.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy text: ', err);
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = text;
                    document.body.appendChild(textArea);
                    textArea.select();
                    try {
                        document.execCommand('copy');
                        const originalText = buttonElement.innerHTML;
                        buttonElement.innerHTML = '<i class="fas fa-check"></i> Copied!';
                        buttonElement.classList.add('copied');
                        setTimeout(() => {
                            buttonElement.innerHTML = originalText;
                            buttonElement.classList.remove('copied');
                        }, 2000);
                    } catch (fallbackErr) {
                        console.error('Fallback copy failed: ', fallbackErr);
                        alert('Copy failed. Please copy the text manually.');
                    }
                    document.body.removeChild(textArea);
                }
            }
            
            // Close modal when clicking outside
            document.addEventListener('click', function(event) {
                const modal = document.querySelector('.share-modal-overlay');
                if (modal && event.target === modal) {
                    htmx.ajax('GET', `/api/shelf/${slug}/close-share-modal`, {
                        target: '#share-modal-container',
                        swap: 'innerHTML'
                    });
                }
            });
            """)
        )
        
        return (
            Title(f"{shelf.name} - Bibliome"),
            *meta_tags,
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            ),
            UniversalFooter()
        )

# API routes for HTMX
@rt("/api/search-books", methods=["POST"])
async def search_books_api(query: str, bookshelf_id: int, auth):
    """HTMX endpoint for book search."""
    if not auth:
        return Div("Authentication required.", cls="search-message")
    
    # If query is empty, clear results
    if not query.strip():
        return Div("", cls="search-results-list")
    
    try:
        # Check if user can add books to this bookshelf
        shelf = db_tables['bookshelves'][bookshelf_id]
        user_did = get_current_user_did(auth)
        from models import can_add_books
        if not can_add_books(shelf, user_did, db_tables):
            return Div("You don't have permission to add books to this shelf.", cls="search-message")
        
        logger.info(f"Book search request: '{query.strip()}' for shelf {bookshelf_id}")
        results = await book_api.search_books(query.strip(), max_results=8)
        
        if results:
            logger.debug(f"Book search returned {len(results)} results")
            return Div(
                *[SearchResultCard(book, bookshelf_id) for book in results],
                cls="search-results-list"
            )
        else:
            logger.debug(f"No books found for query: '{query.strip()}'")
            return Div(
                P("No books found. Try a different search term."),
                P("Tips:", style="margin-top: 1rem; font-weight: bold;"),
                Ul(
                    Li("Try searching by book title"),
                    Li("Use fewer words for broader results"),
                    Li("Check spelling of author or title names")
                ),
                cls="search-message"
            )
            
    except Exception as e:
        logger.error(f"Book search error for query '{query.strip()}': {e}", exc_info=True)
        return Div(f"Search error: {str(e)}", cls="search-message")

@rt("/api/add-book", methods=["POST"])
def add_book_api(bookshelf_id: int, title: str, author: str, isbn: str, description: str, 
                cover_url: str, publisher: str, published_date: str, page_count: int, auth):
    """HTMX endpoint to add a book to a bookshelf."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        from models import Book, Upvote, add_book_record, can_add_books
        # Check permissions - use can_add_books instead of can_edit_bookshelf
        shelf = db_tables['bookshelves'][bookshelf_id]
        user_did = get_current_user_did(auth)

        if not can_add_books(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        user_did = auth['did']
        
        # Check if book already exists on this shelf (by ISBN first, then by title+author)
        existing_book = None
        if isbn and isbn.strip():
            # Try to find by ISBN first
            existing_books = list(db_tables['books']("bookshelf_id=? AND isbn=?", (bookshelf_id, isbn.strip())))
            if existing_books:
                existing_book = existing_books[0]
        
        if not existing_book:
            # Try to find by title and author combination
            existing_books = list(db_tables['books']("bookshelf_id=? AND title=? AND author=?", 
                                                   (bookshelf_id, title.strip(), author.strip())))
            if existing_books:
                existing_book = existing_books[0]
        
        if existing_book:
            # Book already exists - check if user has already voted
            existing_upvote = None
            try:
                existing_upvote = db_tables['upvotes']("book_id=? AND user_did=?", 
                                                     (existing_book.id, user_did))[0]
            except:
                pass
            
            if existing_upvote:
                # User has already voted for this book
                return Div("You've already added this book to the shelf!", cls="alert alert-info")
            else:
                # Add user's vote to existing book
                upvote = Upvote(
                    book_id=existing_book.id,
                    user_did=user_did,
                    created_at=datetime.now()
                )
                db_tables['upvotes'].insert(upvote)
                
                # Get updated book with vote count and return it
                existing_book.upvote_count = len(db_tables['upvotes']("book_id=?", (existing_book.id,)))
                existing_book.user_has_upvoted = True
                return existing_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=existing_book.upvote_count)
        else:
            atproto_uri = None
            try:
                client = bluesky_auth.get_client_from_session(auth)
                # 1. Write to AT Protocol
                atproto_uri = add_book_record(client, shelf.atproto_uri, title, author, isbn)
            except Exception as e:
                logger.error(f"Failed to write book to AT Protocol: {e}", exc_info=True)
                # Don't fail the whole request, just log the error and continue

            # 2. Write to local DB
            book = Book(
                bookshelf_id=bookshelf_id,
                isbn=isbn,
                title=title,
                author=author,
                cover_url=cover_url,
                description=description,
                publisher=publisher,
                published_date=published_date,
                page_count=page_count,
                atproto_uri=atproto_uri,
                added_by_did=user_did,
                added_at=datetime.now()
            )
            
            created_book = db_tables['books'].insert(book)
            
            # Create the initial upvote record from the person who added the book
            upvote = Upvote(
                book_id=created_book.id,
                user_did=user_did,
                created_at=datetime.now()
            )
            db_tables['upvotes'].insert(upvote)
            
            # Log activity for social feed
            try:
                from models import log_activity
                log_activity(user_did, 'book_added', db_tables, bookshelf_id=bookshelf_id, book_id=created_book.id)
            except Exception as e:
                logger.warning(f"Could not log book addition activity: {e}")

            # Trigger automation if threshold is met
            try:
                from models import get_book_count_for_shelf
                book_count = get_book_count_for_shelf(bookshelf_id, db_tables)
                
                # Define post_threshold here or get from a config
                post_threshold = int(os.getenv('BLUESKY_POST_THRESHOLD', 3))

                if book_count == post_threshold:
                    base_url = f"http://{os.getenv('HOST', 'localhost')}:{os.getenv('PORT', 5001)}"
                    shelf_url = f"{base_url}/shelf/{shelf.slug}"
                    context = {
                        'shelf_name': shelf.name,
                        'book_count': book_count,
                        'shelf_url': shelf_url
                    }
                    trigger_automation('shelf_threshold_reached', context)
            except Exception as e:
                logger.error(f"Error triggering automation for shelf {bookshelf_id}: {e}", exc_info=True)
            
            # Set the computed attributes and return the book card
            created_book.upvote_count = 1
            created_book.user_has_upvoted = True
            return created_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=1)
        
    except Exception as e:
        return Div(f"Error adding book: {str(e)}", cls="error")

@rt("/api/add-book-and-close", methods=["POST"])
def add_book_and_close_api(bookshelf_id: int, title: str, author: str, isbn: str, description: str, 
                          cover_url: str, publisher: str, published_date: str, page_count: int, auth):
    """HTMX endpoint to add a book to a bookshelf and close the add books interface."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        from models import Book, Upvote, add_book_record, can_add_books
        from components import AddBooksToggle
        
        # Check permissions
        shelf = db_tables['bookshelves'][bookshelf_id]
        user_did = get_current_user_did(auth)

        if not can_add_books(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        user_did = auth['did']
        
        # Check if book already exists on this shelf (by ISBN first, then by title+author)
        existing_book = None
        if isbn and isbn.strip():
            # Try to find by ISBN first
            existing_books = list(db_tables['books']("bookshelf_id=? AND isbn=?", (bookshelf_id, isbn.strip())))
            if existing_books:
                existing_book = existing_books[0]
        
        if not existing_book:
            # Try to find by title and author combination
            existing_books = list(db_tables['books']("bookshelf_id=? AND title=? AND author=?", 
                                                   (bookshelf_id, title.strip(), author.strip())))
            if existing_books:
                existing_book = existing_books[0]
        
        # Create the close interface component (out-of-band swap)
        close_interface = Div(
            Button(
                "📚 Add Books", 
                hx_get=f"/api/shelf/{bookshelf_id}/add-books-form",
                hx_target="#add-books-container",
                hx_swap="outerHTML",
                cls="add-books-toggle primary"
            ),
            id="add-books-container",
            hx_swap_oob="true"
        )
        
        if existing_book:
            # Book already exists - check if user has already voted
            existing_upvote = None
            try:
                existing_upvote = db_tables['upvotes']("book_id=? AND user_did=?", 
                                                     (existing_book.id, user_did))[0]
            except:
                pass
            
            if existing_upvote:
                # User has already voted for this book
                return Div("You've already added this book to the shelf!", cls="alert alert-info"), close_interface
            else:
                # Add user's vote to existing book
                upvote = Upvote(
                    book_id=existing_book.id,
                    user_did=user_did,
                    created_at=datetime.now()
                )
                db_tables['upvotes'].insert(upvote)
                
                # Get updated book with vote count and return it
                existing_book.upvote_count = len(db_tables['upvotes']("book_id=?", (existing_book.id,)))
                existing_book.user_has_upvoted = True
                return existing_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=existing_book.upvote_count), close_interface
        else:
            atproto_uri = None
            try:
                client = bluesky_auth.get_client_from_session(auth)
                # 1. Write to AT Protocol
                atproto_uri = add_book_record(client, shelf.atproto_uri, title, author, isbn)
            except Exception as e:
                logger.error(f"Failed to write book to AT Protocol: {e}", exc_info=True)
                # Don't fail the whole request, just log the error and continue

            # 2. Write to local DB
            book = Book(
                bookshelf_id=bookshelf_id,
                isbn=isbn,
                title=title,
                author=author,
                cover_url=cover_url,
                description=description,
                publisher=publisher,
                published_date=published_date,
                page_count=page_count,
                atproto_uri=atproto_uri,
                added_by_did=user_did,
                added_at=datetime.now()
            )
            
            created_book = db_tables['books'].insert(book)
            
            # Create the initial upvote record from the person who added the book
            upvote = Upvote(
                book_id=created_book.id,
                user_did=user_did,
                created_at=datetime.now()
            )
            db_tables['upvotes'].insert(upvote)
            
            # Log activity for social feed
            try:
                from models import log_activity
                log_activity(user_did, 'book_added', db_tables, bookshelf_id=bookshelf_id, book_id=created_book.id)
            except Exception as e:
                logger.warning(f"Could not log book addition activity: {e}")
            
            # Set the computed attributes and return the book card with close interface
            created_book.upvote_count = 1
            created_book.user_has_upvoted = True
            return created_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=1), close_interface
        
    except Exception as e:
        return Div(f"Error adding book: {str(e)}", cls="error")

@rt("/book/{book_id}/upvote", methods=["POST"])
def upvote_book(book_id: int, auth):
    """HTMX endpoint to upvote/downvote a book. Hides book from view if votes reach 0."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        book = db_tables['books'][book_id]
        user_did = get_current_user_did(auth)
        
        # Check if user already upvoted
        try:
            existing_upvote = db_tables['upvotes']("book_id=? AND user_did=?", (book_id, user_did))[0]
            if existing_upvote:
                # Remove upvote (downvote)
                db_tables['upvotes'].delete((book_id, user_did))
                
                # Count remaining votes
                new_vote_count = len(db_tables['upvotes']("book_id=?", (book_id,)))
                
                # If votes reach 0, hide book from view (return empty response)
                if new_vote_count <= 0:
                    logger.info(f"Book '{book.title}' hidden from shelf due to 0 votes")
                    return ""
                else:
                    # Return updated card with new count
                    book.upvote_count = new_vote_count
                    book.user_has_upvoted = False
                    return book.as_interactive_card(can_upvote=True, user_has_upvoted=False, upvote_count=new_vote_count)
            else:
                # Add upvote
                from models import Upvote
                upvote = Upvote(book_id=book_id, user_did=user_did, created_at=datetime.now())
                db_tables['upvotes'].insert(upvote)
                
                # Count total votes
                new_vote_count = len(db_tables['upvotes']("book_id=?", (book_id,)))
                
                # Return updated card with new count
                book.upvote_count = new_vote_count
                book.user_has_upvoted = True
                return book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=new_vote_count)
        except:
            # Add upvote (first time)
            from models import Upvote
            upvote = Upvote(book_id=book_id, user_did=user_did, created_at=datetime.now())
            db_tables['upvotes'].insert(upvote)
            
            # Count total votes
            new_vote_count = len(db_tables['upvotes']("book_id=?", (book_id,)))
            
            # Return updated card with new count
            book.upvote_count = new_vote_count
            book.user_has_upvoted = True
            return book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=new_vote_count)
            
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="error")

@rt("/book/{book_id}/remove", methods=["POST"])
def remove_book(book_id: int, auth):
    """HTMX endpoint to remove a book from a bookshelf (moderator/owner only)."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        book = db_tables['books'][book_id]
        shelf = db_tables['bookshelves'][book.bookshelf_id]
        user_did = get_current_user_did(auth)
        
        # Check if user can remove books from this shelf
        from models import can_remove_books
        if not can_remove_books(shelf, user_did, db_tables):
            return Div("You don't have permission to remove books from this shelf.", cls="error")
        
        # Get upvote count for logging
        upvote_count = len(db_tables['upvotes']("book_id=?", (book_id,)))
        
        # Delete all upvotes for this book first
        try:
            db_tables['upvotes'].delete_where("book_id=?", (book_id,))
        except:
            pass
        
        # Delete the book
        db_tables['books'].delete(book_id)
        
        logger.info(f"Book '{book.title}' removed from shelf '{shelf.name}' by {auth.get('handle', 'unknown')} (had {upvote_count} votes)")
        
        # Return empty response to remove the book card from the UI
        return ""
        
    except Exception as e:
        logger.error(f"Error removing book {book_id}: {e}", exc_info=True)
        return Div(f"Error removing book: {str(e)}", cls="error")

@rt("/api/shelf/{bookshelf_id}/add-books-toggle")
def get_add_books_toggle(bookshelf_id: int, auth):
    """HTMX endpoint to get the add books toggle button."""
    if not auth: return ""
    return AddBooksToggle(bookshelf_id)

@rt("/api/shelf/{bookshelf_id}/add-books-form")
def get_add_books_form(bookshelf_id: int, auth):
    """HTMX endpoint to get the add books form."""
    if not auth: return ""
    return BookSearchForm(bookshelf_id)

@rt("/api/shelf/{slug}/toggle-view")
def toggle_view(slug: str, view: str, auth):
    """HTMX endpoint to toggle between grid and list view."""
    if not auth: return ""
    
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return Div("Shelf not found", cls="error")
        
        # Check permissions
        user_did = get_current_user_did(auth)
        if not can_view_bookshelf(shelf, user_did, db_tables):
            return Div("Access denied", cls="error")
        
        # Import permission functions
        from models import (can_add_books, can_vote_books, can_remove_books, get_books_with_upvotes)
        
        can_add = can_add_books(shelf, user_did, db_tables)
        can_vote = can_vote_books(shelf, user_did, db_tables)
        can_remove = can_remove_books(shelf, user_did, db_tables)
        
        # Get books with upvote counts
        shelf_books = get_books_with_upvotes(shelf.id, user_did, db_tables)
        
        # Determine user authentication status
        user_auth_status = "anonymous" if not auth else "logged_in"
        
        # Always create consistent structure with book-grid for HTMX targeting
        if shelf_books:
            if view == "list":
                from components import BookListView
                books_content = BookListView(shelf_books, can_upvote=can_vote, can_remove=can_remove, user_auth_status=user_auth_status)
            else:  # grid view (default)
                books_content = Div(*[book.as_interactive_card(
                    can_upvote=can_vote, 
                    user_has_upvoted=book.user_has_upvoted,
                    upvote_count=book.upvote_count,
                    can_remove=can_remove,
                    user_auth_status=user_auth_status
                ) for book in shelf_books], cls="book-grid", id="book-grid")
            
            books_section_content = Div(books_content, id="books-container")
        else:
            from components import EnhancedEmptyState
            books_section_content = Div(
                EnhancedEmptyState(can_add=can_add, shelf_id=shelf.id, user_auth_status=user_auth_status),
                # Always include an empty book-grid div for HTMX targeting
                Div(id="book-grid", cls="book-grid"),
                id="books-container"
            )
        
        # Return the entire books section with the correct view class
        return Section(
            books_section_content,
            cls=f"books-section {view}-view",
            id="books-section"
        )
        
    except Exception as e:
        logger.error(f"Error toggling view for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

# Management routes
@rt("/shelf/{slug}/manage")
def manage_shelf(slug: str, auth, req):
    """Display unified management interface for a bookshelf."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
        if not shelf:
            return NavBar(auth), Container(
                H1("Bookshelf Not Found"),
                P("The bookshelf you're looking for doesn't exist."),
                A("← Back to Home", href="/")
            )
        
        user_did = get_current_user_did(auth)
        from models import can_manage_members, can_generate_invites
        
        can_edit = can_edit_bookshelf(shelf, user_did, db_tables)
        can_manage = can_manage_members(shelf, user_did, db_tables)
        can_generate = can_generate_invites(shelf, user_did, db_tables)
        is_owner = shelf.owner_did == user_did
        
        if not (can_edit or can_generate):
            return NavBar(auth), Container(
                H1("Access Denied"),
                P("You don't have permission to manage this bookshelf."),
                A("← Back to Shelf", href=f"/shelf/{shelf.slug}")
            )
        
        # Get all members (active permissions + owner)
        # PRESERVED: pending_members logic kept for future approval workflows, but not used in UI
        permissions = list(db_tables['permissions']("bookshelf_id=?", (shelf.id,)))
        members = []
        pending_members = []  # Currently always empty since all invites create active permissions
        
        # Add owner to members list
        try:
            owner = db_tables['users'][shelf.owner_did]
            members.append({
                'user': owner,
                'permission': type('obj', (object,), {'role': 'owner', 'status': 'active'})()
            })
        except:
            pass
        
        # Add other members (preserving pending logic for future use)
        for perm in permissions:
            try:
                user = db_tables['users'][perm.user_did]
                member_data = {'user': user, 'permission': perm}
                
                # PRESERVED: pending status filtering (currently never matches)
                if perm.status == 'pending':
                    pending_members.append(member_data)
                else:
                    members.append(member_data)
            except:
                continue
        
        # Get active invites
        invites = list(db_tables['bookshelf_invites']("bookshelf_id=? AND is_active=1", (shelf.id,)))
        
        # Build management sections
        sections = []
        
        # Edit Details Section
        if can_edit:
            sections.append(
                Div(
                    H3("Edit Details"),
                    Form(
                        Fieldset(
                            Label("Shelf Name", Input(
                                name="name",
                                type="text",
                                value=shelf.name,
                                required=True,
                                maxlength=100
                            )),
                            Label("Description", Textarea(
                                shelf.description,
                                name="description",
                                rows=3,
                                maxlength=500
                            )),
                            Label("Privacy Level", Select(
                                Option("Public - Visible to everyone and appears in search results", value="public", selected=(shelf.privacy == "public")),
                                Option("Link Only - Hidden from search, but viewable by anyone with the link", value="link-only", selected=(shelf.privacy == "link-only")),
                                Option("Private - Coming soon (we're working on true privacy)", value="private", selected=(shelf.privacy == "private"), disabled=True),
                                name="privacy"
                            )),
                            P("Note: All shelves are shared across the decentralized network. True private shelves are coming soon!", 
                              cls="privacy-explanation", 
                              style="font-size: 0.85rem; color: var(--brand-muted); margin-top: 0.5rem; font-style: italic;"),
                            Label(
                                CheckboxX(
                                    id="self_join",
                                    name="self_join",
                                    checked=shelf.self_join,
                                    label="Allow anyone to join as a contributor"
                                ),
                                "Open Collaboration",
                                cls="self-join-label"
                            ),
                            P("⚠️ Alpha Version: Data may be reset during development.", 
                              cls="alpha-form-disclaimer", 
                              style="font-size: 0.8rem; color: var(--brand-warning); margin-top: 1rem; padding: 0.5rem; background: var(--brand-warning-bg); border-radius: 4px; border-left: 3px solid var(--brand-warning);"),
                        ),
                        Button("Save Changes", type="submit", cls="primary"),
                        action=f"/shelf/{shelf.slug}/update",
                        method="post"
                    ),
                    cls="management-section"
                )
            )
        
        # Share & Members Section
        if can_generate:
            sections.append(
                Div(
                    ShareInterface(
                        bookshelf=shelf,
                        members=members,
                        invites=invites,
                        can_manage=can_manage,
                        can_generate_invites=can_generate,
                        req=req  # Pass the request object
                    ),
                    cls="management-section"
                )
            )
        
        # Delete Section (Owner only)
        if is_owner:
            sections.append(
                Div(
                    H3("Danger Zone", style="color: #dc3545;"),
                    P("Once you delete a bookshelf, there is no going back. This will permanently delete the bookshelf, all its books, and all associated data."),
                    Button(
                        "Delete Bookshelf",
                        hx_get=f"/api/shelf/{shelf.slug}/delete-confirm",
                        hx_target="#delete-section",
                        hx_swap="outerHTML",
                        cls="danger",
                        style="background: #dc3545; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.25rem; cursor: pointer;"
                    ),
                    cls="management-section danger-section",
                    style="border: 2px solid #dc3545; border-radius: 0.5rem; padding: 1.5rem; margin-top: 2rem;",
                    id="delete-section"
                )
            )
        
        content = [
            Div(
                H1(f"Manage: {shelf.name}"),
                A("← Back to Shelf", href=f"/shelf/{shelf.slug}", cls="secondary"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
            ),
            *sections
        ]
        
        
        return (
            Title(f"Manage: {shelf.name} - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            ),
            UniversalFooter()
        )

@rt("/shelf/{slug}/share")
def share_shelf(slug: str, auth, req):
    """Display share interface for a bookshelf."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
        if not shelf:
            return NavBar(auth), Container(
                H1("Bookshelf Not Found"),
                P("The bookshelf you're looking for doesn't exist."),
                A("← Back to Home", href="/")
            )
        
        user_did = get_current_user_did(auth)
        from models import can_manage_members, can_generate_invites
        
        can_manage = can_manage_members(shelf, user_did, db_tables)
        can_generate = can_generate_invites(shelf, user_did, db_tables)
        
        if not can_generate:
            return NavBar(auth), Container(
                H1("Access Denied"),
                P("You don't have permission to manage sharing for this bookshelf."),
                A("← Back to Shelf", href=f"/shelf/{shelf.slug}")
            )
        
        # Get all members (active permissions + owner)
        # PRESERVED: pending_members logic kept for future approval workflows, but not used in UI
        permissions = list(db_tables['permissions']("bookshelf_id=?", (shelf.id,)))
        members = []
        pending_members = []  # Currently always empty since all invites create active permissions
        
        # Add owner to members list
        try:
            owner = db_tables['users'][shelf.owner_did]
            members.append({
                'user': owner,
                'permission': type('obj', (object,), {'role': 'owner', 'status': 'active'})()
            })
        except:
            pass
        
        # Add other members (preserving pending logic for future use)
        for perm in permissions:
            try:
                user = db_tables['users'][perm.user_did]
                member_data = {'user': user, 'permission': perm}
                
                # PRESERVED: pending status filtering (currently never matches)
                if perm.status == 'pending':
                    pending_members.append(member_data)
                else:
                    members.append(member_data)
            except:
                continue
        
        # Get active invites
        invites = list(db_tables['bookshelf_invites']("bookshelf_id=? AND is_active=1", (shelf.id,)))
        
        content = [
            Div(
                H1(f"Share: {shelf.name}"),
                A("← Back to Shelf", href=f"/shelf/{shelf.slug}", cls="secondary"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
            ),
            ShareInterface(
                bookshelf=shelf,
                members=members,
                invites=invites,
                can_manage=can_manage,
                can_generate_invites=can_generate,
                req=req
            )
        ]
        
        return (
            Title(f"Share: {shelf.name} - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(*content),
            UniversalFooter()
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            ),
            UniversalFooter()
        )

# API routes for sharing and management
@rt("/api/shelf/{slug}/invite", methods=["POST"])
def generate_invite(slug: str, role: str, expires_days: str, max_uses: str, auth, req):
    """HTMX endpoint to generate a new invite link."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_generate_invites, get_user_role, can_invite_role, generate_invite_code, BookshelfInvite
        
        # Check permission to generate invites
        if not can_generate_invites(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Check if inviter has permission to grant the selected role
        inviter_role = get_user_role(shelf, user_did, db_tables)
        if not can_invite_role(inviter_role, role):
            return Div(f"You do not have permission to create '{role}' invites.", cls="error")
        
        # Create expiration date if specified
        expires_at = None
        if expires_days and expires_days.isdigit():
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=int(expires_days))
        
        # Create max uses if specified
        max_uses_val = int(max_uses) if max_uses and max_uses.isdigit() else None
        
        # Create invite
        invite = BookshelfInvite(
            bookshelf_id=shelf.id,
            invite_code=generate_invite_code(),
            role=role,
            created_by_did=user_did,
            created_at=datetime.now(),
            expires_at=expires_at,
            max_uses=max_uses_val
        )
        
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        # Return the new invite card
        return InviteCard(created_invite, shelf.slug, req)
        
    except Exception as e:
        logger.error(f"Error generating invite for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/invite/{invite_id}", methods=["DELETE"])
def revoke_invite(slug: str, invite_id: int, auth):
    """HTMX endpoint to revoke an invite link."""
    if not auth: return ""
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_generate_invites
        if not can_generate_invites(shelf, user_did, db_tables):
            return "" # Fail silently
        
        # Deactivate the invite
        db_tables['bookshelf_invites'].update({'is_active': False}, invite_id)
        
        return "" # Return empty to remove from UI
        
    except Exception as e:
        logger.error(f"Error revoking invite {invite_id} for shelf {slug}: {e}", exc_info=True)
        return ""

@rt("/shelf/join/{invite_code}")
def join_shelf(invite_code: str, auth, sess):
    """Page for users to accept an invitation to a bookshelf."""
    if not auth:
        sess['next_url'] = f"/shelf/join/{invite_code}"
        return RedirectResponse('/auth/login', status_code=303)
    
    from models import validate_invite, Permission
    
    invite = validate_invite(invite_code, db_tables)
    if not invite:
        return NavBar(auth), Container(
            H1("Invalid Invitation"),
            P("This invite link is either invalid or has expired."),
            A("← Back to Home", href="/")
        ), UniversalFooter()
    
    shelf = db_tables['bookshelves'][invite.bookshelf_id]
    user_did = get_current_user_did(auth)
    
    # Check if user is already a member
    existing_permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, user_did))
    if existing_permission:
        sess['info'] = f"You are already a member of '{shelf.name}'."
        return RedirectResponse(f'/shelf/{shelf.slug}', status_code=303)
    
    # Ensure user exists in the database before creating permission
    try:
        user = db_tables['users'][user_did]
        # User exists, maybe update their info if needed (optional)
        update_data = {
            'handle': auth.get('handle'),
            'display_name': auth.get('display_name'),
            'avatar_url': auth.get('avatar_url'),
            'last_login': datetime.now()
        }
        db_tables['users'].update(update_data, user_did)
    except IndexError:
        # User does not exist, create them
        new_user_data = {
            'did': user_did,
            'handle': auth.get('handle'),
            'display_name': auth.get('display_name'),
            'avatar_url': auth.get('avatar_url'),
            'created_at': datetime.now(),
            'last_login': datetime.now()
        }
        db_tables['users'].insert(**new_user_data)
        logger.info(f"New user created via invite: {auth.get('handle')}")
    
    # Add user to the bookshelf
    permission = Permission(
        bookshelf_id=shelf.id,
        user_did=user_did,
        role=invite.role,
        status='active',
        granted_by_did=invite.created_by_did,
        granted_at=datetime.now(),
        joined_at=datetime.now()
    )
    db_tables['permissions'].insert(permission)
    
    # Increment uses count
    db_tables['bookshelf_invites'].update({'uses_count': invite.uses_count + 1}, invite.id)
    
    # Deactivate if max uses reached
    if invite.max_uses and (invite.uses_count + 1) >= invite.max_uses:
        db_tables['bookshelf_invites'].update({'is_active': False}, invite.id)
    
    sess['success'] = f"You have successfully joined '{shelf.name}' as a {invite.role}!"
    return RedirectResponse(f'/shelf/{shelf.slug}', status_code=303)

@rt("/api/shelf/{slug}/privacy", methods=["POST"])
def update_privacy(slug: str, privacy: str, auth):
    """HTMX endpoint to update bookshelf privacy."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_edit_bookshelf
        if not can_edit_bookshelf(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Update privacy
        db_tables['bookshelves'].update({'privacy': privacy}, shelf.id)
        
        # Return updated privacy section (or the whole share interface)
        # For simplicity, let's just return a success message that can be shown in a toast/alert
        return Div(f"Privacy updated to {privacy.replace('-', ' ').title()}", cls="alert alert-success")

    except Exception as e:
        logger.error(f"Error updating privacy for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/member/{member_did}/edit-role")
def get_role_editor(slug: str, member_did: str, auth):
    """HTMX endpoint to get the role editing form."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members
        if not can_manage_members(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        
        from components import MemberRoleEditor
        return MemberRoleEditor(member_user, permission.role, slug)
        
    except Exception as e:
        logger.error(f"Error getting role editor for member {member_did} on shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/member/{member_did}/role-preview", methods=["POST"])
def preview_role_change(slug: str, member_did: str, new_role: str, auth):
    """HTMX endpoint to preview a role change before confirmation."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members, get_user_role, can_invite_role
        
        # Check permission to manage members
        if not can_manage_members(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Check if manager can assign the target role
        manager_role = get_user_role(shelf, user_did, db_tables)
        if not can_invite_role(manager_role, new_role):
            return Div(f"You cannot assign the role '{new_role}'.", cls="error")
        
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        
        from components import RoleChangePreview
        return RoleChangePreview(member_user, permission.role, new_role, slug)
        
    except Exception as e:
        logger.error(f"Error previewing role change for member {member_did} on shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/member/{member_did}/role-confirm", methods=["POST"])
def confirm_role_change(slug: str, member_did: str, new_role: str, auth):
    """HTMX endpoint to confirm and apply a role change."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members, get_user_role, can_invite_role
        
        # Check permission to manage members
        if not can_manage_members(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Check if manager can assign the target role
        manager_role = get_user_role(shelf, user_did, db_tables)
        if not can_invite_role(manager_role, new_role):
            return Div(f"You cannot assign the role '{new_role}'.", cls="error")
        
        # Update the permission
        db_tables['permissions'].update({'role': new_role}, f"bookshelf_id={shelf.id} AND user_did='{member_did}'")
        
        # Return the updated member card with success highlight
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        
        from components import MemberCard
        updated_card = MemberCard(member_user, permission, can_manage=True, bookshelf_slug=slug)
        
        # Add success styling temporarily
        return Div(
            updated_card,
            Script(f"""
                setTimeout(() => {{
                    const card = document.getElementById('member-{member_did}');
                    if (card) {{
                        card.style.background = '#d4edda';
                        card.style.borderColor = '#c3e6cb';
                        setTimeout(() => {{
                            card.style.background = '';
                            card.style.borderColor = '';
                        }}, 2000);
                    }}
                }}, 100);
            """),
            id=f"member-{member_did}"
        )
        
    except Exception as e:
        logger.error(f"Error confirming role change for member {member_did} on shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/member/{member_did}/cancel-edit")
def cancel_role_edit(slug: str, member_did: str, auth):
    """HTMX endpoint to cancel role editing and return to read mode."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members
        if not can_manage_members(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        
        # Return the read-mode controls
        role_badge_colors = {
            'owner': 'badge-owner',
            'moderator': 'badge-moderator', 
            'contributor': 'badge-contributor',
            'viewer': 'badge-viewer',
            'pending': 'badge-pending'
        }
        
        return Div(
            Span(f"{permission.role.title()}", cls=f"role-display {role_badge_colors.get(permission.role, 'badge-viewer')}"),
            Button(
                "Edit",
                hx_get=f"/api/shelf/{slug}/member/{member_did}/edit-role",
                hx_target=f"#member-controls-{member_did}",
                hx_swap="outerHTML",
                cls="edit-role-btn secondary small",
                title="Change member role"
            ),
            Button(
                "Remove",
                hx_delete=f"/api/shelf/{slug}/member/{member_did}",
                hx_target=f"#member-{member_did}",
                hx_swap="outerHTML",
                hx_confirm="Are you sure you want to remove this member?",
                cls="remove-member-btn secondary small"
            ),
            cls="role-controls-read",
            id=f"member-controls-{member_did}"
        )
        
    except Exception as e:
        logger.error(f"Error canceling role edit for member {member_did} on shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/member/{member_did}", methods=["DELETE"])
def remove_member(slug: str, member_did: str, auth):
    """HTMX endpoint to remove a member from a bookshelf."""
    if not auth: return ""
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members
        if not can_manage_members(shelf, user_did, db_tables):
            return "" # Fail silently
        
        # Prevent owner from being removed
        if shelf.owner_did == member_did:
            return "" # Cannot remove owner
        
        # Delete the permission
        db_tables['permissions'].delete_where("bookshelf_id=? AND user_did=?", (shelf.id, member_did))
        
        return "" # Return empty to remove from UI
        
    except Exception as e:
        logger.error(f"Error removing member {member_did} from shelf {slug}: {e}", exc_info=True)
        return ""

# UNUSED: Pending member approval system preserved for future approval workflows
# Currently all invites create active permissions immediately, so this endpoint is never called
@rt("/api/shelf/{slug}/member/{member_did}/approve", methods=["POST"])
def approve_member(slug: str, member_did: str, auth):
    """UNUSED: HTMX endpoint to approve a pending member. Preserved for future approval workflows."""
    if not auth: return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0]
        user_did = get_current_user_did(auth)
        
        from models import can_manage_members
        if not can_manage_members(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Update permission status to active
        db_tables['permissions'].update({'status': 'active'}, f"bookshelf_id={shelf.id} AND user_did='{member_did}'")
        
        # Return the updated member card
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        return MemberCard(member_user, permission, can_manage=True, bookshelf_slug=slug)
        
    except Exception as e:
        logger.error(f"Error approving member {member_did} on shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/shelf/{slug}/update", methods=["POST"])
def update_shelf(slug: str, name: str, description: str, privacy: str, auth, sess, self_join: bool = False):
    """Handle bookshelf update."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
        if not shelf:
            sess['error'] = "Bookshelf not found."
            return RedirectResponse('/', status_code=303)
        
        # Check if user can edit this bookshelf
        if not can_edit_bookshelf(shelf, get_current_user_did(auth), db_tables):
            sess['error'] = "You don't have permission to edit this bookshelf."
            return RedirectResponse(f'/shelf/{shelf.slug}', status_code=303)
        
        # Update the bookshelf
        update_data = {
            'name': name.strip(),
            'description': description.strip(),
            'privacy': privacy,
            'self_join': self_join,
            'updated_at': datetime.now()
        }
        
        db_tables['bookshelves'].update(update_data, shelf.id)
        sess['success'] = "Bookshelf updated successfully!"
        return RedirectResponse(f'/shelf/{shelf.slug}/manage', status_code=303)
        
    except Exception as e:
        sess['error'] = f"Error updating bookshelf: {str(e)}"
        return RedirectResponse(f'/shelf/{slug}/manage', status_code=303)

@rt("/api/shelf/{slug}/delete-confirm")
def get_delete_confirmation(slug: str, auth):
    """HTMX endpoint to show delete confirmation form."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
        if not shelf:
            return Div("Bookshelf not found.", cls="error")
        
        # Check if user is the owner
        if shelf.owner_did != get_current_user_did(auth):
            return Div("Only the owner can delete a bookshelf.", cls="error")
        
        return Card(
            H3("Delete Bookshelf", style="color: #dc3545; margin-bottom: 1rem;"),
            P(f"Are you sure you want to delete '{shelf.name}'? This action cannot be undone."),
            P("All books, votes, and sharing settings will be permanently removed.", style="font-weight: bold; color: #dc3545;"),
            P("To confirm, type the bookshelf name below:", style="font-weight: bold; margin-top: 1rem;"),
            Form(
                Input(
                    type="text",
                    name="confirmation_name",
                    placeholder=f"Type '{shelf.name}' to confirm",
                    required=True,
                    hx_post=f"/api/shelf/{slug}/validate-delete",
                    hx_target="#delete-validation",
                    hx_trigger="keyup changed delay:300ms",
                    hx_vals=f'{{"expected_name": "{shelf.name}"}}',
                    style="width: 100%; margin-bottom: 1rem;"
                ),
                Div(id="delete-validation"),
                Div(
                    Button("Cancel", 
                           hx_get=f"/api/shelf/{slug}/cancel-delete",
                           hx_target="#delete-section",
                           hx_swap="outerHTML",
                           cls="secondary"),
                    Button("Delete Forever", 
                           type="submit",
                           id="delete-confirm-btn",
                           disabled=True,
                           style="background: #dc3545; color: white; margin-left: 0.5rem;"),
                    style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem;"
                ),
                hx_post=f"/shelf/{slug}/delete",
                hx_target="body",
                hx_swap="outerHTML"
            ),
            cls="delete-confirmation-card",
            style="background: #fff5f5; border: 2px solid #dc3545; border-radius: 0.5rem; padding: 1.5rem; margin-top: 1rem;"
        )
        
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/validate-delete", methods=["POST"])
def validate_delete_name(slug: str, confirmation_name: str, expected_name: str, auth):
    """HTMX endpoint to validate the delete confirmation name."""
    if not auth:
        return ""
    
    if confirmation_name.strip() == expected_name:
        return Script("""
            document.getElementById('delete-confirm-btn').disabled = false;
            document.getElementById('delete-confirm-btn').style.opacity = '1';
        """), Div("✓ Name matches - you can now delete the bookshelf", 
                 style="color: #28a745; font-weight: bold; margin-top: 0.5rem;")
    elif confirmation_name.strip():
        return Script("""
            document.getElementById('delete-confirm-btn').disabled = true;
            document.getElementById('delete-confirm-btn').style.opacity = '0.5';
        """), Div("✗ Name doesn't match", 
                 style="color: #dc3545; font-weight: bold; margin-top: 0.5rem;")
    else:
        return Script("""
            document.getElementById('delete-confirm-btn').disabled = true;
            document.getElementById('delete-confirm-btn').style.opacity = '0.5';
        """), ""

@rt("/api/shelf/{slug}/cancel-delete")
def cancel_delete(slug: str, auth):
    """HTMX endpoint to cancel delete and show the delete button again."""
    if not auth:
        return ""
    
    return Div(
        H3("Danger Zone", style="color: #dc3545;"),
        P("Once you delete a bookshelf, there is no going back. This will permanently delete the bookshelf, all its books, and all associated data."),
        Button(
            "Delete Bookshelf",
            hx_get=f"/api/shelf/{slug}/delete-confirm",
            hx_target="#delete-section",
            hx_swap="outerHTML",
            cls="danger",
            style="background: #dc3545; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.25rem; cursor: pointer;"
        ),
        cls="management-section danger-section",
        style="border: 2px solid #dc3545; border-radius: 0.5rem; padding: 1.5rem; margin-top: 2rem;",
        id="delete-section"
    )

@rt("/api/load-network-activity")
def load_network_activity_api(auth):
    """HTMX endpoint to load network activity in the background."""
    if not auth:
        from components import NetworkActivityPreviewError
        return NetworkActivityPreviewError()
    
    try:
        from models import get_network_activity
        logger.info(f"Background loading network activity for user: {auth.get('handle')}")
        network_activities = get_network_activity(auth, db_tables, bluesky_auth, limit=5)
        logger.info(f"Background network activities loaded: {len(network_activities)} activities found")
        
        return NetworkActivityPreview(network_activities, auth)
    except Exception as e:
        logger.error(f"Error loading network activity in background: {e}", exc_info=True)
        # Return error state with retry option
        from components import NetworkActivityPreviewError
        return NetworkActivityPreviewError()

@rt("/api/shelf/{slug}/self-join", methods=["POST"])
def self_join_shelf(slug: str, auth):
    """HTMX endpoint for users to join a public shelf as a contributor."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return Div("Bookshelf not found.", cls="error")
        
        user_did = get_current_user_did(auth)
        
        # Validate self-join conditions
        if shelf.privacy != 'public':
            return Div("This bookshelf is not public.", cls="error")
        
        if not shelf.self_join:
            return Div("This bookshelf does not allow self-joining.", cls="error")
        
        if shelf.owner_did == user_did:
            return Div("You are the owner of this bookshelf.", cls="error")
        
        # Check if user is already a member
        existing_permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, user_did))
        if existing_permission:
            return Div("You are already a member of this bookshelf.", cls="error")
        
        # Ensure user exists in the database
        try:
            user = db_tables['users'][user_did]
            # Update user info if needed
            update_data = {
                'handle': auth.get('handle'),
                'display_name': auth.get('display_name'),
                'avatar_url': auth.get('avatar_url'),
                'last_login': datetime.now()
            }
            db_tables['users'].update(update_data, user_did)
        except IndexError:
            # User does not exist, create them
            new_user_data = {
                'did': user_did,
                'handle': auth.get('handle'),
                'display_name': auth.get('display_name'),
                'avatar_url': auth.get('avatar_url'),
                'created_at': datetime.now(),
                'last_login': datetime.now()
            }
            db_tables['users'].insert(**new_user_data)
            logger.info(f"New user created via self-join: {auth.get('handle')}")
        
        # Add user as contributor
        from models import Permission
        permission = Permission(
            bookshelf_id=shelf.id,
            user_did=user_did,
            role='contributor',
            status='active',
            granted_by_did=shelf.owner_did,  # System grants on behalf of owner
            granted_at=datetime.now(),
            joined_at=datetime.now()
        )
        db_tables['permissions'].insert(permission)
        
        logger.info(f"User {auth.get('handle')} self-joined shelf '{shelf.name}' as contributor")
        
        # Return success component
        from components import SelfJoinSuccess
        return SelfJoinSuccess(shelf.name)
        
    except Exception as e:
        logger.error(f"Error in self-join for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error joining bookshelf: {str(e)}", cls="error")

@rt("/shelf/{slug}/delete", methods=["POST"])
def delete_shelf(slug: str, confirmation_name: str, auth, sess):
    """Handle bookshelf deletion with confirmation."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
        if not shelf:
            sess['error'] = "Bookshelf not found."
            return RedirectResponse('/', status_code=303)
        
        # Check if user is the owner
        if shelf.owner_did != get_current_user_did(auth):
            sess['error'] = "Only the owner can delete a bookshelf."
            return RedirectResponse(f'/shelf/{shelf.slug}', status_code=303)
        
        # Validate confirmation name
        if confirmation_name.strip() != shelf.name:
            sess['error'] = "Confirmation name doesn't match. Deletion cancelled."
            return RedirectResponse(f'/shelf/{slug}/manage', status_code=303)
        
        # Delete all related data in correct order
        # 1. Delete upvotes for books in this shelf
        shelf_books = list(db_tables['books']("bookshelf_id=?", (shelf.id,)))
        for book in shelf_books:
            # Delete upvotes for this book
            try:
                db_tables['upvotes'].delete_where("book_id=?", (book.id,))
            except:
                pass
        
        # 2. Delete books
        try:
            db_tables['books'].delete_where("bookshelf_id=?", (shelf.id,))
        except:
            pass
        
        # 3. Delete permissions
        try:
            db_tables['permissions'].delete_where("bookshelf_id=?", (shelf.id,))
        except:
            pass
        
        # 4. Delete invites
        try:
            db_tables['bookshelf_invites'].delete_where("bookshelf_id=?", (shelf.id,))
        except:
            pass
        
        # 5. Finally delete the bookshelf
        db_tables['bookshelves'].delete(shelf.id)
        
        sess['success'] = f"Bookshelf '{shelf.name}' has been permanently deleted."
        return RedirectResponse('/', status_code=303)
        
    except Exception as e:
        sess['error'] = f"Error deleting bookshelf: {str(e)}"
        return RedirectResponse(f'/shelf/{slug}/manage', status_code=303)

# Share functionality API endpoints
@rt("/api/shelf/{slug}/share-modal")
def get_share_modal(slug: str, auth, req):
    """HTMX endpoint to get the share modal content."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return Div("Bookshelf not found.", cls="error")
        
        user_did = get_current_user_did(auth)
        from models import can_generate_invites, get_user_role
        
        # Check if user can access share functionality at all
        # For now, we allow anyone who can view the shelf to see share options
        # but filter the options based on their permissions
        if not can_view_bookshelf(shelf, user_did, db_tables):
            return Div("Permission denied.", cls="error")
        
        # Get user's role and permissions
        user_role = get_user_role(shelf, user_did, db_tables)
        can_generate = can_generate_invites(shelf, user_did, db_tables)
        
        # Get base URL from request
        base_url = f"{req.url.scheme}://{req.url.netloc}"
        
        from components import ShareModal
        return ShareModal(shelf, base_url, user_role=user_role, can_generate_invites=can_generate)
        
    except Exception as e:
        logger.error(f"Error getting share modal for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/share-preview", methods=["POST"])
def get_share_preview(slug: str, share_type: str, auth, req):
    """HTMX endpoint to get preview of what will be shared."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return Div("Bookshelf not found.", cls="error")
        
        user_did = get_current_user_did(auth)
        from models import can_generate_invites
        
        # Check permissions based on share type
        if share_type == "public_link":
            # Anyone who can view the shelf can share public links
            if not can_view_bookshelf(shelf, user_did, db_tables):
                return Div("Permission denied.", cls="error")
        else:
            # Invite-based sharing requires invite generation permissions
            if not can_generate_invites(shelf, user_did, db_tables):
                return Div("Permission denied.", cls="error")
        
        # Get base URL from request
        base_url = f"{req.url.scheme}://{req.url.netloc}"
        
        from components import SharePreview
        return SharePreview(shelf, share_type, base_url)
        
    except Exception as e:
        logger.error(f"Error getting share preview for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/generate-share-link", methods=["POST"])
def generate_share_link(slug: str, share_type: str, auth, req):
    """HTMX endpoint to generate the actual sharing link."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        shelf = get_shelf_by_slug(slug, db_tables)
        if not shelf:
            return Div("Bookshelf not found.", cls="error")
        
        user_did = get_current_user_did(auth)
        from models import can_generate_invites
        
        # Get base URL from request
        base_url = f"{req.url.scheme}://{req.url.netloc}"
        
        if share_type == "public_link":
            # Generate direct public link (for public/link-only shelves)
            # Check if user can view the shelf (less restrictive than invite generation)
            if not can_view_bookshelf(shelf, user_did, db_tables):
                return Div("Permission denied.", cls="error")
            
            if shelf.privacy not in ['public', 'link-only']:
                return Div("Direct links are only available for public and link-only shelves.", cls="error")
            
            link = f"{base_url}/shelf/{shelf.slug}"
            message = f"Check out my bookshelf '{shelf.name}' on Bibliome: {link}"
        
        elif share_type == "invite_viewer":
            # Generate view-only invite
            if not can_generate_invites(shelf, user_did, db_tables):
                return Div("Permission denied.", cls="error")
            
            from models import generate_invite_code, BookshelfInvite
            invite = BookshelfInvite(
                bookshelf_id=shelf.id,
                invite_code=generate_invite_code(),
                role="viewer",
                created_by_did=user_did,
                created_at=datetime.now(),
                expires_at=None,  # No expiration for view links
                max_uses=None     # No usage limit for view links
            )
            created_invite = db_tables['bookshelf_invites'].insert(invite)
            link = f"{base_url}/shelf/join/{created_invite.invite_code}"
            if shelf.privacy == "private":
                message = f"I've shared my private bookshelf with you: '{shelf.name}' - {link}"
            else:
                message = f"Check out my bookshelf '{shelf.name}' on Bibliome: {link}"
        
        elif share_type == "invite_contributor":
            # Generate contributor invite
            if not can_generate_invites(shelf, user_did, db_tables):
                return Div("Permission denied.", cls="error")
            
            from models import generate_invite_code, BookshelfInvite
            invite = BookshelfInvite(
                bookshelf_id=shelf.id,
                invite_code=generate_invite_code(),
                role="contributor",
                created_by_did=user_did,
                created_at=datetime.now(),
                expires_at=None,  # No expiration for contribution invites
                max_uses=None     # No usage limit for contribution invites
            )
            created_invite = db_tables['bookshelf_invites'].insert(invite)
            link = f"{base_url}/shelf/join/{created_invite.invite_code}"
            message = f"Join my bookshelf '{shelf.name}' on Bibliome and help build our reading list: {link}"
        
        else:
            return Div("Invalid share type.", cls="error")
        
        from components import ShareLinkResult
        return ShareLinkResult(link, message, share_type)
        
    except Exception as e:
        logger.error(f"Error generating share link for shelf {slug}: {e}", exc_info=True)
        return Div(f"Error: {str(e)}", cls="error")

@rt("/api/shelf/{slug}/close-share-modal")
def close_share_modal(slug: str, auth):
    """HTMX endpoint to close the share modal."""
    if not auth:
        return ""
    
    return ""  # Return empty content to clear the modal

# Contact functionality API endpoints
@rt("/api/contact-modal")
def get_contact_modal():
    """HTMX endpoint to get the contact modal content."""
    return ContactModal()

@rt("/api/close-contact-modal")
def close_contact_modal():
    """HTMX endpoint to close the contact modal."""
    return ""  # Return empty content to clear the modal

@rt("/api/contact", methods=["POST"])
async def send_contact_email(name: str, email: str, subject: str, message: str):
    """HTMX endpoint to send contact form email via SMTP2GO API."""
    import httpx
    
    try:
        # Get email configuration from environment
        contact_email = os.getenv('CONTACT_EMAIL')
        sender_email = os.getenv('SENDER_EMAIL')
        api_key = os.getenv('SMTP2GO_API_KEY')
        
        if not all([contact_email, sender_email, api_key]):
            logger.error("SMTP2GO configuration incomplete")
            return ContactFormError("Email service is not configured. Please try again later.")
        
        # Prepare email payload for SMTP2GO API
        email_payload = {
            "sender": sender_email,
            "to": [contact_email],
            "subject": f"Bibliome Contact Form: {subject}",
            "text_body": f"""New contact form submission from Bibliome:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent via the Bibliome contact form.
Reply directly to this email to respond to {name} at {email}.""",
            "html_body": f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px;">
        New Contact Form Submission
    </h2>
    
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Name:</strong> {name}</p>
        <p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>
        <p><strong>Subject:</strong> {subject}</p>
    </div>
    
    <div style="margin: 20px 0;">
        <h3 style="color: #333;">Message:</h3>
        <div style="background: white; padding: 15px; border-left: 4px solid #007bff; border-radius: 4px;">
            {message.replace(chr(10), '<br>')}
        </div>
    </div>
    
    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
    <p style="color: #666; font-size: 14px;">
        This message was sent via the Bibliome contact form.<br>
        Reply directly to this email to respond to {name} at {email}.
    </p>
</div>
"""
        }
        
        # Send email via SMTP2GO API
        headers = {
            'Content-Type': 'application/json',
            'X-Smtp2go-Api-Key': api_key,
            'accept': 'application/json'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.smtp2go.com/v3/email/send',
                json=email_payload,
                headers=headers,
                timeout=30.0
            )
        
        if response.status_code == 200:
            response_data = response.json()
            email_id = response_data.get('data', {}).get('email_id', 'unknown')
            logger.info(f"Contact form email sent successfully via SMTP2GO. Email ID: {email_id}. From: {email} ({name}) Subject: {subject}")
            return ContactFormSuccess()
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get('data', {}).get('error', f'HTTP {response.status_code}')
            logger.error(f"SMTP2GO API error: {error_msg} (Status: {response.status_code})")
            return ContactFormError("There was an error sending your message. Please try again later.")
        
    except httpx.TimeoutException:
        logger.error("SMTP2GO API timeout")
        return ContactFormError("Email service timeout. Please try again later.")
    except Exception as e:
        logger.error(f"Error sending contact email via SMTP2GO: {e}", exc_info=True)
        return ContactFormError("There was an error sending your message. Please try again later.")

# Entry point integration for background services
if __name__ == "__main__":
    import os
    import sys
    import time
    import signal
    import threading
    from service_manager import ServiceManager

    # Global service manager instance
    service_manager = None

    def start_background_services():
        """Start background services in a separate thread."""
        global service_manager
        
        try:
            logger.info("Starting background services...")
            service_manager = ServiceManager(setup_signals=False)
            
            # Start services
            service_manager.start_all_services()
            
            # Give services a moment to start
            time.sleep(3)
            
            # Print initial status
            service_manager.print_status()
            
            logger.info("Background services started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start background services: {e}")

    def setup_signal_handlers():
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            
            if service_manager:
                logger.info("Stopping background services...")
                service_manager.stop_all_services()
            
            logger.info("Bibliome application shutdown complete")
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("Starting Bibliome Application Suite")
    print("=" * 60)
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Check if we should skip background services (useful for development)
    skip_services = os.getenv('BIBLIOME_SKIP_SERVICES', 'false').lower() == 'true'
    
    if not skip_services:
        print("🔄 Starting background services...")
        # Start background services in a separate thread
        services_thread = threading.Thread(target=start_background_services, daemon=True)
        services_thread.start()
        
        # Give services time to start
        time.sleep(5)
    else:
        print("⏭️ Skipping background services (BIBLIOME_SKIP_SERVICES=true)")
    
    print("🌐 Starting web application...")
    print("📊 Admin dashboard: http://localhost:5001/admin")
    print("🔍 Process monitoring: http://localhost:5001/admin/processes")
    print("=" * 60)
    
    try:
        serve()
    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
        if service_manager:
            print("🔄 Stopping background services...")
            service_manager.stop_all_services()
    except Exception as e:
        logger.error(f"Application error: {e}")
        if service_manager:
            service_manager.stop_all_services()
        raise
else:
    # When imported as a module, just call serve normally
    serve()
