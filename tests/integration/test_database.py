"""
Integration tests for database operations.

Tests CRUD operations and complex queries against the SQLite database.
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestUserOperations:
    """Tests for User CRUD operations."""
    
    def test_create_user(self, db_tables, factory):
        """Test creating a new user."""
        user = factory.create_user(
            did="did:plc:newuser123",
            handle="newuser.bsky.social",
            display_name="New User"
        )
        
        created = db_tables['users'].insert(user)
        
        # User uses 'did' as primary key, not 'id'
        assert created.did == "did:plc:newuser123"
        assert created.handle == "newuser.bsky.social"
    
    def test_get_user_by_did(self, db_with_user):
        """Test retrieving user by DID."""
        db_tables, test_user = db_with_user
        
        found = db_tables['users'].get(test_user.did)
        
        assert found is not None
        assert found.handle == test_user.handle
    
    def test_update_user(self, db_with_user):
        """Test updating user details."""
        db_tables, test_user = db_with_user
        
        test_user.display_name = "Updated Name"
        test_user.last_login = datetime.now(timezone.utc)
        db_tables['users'].update(test_user)
        
        updated = db_tables['users'].get(test_user.did)
        assert updated.display_name == "Updated Name"
    
    def test_find_user_by_handle(self, db_with_user):
        """Test finding user by handle."""
        db_tables, test_user = db_with_user
        
        # FastLite uses where_args, not args
        results = list(db_tables['users'](where="handle = ?", where_args=[test_user.handle]))
        
        assert len(results) == 1
        assert results[0].did == test_user.did


class TestBookshelfOperations:
    """Tests for Bookshelf CRUD operations."""
    
    def test_create_bookshelf(self, db_with_user, factory):
        """Test creating a new bookshelf."""
        db_tables, user = db_with_user
        
        shelf = factory.create_bookshelf(
            owner_did=user.did,
            name="My Test Shelf",
            privacy="public"
        )
        
        created = db_tables['bookshelves'].insert(shelf)
        
        assert created.id is not None
        assert created.name == "My Test Shelf"
        assert created.owner_did == user.did
    
    def test_get_bookshelf_by_slug(self, db_with_shelf):
        """Test retrieving bookshelf by slug."""
        db_tables, user, shelf = db_with_shelf
        
        results = list(db_tables['bookshelves'](where="slug = ?", where_args=[shelf.slug]))
        
        assert len(results) == 1
        assert results[0].name == shelf.name
    
    def test_update_bookshelf_privacy(self, db_with_shelf):
        """Test updating bookshelf privacy setting."""
        db_tables, user, shelf = db_with_shelf
        
        shelf.privacy = "private"
        shelf.updated_at = datetime.now(timezone.utc)
        db_tables['bookshelves'].update(shelf)
        
        updated = db_tables['bookshelves'].get(shelf.id)
        assert updated.privacy == "private"
    
    def test_get_user_bookshelves(self, db_with_user, factory):
        """Test getting all bookshelves for a user."""
        db_tables, user = db_with_user
        
        # Create multiple shelves
        for i in range(3):
            shelf = factory.create_bookshelf(
                owner_did=user.did,
                name=f"Shelf {i}"
            )
            db_tables['bookshelves'].insert(shelf)
        
        shelves = list(db_tables['bookshelves'](where="owner_did = ?", where_args=[user.did]))
        
        assert len(shelves) == 3


class TestBookOperations:
    """Tests for Book CRUD operations."""
    
    def test_add_book_to_shelf(self, db_with_shelf, factory):
        """Test adding a book to a bookshelf."""
        db_tables, user, shelf = db_with_shelf
        
        book = factory.create_book(
            bookshelf_id=shelf.id,
            added_by_did=user.did,
            title="Test Book",
            author="Test Author"
        )
        
        created = db_tables['books'].insert(book)
        
        assert created.id is not None
        assert created.title == "Test Book"
        assert created.bookshelf_id == shelf.id
    
    def test_get_books_for_shelf(self, db_with_books):
        """Test getting all books for a bookshelf."""
        db_tables, user, shelf, books = db_with_books
        
        shelf_books = list(db_tables['books'](where="bookshelf_id = ?", where_args=[shelf.id]))
        
        assert len(shelf_books) == 3
    
    def test_delete_book(self, db_with_books):
        """Test deleting a book from a shelf."""
        db_tables, user, shelf, books = db_with_books
        
        book_to_delete = books[0]
        db_tables['books'].delete(book_to_delete.id)
        
        remaining = list(db_tables['books'](where="bookshelf_id = ?", where_args=[shelf.id]))
        assert len(remaining) == 2
    
    def test_search_books_by_title(self, db_with_books):
        """Test searching books by title."""
        db_tables, user, shelf, books = db_with_books
        
        results = list(db_tables['books'](where="title LIKE ?", where_args=["%Book 1%"]))
        
        assert len(results) == 1
        assert "Book 1" in results[0].title


class TestPermissionOperations:
    """Tests for Permission CRUD operations."""
    
    def test_grant_permission(self, db_with_shelf, factory):
        """Test granting permission to a user."""
        from models import Permission
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create another user
        new_user = factory.create_user(did="did:plc:newmember123")
        db_tables['users'].insert(new_user)
        
        permission = Permission(
            bookshelf_id=shelf.id,
            user_did=new_user.did,
            role="contributor",
            status="active",
            granted_by_did=owner.did,
            granted_at=datetime.now(timezone.utc),
            joined_at=datetime.now(timezone.utc)
        )
        
        created = db_tables['permissions'].insert(permission)
        
        assert created.id is not None
        assert created.role == "contributor"
    
    def test_get_shelf_members(self, db_with_permissions):
        """Test getting all members of a bookshelf."""
        db_tables, shelf, users = db_with_permissions
        
        permissions = list(db_tables['permissions'](
            where="bookshelf_id = ? AND status = ?",
            where_args=[shelf.id, "active"]
        ))
        
        # Should have viewer, contributor, and moderator
        assert len(permissions) == 3
    
    def test_update_permission_role(self, db_with_permissions):
        """Test updating a user's role."""
        db_tables, shelf, users = db_with_permissions
        
        # Get contributor's permission
        perms = list(db_tables['permissions'](
            where="bookshelf_id = ? AND user_did = ?",
            where_args=[shelf.id, users['contributor'].did]
        ))
        
        perm = perms[0]
        perm.role = "moderator"
        db_tables['permissions'].update(perm)
        
        updated = db_tables['permissions'].get(perm.id)
        assert updated.role == "moderator"
    
    def test_revoke_permission(self, db_with_permissions):
        """Test revoking a permission."""
        db_tables, shelf, users = db_with_permissions
        
        perms = list(db_tables['permissions'](
            where="bookshelf_id = ? AND user_did = ?",
            where_args=[shelf.id, users['viewer'].did]
        ))
        
        perm = perms[0]
        perm.status = "revoked"
        db_tables['permissions'].update(perm)
        
        # Check active permissions count decreased
        active = list(db_tables['permissions'](
            where="bookshelf_id = ? AND status = ?",
            where_args=[shelf.id, "active"]
        ))
        assert len(active) == 2


class TestInviteOperations:
    """Tests for BookshelfInvite operations."""
    
    def test_create_invite(self, db_with_shelf, factory):
        """Test creating a bookshelf invite."""
        db_tables, owner, shelf = db_with_shelf
        
        invite = factory.create_invite(
            bookshelf_id=shelf.id,
            created_by_did=owner.did,
            role="contributor"
        )
        
        created = db_tables['bookshelf_invites'].insert(invite)
        
        assert created.id is not None
        assert created.is_active == True
        assert len(created.invite_code) > 0
    
    def test_find_invite_by_code(self, db_with_shelf, factory):
        """Test finding invite by code."""
        db_tables, owner, shelf = db_with_shelf
        
        invite = factory.create_invite(
            bookshelf_id=shelf.id,
            created_by_did=owner.did,
            invite_code="ABC123XY"
        )
        db_tables['bookshelf_invites'].insert(invite)
        
        results = list(db_tables['bookshelf_invites'](
            where="invite_code = ? AND is_active = ?",
            where_args=["ABC123XY", True]
        ))
        
        assert len(results) == 1
        assert results[0].bookshelf_id == shelf.id
    
    def test_increment_invite_uses(self, db_with_shelf, factory):
        """Test incrementing invite usage count."""
        db_tables, owner, shelf = db_with_shelf
        
        invite = factory.create_invite(
            bookshelf_id=shelf.id,
            created_by_did=owner.did,
            max_uses=5,
            uses_count=0
        )
        created = db_tables['bookshelf_invites'].insert(invite)
        
        created.uses_count += 1
        db_tables['bookshelf_invites'].update(created)
        
        updated = db_tables['bookshelf_invites'].get(created.id)
        assert updated.uses_count == 1
    
    def test_deactivate_expired_invite(self, db_with_shelf, factory):
        """Test deactivating an expired invite."""
        db_tables, owner, shelf = db_with_shelf
        
        # Create expired invite
        invite = factory.create_invite(
            bookshelf_id=shelf.id,
            created_by_did=owner.did,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        created = db_tables['bookshelf_invites'].insert(invite)
        
        created.is_active = False
        db_tables['bookshelf_invites'].update(created)
        
        updated = db_tables['bookshelf_invites'].get(created.id)
        assert updated.is_active == False


class TestCommentOperations:
    """Tests for Comment CRUD operations."""
    
    def test_create_comment(self, db_with_books):
        """Test creating a comment on a book."""
        from models import Comment
        
        db_tables, user, shelf, books = db_with_books
        
        comment = Comment(
            book_id=books[0].id,
            user_did=user.did,
            content="Great book!",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        created = db_tables['comments'].insert(comment)
        
        assert created.id is not None
        assert created.content == "Great book!"
    
    def test_get_comments_for_book(self, db_with_books):
        """Test getting all comments for a book."""
        from models import Comment
        
        db_tables, user, shelf, books = db_with_books
        
        # Add multiple comments
        for i in range(3):
            comment = Comment(
                book_id=books[0].id,
                user_did=user.did,
                content=f"Comment {i}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db_tables['comments'].insert(comment)
        
        comments = list(db_tables['comments'](where="book_id = ?", where_args=[books[0].id]))
        
        assert len(comments) == 3
    
    def test_delete_comment(self, db_with_books):
        """Test deleting a comment."""
        from models import Comment
        from apswutils.db import NotFoundError
        
        db_tables, user, shelf, books = db_with_books
        
        comment = Comment(
            book_id=books[0].id,
            user_did=user.did,
            content="To be deleted",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        created = db_tables['comments'].insert(comment)
        
        db_tables['comments'].delete(created.id)
        
        # FastLite raises NotFoundError when item doesn't exist
        with pytest.raises(NotFoundError):
            db_tables['comments'].get(created.id)


class TestActivityLogOperations:
    """Tests for Activity operations."""
    
    def test_log_activity(self, db_with_shelf):
        """Test logging user activity."""
        from models import log_activity
        
        db_tables, user, shelf = db_with_shelf
        
        # Use the log_activity function - signature: (user_did, activity_type, db_tables, ...)
        log_activity(
            user.did,
            "bookshelf_created",
            db_tables,
            bookshelf_id=shelf.id
        )
        
        # Table is 'activities', not 'activity_logs'
        logs = list(db_tables['activities'](where="user_did = ?", where_args=[user.did]))
        
        assert len(logs) >= 1
        assert logs[0].activity_type == "bookshelf_created"
    
    def test_get_user_activity(self, db_with_shelf):
        """Test getting activity for a user."""
        from models import log_activity
        
        db_tables, user, shelf = db_with_shelf
        
        # Log multiple activities
        activity_types = ["bookshelf_created", "book_added", "comment_added"]
        for activity_type in activity_types:
            log_activity(
                user.did,
                activity_type,
                db_tables,
                bookshelf_id=shelf.id
            )
        
        logs = list(db_tables['activities'](where="user_did = ?", where_args=[user.did]))
        
        assert len(logs) == 3
    
    def test_get_shelf_activity(self, db_with_shelf, factory):
        """Test getting activity for a bookshelf."""
        from models import log_activity
        
        db_tables, owner, shelf = db_with_shelf
        
        # Create another user
        other_user = factory.create_user(did="did:plc:otheruser123")
        db_tables['users'].insert(other_user)
        
        # Log activities from different users
        for u in [owner, other_user]:
            log_activity(
                u.did,
                "book_added",
                db_tables,
                bookshelf_id=shelf.id
            )
        
        logs = list(db_tables['activities'](where="bookshelf_id = ?", where_args=[shelf.id]))
        
        assert len(logs) == 2


class TestComplexQueries:
    """Tests for complex database queries."""
    
    def test_get_public_shelves_with_book_count(self, db_with_books):
        """Test query for public shelves with book count."""
        db_tables, user, shelf, books = db_with_books
        
        # Get shelf with book count using raw query
        shelf_books = list(db_tables['books'](where="bookshelf_id = ?", where_args=[shelf.id]))
        
        assert len(shelf_books) == 3
    
    def test_get_user_permissions_across_shelves(self, db_with_user, factory):
        """Test getting all permissions for a user across shelves."""
        from models import Permission
        
        db_tables, user = db_with_user
        
        # Create multiple shelves with permissions
        for i in range(3):
            owner = factory.create_user(did=f"did:plc:owner{i}")
            db_tables['users'].insert(owner)
            
            shelf = factory.create_bookshelf(owner_did=owner.did, name=f"Shelf {i}")
            created_shelf = db_tables['bookshelves'].insert(shelf)
            
            perm = Permission(
                bookshelf_id=created_shelf.id,
                user_did=user.did,
                role="contributor",
                status="active",
                granted_by_did=owner.did,
                granted_at=datetime.now(timezone.utc),
                joined_at=datetime.now(timezone.utc)
            )
            db_tables['permissions'].insert(perm)
        
        perms = list(db_tables['permissions'](where="user_did = ?", where_args=[user.did]))
        
        assert len(perms) == 3
    
    def test_search_books_across_shelves(self, db_with_user, factory):
        """Test searching books across multiple bookshelves."""
        db_tables, user = db_with_user
        
        # Create multiple shelves with books
        for i in range(2):
            shelf = factory.create_bookshelf(owner_did=user.did, name=f"Shelf {i}")
            created_shelf = db_tables['bookshelves'].insert(shelf)
            
            # Add books with searchable titles
            for j in range(2):
                book = factory.create_book(
                    bookshelf_id=created_shelf.id,
                    added_by_did=user.did,
                    title=f"Python Book {i}-{j}" if j == 0 else f"Java Book {i}-{j}"
                )
                db_tables['books'].insert(book)
        
        # Search for Python books
        python_books = list(db_tables['books'](where="title LIKE ?", where_args=["%Python%"]))
        
        assert len(python_books) == 2
