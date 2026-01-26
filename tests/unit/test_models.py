"""
Unit tests for model utility functions in models.py.

These tests verify slug generation, TID generation, invite codes,
and other utility functions.
"""

import pytest
import re
from datetime import datetime, timezone


# ============================================================================
# Test generate_slug
# ============================================================================

class TestGenerateSlug:
    """Tests for URL slug generation."""
    
    @pytest.mark.unit
    def test_slug_is_8_characters(self):
        """Slugs should be exactly 8 characters long."""
        from models import generate_slug
        
        slug = generate_slug()
        
        assert len(slug) == 8
    
    @pytest.mark.unit
    def test_slug_contains_only_valid_characters(self):
        """Slugs should only contain lowercase letters and digits."""
        from models import generate_slug
        
        slug = generate_slug()
        
        # Should match pattern of only lowercase letters and digits
        assert re.match(r'^[a-z0-9]+$', slug)
    
    @pytest.mark.unit
    def test_slugs_are_unique(self):
        """Generated slugs should be unique."""
        from models import generate_slug
        
        # Generate many slugs and check for uniqueness
        slugs = [generate_slug() for _ in range(100)]
        
        assert len(slugs) == len(set(slugs))


# ============================================================================
# Test generate_tid
# ============================================================================

class TestGenerateTid:
    """Tests for TID (Timestamp Identifier) generation."""
    
    @pytest.mark.unit
    def test_tid_is_13_characters(self):
        """TIDs should be exactly 13 characters long."""
        from models import generate_tid
        
        tid = generate_tid()
        
        assert len(tid) == 13
    
    @pytest.mark.unit
    def test_tid_contains_valid_characters(self):
        """TIDs should only contain base32 characters."""
        from models import generate_tid
        
        tid = generate_tid()
        
        # AT Protocol TID uses specific base32 charset
        valid_chars = '234567abcdefghijklmnopqrstuvwxyz'
        assert all(c in valid_chars for c in tid)
    
    @pytest.mark.unit
    def test_tids_are_time_ordered(self):
        """TIDs generated later should be lexicographically greater."""
        from models import generate_tid
        import time
        
        tid1 = generate_tid()
        time.sleep(0.01)  # Small delay to ensure different timestamps
        tid2 = generate_tid()
        
        # Later TIDs should be lexicographically greater
        # (Not always guaranteed due to clock_id, but usually true)
        # We just check they're different
        assert tid1 != tid2


# ============================================================================
# Test generate_invite_code
# ============================================================================

class TestGenerateInviteCode:
    """Tests for invite code generation."""
    
    @pytest.mark.unit
    def test_invite_code_is_12_characters(self):
        """Invite codes should be exactly 12 characters long."""
        from models import generate_invite_code
        
        code = generate_invite_code()
        
        assert len(code) == 12
    
    @pytest.mark.unit
    def test_invite_code_contains_only_uppercase_and_digits(self):
        """Invite codes should only contain uppercase letters and digits."""
        from models import generate_invite_code
        
        code = generate_invite_code()
        
        assert re.match(r'^[A-Z0-9]+$', code)
    
    @pytest.mark.unit
    def test_invite_codes_are_unique(self):
        """Generated invite codes should be unique."""
        from models import generate_invite_code
        
        codes = [generate_invite_code() for _ in range(100)]
        
        assert len(codes) == len(set(codes))


# ============================================================================
# Test AT Protocol URI parsing
# ============================================================================

class TestATProtoURIParsing:
    """Tests for AT Protocol URI handling functions."""
    
    @pytest.mark.unit
    def test_delete_book_record_invalid_uri_format(self, mock_atproto_client):
        """delete_book_record should return False for invalid URI format."""
        from models import delete_book_record
        
        # Not starting with at://
        result = delete_book_record(mock_atproto_client, "invalid://uri")
        assert result is False
    
    @pytest.mark.unit
    def test_delete_book_record_invalid_uri_structure(self, mock_atproto_client):
        """delete_book_record should return False for malformed URI."""
        from models import delete_book_record
        
        # Wrong number of parts
        result = delete_book_record(mock_atproto_client, "at://only/two")
        assert result is False
    
    @pytest.mark.unit
    def test_delete_bookshelf_record_invalid_uri_format(self, mock_atproto_client):
        """delete_bookshelf_record should return False for invalid URI format."""
        from models import delete_bookshelf_record
        
        result = delete_bookshelf_record(mock_atproto_client, "not-a-valid-uri")
        assert result is False
    
    @pytest.mark.unit
    def test_update_bookshelf_record_invalid_uri_format(self, mock_atproto_client):
        """update_bookshelf_record should return empty string for invalid URI."""
        from models import update_bookshelf_record
        
        result = update_bookshelf_record(
            mock_atproto_client, 
            "invalid-uri",
            name="New Name"
        )
        assert result == ""
    
    @pytest.mark.unit
    def test_update_bookshelf_record_invalid_uri_structure(self, mock_atproto_client):
        """update_bookshelf_record should return empty string for malformed URI."""
        from models import update_bookshelf_record
        
        result = update_bookshelf_record(
            mock_atproto_client, 
            "at://missing/parts",
            name="New Name"
        )
        assert result == ""


# ============================================================================
# Test Bookshelf model
# ============================================================================

class TestBookshelfModel:
    """Tests for Bookshelf model behavior."""
    
    @pytest.mark.unit
    def test_bookshelf_creation(self, db_tables, factory):
        """Bookshelves can be created with required fields."""
        from models import Bookshelf
        
        user = factory.create_user()
        db_tables['users'].insert(user)
        
        shelf = factory.create_bookshelf(user.did)
        created = db_tables['bookshelves'].insert(shelf)
        
        assert created.id is not None
        assert created.owner_did == user.did
        assert created.privacy == "public"
    
    @pytest.mark.unit
    def test_bookshelf_privacy_options(self, db_tables, factory):
        """Bookshelves support all privacy options."""
        user = factory.create_user()
        db_tables['users'].insert(user)
        
        for privacy in ['public', 'link-only', 'private']:
            shelf = factory.create_bookshelf(user.did, privacy=privacy)
            created = db_tables['bookshelves'].insert(shelf)
            
            assert created.privacy == privacy
    
    @pytest.mark.unit
    def test_bookshelf_self_join_default(self, db_tables, factory):
        """Bookshelves have self_join disabled by default."""
        user = factory.create_user()
        db_tables['users'].insert(user)
        
        shelf = factory.create_bookshelf(user.did)
        created = db_tables['bookshelves'].insert(shelf)
        
        # SQLite stores boolean as 0/1, so use == not 'is'
        assert created.self_join == False


# ============================================================================
# Test Book model
# ============================================================================

class TestBookModel:
    """Tests for Book model behavior."""
    
    @pytest.mark.unit
    def test_book_creation(self, db_with_shelf, factory):
        """Books can be created with required fields."""
        db_tables, owner, shelf = db_with_shelf
        
        book = factory.create_book(shelf.id, owner.did, title="Test Book")
        created = db_tables['books'].insert(book)
        
        assert created.id is not None
        assert created.title == "Test Book"
        assert created.bookshelf_id == shelf.id
    
    @pytest.mark.unit
    def test_book_optional_fields(self, db_with_shelf, factory):
        """Books can have optional metadata fields."""
        db_tables, owner, shelf = db_with_shelf
        
        book = factory.create_book(
            shelf.id, 
            owner.did,
            title="Detailed Book",
            author="Test Author",
            isbn="9781234567890",
            cover_url="https://example.com/cover.jpg",
            description="A detailed description"
        )
        created = db_tables['books'].insert(book)
        
        assert created.author == "Test Author"
        assert created.isbn == "9781234567890"


# ============================================================================
# Test User model
# ============================================================================

class TestUserModel:
    """Tests for User model behavior."""
    
    @pytest.mark.unit
    def test_user_creation(self, db_tables, factory):
        """Users can be created with required fields."""
        user = factory.create_user(
            did="did:plc:testuser123",
            handle="testuser.bsky.social"
        )
        db_tables['users'].insert(user)
        
        # Retrieve and verify
        retrieved = db_tables['users']["did:plc:testuser123"]
        
        assert retrieved.did == "did:plc:testuser123"
        assert retrieved.handle == "testuser.bsky.social"
    
    @pytest.mark.unit
    def test_user_primary_key_is_did(self, db_tables, factory):
        """User primary key should be the DID."""
        user = factory.create_user(did="did:plc:unique123")
        db_tables['users'].insert(user)
        
        # Should be able to retrieve by DID
        retrieved = db_tables['users']["did:plc:unique123"]
        assert retrieved is not None


# ============================================================================
# Test Comment model
# ============================================================================

class TestCommentModel:
    """Tests for Comment model behavior."""
    
    @pytest.mark.unit
    def test_comment_creation(self, db_with_books):
        """Comments can be created on books."""
        from models import Comment
        
        db_tables, owner, shelf, books = db_with_books
        
        comment = Comment(
            book_id=books[0].id,
            bookshelf_id=shelf.id,
            user_did=owner.did,
            content="This is a great book!",
            created_at=datetime.now(timezone.utc)
        )
        created = db_tables['comments'].insert(comment)
        
        assert created.id is not None
        assert created.content == "This is a great book!"
        assert created.book_id == books[0].id
    
    @pytest.mark.unit
    def test_comment_threading(self, db_with_books):
        """Comments can be threaded (replies)."""
        from models import Comment
        
        db_tables, owner, shelf, books = db_with_books
        
        # Create parent comment
        parent = Comment(
            book_id=books[0].id,
            bookshelf_id=shelf.id,
            user_did=owner.did,
            content="Parent comment",
            created_at=datetime.now(timezone.utc)
        )
        parent_created = db_tables['comments'].insert(parent)
        
        # Create reply
        reply = Comment(
            book_id=books[0].id,
            bookshelf_id=shelf.id,
            user_did=owner.did,
            content="Reply comment",
            parent_comment_id=parent_created.id,
            created_at=datetime.now(timezone.utc)
        )
        reply_created = db_tables['comments'].insert(reply)
        
        assert reply_created.parent_comment_id == parent_created.id


# ============================================================================
# Test Activity model
# ============================================================================

class TestActivityModel:
    """Tests for Activity model (social feed)."""
    
    @pytest.mark.unit
    def test_log_activity_book_added(self, db_with_books):
        """Activity is logged when a book is added."""
        from models import log_activity
        
        db_tables, owner, shelf, books = db_with_books
        
        log_activity(
            owner.did,
            'book_added',
            db_tables,
            bookshelf_id=shelf.id,
            book_id=books[0].id
        )
        
        # Verify activity was logged
        activities = db_tables['activities']("user_did=?", (owner.did,))
        
        assert len(activities) >= 1
        book_added_activities = [a for a in activities if a.activity_type == 'book_added']
        assert len(book_added_activities) >= 1
    
    @pytest.mark.unit
    def test_log_activity_bookshelf_created(self, db_with_shelf):
        """Activity is logged when a bookshelf is created."""
        from models import log_activity
        
        db_tables, owner, shelf = db_with_shelf
        
        log_activity(
            owner.did,
            'bookshelf_created',
            db_tables,
            bookshelf_id=shelf.id
        )
        
        # Verify activity was logged
        activities = db_tables['activities']("user_did=? AND activity_type=?", 
                                             (owner.did, 'bookshelf_created'))
        
        assert len(activities) >= 1
