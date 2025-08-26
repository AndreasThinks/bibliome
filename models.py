"""Database models for BookdIt using FastLite."""

from fastlite import *
from datetime import datetime
from typing import Optional
import secrets
import string
from fasthtml.common import *
from fastcore.all import patch
from fastcore.xtras import flexicache, time_policy
from atproto import Client, models as at_models

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
    data_source: str = "local"  # 'local', 'network', 'historical'

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
    data_source: str = "local"  # 'local', 'network', 'historical'

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
    data_source: str = "local"  # 'local', 'network', 'historical'

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

class TrackedProfile:
    """Track profiles discovered for historical scanning."""
    did: str  # Primary key - AT Protocol DID
    handle: str = ""
    display_name: str = ""
    discovered_at: datetime = None
    discovery_source: str = ""  # 'user', 'follows', 'network'
    last_scanned_at: datetime = None
    scan_priority: int = 1  # 1=high, 2=medium, 3=low
    is_active: bool = True
    notes: str = ""

class HistoricalScanQueue:
    """Queue for historical scanning jobs."""
    id: int = None  # Auto-incrementing primary key
    profile_did: str
    collection_type: str  # 'bookshelf', 'book', 'both'
    priority: int = 1
    status: str = "pending"  # 'pending', 'processing', 'completed', 'failed'
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    error_message: str = ""
    retry_count: int = 0

# Global database instance to prevent multiple connections
_db_instance = None

def setup_database(db_path: str = 'data/bookdit.db', migrations_dir: str = 'migrations'):
    """Initialize the database with fastmigrate and all tables."""
    import os
    from fastmigrate.core import create_db, run_migrations, get_db_version
    
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Initialize fastmigrate managed database
    # If no db exists, it's created and set to version 0
    # If a db exists, nothing happens
    create_db(db_path)
    
    # Apply any pending migrations from migrations_dir
    success = run_migrations(db_path, migrations_dir)
    if not success:
        raise RuntimeError("Database migration failed! Application cannot continue.")
    
    # Get current database version for logging
    version = get_db_version(db_path)
    print(f"Database initialized at version {version}")
    
    # Create FastLite database connection with WAL mode
    db = database(db_path)
    
    # Configure SQLite for better concurrency
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL") 
    db.execute("PRAGMA wal_autocheckpoint=1000")
    db.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    
    # Create table objects for FastLite operations
    # These will connect to existing tables created by migrations
    users = db.create(User, pk='did', transform=True)
    bookshelves = db.create(Bookshelf, transform=True)
    books = db.create(Book, transform=True)
    permissions = db.create(Permission, transform=True)
    bookshelf_invites = db.create(BookshelfInvite, transform=True)
    upvotes = db.create(Upvote, pk=['book_id', 'user_did'], transform=True)
    activities = db.create(Activity, transform=True)
    
    # Create historical tracking tables
    tracked_profiles = db.create(TrackedProfile, pk='did', transform=True)
    historical_scan_queue = db.create(HistoricalScanQueue, transform=True)
    
    # Add process monitoring tables
    from fastlite import Table
    process_status = Table(db, 'process_status')
    process_logs = Table(db, 'process_logs')
    process_metrics = Table(db, 'process_metrics')
    
    return {
        'db': db,
        'users': users,
        'bookshelves': bookshelves,
        'books': books,
        'permissions': permissions,
        'bookshelf_invites': bookshelf_invites,
        'upvotes': upvotes,
        'activities': activities,
        'tracked_profiles': tracked_profiles,
        'historical_scan_queue': historical_scan_queue,
        'process_status': process_status,
        'process_logs': process_logs,
        'process_metrics': process_metrics
    }

def get_database():
    """Get the shared database instance. Creates it if it doesn't exist."""
    global _db_instance
    if _db_instance is None:
        _db_instance = setup_database()
    return _db_instance

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
    """Get books for a bookshelf with upvote counts, user voting status, and added-by user info."""
    if not db_tables:
        return []
    
    try:
        # Use SQL query to get books with user info who added them
        query = """
            SELECT b.*, u.handle as added_by_handle, u.display_name as added_by_display_name
            FROM book b
            LEFT JOIN user u ON b.added_by_did = u.did
            WHERE b.bookshelf_id = ?
        """
        
        cursor = db_tables['db'].execute(query, (bookshelf_id,))
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        
        books_with_votes = []
        for row in rows:
            book_data = dict(zip(columns, row))
            
            # Extract user info before creating Book object
            added_by_handle = book_data.pop('added_by_handle', None)
            added_by_display_name = book_data.pop('added_by_display_name', None)
            
            # Create Book object
            book = Book(**{k: v for k, v in book_data.items() if k in Book.__annotations__})
            
            # Count upvotes for this book
            upvote_count = len(db_tables['upvotes']("book_id=?", (book.id,)))
            
            # Skip books with no upvotes
            if upvote_count == 0:
                continue
            
            # Check if current user has upvoted this book
            user_has_upvoted = False
            if user_did:
                try:
                    user_upvote = db_tables['upvotes']("book_id=? AND user_did=?", (book.id, user_did))[0]
                    user_has_upvoted = user_upvote is not None
                except IndexError:
                    user_has_upvoted = False
            
            # Add computed attributes to the book object
            book.upvote_count = upvote_count
            book.user_has_upvoted = user_has_upvoted
            book.added_by_handle = added_by_handle
            book.added_by_display_name = added_by_display_name
            
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

@flexicache(time_policy(600), maxsize=100)  # 10 minute cache, 100 different filter combinations
def get_network_activity(auth_data: dict, db_tables, bluesky_auth, limit: int = 20, offset: int = 0, activity_type: str = "all", date_filter: str = "all"):
    """Get recent activity from users in the current user's network with filtering, pagination, and data source tracking. Results cached for 10 minutes."""
    import logging
    logger = logging.getLogger(__name__)
    cache_key = f"{auth_data.get('did')}:{limit}:{offset}:{activity_type}:{date_filter}"
    logger.debug(f"Cache miss for network activity: {cache_key}")
    try:
        # Get list of users the current user follows
        following_dids = bluesky_auth.get_following_list(auth_data, limit=100)
        
        if not following_dids:
            return []
        
        current_user_did = auth_data.get('did')
        
        # Enhanced query to include data source information from bookshelves and books
        placeholders = ','.join(['?' for _ in following_dids])
        query = f"""
            SELECT a.*, b.name as bookshelf_name, b.slug as bookshelf_slug, b.privacy,
                   b.data_source as bookshelf_data_source,
                   bk.title as book_title, bk.author as book_author, bk.cover_url as book_cover_url,
                   bk.data_source as book_data_source
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
        
        # Format activities with user profiles and enhanced data source information
        activities = []
        for row in raw_activities:
            # Parse metadata to determine activity source
            import json
            activity_source = 'local'  # default
            metadata_str = row[6] or '{}'
            try:
                metadata = json.loads(metadata_str)
                if 'source' in metadata:
                    if metadata['source'] == 'network_firehose':
                        activity_source = 'network'
                    elif metadata['source'] == 'historical_scanner':
                        activity_source = 'historical'
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Determine overall data source based on activity source and related records
            bookshelf_data_source = row[10] if len(row) > 10 else 'local'
            book_data_source = row[14] if len(row) > 14 else 'local'
            
            # Priority: historical > network > local
            overall_data_source = activity_source
            if bookshelf_data_source == 'historical' or book_data_source == 'historical':
                overall_data_source = 'historical'
            elif bookshelf_data_source == 'network' or book_data_source == 'network':
                if overall_data_source != 'historical':
                    overall_data_source = 'network'
            
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
                'bookshelf_data_source': bookshelf_data_source,
                'book_title': row[11] if len(row) > 11 else None,
                'book_author': row[12] if len(row) > 12 else None,
                'book_cover_url': row[13] if len(row) > 13 else None,
                'book_data_source': book_data_source,
                'activity_source': activity_source,
                'data_source': overall_data_source,
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

@flexicache(time_policy(900), maxsize=200)  # 15 minute cache, 200 different shelves
def calculate_shelf_activity_score(shelf_id: int, db_tables) -> float:
    """Calculate an activity score for a bookshelf based on various metrics. Results cached for 15 minutes."""
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Cache miss for shelf activity score: {shelf_id}")
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
        
        # Total engagement (upvotes) - weight: 20%
        upvotes_query = """
            SELECT COUNT(*) FROM upvote u
            JOIN book b ON u.book_id = b.id
            WHERE b.bookshelf_id = ?
        """
        cursor = db_tables['db'].execute(upvotes_query, (shelf_id,))
        total_upvotes = cursor.fetchone()[0]
        
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
            (total_upvotes * 2) * 0.2 +        # Engagement
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
def as_interactive_card(self: Book, can_upvote=False, user_has_upvoted=False, upvote_count=0, can_remove=False, user_auth_status="anonymous"):
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
    
    # Shorter description for compact tiles
    description = P(
        self.description[:80] + "..." if len(self.description) > 80 else self.description,
        cls="book-description"
    ) if self.description else None
    
    # Build voting buttons with better permission-aware states
    voting_buttons = []
    
    if can_upvote:
        # User can vote - show active buttons
        upvote_cls = "vote-btn upvote-btn" + (" voted" if user_has_upvoted else "")
        voting_buttons.append(Button(
            "👍",
            hx_post=f"/book/{self.id}/upvote",
            hx_target=f"#book-{self.id}",
            hx_swap="outerHTML",
            cls=upvote_cls,
            disabled=user_has_upvoted,
            title=f"Upvote ({upvote_count})" if not user_has_upvoted else f"Remove upvote ({upvote_count})",
            onclick="event.stopPropagation()"
        ))
        
        # Downvote button (remove vote if user has upvoted)
        downvote_cls = "vote-btn downvote-btn" + (" disabled" if not user_has_upvoted else "")
        downvote_attrs = {
            "cls": downvote_cls,
            "disabled": not user_has_upvoted,
            "title": "Remove vote" if user_has_upvoted else "You haven't upvoted this book",
            "onclick": "event.stopPropagation()"
        }
        if user_has_upvoted:
            downvote_attrs.update({
                "hx_post": f"/book/{self.id}/upvote",
                "hx_target": f"#book-{self.id}",
                "hx_swap": "outerHTML"
            })
        
        voting_buttons.append(Button("👎", **downvote_attrs))
    else:
        # User cannot vote - show appropriate disabled state with clear messaging
        if user_auth_status == "anonymous":
            # Not logged in
            voting_buttons.append(Button(
                "👍", 
                cls="vote-btn upvote-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to vote on books",
                onclick="window.location.href='/auth/login'"
            ))
            voting_buttons.append(Button(
                "👎", 
                cls="vote-btn downvote-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to vote on books",
                onclick="window.location.href='/auth/login'"
            ))
        else:
            # Logged in but no permission
            voting_buttons.append(Button(
                "👍", 
                cls="vote-btn upvote-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can vote on books in this shelf"
            ))
            voting_buttons.append(Button(
                "👎", 
                cls="vote-btn downvote-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can vote on books in this shelf"
            ))
    
    # Vote count display
    vote_count_display = Span(f"{upvote_count}", cls="vote-count")
    
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
    
    # Cover container
    card_children.append(Div(cover, cls="book-cover-container"))
    
    # Book info section
    book_info_children = [
        Div(
            H4(self.title, cls="book-title"),
            # Import and add data source badge
            eval("DataSourceBadge(getattr(self, 'data_source', 'local'), size='mini')") if hasattr(__import__('components'), 'DataSourceBadge') else None,
            cls="book-title-row"
        ),
    ]
    
    if self.author:
        book_info_children.append(P(self.author, cls="book-author"))
    
    if description:
        book_info_children.append(description)
    
    # Voting section
    book_info_children.append(Div(
        Div(*voting_buttons, cls="voting-buttons"),
        vote_count_display,
        cls="book-voting"
    ))
    
    # More info link
    book_info_children.append(A(
        "More Info",
        href=google_books_url,
        target="_blank",
        rel="noopener noreferrer",
        cls="more-info-link",
        title="View on Google Books"
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
    
    # Voting cell with permission-aware states
    voting_buttons = []
    if can_upvote:
        upvote_cls = "vote-btn-small upvote-btn" + (" voted" if user_has_upvoted else "")
        voting_buttons.append(Button(
            "👍",
            hx_post=f"/book/{self.id}/upvote",
            hx_target=f"#book-row-{self.id}",
            hx_swap="outerHTML",
            cls=upvote_cls,
            disabled=user_has_upvoted,
            title=f"Upvote ({upvote_count})" if not user_has_upvoted else f"Remove upvote ({upvote_count})"
        ))
        
        downvote_cls = "vote-btn-small downvote-btn" + (" disabled" if not user_has_upvoted else "")
        downvote_attrs = {
            "cls": downvote_cls,
            "disabled": not user_has_upvoted,
            "title": "Remove vote" if user_has_upvoted else "You haven't upvoted this book"
        }
        if user_has_upvoted:
            downvote_attrs.update({
                "hx_post": f"/book/{self.id}/upvote",
                "hx_target": f"#book-row-{self.id}",
                "hx_swap": "outerHTML"
            })
        voting_buttons.append(Button("👎", **downvote_attrs))
    else:
        # Permission-aware disabled states
        if user_auth_status == "anonymous":
            voting_buttons.append(Button(
                "👍", 
                cls="vote-btn-small upvote-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to vote on books",
                onclick="window.location.href='/auth/login'"
            ))
            voting_buttons.append(Button(
                "👎", 
                cls="vote-btn-small downvote-btn disabled-anonymous", 
                disabled=True, 
                title="Sign in to vote on books",
                onclick="window.location.href='/auth/login'"
            ))
        else:
            voting_buttons.append(Button(
                "👍", 
                cls="vote-btn-small upvote-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can vote on books in this shelf"
            ))
            voting_buttons.append(Button(
                "👎", 
                cls="vote-btn-small downvote-btn disabled-no-permission", 
                disabled=True, 
                title="Only contributors can vote on books in this shelf"
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

def ensure_user_exists(repo_did: str, db_tables, data_source: str = 'network'):
    """Ensure user exists in database, create placeholder if needed."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        existing_user = db_tables['users'].get(repo_did)
        if existing_user:
            return existing_user
    except:
        pass
    
    # Create placeholder user - will be updated when they log in
    try:
        user_data = {
            'did': repo_did,
            'handle': f"user-{repo_did[-8:]}", # Use last 8 chars of DID as temp handle
            'display_name': f"User {repo_did[-8:]}",
            'avatar_url': '',
            'created_at': datetime.now(),
            'last_login': datetime.now(),
            'data_source': data_source
        }
        db_tables['users'].insert(user_data)
        logger.info(f"Created placeholder user for DID: {repo_did}")
        return user_data
    except Exception as e:
        logger.error(f"Error creating placeholder user for {repo_did}: {e}")
        return None

def store_bookshelf_from_network(record: dict, repo_did: str, record_uri: str, data_source: str = 'network'):
    """Stores a bookshelf discovered on the network with data source tracking."""
    import logging
    import json
    logger = logging.getLogger(__name__)
    
    try:
        db_tables = get_database()
        logger.info(f"Discovered new bookshelf from {repo_did}: {record.get('name')} (source: {data_source})")
        
        # Avoid duplicates by atproto_uri
        existing = list(db_tables['bookshelves'](f"atproto_uri='{record_uri}'"))
        if existing:
            logger.debug(f"Bookshelf already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did, db_tables, data_source=data_source)

        shelf_data = {
            'name': record.get('name', 'Untitled Bookshelf'),
            'description': record.get('description', ''),
            'privacy': record.get('privacy', 'public'),
            'owner_did': repo_did,
            'atproto_uri': record_uri,
            'slug': f"net-{record_uri.split('/')[-1]}",  # Create a unique slug
            'data_source': data_source,  # Track the source
            'created_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00')),
            'updated_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        created_shelf = db_tables['bookshelves'].insert(Bookshelf(**shelf_data))
        bookshelf_id = created_shelf.id if hasattr(created_shelf, 'id') else created_shelf
        
        # Log activity for network discovery
        metadata = json.dumps({"source": data_source})
        log_activity(
            user_did=repo_did,
            activity_type='bookshelf_created',
            db_tables=db_tables,
            bookshelf_id=bookshelf_id,
            metadata=metadata
        )
        
        logger.info(f"Successfully stored {data_source} bookshelf: {record.get('name')} (ID: {bookshelf_id})")
        
    except Exception as e:
        logger.error(f"Error storing bookshelf from {data_source}: {e}", exc_info=True)

def store_book_from_network(record: dict, repo_did: str, record_uri: str, data_source: str = 'network'):
    """Stores a book discovered on the network with data source tracking."""
    import logging
    import json
    logger = logging.getLogger(__name__)
    
    try:
        db_tables = get_database()
        logger.info(f"Discovered new book from {repo_did}: {record.get('title')} (source: {data_source})")
        
        # Avoid duplicates by atproto_uri
        existing = list(db_tables['books'](f"atproto_uri='{record_uri}'"))
        if existing:
            logger.debug(f"Book already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did, db_tables, data_source=data_source)

        # Find the bookshelf in the local DB
        bookshelf_ref = record.get('bookshelfRef')
        if not bookshelf_ref:
            logger.warning(f"Book {record.get('title')} has no bookshelf reference")
            return

        bookshelf = list(db_tables['bookshelves'](f"atproto_uri='{bookshelf_ref}'"))
        if not bookshelf:
            logger.warning(f"Bookshelf not found for book {record.get('title')}: {bookshelf_ref}")
            return

        book_data = {
            'bookshelf_id': bookshelf[0].id,
            'title': record.get('title', 'Untitled Book'),
            'author': record.get('author', ''),
            'isbn': record.get('isbn', ''),
            'added_by_did': repo_did,
            'atproto_uri': record_uri,
            'data_source': data_source,  # Track the source
            'added_at': datetime.fromisoformat(record.get('addedAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        created_book = db_tables['books'].insert(Book(**book_data))
        book_id = created_book.id if hasattr(created_book, 'id') else created_book
        
        # Log activity for network discovery
        metadata = json.dumps({"source": data_source})
        log_activity(
            user_did=repo_did,
            activity_type='book_added',
            db_tables=db_tables,
            bookshelf_id=bookshelf[0].id,
            book_id=book_id,
            metadata=metadata
        )
        
        logger.info(f"Successfully stored {data_source} book: {record.get('title')} (ID: {book_id})")
        
    except Exception as e:
        logger.error(f"Error storing book from {data_source}: {e}", exc_info=True)
