"""Main FastHTML application for BookdIt."""

from fasthtml.common import *
from models import setup_database, can_view_bookshelf, can_edit_bookshelf, can_admin_bookshelf
from api_clients import BookAPIClient
from components import *
import os
from datetime import datetime
from dotenv import load_dotenv
from auth import BlueskyAuth, get_current_user_did, auth_beforeware

load_dotenv()

# Initialize database
db_tables = setup_database()

# Initialize external services
bluesky_auth = BlueskyAuth()
book_api = BookAPIClient()

# Custom CSS for the application
app_css = """
/* Main Navigation */
.main-nav {
    background: var(--primary);
    padding: 1rem 0;
    margin-bottom: 2rem;
}

.nav-container {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 1rem;
}

.logo {
    font-size: 1.5rem;
    font-weight: bold;
    color: white;
    text-decoration: none;
}

.user-menu {
    display: flex;
    gap: 1rem;
    align-items: center;
    color: white;
}

.user-menu a {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: 0.25rem;
    transition: background-color 0.2s;
}

.user-menu a:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

/* Bookshelf Grid */
.bookshelf-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.bookshelf-card {
    border: 1px solid var(--muted-border-color);
    border-radius: 0.5rem;
    padding: 1.5rem;
    transition: box-shadow 0.2s;
}

.bookshelf-card:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

/* Book Grid */
.book-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.book-card {
    border: 1px solid var(--muted-border-color);
    border-radius: 0.5rem;
    overflow: hidden;
    transition: transform 0.2s;
}

.book-card:hover {
    transform: translateY(-2px);
}

.book-cover-container {
    height: 250px;
    overflow: hidden;
}

.book-cover {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.book-cover-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--muted-color);
    font-size: 3rem;
}

.book-info {
    padding: 1rem;
}

.book-title {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    line-height: 1.3;
}

.book-author {
    margin: 0 0 0.5rem 0;
    color: var(--muted-color);
    font-size: 0.9rem;
}

.book-description {
    margin: 0 0 1rem 0;
    font-size: 0.8rem;
    color: var(--muted-color);
    line-height: 1.4;
}

.upvote-btn {
    background: none;
    border: 1px solid var(--muted-border-color);
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    cursor: pointer;
    font-size: 0.8rem;
}

.upvote-btn:hover:not(:disabled) {
    background: var(--primary);
    color: white;
}

.upvote-btn.upvoted {
    background: var(--primary);
    color: white;
}

/* Search Results */
.search-results {
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid var(--muted-border-color);
    border-radius: 0.5rem;
    margin-top: 1rem;
}

.search-result-card {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border-bottom: 1px solid var(--muted-border-color);
}

.search-result-card:last-child {
    border-bottom: none;
}

.search-result-cover-container {
    flex-shrink: 0;
    width: 80px;
    height: 120px;
}

.search-result-cover {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 0.25rem;
}

.cover-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--muted-color);
    border-radius: 0.25rem;
    font-size: 2rem;
}

.search-result-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.add-book-btn {
    align-self: flex-start;
    margin-top: auto;
}

/* Alerts */
.alert {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
}

.alert-error {
    background: #fee;
    border: 1px solid #fcc;
    color: #c33;
}

.alert-success {
    background: #efe;
    border: 1px solid #cfc;
    color: #363;
}

.alert-info {
    background: #eef;
    border: 1px solid #ccf;
    color: #336;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--muted-color);
}

/* Loading */
.loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem;
    font-size: 0.9rem;
    color: var(--muted-color);
}

.spinner {
    width: 1.5rem;
    height: 1.5rem;
    border: 2px solid var(--muted-border-color);
    border-top: 2px solid var(--primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Search form improvements */
.search-form {
    margin-bottom: 1rem;
}

.search-form input {
    width: 100%;
    margin-bottom: 0.5rem;
}

/* HTMX indicator styling */
.htmx-indicator {
    opacity: 0;
    transition: opacity 0.3s ease-in-out;
}

.htmx-request .htmx-indicator {
    opacity: 1;
}

.htmx-request.htmx-indicator {
    opacity: 1;
}

/* Responsive */
@media (max-width: 768px) {
    .nav-container {
        flex-direction: column;
        gap: 1rem;
    }
    
    .user-menu {
        flex-wrap: wrap;
        justify-content: center;
    }
    
    .bookshelf-grid,
    .book-grid {
        grid-template-columns: 1fr;
    }
    
    .search-result-card {
        flex-direction: column;
    }
    
    .search-result-cover-container {
        width: 100px;
        height: 150px;
        align-self: center;
    }
}
"""

# Beforeware function that includes database tables
def before_handler(req, sess):
    return auth_beforeware(req, sess, db_tables)

# Initialize FastHTML app
app, rt = fast_app(
    before=Beforeware(before_handler, skip=[r'/static/.*', r'/favicon\.ico']),
    hdrs=(
        picolink,
        Style(app_css),
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
    """Homepage - shows public shelves or user's shelves if logged in."""

    bookshelves = db_tables['bookshelves']

    if not auth:
        # Show public bookshelves for anonymous users
        public_shelves = bookshelves(where="privacy='public'", limit=12)    
        content = [
            H1("Welcome to BookdIt! 📚"),
            P("Discover and share amazing book collections from the community."),
            Div(*public_shelves, cls="bookshelf-grid") if public_shelves else EmptyState(
                "No public bookshelves yet",
                "Be the first to create and share a bookshelf!",
                "Get Started",
                "/auth/login"
            )
        ]
    else:
        # Show user's bookshelves
        current_auth_did = get_current_user_did(auth)
        print(f"Current user DID: {current_auth_did}")
        # Use parameterized query to handle DIDs with colons safely
        user_shelves = bookshelves("owner_did=?", (current_auth_did,), limit=12)

        content = [
            Div(
                H1(f"Welcome back, {auth.get('display_name', auth['handle'])}! 👋"),
                A("Create New Shelf", href="/shelf/new", cls="primary"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
            ),
            Div(*[BookshelfCard(shelf, is_owner=True, can_edit=True) for shelf in user_shelves], cls="bookshelf-grid") if user_shelves else EmptyState(
                "You haven't created any bookshelves yet",
                "Start building your first collection of books!",
                "Create Your First Shelf",
                "/shelf/new"
            )
        ]
    
    return NavBar(auth), Container(*content)

# Authentication routes
@app.get("/auth/login")
def login_page(sess):
    """Display login form."""
    error_msg = sess.pop('error', None)
    return NavBar(), bluesky_auth.create_login_form(error_msg)

@app.post("/auth/login")
async def login_handler(handle: str, password: str, sess):
    """Handle login form submission."""
    print(f"Login attempt - Handle: {handle}, Password length: {len(password) if password else 0}")
    
    user_data = await bluesky_auth.authenticate_user(handle, password)
    print(f"Authentication result: {user_data is not None}")
    
    if user_data:
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
            print("New user created in database")
        except:
            # User already exists, update their info and last login
            update_data = {
                'handle': user_data['handle'],
                'display_name': user_data['display_name'],
                'avatar_url': user_data['avatar_url'],
                'last_login': datetime.now()
            }
            db_tables['users'].update(update_data, user_data['did'])
            print("Existing user updated in database")
        
        # Store full auth data (including JWTs) in session
        sess['auth'] = user_data
        print(f"User authenticated successfully: {user_data['handle']}")
        return RedirectResponse('/', status_code=303)
    else:
        print("Authentication failed")
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
    
    return NavBar(auth), Container(
        H1("Create New Bookshelf"),
        CreateBookshelfForm()
    )

@rt("/shelf/create", methods=["POST"])
def create_shelf(name: str, description: str, privacy: str, auth, sess):
    """Handle bookshelf creation."""
    if not auth:
        return RedirectResponse('/auth/login', status_code=303)
    
    try:
        from models import Bookshelf, generate_slug
        from datetime import datetime
        
        shelf = Bookshelf(
            name=name.strip(),
            slug=generate_slug(),
            description=description.strip(),
            owner_did=auth['did'],
            privacy=privacy,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        created_shelf = db_tables['bookshelves'].insert(shelf)
        return RedirectResponse(f'/shelf/{created_shelf.slug}', status_code=303)
    except Exception as e:
        sess['error'] = f"Error creating bookshelf: {str(e)}"
        return RedirectResponse('/shelf/new', status_code=303)

@rt("/shelf/{slug}")
def view_shelf(slug: str, auth):
    """Display a bookshelf."""
    try:
        shelf = db_tables['bookshelves']("slug=?", (slug,))[0] if db_tables['bookshelves']("slug=?", (slug,)) else None
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
        
        can_edit = can_edit_bookshelf(shelf, user_did, db_tables)
        
        # Get books in this shelf that have at least 1 upvote
        shelf_books = list(db_tables['books']("bookshelf_id=? AND upvotes > 0", (shelf.id,)))
        
        # Check which books user has upvoted
        user_upvotes = set()
        if user_did:
            upvotes = db_tables['upvotes']("user_did=?", (user_did,))
            user_upvotes = {upvote.book_id for upvote in upvotes}
        
        content = [
            Div(
                Div(
                    H1(shelf.name),
                    P(shelf.description) if shelf.description else None,
                    P(f"Privacy: {shelf.privacy.replace('-', ' ').title()}", cls="muted")
                ),
                Div(
                    A("Edit Shelf", href=f"/shelf/{shelf.slug}/edit", cls="secondary") if can_edit else None,
                    style="text-align: right;"
                ) if can_edit else None,
                style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;"
            )
        ]
        
        if can_edit:
            content.append(BookSearchForm(shelf.id))
        
        # Always include the book-grid div, even when empty
        if shelf_books:
            book_grid_content = [BookCard(book, can_upvote=can_edit, user_has_upvoted=book.id in user_upvotes) 
                               for book in shelf_books]
        else:
            book_grid_content = [
                Div(
                    EmptyState(
                        "No books yet",
                        "This bookshelf is waiting for its first book!" if can_edit else "This bookshelf doesn't have any books yet.",
                        "Add a Book" if can_edit else None,
                        "#" if can_edit else None
                    ),
                    id="empty-state-container"
                )
            ]
        
        content.append(
            Div(
                *book_grid_content,
                cls="book-grid",
                id="book-grid"
            )
        )
        
        return NavBar(auth), Container(*content)
        
    except Exception as e:
        return NavBar(auth), Container(
            H1("Error"),
            P(f"An error occurred: {str(e)}"),
            A("← Back to Home", href="/")
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
        # Check if user can edit this bookshelf
        shelf = db_tables['bookshelves'][bookshelf_id]
        if not can_edit_bookshelf(shelf, get_current_user_did(auth), db_tables):
            return Div("You don't have permission to add books to this shelf.", cls="search-message")
        
        print(f"Searching for books with query: '{query.strip()}'")
        results = await book_api.search_books(query.strip(), max_results=8)
        
        if results:
            print(f"Found {len(results)} books")
            return Div(
                *[SearchResultCard(book, bookshelf_id) for book in results],
                cls="search-results-list"
            )
        else:
            print("No books found")
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
        print(f"Search error: {e}")
        return Div(f"Search error: {str(e)}", cls="search-message")

@rt("/api/add-book", methods=["POST"])
def add_book_api(bookshelf_id: int, title: str, author: str, isbn: str, description: str, 
                cover_url: str, publisher: str, published_date: str, page_count: int, auth):
    """HTMX endpoint to add a book to a bookshelf."""
    if not auth:
        return Div("Authentication required.", cls="error")
    
    try:
        # Check permissions
        shelf = db_tables['bookshelves'][bookshelf_id]
        if not can_edit_bookshelf(shelf, get_current_user_did(auth), db_tables):
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
                                                     (existing_book.id, user_did)).first()
            except:
                pass
            
            if existing_upvote:
                # User has already voted for this book
                return Div("You've already added this book to the shelf!", cls="alert alert-info")
            else:
                # Add user's vote to existing book
                from models import Upvote
                upvote = Upvote(
                    book_id=existing_book.id,
                    user_did=user_did,
                    created_at=datetime.now()
                )
                db_tables['upvotes'].insert(upvote)
                
                # Update vote count
                new_vote_count = existing_book.upvotes + 1
                db_tables['books'].update({'upvotes': new_vote_count}, existing_book.id)
                
                # Get updated book and return it
                updated_book = db_tables['books'][existing_book.id]
                return BookCard(updated_book, can_upvote=True, user_has_upvoted=True)
        else:
            # Create new book with initial upvote count of 1
            from models import Book, Upvote
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
                added_by_did=user_did,
                added_at=datetime.now(),
                upvotes=1  # Start with 1 upvote from the person who added it
            )
            
            created_book = db_tables['books'].insert(book)
            
            # Create the initial upvote record from the person who added the book
            upvote = Upvote(
                book_id=created_book.id,
                user_did=user_did,
                created_at=datetime.now()
            )
            db_tables['upvotes'].insert(upvote)
            
            # Return the book card showing the user has already upvoted
            return BookCard(created_book, can_upvote=True, user_has_upvoted=True)
        
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
            existing_upvote = db_tables['upvotes']("book_id=? AND user_did=?", (book_id, user_did)).first()
            if existing_upvote:
                # Remove upvote (downvote)
                db_tables['upvotes'].delete((book_id, user_did))
                new_vote_count = book.upvotes - 1
                
                # Update vote count in database
                db_tables['books'].update({'upvotes': new_vote_count}, book_id)
                
                # If votes reach 0, hide book from view (return empty response)
                if new_vote_count <= 0:
                    print(f"Book '{book.title}' hidden from shelf due to 0 votes")
                    return ""
                else:
                    # Return updated card
                    updated_book = db_tables['books'][book_id]
                    return BookCard(updated_book, can_upvote=True, user_has_upvoted=False)
            else:
                # Add upvote
                from models import Upvote
                upvote = Upvote(book_id=book_id, user_did=user_did, created_at=datetime.now())
                db_tables['upvotes'].insert(upvote)
                db_tables['books'].update({'upvotes': book.upvotes + 1}, book_id)
                updated_book = db_tables['books'][book_id]
                return BookCard(updated_book, can_upvote=True, user_has_upvoted=True)
        except:
            # Add upvote (first time)
            from models import Upvote
            upvote = Upvote(book_id=book_id, user_did=user_did, created_at=datetime.now())
            db_tables['upvotes'].insert(upvote)
            db_tables['books'].update({'upvotes': book.upvotes + 1}, book_id)
            updated_book = db_tables['books'][book_id]
            return BookCard(updated_book, can_upvote=True, user_has_upvoted=True)
            
    except Exception as e:
        return Div(f"Error: {str(e)}", cls="error")

serve()
