"""Database models for BookdIt using FastLite."""

from fastlite import *
from datetime import datetime
from typing import Optional
import secrets
import string
from fasthtml.common import *
from fastcore.all import patch
from atproto import Client, models as at_models
from atproto_client.models.com.atproto.repo.delete_record import Data as DeleteRecordData
from atproto_client.exceptions import UnauthorizedError, BadRequestError
import logging

logger = logging.getLogger(__name__)

def create_bookshelf_record(client: Client, name: str, description: str, privacy: str) -> str:
    """Creates a bookshelf record on the user's repo and returns its AT-URI."""
    record = {
        '$type': 'com.bibliome.bookshelf',
        'name': name,
        'description': description,
        'privacy': privacy,
        'createdAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.bookshelf',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri

def add_book_record(client: Client, bookshelf_uri: str, title: str, author: str, isbn: str) -> str:
    """Creates a book record on the user's repo and returns its AT-URI."""
    record = {
        '$type': 'com.bibliome.book',
        'title': title,
        'author': author,
        'isbn': isbn,
        'bookshelfRef': bookshelf_uri,
        'addedAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.book',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri

def delete_bookshelf_record(client: Client, atproto_uri: str) -> bool:
    """
    Delete a bookshelf record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the bookshelf record to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Create the Data object for the delete_record call
        delete_data = DeleteRecordData(
            repo=repo,
            collection=collection,
            rkey=rkey
        )

        # Call the delete_record method
        logger.info(f"Deleting bookshelf record: {atproto_uri}")
        client.com.atproto.repo.delete_record(delete_data)

        logger.info(f"Successfully deleted bookshelf record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Bookshelf record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting bookshelf {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete bookshelf record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting bookshelf record {atproto_uri}: {e}")
        return False

def delete_book_record(client: Client, atproto_uri: str) -> bool:
    """
    Delete a book record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the book record to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Create the Data object for the delete_record call
        delete_data = DeleteRecordData(
            repo=repo,
            collection=collection,
            rkey=rkey
        )

        # Call the delete_record method
        logger.info(f"Deleting book record: {atproto_uri}")
        client.com.atproto.repo.delete_record(delete_data)

        logger.info(f"Successfully deleted book record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Book record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting book {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete book record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting book record {atproto_uri}: {e}")
        return False

def create_comment_record(client: Client, book_uri: str, bookshelf_uri: str, content: str) -> str:
    """Creates a comment record on the user's repo and returns its AT-URI."""
    record = {
        '$type': 'com.bibliome.comment',
        'content': content,
        'bookRef': book_uri,
        'bookshelfRef': bookshelf_uri,
        'createdAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.comment',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri

def update_comment_record(client: Client, comment_uri: str, content: str) -> str:
    """Updates a comment record on AT Protocol and returns its AT-URI."""
    try:
        # Parse the URI into components
        if not comment_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {comment_uri}")
            return ""

        parts = comment_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {comment_uri}")
            return ""

        repo, collection, rkey = parts

        # Get the existing record first to preserve other fields
        existing_record = client.com.atproto.repo.get_record(
            at_models.ComAtprotoRepoGetRecord.Params(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        # Update the record with new content and editedAt timestamp
        updated_record = existing_record.value
        updated_record['content'] = content
        updated_record['editedAt'] = client.get_current_time_iso()

        response = client.com.atproto.repo.put_record(
            at_models.ComAtprotoRepoPutRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey,
                record=updated_record
            )
        )
        return response.uri

    except Exception as e:
        logger.error(f"Error updating comment record {comment_uri}: {e}")
        return ""

def delete_comment_record(client: Client, atproto_uri: str) -> bool:
    """
    Delete a comment record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the comment record to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Create the Data object for the delete_record call
        delete_data = DeleteRecordData(
            repo=repo,
            collection=collection,
            rkey=rkey
        )

        # Call the delete_record method
        logger.info(f"Deleting comment record: {atproto_uri}")
        client.com.atproto.repo.delete_record(delete_data)

        logger.info(f"Successfully deleted comment record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Comment record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting comment {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete comment record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting comment record {atproto_uri}: {e}")
        return False

def generate_tid():
    """Generate a TID (Timestamp Identifier)."""
    import time
    import random

    chars = '234567abcdefghijklmnopqrstuvwxyz'
    
    timestamp = int(time.time() * 1_000_000)
    clock_id = random.randint(0, 1023)
    
    tid_int = (timestamp << 10) | clock_id
    
    tid_str = ''
    for _ in range(13):
        tid_str = chars[tid_int % 32] + tid_str
        tid_int //= 32
        
    return tid_str

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
    # Remote origin tracking
    is_remote: bool = False
    discovered_at: datetime = None
    last_seen_remote: datetime = None
    remote_sync_status: str = "local"

class Bookshelf:
    """Bookshelf model for organizing books."""
    id: int = None  # Auto-incrementing primary key
    name: str
    owner_did: str
    slug: str = ""  # URL-friendly identifier
    description: str = ""
    privacy: str = "public"  # 'public', 'link-only', 'private'
    self_join: bool = False  # Allow anyone to join as contributor
    atproto_uri: str = "" # AT-Proto URI of the record
    created_at: datetime = None
    updated_at: datetime = None
    # Remote origin tracking
    is_remote: bool = False
    remote_owner_did: str = ""
    discovered_at: datetime = None
    last_synced: datetime = None
    remote_sync_status: str = "local"
    original_atproto_uri: str = ""

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
    atproto_uri: str = "" # AT-Proto URI of the record
    added_at: datetime = None
    # Remote origin tracking
    is_remote: bool = False
    remote_added_by_did: str = ""
    discovered_at: datetime = None
    original_atproto_uri: str = ""
    remote_sync_status: str = "local"

class Permission:
    """Permission model for role-based access to bookshelves."""
    id: int = None  # Auto-incrementing primary key
    bookshelf_id: int
    user_did: str
    role: str  # 'viewer', 'contributor', 'moderator', 'owner'
    # UNUSED: status and invited_at fields preserved for future approval workflows
    # Currently all invites create active permissions immediately via invite links
    status: str = "active"  # 'active', 'pending' - pending status not currently used
    granted_by_did: str
    granted_at: datetime = None
    invited_at: datetime = None  # UNUSED: preserved for future direct invitation features
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


class Comment:
    """Comment model for book discussions."""
    id: int = None  # Auto-incrementing primary key
    book_id: int
    bookshelf_id: int  # Reference to bookshelf for context/permissions
    user_did: str
    content: str
    parent_comment_id: int = None  # For threaded replies
    created_at: datetime = None
    updated_at: datetime = None
    is_edited: bool = False
    # AT Protocol sync fields
    atproto_uri: str = ""
    is_remote: bool = False
    remote_user_did: str = ""
    discovered_at: datetime = None
    original_atproto_uri: str = ""
    remote_sync_status: str = "local"

class Activity:
    """Track user activity for social feed."""
    id: int = None  # Auto-incrementing primary key
    user_did: str
    activity_type: str  # 'bookshelf_created', 'book_added', 'comment_added'
    bookshelf_id: int = None
    book_id: int = None
    created_at: datetime = None
    # JSON field for additional metadata
    metadata: str = ""  # JSON string for flexible data

class SyncLog:
    """Log synchronization activities."""
    id: int = None
    sync_type: str  # 'user', 'bookshelf', 'book'
    target_id: str  # The ID/DID of the synced record
    action: str     # 'discovered', 'imported', 'updated', 'failed'
    details: str = ""  # JSON with additional info
    timestamp: datetime = None

class ProcessStatus:
    """Process status model."""
    process_name: str
    process_type: str
    status: str
    pid: int = None
    started_at: datetime = None
    last_heartbeat: datetime = None
    last_activity: datetime = None
    restart_count: int = 0
    error_message: str = ""
    config_data: str = ""
    created_at: datetime = None
    updated_at: datetime = None

class ProcessLog:
    """Process log model."""
    id: int = None
    process_name: str
    log_level: str
    event_type: str
    message: str
    details: str = ""
    timestamp: datetime = None

class ProcessMetric:
    """Process metric model."""
    id: int = None
    process_name: str
    metric_name: str
    metric_value: int
    metric_type: str = "counter"
    recorded_at: datetime = None

def setup_database(db_path: str = 'data/bookdit.db', migrations_dir: str = 'migrations', memory: bool = False):
    """Initialize the database with fastmigrate and all tables."""
    import os

    if memory:
        db_path = ':memory:'
        print("Setting up in-memory database for testing.")
        db = database(db_path)
    else:
        from fastmigrate.core import create_db, run_migrations, get_db_version
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize fastmigrate managed database
        create_db(db_path)
        
        # Apply any pending migrations from migrations_dir
        success = run_migrations(db_path, migrations_dir)
        if not success:
            raise RuntimeError("Database migration failed! Application cannot continue.")
        
        # Get current database version for logging
        version = get_db_version(db_path)
        print(f"Database initialized at version {version}")
        
        # Create FastLite database connection
        db = database(db_path)
    
    # Configure SQLite for better concurrency
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL") 
    db.execute("PRAGMA wal_autocheckpoint=1000")
    db.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    db.execute("PRAGMA cache_size=10000")
    db.execute("PRAGMA temp_store=memory")
    db.execute("PRAGMA mmap_size=268435456")
    
    # Create table objects for FastLite operations
    # These will connect to existing tables created by migrations
    users = db.create(User, pk='did', transform=True,  if_not_exists=True)
    bookshelves = db.create(Bookshelf, transform=True,  if_not_exists=True)
    books = db.create(Book, transform=True,  if_not_exists=True)
    permissions = db.create(Permission, transform=True,  if_not_exists=True)
    bookshelf_invites = db.create(BookshelfInvite, transform=True,  if_not_exists=True)
    comments = db.create(Comment, transform=True,  if_not_exists=True)
    activities = db.create(Activity, transform=True,  if_not_exists=True)
    sync_logs = db.create(SyncLog, transform=True,  if_not_exists=True)
    
    # Connect to process monitoring tables created by migrations
    # Use FastLite's object transformation but specify correct table names
    try:
        # For process_status, we need to connect to the existing table
        process_status = db.t.process_status
        # Wrap it with the ProcessStatus class for object transformation
        process_status = db.create(ProcessStatus, pk='process_name', transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_status = db["process_status"]
    
    try:
        # For process_logs, connect to existing table
        process_logs = db.t.process_logs
        # Wrap it with the ProcessLog class for object transformation
        process_logs = db.create(ProcessLog, transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_logs = db["process_logs"]
    
    try:
        # For process_metrics, connect to existing table
        process_metrics = db.t.process_metrics
        # Wrap it with the ProcessMetric class for object transformation
        process_metrics = db.create(ProcessMetric, transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_metrics = db["process_metrics"]
    
    return {
        'db': db,
        'users': users,
        'bookshelves': bookshelves,
        'books': books,
        'permissions': permissions,
        'bookshelf_invites': bookshelf_invites,
        'comments': comments,
        'activities': activities,
        'sync_logs': sync_logs,
        'process_status': process_status,
        'process_logs': process_logs,
        'process_metrics': process_metrics
    }

def get_database():
    """This function is deprecated. Use database_manager.db_manager instead."""
    raise DeprecationWarning("get_database() is deprecated. Use database_manager.db_manager instead.")

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
    """Check if user can add books and vote (contributor, moderator, owner, or self-join enabled)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)

def can_vote_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can vote on books (contributor, moderator, owner, or self-join enabled)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)

def can_remove_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can remove books (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never remove books
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_edit_bookshelf(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can edit bookshelf details (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never edit
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_manage_members(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can manage members (moderator with limits, owner full access)."""
    if not user_did:
        return False
    return bookshelf.owner_did == user_did or check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)

def can_generate_invites(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can generate invites (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never generate invites
    
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

def can_comment_on_books(bookshelf, user_did: str, db_tables) -> bool:
    """Check if user can comment on books (same as can_add_books)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)

def can_edit_comment(comment, user_did: str, db_tables) -> bool:
    """Check if user can edit a comment (own comments only)."""
    if not user_did:
        return False
    return comment.user_did == user_did

def can_delete_comment(comment, user_did: str, db_tables) -> bool:
    """Check if user can delete a comment (own comments or moderator/owner)."""
    if not user_did:
        return False
    
    # Users can delete their own comments
    if comment.user_did == user_did:
        return True
    
    # Moderators and owners can delete any comments
    try:
        bookshelf = db_tables['bookshelves'][comment.bookshelf_id]
        return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)
    except:
        return False

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
    
    # Users can only invite others with a role level lower than their own
    return inviter_level > target_level

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
    """Get books for a bookshelf with vote counts based on Book records, user voting status, and added-by user info.

    In the new system, each Book record represents a user's +1 vote for that book.
    We count Book records grouped by title/author/ISBN to get the vote count.
    """
    if not db_tables:
        return []

    try:
        # Query to get unique books with vote counts based on Book records
        # Group by title, author, and ISBN to identify the same book added by different users
        query = """
            SELECT
                b.title,
                b.author,
                b.isbn,
                b.cover_url,
                b.description,
                b.publisher,
                b.published_date,
                b.page_count,
                COUNT(*) as upvote_count,
                MIN(b.id) as representative_id,
                MIN(b.added_at) as first_added_at,
                CASE WHEN user_book.id IS NOT NULL THEN 1 ELSE 0 END as user_has_upvoted,
                first_adder.handle as added_by_handle,
                first_adder.display_name as added_by_display_name
            FROM book b
            LEFT JOIN book user_book ON b.bookshelf_id = user_book.bookshelf_id 
                AND b.title = user_book.title 
                AND b.author = user_book.author 
                AND COALESCE(b.isbn, '') = COALESCE(user_book.isbn, '')
                AND user_book.added_by_did = ?
            LEFT JOIN book first_book ON b.title = first_book.title 
                AND b.author = first_book.author 
                AND COALESCE(b.isbn, '') = COALESCE(first_book.isbn, '')
                AND b.bookshelf_id = first_book.bookshelf_id
                AND first_book.added_at = (
                    SELECT MIN(added_at) FROM book 
                    WHERE bookshelf_id = ? 
                    AND title = b.title 
                    AND author = b.author 
                    AND COALESCE(isbn, '') = COALESCE(b.isbn, '')
                )
            LEFT JOIN user first_adder ON first_book.added_by_did = first_adder.did
            WHERE b.bookshelf_id = ?
            GROUP BY b.title, b.author, COALESCE(b.isbn, '')
            ORDER BY upvote_count DESC, b.title ASC
        """

        # Use FastLite's q() method for efficient raw SQL execution
        params = [user_did or '', bookshelf_id, bookshelf_id]
        rows = db_tables['db'].q(query, params)

        books_with_votes = []
        for row in rows:
            # Create a Book object using the representative data
            book = Book(
                id=row['representative_id'],
                bookshelf_id=bookshelf_id,
                title=row['title'],
                author=row['author'],
                isbn=row['isbn'] or '',
                cover_url=row['cover_url'] or '',
                description=row['description'] or '',
                publisher=row['publisher'] or '',
                published_date=row['published_date'] or '',
                page_count=row['page_count'] or 0,
                added_by_did='',  # Not relevant for grouped books
                added_at=row['first_added_at']
            )

            # Add computed attributes
            book.upvote_count = row['upvote_count']
            book.user_has_upvoted = bool(row['user_has_upvoted'])
            book.added_by_handle = row['added_by_handle']
            book.added_by_display_name = row['added_by_display_name']

            books_with_votes.append(book)

        return books_with_votes
    except Exception as e:
        logger.error(f"Error getting books with vote counts: {e}")
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

def get_network_activity(auth_data: dict, db_tables, bluesky_auth, limit: int = 20, offset: int = 0, activity_type: str = "all", date_filter: str = "all"):
    """Get recent activity from users in the current user's network with filtering and pagination."""
    try:
        # Get list of users the current user follows
        following_dids = bluesky_auth.get_following_list(auth_data, limit=100)
        
        if not following_dids:
            return []
        
        current_user_did = auth_data.get('did')
        
        # Build query to get activities from followed users with permission-aware privacy filtering
        placeholders = ','.join(['?' for _ in following_dids])
        query = f"""
            SELECT a.*, b.name as bookshelf_name, b.slug as bookshelf_slug, b.privacy,
                   bk.title as book_title, bk.author as book_author, bk.cover_url as book_cover_url
            FROM activity a
            LEFT JOIN bookshelf b ON a.bookshelf_id = b.id
            LEFT JOIN book bk ON a.book_id = bk.id
            LEFT JOIN permission p ON b.id = p.bookshelf_id AND p.user_did = ? AND p.status = 'active'
            WHERE a.user_did IN ({placeholders})
            AND (
                b.privacy = 'public' 
                OR b.privacy = 'link-only'
                OR (b.privacy = 'private' AND b.owner_did = ?)
                OR (b.privacy = 'private' AND p.user_did IS NOT NULL)
            )
        """
        
        params = [current_user_did] + following_dids + [current_user_did]
        
        # Add activity type filter
        if activity_type != "all":
            query += " AND a.activity_type = ?"
            params.append(activity_type)
        
        # Add date filter
        if date_filter != "all":
            if date_filter == "1d":
                query += " AND a.created_at >= datetime('now', '-1 day')"
            elif date_filter == "7d":
                query += " AND a.created_at >= datetime('now', '-7 days')"
            elif date_filter == "30d":
                query += " AND a.created_at >= datetime('now', '-30 days')"
        
        query += " ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # Execute raw SQL query
        cursor = db_tables['db'].execute(query, params)
        raw_activities = cursor.fetchall()
        
        # Get profiles for the users who created these activities
        activity_user_dids = list(set([row[1] for row in raw_activities]))
        profiles = bluesky_auth.get_profiles_batch(activity_user_dids, auth_data)
        
        # Format activities with user profiles
        activities = []
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

def get_network_activity_count(auth_data: dict, db_tables, bluesky_auth, activity_type: str = "all", date_filter: str = "all"):
    """Get total count of network activities for pagination."""
    try:
        # Get list of users the current user follows
        following_dids = bluesky_auth.get_following_list(auth_data, limit=100)
        
        if not following_dids:
            return 0
        
        current_user_did = auth_data.get('did')
        
        # Build count query with permission-aware privacy filtering
        placeholders = ','.join(['?' for _ in following_dids])
        query = f"""
            SELECT COUNT(*)
            FROM activity a
            LEFT JOIN bookshelf b ON a.bookshelf_id = b.id
            LEFT JOIN permission p ON b.id = p.bookshelf_id AND p.user_did = ? AND p.status = 'active'
            WHERE a.user_did IN ({placeholders})
            AND (
                b.privacy = 'public' 
                OR b.privacy = 'link-only'
                OR (b.privacy = 'private' AND b.owner_did = ?)
                OR (b.privacy = 'private' AND p.user_did IS NOT NULL)
            )
        """
        
        params = [current_user_did] + following_dids + [current_user_did]
        
        # Add activity type filter
        if activity_type != "all":
            query += " AND a.activity_type = ?"
            params.append(activity_type)
        
        # Add date filter
        if date_filter != "all":
            if date_filter == "1d":
                query += " AND a.created_at >= datetime('now', '-1 day')"
            elif date_filter == "7d":
                query += " AND a.created_at >= datetime('now', '-7 days')"
            elif date_filter == "30d":
                query += " AND a.created_at >= datetime('now', '-30 days')"
        
        cursor = db_tables['db'].execute(query, params)
        return cursor.fetchone()[0]
        
    except Exception as e:
        print(f"Error getting network activity count: {e}")
        return 0

def get_shelf_by_slug(slug: str, db_tables):
    """Get a single bookshelf by its slug, returning None if not found."""
    try:
        return db_tables['bookshelves']("slug=?", (slug,))[0]
    except IndexError:
        return None

def get_book_count_for_shelf(bookshelf_id: int, db_tables) -> int:
    """Get the total number of books on a specific bookshelf."""
    try:
        # Use a more efficient count query
        query = "SELECT COUNT(*) FROM book WHERE bookshelf_id = ?"
        cursor = db_tables['db'].execute(query, (bookshelf_id,))
        return cursor.fetchone()[0]
    except Exception as e:
        print(f"Error getting book count for shelf {bookshelf_id}: {e}")
        return 0

def get_public_shelves(db_tables, limit: int = 20, offset: int = 0):
    """Fetch a paginated list of public bookshelves."""
    return db_tables['bookshelves'](where="privacy='public'", limit=limit, offset=offset, order_by='created_at DESC')

def get_user_shelves(user_did: str, db_tables, limit: int = 20, offset: int = 0):
    """Fetch a paginated list of a user's bookshelves (owned + member shelves)."""
    try:
        # Use raw SQL to combine owned shelves and shelves with active permissions
        query = """
            SELECT DISTINCT b.*, 'owner' as user_relationship 
            FROM bookshelf b 
            WHERE b.owner_did = ?
            UNION
            SELECT DISTINCT b.*, p.role as user_relationship
            FROM bookshelf b 
            JOIN permission p ON b.id = p.bookshelf_id 
            WHERE p.user_did = ? AND p.status = 'active'
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        
        cursor = db_tables['db'].execute(query, (user_did, user_did, limit, offset))
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        # Convert raw results back to Bookshelf objects
        shelves = []
        for row in rows:
            shelf_data = dict(zip(columns, row))
            # Extract the user_relationship before creating Bookshelf object
            user_relationship = shelf_data.pop('user_relationship', 'owner')
            shelf = Bookshelf(**{k: v for k, v in shelf_data.items() if k in Bookshelf.__annotations__})
            # Add the relationship info as an attribute
            shelf.user_relationship = user_relationship
            shelves.append(shelf)
        
        return shelves
        
    except Exception as e:
        print(f"Error getting user shelves for {user_did}: {e}")
        # Fallback to just owned shelves if there's an error
        return db_tables['bookshelves']("owner_did=?", (user_did,), limit=limit, offset=offset, order_by='updated_at DESC')

def get_public_shelves_with_stats(db_tables, limit: int = 20, offset: int = 0):
    """Get public shelves with book counts and recent book covers for display."""
    public_shelves = get_public_shelves(db_tables, limit=limit, offset=offset)
    
    for shelf in public_shelves:
        # Get total book count for the shelf
        shelf.book_count = len(db_tables['books']("bookshelf_id=?", (shelf.id,)))
        
        # Get up to 4 recent book covers
        recent_books = db_tables['books'](
            "bookshelf_id=?", (shelf.id,), 
            limit=4, 
            order_by='added_at DESC'
        )
        shelf.recent_covers = [book.cover_url for book in recent_books if book.cover_url]
        
        # Get owner's profile
        try:
            shelf.owner = db_tables['users'][shelf.owner_did]
        except IndexError:
            shelf.owner = None
            
    return public_shelves

def search_shelves(db_tables, query: str = "", book_title: str = "", book_author: str = "", book_isbn: str = "", user_did: str = None, privacy: str = "public", sort_by: str = "updated_at", limit: int = 20, offset: int = 0, open_to_contributions: bool = None):
    """Search for bookshelves based on various criteria, including contained books."""
    # Base query with proper book count aggregation
    sql_query = """
        SELECT bs.*, u.display_name as owner_name, u.handle as owner_handle,
               COUNT(DISTINCT b.id) as book_count
        FROM bookshelf bs
        JOIN user u ON bs.owner_did = u.did
        LEFT JOIN book b ON bs.id = b.bookshelf_id
    """
    
    # Conditions and parameters
    conditions = []
    params = []
    
    # General text search (shelves and books)
    if query:
        conditions.append("(bs.name LIKE ? OR bs.description LIKE ? OR b.title LIKE ? OR b.author LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
        
    # Advanced book search
    if book_title:
        conditions.append("b.title LIKE ?")
        params.append(f"%{book_title}%")
    if book_author:
        conditions.append("b.author LIKE ?")
        params.append(f"%{book_author}%")
    if book_isbn:
        conditions.append("b.isbn = ?")
        params.append(book_isbn)
    
    # Privacy filter
    if privacy != "all":
        conditions.append("bs.privacy = ?")
        params.append(privacy)
    
    # Open to contributions filter
    if open_to_contributions is not None:
        conditions.append("bs.self_join = ?")
        params.append(1 if open_to_contributions else 0)
    
    # Build WHERE clause
    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)
    
    # Group by bookshelf to aggregate book counts
    sql_query += " GROUP BY bs.id, u.display_name, u.handle"
    
    # Sorting
    if sort_by == "updated_at":
        sql_query += " ORDER BY bs.updated_at DESC"
    elif sort_by == "created_at":
        sql_query += " ORDER BY bs.created_at DESC"
    elif sort_by == "name":
        sql_query += " ORDER BY bs.name ASC"
    elif sort_by == "book_count":
        sql_query += " ORDER BY book_count DESC"
    
    # Pagination
    sql_query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    try:
        cursor = db_tables['db'].execute(sql_query, params)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        shelves = []
        for row in rows:
            shelf_data = dict(zip(columns, row))
            # Extract book_count before creating Bookshelf object
            book_count = shelf_data.pop('book_count', 0)
            shelf = Bookshelf(**{k: v for k, v in shelf_data.items() if k in Bookshelf.__annotations__})
            shelf.owner_name = shelf_data.get('owner_name')
            shelf.owner_handle = shelf_data.get('owner_handle')
            shelf.book_count = book_count
            shelves.append(shelf)
        
        # Add book covers and owner info for each shelf (same as get_public_shelves_with_stats)
        for shelf in shelves:
            # Get up to 4 recent book covers
            recent_books = db_tables['books'](
                "bookshelf_id=?", (shelf.id,), 
                limit=4, 
                order_by='added_at DESC'
            )
            shelf.recent_covers = [book.cover_url for book in recent_books if book.cover_url]
            
            # Get owner's profile
            try:
                shelf.owner = db_tables['users'][shelf.owner_did]
            except IndexError:
                shelf.owner = None
        
        return shelves
    except Exception as e:
        print(f"Error searching shelves: {e}")
        return []

def get_recent_community_books(db_tables, limit: int = 15):
    """Fetch the most recently added books from public bookshelves."""
    query = """
        SELECT b.*, bs.name as bookshelf_name, bs.slug as bookshelf_slug
        FROM book b
        JOIN bookshelf bs ON b.bookshelf_id = bs.id
        WHERE bs.privacy = 'public'
        ORDER BY b.added_at DESC
        LIMIT ?
    """
    
    try:
        cursor = db_tables['db'].execute(query, (limit,))
        # Get column descriptions BEFORE calling fetchall()
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        # Manually map results to Book objects since it's a raw query
        books = []
        for row in rows:
            book_data = dict(zip(columns, row))
            book = Book(**{k: v for k, v in book_data.items() if k in Book.__annotations__})
            book.bookshelf_name = book_data.get('bookshelf_name')
            book.bookshelf_slug = book_data.get('bookshelf_slug')
            books.append(book)
        return books
    except Exception as e:
        print(f"Error fetching recent community books: {e}")
        return []

def calculate_shelf_activity_score(shelf_id: int, db_tables) -> float:
    """Calculate an activity score for a bookshelf based on various metrics."""
    try:
        from datetime import datetime, timedelta
        
        # Get shelf info
        shelf = db_tables['bookshelves'][shelf_id]
        
        # Recent book additions (last 30 days) - weight: 40%
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_books_query = """
            SELECT COUNT(*) FROM book 
            WHERE bookshelf_id = ? AND added_at >= ?
        """
        cursor = db_tables['db'].execute(recent_books_query, (shelf_id, thirty_days_ago.isoformat()))
        recent_books_count = cursor.fetchone()[0]
        
        # Contributor count - weight: 30%
        contributors_query = """
            SELECT COUNT(DISTINCT user_did) FROM permission 
            WHERE bookshelf_id = ? AND status = 'active' AND role IN ('contributor', 'moderator')
        """
        cursor = db_tables['db'].execute(contributors_query, (shelf_id,))
        contributor_count = cursor.fetchone()[0]
        
        # Total engagement (book records) - weight: 20%
        # Count total book records as engagement metric
        books_query = """
            SELECT COUNT(*) FROM book 
            WHERE bookshelf_id = ?
        """
        cursor = db_tables['db'].execute(books_query, (shelf_id,))
        total_books = cursor.fetchone()[0]
        
        # Shelf age boost (newer shelves get bonus) - weight: 10%
        # Handle both datetime objects and string dates
        if shelf.created_at:
            if isinstance(shelf.created_at, str):
                try:
                    # Parse ISO format datetime string
                    shelf_created = datetime.fromisoformat(shelf.created_at.replace('Z', '+00:00'))
                except ValueError:
                    # Fallback for other date formats
                    from dateutil.parser import parse
                    shelf_created = parse(shelf.created_at)
            else:
                shelf_created = shelf.created_at
            shelf_age_days = (datetime.now() - shelf_created).days
        else:
            shelf_age_days = 365
        age_score = max(0, 60 - shelf_age_days) / 60  # Boost for shelves < 60 days old
        
        # Calculate weighted score
        activity_score = (
            (recent_books_count * 10) * 0.4 +  # Recent activity
            (contributor_count * 5) * 0.3 +    # Collaboration
            (total_books * 2) * 0.2 +          # Engagement
            (age_score * 20) * 0.1              # Recency
        )
        
        # Open collaboration bonus (+20%)
        if getattr(shelf, 'self_join', False):
            activity_score *= 1.2
        
        return activity_score
        
    except Exception as e:
        print(f"Error calculating activity score for shelf {shelf_id}: {e}")
        return 0.0

def get_mixed_public_shelves(db_tables, limit: int = 20, offset: int = 0):
    """Get a smart mix of new and popular/active public bookshelves."""
    try:
        # Get all public shelves with basic stats
        public_shelves = get_public_shelves_with_stats(db_tables, limit=limit*2, offset=0)  # Get more to mix from
        
        # Calculate activity scores for each shelf
        shelves_with_scores = []
        for shelf in public_shelves:
            activity_score = calculate_shelf_activity_score(shelf.id, db_tables)
            shelf.activity_score = activity_score
            shelves_with_scores.append(shelf)
        
        # Sort by activity score (descending)
        shelves_with_scores.sort(key=lambda s: s.activity_score, reverse=True)
        
        # Get the most active shelves (top 60%)
        active_count = int(limit * 0.6)
        active_shelves = shelves_with_scores[:active_count]
        
        # Get newest shelves (remaining 40%)
        newest_shelves = sorted(
            [s for s in shelves_with_scores if s not in active_shelves],
            key=lambda s: s.created_at or datetime.min,
            reverse=True
        )[:limit - active_count]
        
        # Combine and shuffle for variety
        mixed_shelves = active_shelves + newest_shelves
        import random
        random.shuffle(mixed_shelves)
        
        # Apply pagination
        start_idx = offset
        end_idx = offset + limit
        return mixed_shelves[start_idx:end_idx]
        
    except Exception as e:
        print(f"Error getting mixed public shelves: {e}")
        # Fallback to regular public shelves
        return get_public_shelves_with_stats(db_tables, limit=limit, offset=offset)

def search_shelves_enhanced(db_tables, query: str = "", book_title: str = "", book_author: str = "", book_isbn: str = "", user_did: str = None, privacy: str = "public", sort_by: str = "smart_mix", limit: int = 20, offset: int = 0, open_to_contributions: bool = None):
    """Enhanced search for bookshelves with activity-based sorting options."""
    
    # If sort_by is smart_mix and no search query, use the mixed results
    if sort_by == "smart_mix" and not any([query, book_title, book_author, book_isbn]):
        return get_mixed_public_shelves(db_tables, limit=limit, offset=offset)
    
    # For other cases, use the existing search with enhanced sorting
    shelves = search_shelves(db_tables, query, book_title, book_author, book_isbn, user_did, privacy, sort_by, limit*2, 0, open_to_contributions)
    
    # Apply activity-based sorting for new sort options
    if sort_by == "recently_active":
        # Sort by recent book additions
        for shelf in shelves:
            recent_books_query = """
                SELECT COUNT(*) FROM book 
                WHERE bookshelf_id = ? AND added_at >= datetime('now', '-30 days')
            """
            cursor = db_tables['db'].execute(recent_books_query, (shelf.id,))
            shelf.recent_activity = cursor.fetchone()[0]
        shelves.sort(key=lambda s: getattr(s, 'recent_activity', 0), reverse=True)
        
    elif sort_by == "most_contributors":
        # Sort by contributor count
        for shelf in shelves:
            contributors_query = """
                SELECT COUNT(DISTINCT user_did) FROM permission 
                WHERE bookshelf_id = ? AND status = 'active' AND role IN ('contributor', 'moderator')
            """
            cursor = db_tables['db'].execute(contributors_query, (shelf.id,))
            shelf.contributor_count = cursor.fetchone()[0]
        shelves.sort(key=lambda s: getattr(s, 'contributor_count', 0), reverse=True)
        
    elif sort_by == "most_viewers":
        # Sort by total member count (viewers + contributors + moderators)
        for shelf in shelves:
            viewers_query = """
                SELECT COUNT(DISTINCT user_did) FROM permission 
                WHERE bookshelf_id = ? AND status = 'active'
            """
            cursor = db_tables['db'].execute(viewers_query, (shelf.id,))
            shelf.viewer_count = cursor.fetchone()[0]
        shelves.sort(key=lambda s: getattr(s, 'viewer_count', 0), reverse=True)
    
    # Apply pagination
    return shelves[offset:offset + limit]

def get_user_by_handle(handle: str, db_tables):
    """Get a user by their handle, returning None if not found."""
    try:
        users = db_tables['users']("handle=?", (handle,))
        return users[0] if users else None
    except Exception as e:
        print(f"Error getting user by handle {handle}: {e}")
        return None

def get_user_by_did(did: str, db_tables):
    """Get a user by their DID, returning None if not found."""
    try:
        return db_tables['users'][did]
    except Exception as e:
        print(f"Error getting user by DID {did}: {e}")
        return None

def get_user_public_shelves(user_did: str, db_tables, viewer_did: str = None, limit: int = 20):
    """Get a user's public bookshelves, and link-only shelves if viewer has access."""
    try:
        # Always include public shelves
        privacy_conditions = ["privacy='public'"]
        
        # If viewer is logged in, also include link-only shelves
        if viewer_did:
            privacy_conditions.append("privacy='link-only'")
        
        privacy_clause = " OR ".join(privacy_conditions)
        shelves = db_tables['bookshelves'](
            f"owner_did=? AND ({privacy_clause})", 
            (user_did,), 
            limit=limit, 
            order_by='updated_at DESC'
        )
        
        # Add book counts and recent covers
        for shelf in shelves:
            shelf.book_count = len(db_tables['books']("bookshelf_id=?", (shelf.id,)))
            recent_books = db_tables['books'](
                "bookshelf_id=?", (shelf.id,), 
                limit=4, 
                order_by='added_at DESC'
            )
            shelf.recent_covers = [book.cover_url for book in recent_books if book.cover_url]
        
        return shelves
    except Exception as e:
        print(f"Error getting user public shelves for {user_did}: {e}")
        return []

def get_user_activity(user_did: str, db_tables, viewer_did: str = None, limit: int = 20):
    """Get a user's activity, filtered based on viewer permissions."""
    try:
        # Build privacy filter based on viewer
        if viewer_did:
            # Logged in users can see public and link-only activity
            privacy_filter = "(b.privacy = 'public' OR b.privacy = 'link-only')"
        else:
            # Anonymous users only see public activity
            privacy_filter = "b.privacy = 'public'"
        
        query = f"""
            SELECT a.*, b.name as bookshelf_name, b.slug as bookshelf_slug, b.privacy,
                   bk.title as book_title, bk.author as book_author, bk.cover_url as book_cover_url
            FROM activity a
            LEFT JOIN bookshelf b ON a.bookshelf_id = b.id
            LEFT JOIN book bk ON a.book_id = bk.id
            WHERE a.user_did = ? AND {privacy_filter}
            ORDER BY a.created_at DESC
            LIMIT ?
        """
        
        cursor = db_tables['db'].execute(query, (user_did, limit))
        raw_activities = cursor.fetchall()
        
        # Format activities
        activities = []
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
                'book_cover_url': row[12]
            }
            activities.append(activity_data)
        
        return activities
        
    except Exception as e:
        print(f"Error getting user activity for {user_did}: {e}")
        return []

def search_users(db_tables, query: str = "", viewer_did: str = None, limit: int = 20):
    """Search for users by handle or display name, only showing users with public content."""
    if not query.strip():
        return []
    
    try:
        # Clean the query
        search_term = query.strip()
        
        # Build the search query - only include users who have public content
        sql_query = """
            SELECT DISTINCT u.*, 
                   COUNT(DISTINCT bs.id) as public_shelves_count,
                   COUNT(DISTINCT a.id) as activity_count,
                   bs_recent.name as recent_shelf_name,
                   bs_recent.slug as recent_shelf_slug
            FROM user u
            LEFT JOIN bookshelf bs ON u.did = bs.owner_did AND bs.privacy = 'public'
            LEFT JOIN activity a ON u.did = a.user_did
            LEFT JOIN bookshelf bs_activity ON a.bookshelf_id = bs_activity.id AND bs_activity.privacy = 'public'
            LEFT JOIN bookshelf bs_recent ON u.did = bs_recent.owner_did AND bs_recent.privacy = 'public'
            WHERE (u.handle LIKE ? OR u.display_name LIKE ?)
            AND (bs.id IS NOT NULL OR bs_activity.id IS NOT NULL)
            GROUP BY u.did
            HAVING public_shelves_count > 0 OR activity_count > 0
            ORDER BY public_shelves_count DESC, u.created_at DESC
            LIMIT ?
        """
        
        # Use wildcards for partial matching
        search_pattern = f"%{search_term}%"
        params = [search_pattern, search_pattern, limit]
        
        cursor = db_tables['db'].execute(sql_query, params)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        users = []
        for row in rows:
            user_data = dict(zip(columns, row))
            user = User(**{k: v for k, v in user_data.items() if k in User.__annotations__})
            user.public_shelves_count = user_data.get('public_shelves_count', 0)
            user.activity_count = user_data.get('activity_count', 0)
            user.recent_shelf_name = user_data.get('recent_shelf_name')
            user.recent_shelf_slug = user_data.get('recent_shelf_slug')
            users.append(user)
        
        return users
        
    except Exception as e:
        print(f"Error searching users: {e}")
        return []

def get_book_by_id(book_id: int, db_tables):
    """Get a book by its ID, returning None if not found."""
    try:
        return db_tables['books'][book_id]
    except IndexError:
        return None

def get_book_comments(book_id: int, db_tables, bookshelf_id: int = None, limit: int = 50):
    """Get comments for a book with user information.
    
    Args:
        book_id: The book to get comments for
        db_tables: Database tables
        bookshelf_id: Optional bookshelf ID to filter comments by shelf context
        limit: Maximum number of comments to return
    
    Returns:
        List of comments, filtered by bookshelf if bookshelf_id is provided
    """
    try:
        if bookshelf_id is not None:
            # Filter comments by both book and bookshelf (shelf-specific context)
            query = """
                SELECT c.*, u.handle, u.display_name, u.avatar_url
                FROM comment c
                JOIN user u ON c.user_did = u.did
                WHERE c.book_id = ? AND c.bookshelf_id = ?
                ORDER BY c.created_at ASC
                LIMIT ?
            """
            params = (book_id, bookshelf_id, limit)
        else:
            # Show all comments for the book across all bookshelves (general book page)
            query = """
                SELECT c.*, u.handle, u.display_name, u.avatar_url
                FROM comment c
                JOIN user u ON c.user_did = u.did
                WHERE c.book_id = ?
                ORDER BY c.created_at ASC
                LIMIT ?
            """
            params = (book_id, limit)
        
        cursor = db_tables['db'].execute(query, params)
        # Get column descriptions BEFORE calling fetchall()
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        comments = []
        for row in rows:
            comment_data = dict(zip(columns, row))
            comment = Comment(**{k: v for k, v in comment_data.items() if k in Comment.__annotations__})
            comment.user_handle = comment_data.get('handle')
            comment.user_display_name = comment_data.get('display_name')
            comment.user_avatar_url = comment_data.get('avatar_url')
            comments.append(comment)
        
        return comments
        
    except Exception as e:
        logger.error(f"Error getting comments for book {book_id} (bookshelf {bookshelf_id}): {e}")
        return []

def get_book_activity(book_id: int, db_tables, activity_type: str = "all", limit: int = 20):
    """Get activity for a specific book with filtering."""
    try:
        query = """
            SELECT a.*, u.handle, u.display_name, u.avatar_url,
                   b.name as bookshelf_name, b.slug as bookshelf_slug
            FROM activity a
            JOIN user u ON a.user_did = u.did
            LEFT JOIN bookshelf b ON a.bookshelf_id = b.id
            WHERE a.book_id = ?
        """
        
        params = [book_id]
        
        # Add activity type filter
        if activity_type != "all":
            query += " AND a.activity_type = ?"
            params.append(activity_type)
        
        query += " ORDER BY a.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = db_tables['db'].execute(query, params)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        activities = []
        for row in rows:
            activity_data = dict(zip(columns, row))
            activity = {
                'id': activity_data['id'],
                'user_did': activity_data['user_did'],
                'activity_type': activity_data['activity_type'],
                'bookshelf_id': activity_data['bookshelf_id'],
                'book_id': activity_data['book_id'],
                'created_at': activity_data['created_at'],
                'metadata': activity_data['metadata'],
                'user_handle': activity_data['handle'],
                'user_display_name': activity_data['display_name'],
                'user_avatar_url': activity_data['avatar_url'],
                'bookshelf_name': activity_data['bookshelf_name'],
                'bookshelf_slug': activity_data['bookshelf_slug']
            }
            activities.append(activity)
        
        return activities
        
    except Exception as e:
        print(f"Error getting activity for book {book_id}: {e}")
        return []

def get_book_shelves(book_id: int, db_tables, viewer_did: str = None):
    """Get all shelves that contain this book (with permission filtering)."""
    try:
        # Get the book to find similar books by title/author/ISBN
        book = get_book_by_id(book_id, db_tables)
        if not book:
            return []
        
        # Find all shelves containing books with the same title/author/ISBN
        query = """
            SELECT DISTINCT bs.*, COUNT(b.id) as vote_count
            FROM bookshelf bs
            JOIN book b ON bs.id = b.bookshelf_id
            LEFT JOIN permission p ON bs.id = p.bookshelf_id AND p.user_did = ? AND p.status = 'active'
            WHERE b.title = ? AND b.author = ? AND COALESCE(b.isbn, '') = COALESCE(?, '')
            AND (
                bs.privacy = 'public' 
                OR bs.privacy = 'link-only'
                OR (bs.privacy = 'private' AND bs.owner_did = ?)
                OR (bs.privacy = 'private' AND p.user_did IS NOT NULL)
            )
            GROUP BY bs.id
            ORDER BY vote_count DESC, bs.updated_at DESC
        """
        
        params = [viewer_did or '', book.title, book.author, book.isbn or '', viewer_did or '']
        cursor = db_tables['db'].execute(query, params)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        shelves = []
        for row in rows:
            shelf_data = dict(zip(columns, row))
            vote_count = shelf_data.pop('vote_count', 0)
            shelf = Bookshelf(**{k: v for k, v in shelf_data.items() if k in Bookshelf.__annotations__})
            shelf.vote_count = vote_count
            shelves.append(shelf)
        
        return shelves
        
    except Exception as e:
        print(f"Error getting shelves for book {book_id}: {e}")
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
def as_interactive_card(self: Book, can_upvote=False, user_has_upvoted=False, upvote_count=0, can_remove=False, user_auth_status="anonymous", db_tables=None):
    """Render Book as a card with clickable title, +1/-1 toggle, and optional comment preview."""
    
    cover = Img(
        src=self.cover_url,
        alt=f"Cover of {self.title}",
        cls="book-cover",
        loading="lazy"
    ) if self.cover_url else Div("📖", cls="book-cover-placeholder")
    
    # Shorter description for compact tiles
    description = P(
        self.description[:80] + "..." if len(self.description) > 80 else self.description,
        cls="book-description"
    ) if self.description else None
    
    # Get a random comment if available
    comment_preview = None
    if db_tables:
        try:
            comments = get_book_comments(self.id, db_tables, limit=10)
            if comments:
                import random
                random_comment = random.choice(comments)
                comment_preview = Div(
                    P(f'"{random_comment.content[:60]}{"..." if len(random_comment.content) > 60 else ""}"', 
                      cls="comment-preview-text"),
                    P(f"— {random_comment.user_display_name or random_comment.user_handle}", 
                      cls="comment-preview-author"),
                    cls="comment-preview"
                )
        except Exception as e:
            # Silently handle any errors in comment fetching
            pass
    
    # Build action row with just +1/-1 toggle and comment button
    action_icons = []
    
    # 1. +1/-1 Toggle Button
    if can_upvote:
        if user_has_upvoted:
            # User has +1, show -1 option
            action_icons.append(Button(
                "-1",
                hx_post=f"/book/{self.id}/toggle",
                hx_target=f"#book-{self.id}",
                hx_swap="outerHTML",
                cls="action-btn toggle-btn remove-vote",
                title=f"Remove your +1 (currently {upvote_count} votes)",
                onclick="event.stopPropagation()"
            ))
        else:
            # User doesn't have +1, show +1 option
            action_icons.append(Button(
                "+1",
                hx_post=f"/book/{self.id}/toggle",
                hx_target=f"#book-{self.id}",
                hx_swap="outerHTML",
                cls="action-btn toggle-btn add-vote",
                title=f"Add your +1 (currently {upvote_count} votes)",
                onclick="event.stopPropagation()"
            ))
    else:
        # User cannot vote - show appropriate disabled state
        if user_auth_status == "anonymous":
            action_icons.append(Button(
                "+1", 
                cls="action-btn toggle-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to add books to this shelf",
                onclick="window.location.href='/auth/login'"
            ))
        else:
            action_icons.append(Button(
                "+1", 
                cls="action-btn toggle-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can add books to this shelf"
            ))
    
    # 2. Comment Icon - HTMX modal trigger
    # Try to get bookshelf context from the current page URL
    action_icons.append(Button(
        "💬",
        hx_get=f"/api/book/{self.id}/comment-modal",
        hx_target="#comment-modal-container",
        hx_swap="innerHTML",
        cls="action-btn comment-btn",
        title="View and add comments",
        onclick="event.stopPropagation()"
    ))
    
    # 3. Add to Shelf Icon
    action_icons.append(Button(
        "📚",
        cls="action-btn add-to-shelf-btn",
        title="Add to one of your shelves",
        onclick="event.stopPropagation(); showShelfSelector(this)",
        **{"data-book-id": self.id, "data-book-title": self.title, "data-book-author": self.author, "data-book-isbn": self.isbn or ""}
    ))
    
    # Build the card components
    card_children = []
    
    # Remove button (red cross in top-right corner) - only if user can remove
    if can_remove:
        escaped_title = self.title.replace("'", "\\'").replace('"', '\\"')
        card_children.append(Button(
            "×",
            onclick=f"confirmRemoveBook({self.id}, '{escaped_title}', {upvote_count})",
            cls="remove-btn-cross",
            title="Remove book from shelf"
        ))
    
    # Cover container with vote count badge overlay
    cover_container_children = [cover]
    
    # Vote count badge (always visible, positioned over cover)
    if upvote_count > 0:
        cover_container_children.append(Div(
            f"{upvote_count}",
            cls="vote-count-badge",
            title=f"{upvote_count} votes"
        ))
    
    card_children.append(Div(*cover_container_children, cls="book-cover-container"))
    
    # Book info section
    book_info_children = [
        # Clickable book title that links to book detail page
        A(self.title, href=f"/book/{self.id}", cls="book-title-link"),
    ]
    
    if self.author:
        book_info_children.append(P(self.author, cls="book-author"))
    
    if description:
        book_info_children.append(description)
    
    # Add comment preview if available
    if comment_preview:
        book_info_children.append(comment_preview)
    
    # Action row with +1/-1 toggle and comment button
    book_info_children.append(Div(
        *action_icons,
        cls="book-actions-row"
    ))
    
    # Discrete user attribution
    added_by_handle = getattr(self, 'added_by_handle', None)
    added_by_display_name = getattr(self, 'added_by_display_name', None)
    if added_by_handle:
        user_display = added_by_display_name or added_by_handle
        book_info_children.append(P(
            "Added by ",
            A(f"@{added_by_handle}", href=f"/user/{added_by_handle}", cls="book-added-by-link", title="View profile"),
            cls="book-added-by"
        ))
    
    card_children.append(Div(*book_info_children, cls="book-info"))
    
    return Div(
        *card_children,
        cls="book-card interactive-book",
        id=f"book-{self.id}"
    )

@patch
def as_table_row(self: Book, can_upvote=False, user_has_upvoted=False, upvote_count=0, can_remove=False, user_auth_status="anonymous"):
    """Render Book as a table row for list view."""
    # Generate Google Books URL
    if self.isbn:
        google_books_url = f"https://books.google.com/books?isbn={self.isbn}"
    else:
        # Fallback to search query if no ISBN
        search_query = f"{self.title} {self.author}".replace(" ", "+")
        google_books_url = f"https://books.google.com/books?q={search_query}"
    
    # Small cover thumbnail
    cover_cell = Td(
        Img(
            src=self.cover_url,
            alt=f"Cover of {self.title}",
            cls="book-table-cover",
            loading="lazy"
        ) if self.cover_url else Div("📖", cls="book-table-cover-placeholder"),
        cls="cover-cell"
    )
    
    # Title cell
    title_cell = Td(
        Strong(self.title, cls="book-table-title"),
        cls="title-cell"
    )
    
    # Author cell
    author_cell = Td(
        self.author if self.author else "Unknown Author",
        cls="author-cell"
    )
    
    # Description cell (truncated) with discrete user attribution
    description_parts = []
    description_text = self.description[:60] + "..." if len(self.description) > 60 else self.description
    if description_text:
        description_parts.append(Div(description_text, cls="book-table-description"))
    
    # Add discrete user attribution
    added_by_handle = getattr(self, 'added_by_handle', None)
    if added_by_handle:
        description_parts.append(Div(
            "Added by ",
            A(f"@{added_by_handle}", href=f"/user/{added_by_handle}", cls="book-added-by-link", title="View profile"),
            cls="book-added-by-table"
        ))
    
    description_cell = Td(
        *description_parts if description_parts else ["—"],
        cls="description-cell"
    )
    
    # Voting cell with +1/-1 toggle system (matching card view)
    voting_buttons = []
    if can_upvote:
        if user_has_upvoted:
            # User has +1, show -1 option
            voting_buttons.append(Button(
                "-1",
                hx_post=f"/book/{self.id}/toggle",
                hx_target=f"#book-row-{self.id}",
                hx_swap="outerHTML",
                cls="vote-btn-small toggle-btn remove-vote",
                title=f"Remove your +1 (currently {upvote_count} votes)",
                onclick="event.stopPropagation()"
            ))
        else:
            # User doesn't have +1, show +1 option
            voting_buttons.append(Button(
                "+1",
                hx_post=f"/book/{self.id}/toggle",
                hx_target=f"#book-row-{self.id}",
                hx_swap="outerHTML",
                cls="vote-btn-small toggle-btn add-vote",
                title=f"Add your +1 (currently {upvote_count} votes)",
                onclick="event.stopPropagation()"
            ))
    else:
        # Permission-aware disabled states
        if user_auth_status == "anonymous":
            voting_buttons.append(Button(
                "+1", 
                cls="vote-btn-small toggle-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to add books to this shelf",
                onclick="window.location.href='/auth/login'"
            ))
        else:
            voting_buttons.append(Button(
                "+1", 
                cls="vote-btn-small toggle-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can add books to this shelf"
            ))
    
    votes_cell = Td(
        Div(
            Div(*voting_buttons, cls="table-voting-buttons"),
            Span(f"{upvote_count}", cls="table-vote-count"),
            cls="table-voting"
        ),
        cls="votes-cell"
    )
    
    # Actions cell
    actions = [
        A("More Info", href=google_books_url, target="_blank", rel="noopener noreferrer", 
          cls="table-more-info-link", title="View on Google Books")
    ]
    
    if can_remove:
        escaped_title = self.title.replace("'", "\\'").replace('"', '\\"')
        actions.append(Button(
            "×",
            onclick=f"confirmRemoveBook({self.id}, '{escaped_title}', {upvote_count})",
            cls="table-remove-btn",
            title="Remove book from shelf"
        ))
    
    actions_cell = Td(
        Div(*actions, cls="table-actions"),
        cls="actions-cell"
    )
    
    return Tr(
        cover_cell,
        title_cell,
        author_cell,
        description_cell,
        votes_cell,
        actions_cell,
        cls="book-table-row",
        id=f"book-row-{self.id}"
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
