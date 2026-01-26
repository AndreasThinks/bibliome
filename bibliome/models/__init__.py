"""Models package for Bibliome.

This package provides database models, setup functions, and query utilities.
All exports are re-exported here for backward compatibility with existing imports.
"""

# Entity classes
from .entities import (
    User,
    Bookshelf,
    Book,
    Permission,
    BookshelfInvite,
    Comment,
    Activity,
    SyncLog,
    ProcessStatus,
    ProcessLog,
    ProcessMetric,
    Upvote,  # Deprecated alias
)

# Database setup
from .database import (
    setup_database,
    get_database,
    validate_primary_key_setup,
)

__all__ = [
    # Entities
    'User',
    'Bookshelf',
    'Book',
    'Permission',
    'BookshelfInvite',
    'Comment',
    'Activity',
    'SyncLog',
    'ProcessStatus',
    'ProcessLog',
    'ProcessMetric',
    'Upvote',
    # Database
    'setup_database',
    'get_database',
    'validate_primary_key_setup',
]
