"""Database models for BookdIt using FastLite."""

from fastlite import *
from datetime import datetime
from typing import Optional
import secrets
import string
from fasthtml.common import *
from fastcore.all import patch

def generate_slug():
    """Generate a random URL-safe slug."""
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))

# FastLite style classes - automatically converted to flexiclasses
class User:
    """User model for Bluesky/AT-Proto users."""
    did: str  # Bluesky DID (Decentralized Identifier) - primary key
    handle: str
    display_name: str = ""
    avatar_url: str = ""
    created_at: datetime = None
    last_login: datetime = None

class Bookshelf:
    """Bookshelf model for organizing books."""
    id: int = None  # Auto-incrementing primary key
    name: str
    owner_did: str
    slug: str = ""  # URL-friendly identifier
    description: str = ""
    privacy: str = "public"  # 'public', 'link-only', 'private'
    created_at: datetime = None
    updated_at: datetime = None

class Book:
    """Book model with metadata from external APIs."""
    id: int = None  # Auto-incrementing primary key
    bookshelf_id: int
    title: str
    added_by_did: str
    isbn: str = ""
    author: str = ""
    cover_url: str = ""
    description: str = ""
    publisher: str = ""
    published_date: str = ""
    page_count: int = 0
    added_at: datetime = None

class Permission:
    """Permission model for role-based access to bookshelves."""
    id: int = None  # Auto-incrementing primary key
    bookshelf_id: int
    user_did: str
    role: str  # 'viewer', 'contributor', 'moderator', 'owner'
    status: str = "active"  # 'active', 'pending'
    granted_by_did: str
    granted_at: datetime = None
    invited_at: datetime = None
    joined_at: datetime = None

class BookshelfInvite:
    """Invitation model for sharing bookshelves."""
    id: int = None  # Auto-incrementing primary key
    bookshelf_id: int
    invite_code: str  # Unique random string
    role: str  # Role to assign when invite is redeemed
    created_by_did: str
    created_at: datetime = None
    expires_at: datetime = None  # Optional expiration
    max_uses: int = None  # Optional usage limit
    uses_count: int = 0
    is_active: bool = True

class Upvote:
    """Track user upvotes on books."""
    book_id: int
    user_did: str
    created_at: datetime = None

class Activity:
    """Track user activity for social feed."""
    id: int = None  # Auto-incrementing primary key
    user_did: str
    activity_type: str  # 'bookshelf_created', 'book_added'
    bookshelf_id: int = None
    book_id: int = None
    created_at: datetime = None
    # JSON field for additional metadata
    metadata: str = ""  # JSON string for flexible data

def setup_database(db_path: str = 'data/bookdit.db'):
    """Initialize the database with all tables."""
    db = database(db_path)
    
    # Create tables with appropriate primary keys
    users = db.create(User, pk='did', transform=True)
    bookshelves = db.create(Bookshelf, transform=True)
    books = db.create(Book, transform=True)
    permissions = db.create(Permission, transform=True)
    bookshelf_invites = db.create(BookshelfInvite, transform=True)
    upvotes = db.create(Upvote, pk=['book_id', 'user_did'], transform=True)
    activities = db.create(Activity, transform=True)
    
    return {
        'db': db,
        'users': users,
        'bookshelves': bookshelves,
        'books': books,
        'permissions': permissions,
        'bookshelf_invites': bookshelf_invites,
        'upvotes': upvotes,
        'activities': activities
    }

def generate_invite_code():
    """Generate a secure random invite code."""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))

def check_permission(bookshelf, user_did: str, required_roles: list[str], db_tables) -> bool:
    """Check if user has required permission for a bookshelf."""
    if not user_did:
        return bookshelf.privacy == 'public'
    
    # Owner always has all permissions
    if bookshelf.owner_did == user_did:
        return True
    
    # Check explicit permissions (only active permissions)
    try:
        perm = db_tables['permissions']("bookshelf_id=? AND user_did=? AND status='active'", (bookshelf.id, user_did))[0]
        return perm and perm.role in required_roles
    except:
        return False

def can_view_bookshelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can view a bookshelf."""
    if bookshelf.privacy == 'public':
        return True
    elif bookshelf.privacy == 'link-only':
        return True  # Anyone with the link can view
    else:  # private
        return check_permission(bookshelf, user_did, ['viewer', 'contributor', 'moderator', 'owner'], db_tables)

def can_add_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can add books and vote (contributor, moderator, owner)."""
    return check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables)

def can_vote_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can vote on books (contributor, moderator, owner)."""
    return check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables)

def can_remove_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can remove books (moderator, owner)."""
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_edit_bookshelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can edit bookshelf details (moderator, owner)."""
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_manage_members(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can manage members (moderator with limits, owner full access)."""
    if not user_did:
        return False
    return bookshelf.owner_did == user_did or check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_generate_invites(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can generate invites (moderator, owner)."""
    if not user_did:
        return False
    
    # Owner can always generate invites
    if bookshelf.owner_did == user_did:
        return True
    
    # Moderators can generate invites
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_delete_shelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can delete the entire bookshelf (owner only)."""
    if not user_did:
        return False
    return bookshelf.owner_did == user_did

def get_user_role(bookshelf, user_did: str, db_tables) -> str:
    """Get the user's role for a bookshelf."""
    if not user_did:
        return None
    
    # Check if owner
    if bookshelf.owner_did == user_did:
        return 'owner'
    
    # Check explicit permissions
    try:
        perm = db_tables['permissions']("bookshelf_id=? AND user_did=? AND status='active'", (bookshelf.id, user_did))[0]
        return perm.role if perm else None
    except:
        return None

def can_invite_role(inviter_role: str, target_role: str) -> bool:
    """Check if a user with inviter_role can invite someone with target_role."""
    role_hierarchy = ['viewer', 'contributor', 'moderator', 'owner']
    
    if inviter_role not in role_hierarchy or target_role not in role_hierarchy:
        return False
    
    inviter_level = role_hierarchy.index(inviter_role)
    target_level = role_hierarchy.index(target_role)
    
    # Moderators can invite up to moderator level
    if inviter_role == 'moderator':
        return target_level <= 2  # viewer, contributor, moderator
    
    # Owners can invite anyone
    if inviter_role == 'owner':
        return True
    
    return False

def validate_invite(invite_code: str, db_tables) -> Optional[object]:
    """Validate an invite code and return the invite if valid."""
    try:
        invite = db_tables['bookshelf_invites']("invite_code=? AND is_active=1", (invite_code,))[0]
        if not invite:
            return None
        
        # Check if expired
        if invite.expires_at and datetime.now() > invite.expires_at:
            return None
        
        # Check if max uses reached
        if invite.max_uses and invite.uses_count >= invite.max_uses:
            return None
        
        return invite
    except:
        return None

def get_books_with_upvotes(bookshelf_id: int, user_did: str = None, db_tables=None):
    """Get books for a bookshelf with upvote counts and user voting status using MiniDataAPI."""
    if not db_tables:
        return []
    
    try:
        # Get all books for this bookshelf
        all_books = db_tables['books']("bookshelf_id=?", (bookshelf_id,))
        
        books_with_votes = []
        for book in all_books:
            # Count upvotes for this book
            upvote_count = len(db_tables['upvotes']("book_id=?", (book.id,)))
            
            # Skip books with no upvotes
            if upvote_count == 0:
                continue
            
            # Check if current user has upvoted this book
            user_has_upvoted = False
            if user_did:
                user_upvote = db_tables['upvotes']("book_id=? AND user_did=?", (book.id, user_did))[0]
                user_has_upvoted = user_upvote is not None
            
            # Add computed attributes to the book object
            book.upvote_count = upvote_count
            book.user_has_upvoted = user_has_upvoted
            
            books_with_votes.append(book)
        
        # Sort by upvote count (descending) then by title
        books_with_votes.sort(key=lambda b: (-b.upvote_count, b.title))
        
        return books_with_votes
    except Exception as e:
        print(f"Error getting books with upvotes: {e}")
        return []

def log_activity(user_did: str, activity_type: str, db_tables, bookshelf_id: int = None, book_id: int = None, metadata: str = ""):
    """Log user activity for the social feed."""
    try:
        activity = Activity(
            user_did=user_did,
            activity_type=activity_type,
            bookshelf_id=bookshelf_id,
            book_id=book_id,
            created_at=datetime.now(),
            metadata=metadata
        )
        db_tables['activities'].insert(activity)
    except Exception as e:
        print(f"Error logging activity: {e}")

async def get_network_activity(auth_data: dict, db_tables, bluesky_auth, limit: int = 20):
    """Get recent activity from users in the current user's network."""
    try:
        # Get list of users the current user follows
        following_dids = await bluesky_auth.get_following_list(auth_data, limit=100)
        
        if not following_dids:
            return []
        
        # Get recent activities from followed users
        # Only show activities for public/link-only shelves
        activities = []
        
        # Build query to get activities from followed users
        placeholders = ','.join(['?' for _ in following_dids])
        query = f"""
            SELECT a.*, b.name as bookshelf_name, b.slug as bookshelf_slug, b.privacy,
                   bk.title as book_title, bk.author as book_author, bk.cover_url as book_cover_url
            FROM activities a
            LEFT JOIN bookshelves b ON a.bookshelf_id = b.id
            LEFT JOIN books bk ON a.book_id = bk.id
            WHERE a.user_did IN ({placeholders})
            AND (b.privacy = 'public' OR b.privacy = 'link-only')
            ORDER BY a.created_at DESC
            LIMIT ?
        """
        
        # Execute raw SQL query
        cursor = db_tables['db'].execute(query, following_dids + [limit])
        raw_activities = cursor.fetchall()
        
        # Get profiles for the users who created these activities
        activity_user_dids = list(set([row[1] for row in raw_activities]))  # user_did is column 1
        profiles = await bluesky_auth.get_profiles_batch(activity_user_dids)
        
        # Format activities with user profiles
        for row in raw_activities:
            activity_data = {
                'id': row[0],
                'user_did': row[1],
                'activity_type': row[2],
                'bookshelf_id': row[3],
                'book_id': row[4],
                'created_at': row[5],
                'metadata': row[6],
                'bookshelf_name': row[7],
                'bookshelf_slug': row[8],
                'bookshelf_privacy': row[9],
                'book_title': row[10],
                'book_author': row[11],
                'book_cover_url': row[12],
                'user_profile': profiles.get(row[1], {
                    'handle': 'unknown',
                    'display_name': 'Unknown User',
                    'avatar_url': ''
                })
            }
            activities.append(activity_data)
        
        return activities
        
    except Exception as e:
        print(f"Error getting network activity: {e}")
        return []

# FT rendering methods for models
@patch
def __ft__(self: Bookshelf):
    """Render a Bookshelf as a Card component."""
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗', 
        'private': '🔒'
    }.get(self.privacy, '🌍')
    
    return Card(
        H3(self.name),
        P(f"{privacy_icon} {self.privacy.replace('-', ' ').title()}", cls="privacy-badge"),
        P(self.description) if self.description else None,
        footer=A("View Shelf", href=f"/shelf/{self.slug}", cls="primary")
    )

@patch
def __ft__(self: Book):
    """Render a Book as a Card component (basic version without upvote functionality)."""
    # Generate Google Books URL
    if self.isbn:
        google_books_url = f"https://books.google.com/books?isbn={self.isbn}"
    else:
        # Fallback to search query if no ISBN
        search_query = f"{self.title} {self.author}".replace(" ", "+")
        google_books_url = f"https://books.google.com/books?q={search_query}"
    
    cover = Img(
        src=self.cover_url,
        alt=f"Cover of {self.title}",
        cls="book-cover",
        loading="lazy"
    ) if self.cover_url else Div("📖", cls="book-cover-placeholder")
    
    description = P(
        self.description[:100] + "..." if len(self.description) > 100 else self.description,
        cls="book-description"
    ) if self.description else None
    
    # Note: upvote count should be passed from the calling code since it's no longer stored in the book
    upvote_count = getattr(self, 'upvote_count', 0)
    
    return A(
        href=google_books_url,
        target="_blank",
        rel="noopener noreferrer"
    )(
        Card(
            Div(cover, cls="book-cover-container"),
            Div(
                H4(self.title, cls="book-title"),
                P(self.author, cls="book-author") if self.author else None,
                description,
                Div(f"👍 {upvote_count}", cls="upvote-count"),
                cls="book-info"
            ),
            cls="book-card clickable-book",
            id=f"book-{self.id}"
        )
    )

@patch
def as_interactive_card(self: Book, can_upvote=False, user_has_upvoted=False, upvote_count=0, can_remove=False):
    """Render Book as a card with upvote and remove functionality."""
    # Generate Google Books URL
    if self.isbn:
        google_books_url = f"https://books.google.com/books?isbn={self.isbn}"
    else:
        # Fallback to search query if no ISBN
        search_query = f"{self.title} {self.author}".replace(" ", "+")
        google_books_url = f"https://books.google.com/books?q={search_query}"
    
    cover = Img(
        src=self.cover_url,
        alt=f"Cover of {self.title}",
        cls="book-cover",
        loading="lazy"
    ) if self.cover_url else Div("📖", cls="book-cover-placeholder")
    
    description = P(
        self.description[:100] + "..." if len(self.description) > 100 else self.description,
        cls="book-description"
    ) if self.description else None
    
    # Build action buttons
    action_buttons = []
    
    if can_upvote:
        # Show different text based on whether user has upvoted
        btn_text = f"👎 Remove Vote ({upvote_count})" if user_has_upvoted else f"👍 Upvote ({upvote_count})"
        action_buttons.append(Button(
            btn_text,
            hx_post=f"/book/{self.id}/upvote",
            hx_target=f"#book-{self.id}",
            hx_swap="outerHTML",
            cls="upvote-btn" + (" upvoted" if user_has_upvoted else ""),
            onclick="event.stopPropagation()"  # Prevent card click when upvoting
        ))
    else:
        action_buttons.append(Div(f"👍 {upvote_count}", cls="upvote-count"))
    
    if can_remove:
        # Add remove button for moderators/owners
        remove_btn_text = "🗑️ Remove"
        if upvote_count > 1:
            remove_btn_text = f"🗑️ Remove ({upvote_count} votes)"
        
        # Escape the title for JavaScript
        escaped_title = self.title.replace("'", "\\'").replace('"', '\\"')
        action_buttons.append(Button(
            remove_btn_text,
            onclick=f"confirmRemoveBook({self.id}, '{escaped_title}', {upvote_count})",
            cls="remove-btn danger",
            style="background: #dc3545; color: white; margin-left: 0.5rem;"
        ))
    
    return Card(
        Div(cover, cls="book-cover-container"),
        Div(
            H4(self.title, cls="book-title"),
            P(self.author, cls="book-author") if self.author else None,
            description,
            Div(*action_buttons, cls="book-actions"),
            cls="book-info"
        ),
        A("View on Google Books", href=google_books_url, target="_blank", rel="noopener noreferrer", cls="google-books-link"),
        cls="book-card interactive-book",
        id=f"book-{self.id}"
    )

@patch
def __ft__(self: User):
    """Render a User as a simple profile component."""
    avatar = Img(
        src=self.avatar_url, 
        alt=self.display_name or self.handle, 
        cls="avatar"
    ) if self.avatar_url else None
    
    return Div(
        avatar,
        Strong(self.display_name or self.handle),
        cls="user-profile"
    )
