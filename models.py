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
    upvotes: int = 0

class Permission:
    """Permission model for role-based access to bookshelves."""
    id: int = None  # Auto-incrementing primary key
    bookshelf_id: int
    user_did: str
    role: str  # 'admin', 'editor', 'viewer'
    granted_by_did: str
    granted_at: datetime = None

class Upvote:
    """Track user upvotes on books."""
    book_id: int
    user_did: str
    created_at: datetime = None

def setup_database(db_path: str = 'data/bookdit.db'):
    """Initialize the database with all tables."""
    db = database(db_path)
    
    # Create tables with appropriate primary keys
    users = db.create(User, pk='did', transform=True)
    bookshelves = db.create(Bookshelf, transform=True)
    books = db.create(Book, transform=True)
    permissions = db.create(Permission, transform=True)
    upvotes = db.create(Upvote, pk=['book_id', 'user_did'], transform=True)
    
    return {
        'db': db,
        'users': users,
        'bookshelves': bookshelves,
        'books': books,
        'permissions': permissions,
        'upvotes': upvotes
    }

def check_permission(bookshelf, user_did: str, required_roles: list[str], db_tables) -> bool:
    """Check if user has required permission for a bookshelf."""
    if not user_did:
        return bookshelf.privacy == 'public'
    
    # Owner always has all permissions
    if bookshelf.owner_did == user_did:
        return True
    
    # Check explicit permissions
    try:
        perm = db_tables['permissions']("bookshelf_id=? AND user_did=?", (bookshelf.id, user_did)).first()
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
        return check_permission(bookshelf, user_did, ['admin', 'editor', 'viewer'], db_tables)

def can_edit_bookshelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can edit a bookshelf."""
    return check_permission(bookshelf, user_did, ['admin', 'editor'], db_tables)

def can_admin_bookshelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can admin a bookshelf."""
    return check_permission(bookshelf, user_did, ['admin'], db_tables)

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
    
    return Card(
        Div(cover, cls="book-cover-container"),
        Div(
            H4(self.title, cls="book-title"),
            P(self.author, cls="book-author") if self.author else None,
            description,
            Div(f"👍 {self.upvotes}", cls="upvote-count"),
            cls="book-info"
        ),
        cls="book-card",
        id=f"book-{self.id}"
    )

@patch
def as_interactive_card(self: Book, can_upvote=False, user_has_upvoted=False):
    """Render Book as a card with upvote functionality."""
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
    
    if can_upvote:
        # Show different text based on whether user has upvoted
        btn_text = f"👎 Remove Vote ({self.upvotes})" if user_has_upvoted else f"👍 Upvote ({self.upvotes})"
        upvote_btn = Button(
            btn_text,
            hx_post=f"/book/{self.id}/upvote",
            hx_target=f"#book-{self.id}",
            hx_swap="outerHTML",
            cls="upvote-btn" + (" upvoted" if user_has_upvoted else "")
        )
    else:
        upvote_btn = Div(f"👍 {self.upvotes}", cls="upvote-count")
    
    return Card(
        Div(cover, cls="book-cover-container"),
        Div(
            H4(self.title, cls="book-title"),
            P(self.author, cls="book-author") if self.author else None,
            description,
            Div(upvote_btn, cls="book-actions"),
            cls="book-info"
        ),
        cls="book-card",
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
