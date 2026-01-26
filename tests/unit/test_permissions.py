"""
Unit tests for the permission system in models.py.

These tests verify that role-based access control works correctly
for all bookshelf operations.
"""

import pytest
from datetime import datetime, timezone, timedelta


# ============================================================================
# Test can_view_bookshelf
# ============================================================================

class TestCanViewBookshelf:
    """Tests for the can_view_bookshelf permission function."""
    
    @pytest.mark.unit
    def test_public_shelf_viewable_by_anyone(self, db_with_shelf):
        """Public shelves should be viewable by anyone, including anonymous users."""
        from models import can_view_bookshelf
        
        db_tables, _, shelf = db_with_shelf
        
        # Anonymous user (None)
        assert can_view_bookshelf(shelf, None, db_tables) is True
        
        # Random user who isn't the owner
        assert can_view_bookshelf(shelf, "did:plc:randomuser", db_tables) is True
        
        # Owner
        assert can_view_bookshelf(shelf, shelf.owner_did, db_tables) is True
    
    @pytest.mark.unit
    def test_link_only_shelf_viewable_by_anyone(self, db_with_shelf):
        """Link-only shelves should be viewable by anyone with the link."""
        from models import can_view_bookshelf
        
        db_tables, _, shelf = db_with_shelf
        
        # Update shelf to link-only
        db_tables['bookshelves'].update({'privacy': 'link-only'}, shelf.id)
        shelf.privacy = 'link-only'
        
        # Anonymous user
        assert can_view_bookshelf(shelf, None, db_tables) is True
        
        # Random user
        assert can_view_bookshelf(shelf, "did:plc:randomuser", db_tables) is True
    
    @pytest.mark.unit
    def test_private_shelf_not_viewable_by_anonymous(self, db_with_shelf):
        """Private shelves should not be viewable by anonymous users."""
        from models import can_view_bookshelf
        
        db_tables, _, shelf = db_with_shelf
        
        # Update shelf to private
        db_tables['bookshelves'].update({'privacy': 'private'}, shelf.id)
        shelf.privacy = 'private'
        
        # Anonymous user should not be able to view
        assert can_view_bookshelf(shelf, None, db_tables) is False
    
    @pytest.mark.unit
    def test_private_shelf_viewable_by_owner(self, db_with_shelf):
        """Private shelves should be viewable by the owner."""
        from models import can_view_bookshelf
        
        db_tables, owner, shelf = db_with_shelf
        
        # Update shelf to private
        db_tables['bookshelves'].update({'privacy': 'private'}, shelf.id)
        shelf.privacy = 'private'
        
        # Owner should be able to view
        assert can_view_bookshelf(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_private_shelf_viewable_by_members(self, db_with_permissions):
        """Private shelves should be viewable by users with any permission level."""
        from models import can_view_bookshelf
        
        db_tables, shelf, users = db_with_permissions
        
        # Update shelf to private
        db_tables['bookshelves'].update({'privacy': 'private'}, shelf.id)
        shelf.privacy = 'private'
        
        # All permission levels should be able to view
        for role in ['viewer', 'contributor', 'moderator', 'owner']:
            assert can_view_bookshelf(shelf, users[role].did, db_tables) is True


# ============================================================================
# Test can_add_books
# ============================================================================

class TestCanAddBooks:
    """Tests for the can_add_books permission function."""
    
    @pytest.mark.unit
    def test_owner_can_add_books(self, db_with_shelf):
        """Owners should always be able to add books."""
        from models import can_add_books
        
        db_tables, owner, shelf = db_with_shelf
        
        assert can_add_books(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_anonymous_cannot_add_books(self, db_with_shelf):
        """Anonymous users should never be able to add books."""
        from models import can_add_books
        
        db_tables, _, shelf = db_with_shelf
        
        assert can_add_books(shelf, None, db_tables) is False
    
    @pytest.mark.unit
    def test_viewer_cannot_add_books(self, db_with_permissions):
        """Viewers should not be able to add books."""
        from models import can_add_books
        
        db_tables, shelf, users = db_with_permissions
        
        # SQLite stores boolean as 0/1, so check equality not identity
        assert can_add_books(shelf, users['viewer'].did, db_tables) == False
    
    @pytest.mark.unit
    def test_contributor_can_add_books(self, db_with_permissions):
        """Contributors should be able to add books."""
        from models import can_add_books
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_add_books(shelf, users['contributor'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_moderator_can_add_books(self, db_with_permissions):
        """Moderators should be able to add books."""
        from models import can_add_books
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_add_books(shelf, users['moderator'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_self_join_allows_any_logged_in_user(self, db_with_shelf):
        """When self_join is enabled, any logged-in user can add books."""
        from models import can_add_books
        
        db_tables, _, shelf = db_with_shelf
        
        # Enable self_join
        db_tables['bookshelves'].update({'self_join': True}, shelf.id)
        shelf.self_join = True
        
        # Random logged-in user should be able to add books
        assert can_add_books(shelf, "did:plc:randomuser", db_tables) is True
    
    @pytest.mark.unit
    def test_self_join_still_requires_login(self, db_with_shelf):
        """Even with self_join, anonymous users cannot add books."""
        from models import can_add_books
        
        db_tables, _, shelf = db_with_shelf
        
        # Enable self_join
        db_tables['bookshelves'].update({'self_join': True}, shelf.id)
        shelf.self_join = True
        
        # Anonymous user should still not be able to add books
        assert can_add_books(shelf, None, db_tables) is False


# ============================================================================
# Test can_remove_books
# ============================================================================

class TestCanRemoveBooks:
    """Tests for the can_remove_books permission function."""
    
    @pytest.mark.unit
    def test_owner_can_remove_books(self, db_with_shelf):
        """Owners should be able to remove books."""
        from models import can_remove_books
        
        db_tables, owner, shelf = db_with_shelf
        
        assert can_remove_books(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_moderator_can_remove_books(self, db_with_permissions):
        """Moderators should be able to remove books."""
        from models import can_remove_books
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_remove_books(shelf, users['moderator'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_contributor_cannot_remove_books(self, db_with_permissions):
        """Contributors should NOT be able to remove books."""
        from models import can_remove_books
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_remove_books(shelf, users['contributor'].did, db_tables) is False
    
    @pytest.mark.unit
    def test_viewer_cannot_remove_books(self, db_with_permissions):
        """Viewers should not be able to remove books."""
        from models import can_remove_books
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_remove_books(shelf, users['viewer'].did, db_tables) is False
    
    @pytest.mark.unit
    def test_anonymous_cannot_remove_books(self, db_with_shelf):
        """Anonymous users should never be able to remove books."""
        from models import can_remove_books
        
        db_tables, _, shelf = db_with_shelf
        
        assert can_remove_books(shelf, None, db_tables) is False


# ============================================================================
# Test can_edit_bookshelf
# ============================================================================

class TestCanEditBookshelf:
    """Tests for the can_edit_bookshelf permission function."""
    
    @pytest.mark.unit
    def test_owner_can_edit(self, db_with_shelf):
        """Owners should be able to edit bookshelf details."""
        from models import can_edit_bookshelf
        
        db_tables, owner, shelf = db_with_shelf
        
        assert can_edit_bookshelf(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_moderator_can_edit(self, db_with_permissions):
        """Moderators should be able to edit bookshelf details."""
        from models import can_edit_bookshelf
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_edit_bookshelf(shelf, users['moderator'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_contributor_cannot_edit(self, db_with_permissions):
        """Contributors should NOT be able to edit bookshelf details."""
        from models import can_edit_bookshelf
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_edit_bookshelf(shelf, users['contributor'].did, db_tables) is False
    
    @pytest.mark.unit
    def test_viewer_cannot_edit(self, db_with_permissions):
        """Viewers should not be able to edit bookshelf details."""
        from models import can_edit_bookshelf
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_edit_bookshelf(shelf, users['viewer'].did, db_tables) is False


# ============================================================================
# Test can_manage_members
# ============================================================================

class TestCanManageMembers:
    """Tests for the can_manage_members permission function."""
    
    @pytest.mark.unit
    def test_owner_can_manage_members(self, db_with_shelf):
        """Owners should be able to manage members."""
        from models import can_manage_members
        
        db_tables, owner, shelf = db_with_shelf
        
        assert can_manage_members(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_moderator_can_manage_members(self, db_with_permissions):
        """Moderators should be able to manage members."""
        from models import can_manage_members
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_manage_members(shelf, users['moderator'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_contributor_cannot_manage_members(self, db_with_permissions):
        """Contributors should NOT be able to manage members."""
        from models import can_manage_members
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_manage_members(shelf, users['contributor'].did, db_tables) is False


# ============================================================================
# Test can_generate_invites
# ============================================================================

class TestCanGenerateInvites:
    """Tests for the can_generate_invites permission function."""
    
    @pytest.mark.unit
    def test_owner_can_generate_invites(self, db_with_shelf):
        """Owners should be able to generate invites."""
        from models import can_generate_invites
        
        db_tables, owner, shelf = db_with_shelf
        
        assert can_generate_invites(shelf, owner.did, db_tables) is True
    
    @pytest.mark.unit
    def test_moderator_can_generate_invites(self, db_with_permissions):
        """Moderators should be able to generate invites."""
        from models import can_generate_invites
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_generate_invites(shelf, users['moderator'].did, db_tables) is True
    
    @pytest.mark.unit
    def test_contributor_cannot_generate_invites(self, db_with_permissions):
        """Contributors should NOT be able to generate invites."""
        from models import can_generate_invites
        
        db_tables, shelf, users = db_with_permissions
        
        assert can_generate_invites(shelf, users['contributor'].did, db_tables) is False
    
    @pytest.mark.unit
    def test_anonymous_cannot_generate_invites(self, db_with_shelf):
        """Anonymous users should never be able to generate invites."""
        from models import can_generate_invites
        
        db_tables, _, shelf = db_with_shelf
        
        assert can_generate_invites(shelf, None, db_tables) is False


# ============================================================================
# Test can_invite_role (role hierarchy)
# ============================================================================

class TestCanInviteRole:
    """Tests for the role hierarchy in can_invite_role function."""
    
    @pytest.mark.unit
    def test_owner_can_invite_any_role(self):
        """Owners should be able to invite moderators, contributors, and viewers."""
        from models import can_invite_role
        
        assert can_invite_role('owner', 'moderator') is True
        assert can_invite_role('owner', 'contributor') is True
        assert can_invite_role('owner', 'viewer') is True
        
        # But not other owners
        assert can_invite_role('owner', 'owner') is False
    
    @pytest.mark.unit
    def test_moderator_can_invite_lower_roles(self):
        """Moderators should be able to invite contributors and viewers."""
        from models import can_invite_role
        
        assert can_invite_role('moderator', 'contributor') is True
        assert can_invite_role('moderator', 'viewer') is True
        
        # But not moderators or owners
        assert can_invite_role('moderator', 'moderator') is False
        assert can_invite_role('moderator', 'owner') is False
    
    @pytest.mark.unit
    def test_contributor_can_only_invite_viewers(self):
        """Contributors should only be able to invite viewers."""
        from models import can_invite_role
        
        assert can_invite_role('contributor', 'viewer') is True
        
        # But not contributors or higher
        assert can_invite_role('contributor', 'contributor') is False
        assert can_invite_role('contributor', 'moderator') is False
        assert can_invite_role('contributor', 'owner') is False
    
    @pytest.mark.unit
    def test_viewer_cannot_invite_anyone(self):
        """Viewers should not be able to invite anyone."""
        from models import can_invite_role
        
        assert can_invite_role('viewer', 'viewer') is False
        assert can_invite_role('viewer', 'contributor') is False
        assert can_invite_role('viewer', 'moderator') is False
        assert can_invite_role('viewer', 'owner') is False
    
    @pytest.mark.unit
    def test_invalid_roles_return_false(self):
        """Invalid roles should return False."""
        from models import can_invite_role
        
        assert can_invite_role('invalid', 'viewer') is False
        assert can_invite_role('owner', 'invalid') is False
        assert can_invite_role('', 'viewer') is False


# ============================================================================
# Test validate_invite
# ============================================================================

class TestValidateInvite:
    """Tests for invite validation."""
    
    @pytest.mark.unit
    def test_valid_invite_returns_invite(self, db_with_shelf, factory):
        """A valid, active invite should be returned."""
        from models import validate_invite
        
        db_tables, owner, shelf = db_with_shelf
        
        invite = factory.create_invite(shelf.id, owner.did)
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        result = validate_invite(created_invite.invite_code, db_tables)
        
        assert result is not None
        assert result.invite_code == created_invite.invite_code
    
    @pytest.mark.unit
    def test_invalid_code_returns_none(self, db_tables):
        """An invalid invite code should return None."""
        from models import validate_invite
        
        result = validate_invite("INVALID_CODE_123", db_tables)
        
        assert result is None
    
    @pytest.mark.unit
    def test_expired_invite_returns_none(self, db_with_shelf, factory):
        """An expired invite should return None."""
        from models import validate_invite
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create an expired invite
        invite = factory.create_invite(
            shelf.id, 
            owner.did,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        result = validate_invite(created_invite.invite_code, db_tables)
        
        assert result is None
    
    @pytest.mark.unit
    def test_max_uses_reached_returns_none(self, db_with_shelf, factory):
        """An invite that has reached max uses should return None."""
        from models import validate_invite
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create an invite with max_uses already reached
        invite = factory.create_invite(
            shelf.id, 
            owner.did,
            max_uses=5,
            uses_count=5
        )
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        result = validate_invite(created_invite.invite_code, db_tables)
        
        assert result is None
    
    @pytest.mark.unit
    def test_inactive_invite_returns_none(self, db_with_shelf, factory):
        """An inactive invite should return None."""
        from models import validate_invite
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create an inactive invite
        invite = factory.create_invite(
            shelf.id, 
            owner.did,
            is_active=False
        )
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        result = validate_invite(created_invite.invite_code, db_tables)
        
        assert result is None
    
    @pytest.mark.unit
    def test_invite_with_remaining_uses_valid(self, db_with_shelf, factory):
        """An invite with uses remaining should be valid."""
        from models import validate_invite
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create an invite with uses remaining
        invite = factory.create_invite(
            shelf.id, 
            owner.did,
            max_uses=5,
            uses_count=3
        )
        created_invite = db_tables['bookshelf_invites'].insert(invite)
        
        result = validate_invite(created_invite.invite_code, db_tables)
        
        assert result is not None


# ============================================================================
# Test get_user_role
# ============================================================================

class TestGetUserRole:
    """Tests for getting a user's role for a bookshelf."""
    
    @pytest.mark.unit
    def test_owner_returns_owner_role(self, db_with_shelf):
        """Owner should return 'owner' role."""
        from models import get_user_role
        
        db_tables, owner, shelf = db_with_shelf
        
        role = get_user_role(shelf, owner.did, db_tables)
        
        assert role == 'owner'
    
    @pytest.mark.unit
    def test_permission_roles_returned_correctly(self, db_with_permissions):
        """Users with permissions should return their correct role."""
        from models import get_user_role
        
        db_tables, shelf, users = db_with_permissions
        
        assert get_user_role(shelf, users['viewer'].did, db_tables) == 'viewer'
        assert get_user_role(shelf, users['contributor'].did, db_tables) == 'contributor'
        assert get_user_role(shelf, users['moderator'].did, db_tables) == 'moderator'
    
    @pytest.mark.unit
    def test_no_permission_returns_none(self, db_with_shelf):
        """User with no permission should return None."""
        from models import get_user_role
        
        db_tables, _, shelf = db_with_shelf
        
        role = get_user_role(shelf, "did:plc:randomuser", db_tables)
        
        assert role is None
    
    @pytest.mark.unit
    def test_anonymous_returns_none(self, db_with_shelf):
        """Anonymous user should return None."""
        from models import get_user_role
        
        db_tables, _, shelf = db_with_shelf
        
        role = get_user_role(shelf, None, db_tables)
        
        assert role is None
