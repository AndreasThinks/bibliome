"""Data model classes for Bibliome.

This module contains only the dataclass definitions for database models.
All business logic, queries, and AT Protocol operations are in separate modules.

Note: These classes use dataclass with default values ordered correctly
(required fields first, optional fields after). They are compatible with
FastLite's db.create() transformation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User model for Bluesky/AT-Proto users."""
    did: str  # Bluesky DID (Decentralized Identifier) - primary key
    handle: str
    display_name: str = ""
    avatar_url: str = ""
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    # Remote origin tracking
    is_remote: bool = False
    discovered_at: Optional[datetime] = None
    last_seen_remote: Optional[datetime] = None
    remote_sync_status: str = "local"
    # OAuth 2.0 fields
    oauth_access_token: str = ""
    oauth_refresh_token: str = ""
    oauth_token_expires_at: Optional[datetime] = None
    oauth_dpop_private_jwk: str = ""  # PEM-encoded private key material
    oauth_dpop_nonce_authserver: str = ""
    oauth_dpop_nonce_pds: str = ""
    oauth_issuer: str = ""
    oauth_pds_url: str = ""
    oauth_state: str = ""
    oauth_code_verifier: str = ""


@dataclass
class Bookshelf:
    """Bookshelf model for organizing books."""
    name: str
    owner_did: str
    id: Optional[int] = None  # Auto-incrementing primary key
    slug: str = ""  # URL-friendly identifier
    description: str = ""
    privacy: str = "public"  # 'public', 'link-only', 'private'
    self_join: bool = False  # Allow anyone to join as contributor
    atproto_uri: str = ""  # AT-Proto URI of the record
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Remote origin tracking
    is_remote: bool = False
    remote_owner_did: str = ""
    discovered_at: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    remote_sync_status: str = "local"
    original_atproto_uri: str = ""


@dataclass
class Book:
    """Book model with metadata from external APIs."""
    bookshelf_id: int
    title: str
    added_by_did: str
    id: Optional[int] = None  # Auto-incrementing primary key
    isbn: str = ""
    author: str = ""
    cover_url: str = ""
    description: str = ""
    publisher: str = ""
    published_date: str = ""
    page_count: int = 0
    atproto_uri: str = ""  # AT-Proto URI of the record
    added_at: Optional[datetime] = None
    # Cover caching fields
    cached_cover_path: str = ""
    cover_cached_at: Optional[datetime] = None
    cover_rate_limited_until: Optional[datetime] = None
    # Remote origin tracking
    is_remote: bool = False
    remote_added_by_did: str = ""
    discovered_at: Optional[datetime] = None
    original_atproto_uri: str = ""
    remote_sync_status: str = "local"


@dataclass
class Permission:
    """Permission model for role-based access to bookshelves."""
    bookshelf_id: int
    user_did: str
    role: str  # 'viewer', 'contributor', 'moderator', 'owner'
    granted_by_did: str
    id: Optional[int] = None  # Auto-incrementing primary key
    # UNUSED: status and invited_at fields preserved for future approval workflows
    # Currently all invites create active permissions immediately via invite links
    status: str = "active"  # 'active', 'pending' - pending status not currently used
    granted_at: Optional[datetime] = None
    invited_at: Optional[datetime] = None  # UNUSED: preserved for future direct invitation features
    joined_at: Optional[datetime] = None


@dataclass
class BookshelfInvite:
    """Invitation model for sharing bookshelves."""
    bookshelf_id: int
    invite_code: str  # Unique random string
    role: str  # Role to assign when invite is redeemed
    created_by_did: str
    id: Optional[int] = None  # Auto-incrementing primary key
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Optional expiration
    max_uses: Optional[int] = None  # Optional usage limit
    uses_count: int = 0
    is_active: bool = True


@dataclass
class Comment:
    """Comment model for book discussions."""
    book_id: int
    bookshelf_id: int  # Reference to bookshelf for context/permissions
    user_did: str
    content: str
    id: Optional[int] = None  # Auto-incrementing primary key
    parent_comment_id: Optional[int] = None  # For threaded replies
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_edited: bool = False
    # AT Protocol sync fields
    atproto_uri: str = ""
    is_remote: bool = False
    remote_user_did: str = ""
    discovered_at: Optional[datetime] = None
    original_atproto_uri: str = ""
    remote_sync_status: str = "local"


@dataclass
class Activity:
    """Track user activity for social feed."""
    user_did: str
    activity_type: str  # 'bookshelf_created', 'book_added', 'comment_added'
    id: Optional[int] = None  # Auto-incrementing primary key
    bookshelf_id: Optional[int] = None
    book_id: Optional[int] = None
    created_at: Optional[datetime] = None
    # JSON field for additional metadata
    metadata: str = ""  # JSON string for flexible data


@dataclass
class SyncLog:
    """Log synchronization activities."""
    sync_type: str  # 'user', 'bookshelf', 'book'
    target_id: str  # The ID/DID of the synced record
    action: str  # 'discovered', 'imported', 'updated', 'failed'
    id: Optional[int] = None
    details: str = ""  # JSON with additional info
    timestamp: Optional[datetime] = None


@dataclass
class ProcessStatus:
    """Process status model."""
    process_name: str
    process_type: str
    status: str
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    restart_count: int = 0
    error_message: str = ""
    config_data: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProcessLog:
    """Process log model."""
    process_name: str
    log_level: str
    event_type: str
    message: str
    id: Optional[int] = None
    details: str = ""
    timestamp: Optional[datetime] = None


@dataclass
class ProcessMetric:
    """Process metric model."""
    process_name: str
    metric_name: str
    metric_value: int
    id: Optional[int] = None
    metric_type: str = "counter"
    recorded_at: Optional[datetime] = None


# Legacy alias - some code may use Upvote but it's no longer a separate model
# In the new system, each Book record represents a user's vote
Upvote = None  # Deprecated - use Book records instead
