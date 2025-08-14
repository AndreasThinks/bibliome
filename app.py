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
    HowItWorksSection, PublicShelvesPreview, LandingPageFooter, NetworkActivityFeed,
    BookshelfCard, EmptyState, CreateBookshelfForm, SearchPageHero,
    SearchShelvesForm, SearchResultsGrid, ExplorePageHero, PublicShelvesGrid,
    BookSearchForm, SearchResultCard, ShareInterface, InviteCard, MemberCard, AddBooksToggle,
    EnhancedEmptyState, ShelfHeader
)
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from auth import BlueskyAuth, get_current_user_did, auth_beforeware

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

# Initialize database
db_tables = setup_database()

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
        Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"),
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
def index(auth):
    """Homepage - beautiful landing page for visitors, dashboard for logged-in users."""
    if not auth:
        # Show beautiful landing page for anonymous users
        public_shelves = get_public_shelves(db_tables, limit=6)
        recent_books = get_recent_community_books(db_tables, limit=15)
        
        return (
            Title("Bibliome - Building the very best reading lists, together"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            LandingPageHero(),
            FeaturesSection(),
            CommunityReadingSection(recent_books),
            HowItWorksSection(),
            PublicShelvesPreview(public_shelves),
            LandingPageFooter()
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
        
        # Add network activity feed
        try:
            from models import get_network_activity
            logger.info(f"Attempting to load network activity for user: {auth.get('handle')}")
            network_activities = get_network_activity(auth, db_tables, bluesky_auth, limit=10)
            logger.info(f"Network activities loaded: {len(network_activities)} activities found")
            
            # Always show the network activity section (with empty state if no activities)
            content.append(NetworkActivityFeed(network_activities, auth))
        except Exception as e:
            logger.error(f"Could not load network activity: {e}", exc_info=True)
            # Show empty state even if there's an error
            content.append(NetworkActivityFeed([], auth))
        
        # Add user's shelves
        content.append(
            Div(*[BookshelfCard(shelf, is_owner=True, can_edit=True) for shelf in user_shelves], cls="bookshelf-grid") if user_shelves else EmptyState(
                "You haven't created any bookshelves yet",
                "Start building your first collection of books!",
                "Create Your First Shelf",
                "/shelf/new"
            )
        )
        
        return (
            Title("Dashboard - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(*content)
        )

# Authentication routes
@app.get("/auth/login")
def login_page(sess):
    """Display login form."""
    error_msg = sess.pop('error', None)
    return (
        Title("Login - Bibliome"),
        Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
        bluesky_auth.create_login_form(error_msg)
    )

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
        
        # Store user in database
        try:
            db_tables['users'].insert(**db_user_data)
            logger.info(f"New user created in database: {user_data['handle']}")
        except Exception as e:
            # User already exists, update their info and last login
            update_data = {
                'handle': user_data['handle'],
                'display_name': user_data['display_name'],
                'avatar_url': user_data['avatar_url'],
                'last_login': datetime.now()
            }
            db_tables['users'].update(update_data, user_data['did'])
            logger.debug(f"Existing user updated in database: {user_data['handle']}")
        
        # Store full auth data (including JWTs) in session
        sess['auth'] = user_data
        return RedirectResponse('/', status_code=303)
    else:
        logger.warning(f"Authentication failed for handle: {handle}")
        sess['error'] = "Invalid credentials. Please check your handle and app password."
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
        Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
        NavBar(auth),
        Container(CreateBookshelfForm())
    )

@rt("/shelf/create", methods=["POST"])
def create_shelf(name: str, description: str, privacy: str, auth, sess):
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

@rt("/search")
def search_page(auth, query: str = "", book_title: str = "", book_author: str = "", book_isbn: str = "", privacy: str = "public", sort_by: str = "updated_at", page: int = 1):
    """Display search page for bookshelves."""
    from models import search_shelves
    
    limit = 12
    offset = (page - 1) * limit
    
    shelves = search_shelves(
        db_tables, 
        query=query, 
        book_title=book_title,
        book_author=book_author,
        book_isbn=book_isbn,
        privacy=privacy, 
        sort_by=sort_by, 
        limit=limit, 
        offset=offset
    )
    
    # For now, we don't have a total count for pagination, so we'll just show next/prev
    
    return (
        Title("Search Shelves - Bibliome"),
        Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
        NavBar(auth),
        Container(
            SearchPageHero(),
            SearchShelvesForm(query=query, book_title=book_title, book_author=book_author, book_isbn=book_isbn, privacy=privacy, sort_by=sort_by),
            SearchResultsGrid(shelves, page=page, query=query, privacy=privacy, sort_by=sort_by)
        )
    )

@rt("/explore")
def explore_page(auth, page: int = 1):
    """Public page to explore all public bookshelves."""
    page = int(page)
    limit = 12
    offset = (page - 1) * limit
    
    shelves = get_public_shelves_with_stats(db_tables, limit=limit, offset=offset)
    total_shelves = len(db_tables['bookshelves'](where="privacy='public'"))
    total_pages = (total_shelves + limit - 1) // limit
    
    return (
        Title("Explore Public Shelves - Bibliome"),
        Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
        NavBar(auth),
        Container(
            ExplorePageHero(),
            PublicShelvesGrid(shelves, page=page, total_pages=total_pages)
        )
    )

@rt("/shelf/{slug}")
def view_shelf(slug: str, auth):
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
        
        # Get books with upvote counts using the new helper function
        from models import get_books_with_upvotes
        shelf_books = get_books_with_upvotes(shelf.id, user_did, db_tables)
        
        # Build action buttons
        action_buttons = []
        if can_edit or can_share:
            action_buttons.append(A("Manage", href=f"/shelf/{shelf.slug}/manage", cls="secondary"))
        
        # New Shelf Header
        shelf_header = ShelfHeader(shelf, action_buttons)
        
        # Show book search form if user can add books
        add_books_section = Section(AddBooksToggle(shelf.id), cls="add-books-section") if can_add else None
        
        # Always include the book-grid div, even when empty
        if shelf_books:
            book_grid_content = [book.as_interactive_card(
                can_upvote=can_vote, 
                user_has_upvoted=book.user_has_upvoted,
                upvote_count=book.upvote_count,
                can_remove=can_remove
            ) for book in shelf_books]
            books_section = Section(Div(*book_grid_content, cls="book-grid", id="book-grid"), cls="books-section")
        else:
            books_section = Section(
                EnhancedEmptyState(can_add=can_add, shelf_id=shelf.id),
                Div(cls="book-grid", id="book-grid"),  # Always include the target div
                cls="books-section"
            )
        
        content = [
            shelf_header,
            add_books_section,
            books_section
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
        
        return (
            Title(f"{shelf.name} - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(*content)
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            )
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
        permissions = list(db_tables['permissions']("bookshelf_id=?", (shelf.id,)))
        members = []
        pending_members = []
        
        # Add owner to members list
        try:
            owner = db_tables['users'][shelf.owner_did]
            members.append({
                'user': owner,
                'permission': type('obj', (object,), {'role': 'owner', 'status': 'active'})()
            })
        except:
            pass
        
        # Add other members
        for perm in permissions:
            try:
                user = db_tables['users'][perm.user_did]
                member_data = {'user': user, 'permission': perm}
                
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
                                Option("Public - Anyone can find and view", value="public", selected=(shelf.privacy == "public")),
                                Option("Link Only - Only people with the link can view", value="link-only", selected=(shelf.privacy == "link-only")),
                                Option("Private - Only invited people can view", value="private", selected=(shelf.privacy == "private")),
                                name="privacy"
                            ))
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
                        pending_members=pending_members,
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
                        onclick=f"showDeleteModal('{shelf.name}')",
                        cls="danger",
                        style="background: #dc3545; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.25rem; cursor: pointer;"
                    ),
                    cls="management-section danger-section",
                    style="border: 2px solid #dc3545; border-radius: 0.5rem; padding: 1.5rem; margin-top: 2rem;"
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
        
        # Add delete confirmation modal if owner
        if is_owner:
            content.append(
                Div(
                    Div(
                        Div(
                            H3("Delete Bookshelf", style="color: #dc3545; margin-bottom: 1rem;"),
                            P(f"Are you sure you want to delete '{shelf.name}'? This action cannot be undone."),
                            P("To confirm, type the bookshelf name below:", style="font-weight: bold; margin-top: 1rem;"),
                            Form(
                                Input(
                                    type="text",
                                    id="delete-confirmation",
                                    placeholder="Type bookshelf name here",
                                    style="width: 100%; margin-bottom: 1rem;",
                                    oninput="validateDeleteInput(this.value)"
                                ),
                                Div(
                                    Button("Cancel", type="button", onclick="hideDeleteModal()", cls="secondary"),
                                    Button("Delete Forever", type="submit", id="delete-confirm-btn", disabled=True, 
                                          style="background: #dc3545; color: white; margin-left: 0.5rem;"),
                                    style="display: flex; gap: 0.5rem; justify-content: flex-end;"
                                ),
                                action=f"/shelf/{shelf.slug}/delete",
                                method="post"
                            ),
                            cls="modal-content",
                            style="background: white; padding: 2rem; border-radius: 0.5rem; max-width: 500px; width: 90%;"
                        ),
                        cls="modal-overlay",
                        style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; z-index: 1000;",
                        onclick="event.target === this && hideDeleteModal()"
                    ),
                    id="delete-modal"
                )
            )
            
            # Add JavaScript for delete modal
            content.append(
                Script(f"""
                function showDeleteModal(shelfName) {{
                    document.getElementById('delete-modal').style.display = 'flex';
                    window.expectedShelfName = shelfName;
                }}
                
                function hideDeleteModal() {{
                    document.getElementById('delete-modal').style.display = 'none';
                    document.getElementById('delete-confirmation').value = '';
                    document.getElementById('delete-confirm-btn').disabled = true;
                }}
                
                function validateDeleteInput(value) {{
                    const confirmBtn = document.getElementById('delete-confirm-btn');
                    if (value === window.expectedShelfName) {{
                        confirmBtn.disabled = false;
                    }} else {{
                        confirmBtn.disabled = true;
                    }}
                }}
                """)
            )
        
        return (
            Title(f"Manage: {shelf.name} - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(*content)
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            )
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
        permissions = list(db_tables['permissions']("bookshelf_id=?", (shelf.id,)))
        members = []
        pending_members = []
        
        # Add owner to members list
        try:
            owner = db_tables['users'][shelf.owner_did]
            members.append({
                'user': owner,
                'permission': type('obj', (object,), {'role': 'owner', 'status': 'active'})()
            })
        except:
            pass
        
        # Add other members
        for perm in permissions:
            try:
                user = db_tables['users'][perm.user_did]
                member_data = {'user': user, 'permission': perm}
                
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
                pending_members=pending_members,
                invites=invites,
                can_manage=can_manage,
                can_generate_invites=can_generate,
                req=req
            )
        ]
        
        return (
            Title(f"Share: {shelf.name} - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(*content)
        )
        
    except Exception as e:
        return (
            Title("Error - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(auth),
            Container(
                H1("Error"),
                P(f"An error occurred: {str(e)}"),
                A("← Back to Home", href="/")
            )
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
        )
    
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

@rt("/api/shelf/{slug}/member/{member_did}/role", methods=["POST"])
def update_member_role(slug: str, member_did: str, role: str, auth):
    """HTMX endpoint to update a member's role."""
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
        if not can_invite_role(manager_role, role):
            return Div(f"You cannot assign the role '{role}'.", cls="error")
        
        # Update the permission
        db_tables['permissions'].update({'role': role}, f"bookshelf_id={shelf.id} AND user_did='{member_did}'")
        
        # Return the updated member card
        member_user = db_tables['users'][member_did]
        permission = db_tables['permissions']("bookshelf_id=? AND user_did=?", (shelf.id, member_did))[0]
        return MemberCard(member_user, permission, can_manage=True, bookshelf_slug=slug)
        
    except Exception as e:
        logger.error(f"Error updating role for member {member_did} on shelf {slug}: {e}", exc_info=True)
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

@rt("/api/shelf/{slug}/member/{member_did}/approve", methods=["POST"])
def approve_member(slug: str, member_did: str, auth):
    """HTMX endpoint to approve a pending member."""
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
def update_shelf(slug: str, name: str, description: str, privacy: str, auth, sess):
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
            'updated_at': datetime.now()
        }
        
        db_tables['bookshelves'].update(update_data, shelf.id)
        sess['success'] = "Bookshelf updated successfully!"
        return RedirectResponse(f'/shelf/{shelf.slug}/manage', status_code=303)
        
    except Exception as e:
        sess['error'] = f"Error updating bookshelf: {str(e)}"
        return RedirectResponse(f'/shelf/{slug}/manage', status_code=303)

@rt("/shelf/{slug}/delete", methods=["POST"])
def delete_shelf(slug: str, auth, sess):
    """Handle bookshelf deletion."""
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

serve()
