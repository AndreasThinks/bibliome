"""Main FastHTML application for Bibliome."""

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


# Beforeware function that includes database tables
def before_handler(req, sess):
    return auth_beforeware(req, sess, db_tables)

# Initialize FastHTML app
app, rt = fast_app(
    before=Beforeware(before_handler, skip=[r'/static/.*', r'/favicon\.ico']),
    # htmlkw={'data-theme':'light'},
    hdrs=(
        picolink,
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

    bookshelves = db_tables['bookshelves']

    if not auth:
        # Show beautiful landing page for anonymous users
        public_shelves = bookshelves(where="privacy='public'", limit=12)
        
        return (
            NavBar(auth),
            LandingPageHero(),
            FeaturesSection(),
            HowItWorksSection(),
            PublicShelvesPreview(public_shelves),
            LandingPageFooter()
        )
    else:
        # Show user's dashboard
        current_auth_did = get_current_user_did(auth)
        print(f"Current user DID: {current_auth_did}")
        # Use parameterized query to handle DIDs with colons safely
        user_shelves = bookshelves("owner_did=?", (current_auth_did,), limit=12)

        content = [
            Div(
                H1(f"Welcome back, {auth.get('display_name', auth['handle'])}! 👋"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
            ),
            Div(*[BookshelfCard(shelf, is_owner=True, can_edit=True) for shelf in user_shelves], cls="bookshelf-grid") if user_shelves else EmptyState(
                "You haven't created any bookshelves yet",
                "Start building your first collection of books!",
                "Create Your First Shelf",
                "/shelf/new"
            )
        ]
        
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
        
        # Get books with upvote counts using the new helper function
        from models import get_books_with_upvotes
        shelf_books = get_books_with_upvotes(shelf.id, user_did, db_tables)
        
        # Import the new permission functions
        from models import can_manage_members, can_generate_invites
        can_manage = can_manage_members(shelf, user_did, db_tables)
        can_share = can_generate_invites(shelf, user_did, db_tables)
        
        # Build action buttons
        action_buttons = []
        if can_edit or can_share:
            action_buttons.append(A("Manage", href=f"/shelf/{shelf.slug}/manage", cls="secondary"))
        
        content = [
            Div(
                Div(
                    H1(shelf.name),
                    P(shelf.description) if shelf.description else None,
                    P(f"Privacy: {shelf.privacy.replace('-', ' ').title()}", cls="muted")
                ),
                Div(
                    *action_buttons,
                    style="display: flex; gap: 0.5rem; text-align: right;"
                ) if action_buttons else None,
                style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;"
            )
        ]
        
        if can_edit:
            content.append(BookSearchForm(shelf.id))
        
        # Always include the book-grid div, even when empty
        if shelf_books:
            book_grid_content = [BookCard(book, can_upvote=can_edit, user_has_upvoted=book.user_has_upvoted) 
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
                                                     (existing_book.id, user_did))[0]
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
                
                # Get updated book with vote count and return it
                existing_book.upvote_count = len(db_tables['upvotes']("book_id=?", (existing_book.id,)))
                existing_book.user_has_upvoted = True
                return existing_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=existing_book.upvote_count)
        else:
            # Create new book (no upvotes field needed)
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
            
            # Set the computed attributes and return the book card
            created_book.upvote_count = 1
            created_book.user_has_upvoted = True
            return created_book.as_interactive_card(can_upvote=True, user_has_upvoted=True, upvote_count=1)
        
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
                    print(f"Book '{book.title}' hidden from shelf due to 0 votes")
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

# Management routes
@rt("/shelf/{slug}/manage")
def manage_shelf(slug: str, auth):
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
                        can_generate_invites=can_generate
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
def share_shelf(slug: str, auth):
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
                can_generate_invites=can_generate
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
