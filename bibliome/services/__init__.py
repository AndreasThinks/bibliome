"""Services package for Bibliome.

This package contains business logic services separated from routes and data access.
"""

from .permissions import (
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

__all__ = [
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
]
