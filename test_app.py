"""Basic tests for BookdIt application."""

import pytest
from fasthtml.common import *
from models import setup_database, User, Bookshelf, Book
from datetime import datetime
import tempfile
import os

def test_database_setup():
    """Test database initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_tables = setup_database(db_path)
        
        assert 'db' in db_tables
        assert 'users' in db_tables
        assert 'bookshelves' in db_tables
        assert 'books' in db_tables
        assert 'permissions' in db_tables
        assert 'upvotes' in db_tables

def test_user_creation():
    """Test user model creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_tables = setup_database(db_path)
        
        created_user = db_tables['users'].insert(
            did="did:plc:test123",
            handle="test.bsky.social",
            display_name="Test User"
        )
        assert created_user.did == "did:plc:test123"
        assert created_user.handle == "test.bsky.social"
        assert created_user.display_name == "Test User"

def test_bookshelf_creation():
    """Test bookshelf model creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_tables = setup_database(db_path)
        
        # Create a user first
        db_tables['users'].insert(
            did="did:plc:test123",
            handle="test.bsky.social",
            display_name="Test User"
        )
        
        # Create a bookshelf
        created_shelf = db_tables['bookshelves'].insert(
            name="My Test Books",
            owner_did="did:plc:test123",
            slug="test-books",
            description="A test bookshelf",
            privacy="public"
        )
        
        assert created_shelf.name == "My Test Books"
        assert created_shelf.slug == "test-books"
        assert created_shelf.privacy == "public"
        assert created_shelf.owner_did == "did:plc:test123"

def test_book_creation():
    """Test book model creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_tables = setup_database(db_path)
        
        # Create user and bookshelf first
        db_tables['users'].insert(
            did="did:plc:test123",
            handle="test.bsky.social",
            display_name="Test User"
        )
        
        created_shelf = db_tables['bookshelves'].insert(
            name="My Test Books",
            slug="test-books",
            description="A test bookshelf",
            owner_did="did:plc:test123",
            privacy="public"
        )
        
        # Create a book
        created_book = db_tables['books'].insert(
            bookshelf_id=created_shelf.id,
            isbn="9780123456789",
            title="Test Book",
            author="Test Author",
            description="A test book",
            added_by_did="did:plc:test123"
        )
        
        assert created_book.title == "Test Book"
        assert created_book.author == "Test Author"
        assert created_book.isbn == "9780123456789"
        assert created_book.bookshelf_id == created_shelf.id

def test_permissions():
    """Test permission checking functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_tables = setup_database(db_path)
        
        from models import can_view_bookshelf, can_edit_bookshelf
        
        # Create user and bookshelf
        db_tables['users'].insert(
            did="did:plc:test123",
            handle="test.bsky.social",
            display_name="Test User"
        )
        
        # Public bookshelf
        created_public = db_tables['bookshelves'].insert(
            name="Public Books",
            slug="public-books",
            owner_did="did:plc:test123",
            privacy="public"
        )
        
        # Private bookshelf
        created_private = db_tables['bookshelves'].insert(
            name="Private Books",
            slug="private-books",
            owner_did="did:plc:test123",
            privacy="private"
        )
        
        # Test public shelf permissions
        assert can_view_bookshelf(created_public, None, db_tables) == True  # Anonymous can view public
        assert can_view_bookshelf(created_public, "did:plc:other", db_tables) == True  # Other user can view public
        assert can_view_bookshelf(created_public, "did:plc:test123", db_tables) == True  # Owner can view
        
        # Test private shelf permissions
        assert can_view_bookshelf(created_private, None, db_tables) == False  # Anonymous cannot view private
        assert can_view_bookshelf(created_private, "did:plc:other", db_tables) == False  # Other user cannot view private
        assert can_view_bookshelf(created_private, "did:plc:test123", db_tables) == True  # Owner can view private
        
        # Test edit permissions
        assert can_edit_bookshelf(created_public, "did:plc:test123", db_tables) == True  # Owner can edit
        assert can_edit_bookshelf(created_public, "did:plc:other", db_tables) == False  # Other user cannot edit

if __name__ == "__main__":
    # Run basic tests
    print("Running BookdIt tests...")
    
    try:
        test_database_setup()
        print("✅ Database setup test passed")
        
        test_user_creation()
        print("✅ User creation test passed")
        
        test_bookshelf_creation()
        print("✅ Bookshelf creation test passed")
        
        test_book_creation()
        print("✅ Book creation test passed")
        
        test_permissions()
        print("✅ Permissions test passed")
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
