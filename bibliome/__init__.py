"""Bibliome - Building the very best reading lists, together.

This is the main package for Bibliome, a decentralized book sharing platform
built on AT Protocol (Bluesky).

Package Structure:
- bibliome.models: Data model classes and database setup
- bibliome.services: Business logic services (permissions, etc.)
- bibliome.atproto: AT Protocol integration (record operations)
- bibliome.routes: HTTP route handlers (planned)
- bibliome.components: UI components (planned)
"""

__version__ = "0.1.0"

# Re-export commonly used items for convenience
from .models import (
    # Entity classes
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
    # Database
    setup_database,
)

from .services import (
    # Permissions
    check_permission,
    can_view_bookshelf,
    can_add_books,
    can_vote_books,
    can_remove_books,
    can_edit_bookshelf,
    can_manage_members,
    can_generate_invites,
    can_delete_shelf,
    can_comment_on_books,
    can_edit_comment,
    can_delete_comment,
    get_user_role,
    can_invite_role,
    validate_invite,
)

from .atproto import (
    # Record operations
    generate_tid,
    create_bookshelf_record,
    add_book_record,
    update_bookshelf_record,
    delete_bookshelf_record,
    delete_book_record,
    create_comment_record,
    update_comment_record,
    delete_comment_record,
)

__all__ = [
    # Version
    '__version__',
    # Models
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
    'setup_database',
    # Permissions
    'check_permission',
    'can_view_bookshelf',
    'can_add_books',
    'can_vote_books',
    'can_remove_books',
    'can_edit_bookshelf',
    'can_manage_members',
    'can_generate_invites',
    'can_delete_shelf',
    'can_comment_on_books',
    'can_edit_comment',
    'can_delete_comment',
    'get_user_role',
    'can_invite_role',
    'validate_invite',
    # AT Protocol
    'generate_tid',
    'create_bookshelf_record',
    'add_book_record',
    'update_bookshelf_record',
    'delete_bookshelf_record',
    'delete_book_record',
    'create_comment_record',
    'update_comment_record',
    'delete_comment_record',
]
