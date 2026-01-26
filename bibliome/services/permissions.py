"""Permission checking logic for Bibliome.

This module contains all role-based access control (RBAC) logic for bookshelves,
books, and comments. Permissions are checked against both ownership and 
explicit permission records.
"""

from datetime import datetime
from typing import Optional, Dict, Any


def check_permission(bookshelf, user_did: str, required_roles: list, db_tables: Dict[str, Any]) -> bool:
    """Check if user has required permission for a bookshelf.
    
    Args:
        bookshelf: The bookshelf object to check permissions for
        user_did: The user's DID (Decentralized Identifier)
        required_roles: List of roles that grant the permission
        db_tables: Database tables dictionary
        
    Returns:
        True if user has permission, False otherwise
    """
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


def can_view_bookshelf(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can view a bookshelf.
    
    Public and link-only shelves are viewable by anyone.
    Private shelves require explicit permission.
    """
    if bookshelf.privacy == 'public':
        return True
    elif bookshelf.privacy == 'link-only':
        return True  # Anyone with the link can view
    else:  # private
        return check_permission(bookshelf, user_did, ['viewer', 'contributor', 'moderator', 'owner'], db_tables)


def can_add_books(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can add books and vote (contributor, moderator, owner, or self-join enabled)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)


def can_vote_books(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can vote on books (contributor, moderator, owner, or self-join enabled)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)


def can_remove_books(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can remove books (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never remove books
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)


def can_edit_bookshelf(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can edit bookshelf details (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never edit
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)


def can_manage_members(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can manage members (moderator with limits, owner full access)."""
    if not user_did:
        return False
    return bookshelf.owner_did == user_did or check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)


def can_generate_invites(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can generate invites (moderator, owner)."""
    if not user_did:
        return False  # Anonymous users can never generate invites
    
    # Owner can always generate invites
    if bookshelf.owner_did == user_did:
        return True
    
    # Moderators can generate invites
    return check_permission(bookshelf, user_did, ['moderator', 'owner'], db_tables)


def can_delete_shelf(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can delete the entire bookshelf (owner only)."""
    if not user_did:
        return False
    return bookshelf.owner_did == user_did


def can_comment_on_books(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can comment on books (same as can_add_books)."""
    if not user_did:
        return False
    # Check explicit permissions OR self-join enabled for logged-in users
    return (check_permission(bookshelf, user_did, ['contributor', 'moderator', 'owner'], db_tables) 
            or bookshelf.self_join)


def can_edit_comment(comment, user_did: str, db_tables: Dict[str, Any]) -> bool:
    """Check if user can edit a comment (own comments only)."""
    if not user_did:
        return False
    return comment.user_did == user_did


def can_delete_comment(comment, user_did: str, db_tables: Dict[str, Any]) -> bool:
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


def get_user_role(bookshelf, user_did: str, db_tables: Dict[str, Any]) -> Optional[str]:
    """Get the user's role for a bookshelf.
    
    Returns:
        Role string ('owner', 'moderator', 'contributor', 'viewer') or None
    """
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
    """Check if a user with inviter_role can invite someone with target_role.
    
    Users can only invite others with a role level lower than their own.
    """
    role_hierarchy = ['viewer', 'contributor', 'moderator', 'owner']
    
    if inviter_role not in role_hierarchy or target_role not in role_hierarchy:
        return False
    
    inviter_level = role_hierarchy.index(inviter_role)
    target_level = role_hierarchy.index(target_role)
    
    # Users can only invite others with a role level lower than their own
    return inviter_level > target_level


def validate_invite(invite_code: str, db_tables: Dict[str, Any]) -> Optional[object]:
    """Validate an invite code and return the invite if valid.
    
    Checks:
    - Invite exists and is active
    - Invite has not expired
    - Max uses not reached
    
    Args:
        invite_code: The invite code to validate
        db_tables: Database tables dictionary
        
    Returns:
        The invite object if valid, None otherwise
    """
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
