"""Database models for BookdIt using FastLite."""

from fastlite import *
from datetime import datetime
from typing import Optional
import secrets
import string

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
    name: str
    owner_did: str
    slug: str = ""  # URL-friendly identifier
    description: str = ""
    privacy: str = "public"  # 'public', 'link-only', 'private'
    created_at: datetime = None
    updated_at: datetime = None

class Book:
    """Book model with metadata from external APIs."""
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
    users = db.create(User, pk='did')
    bookshelves = db.create(Bookshelf)
    books = db.create(Book)
    permissions = db.create(Permission)
    upvotes = db.create(Upvote, pk=['book_id', 'user_did'])
    
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
        perm = db_tables['permissions'].where(
            bookshelf_id=bookshelf.id, 
            user_did=user_did
        ).first()
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
