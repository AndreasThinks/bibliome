"""
Shared pytest fixtures for Bibliome tests.

This module provides test fixtures for:
- In-memory SQLite database with all migrations applied
- Mock Bluesky authentication
- Mock external API clients
- Test data factories
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def db_tables():
    """
    Create an in-memory SQLite database with all tables.
    
    This fixture provides a fresh database for each test, ensuring
    test isolation.
    """
    from models import setup_database
    
    # Use in-memory database for fast tests
    tables = setup_database(memory=True)
    
    yield tables
    
    # Cleanup is automatic with in-memory DB


@pytest.fixture
def db_with_user(db_tables):
    """Database with a single test user already created."""
    from models import User
    
    test_user = User(
        did="did:plc:testuser123",
        handle="testuser.bsky.social",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        created_at=datetime.now(timezone.utc),
        last_login=datetime.now(timezone.utc)
    )
    db_tables['users'].insert(test_user)
    
    return db_tables, test_user


@pytest.fixture
def db_with_shelf(db_with_user):
    """Database with a test user and a public bookshelf."""
    from models import Bookshelf, generate_slug
    
    db_tables, test_user = db_with_user
    
    test_shelf = Bookshelf(
        name="Test Bookshelf",
        slug=generate_slug(),
        description="A test bookshelf for testing",
        owner_did=test_user.did,
        privacy="public",
        self_join=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    created_shelf = db_tables['bookshelves'].insert(test_shelf)
    
    return db_tables, test_user, created_shelf


@pytest.fixture
def db_with_books(db_with_shelf):
    """Database with a user, shelf, and some test books."""
    from models import Book
    
    db_tables, test_user, test_shelf = db_with_shelf
    
    books = []
    for i in range(3):
        book = Book(
            bookshelf_id=test_shelf.id,
            title=f"Test Book {i+1}",
            author=f"Test Author {i+1}",
            isbn=f"978000000000{i}",
            cover_url=f"https://example.com/cover{i}.jpg",
            description=f"Description for test book {i+1}",
            added_by_did=test_user.did,
            added_at=datetime.now(timezone.utc)
        )
        created_book = db_tables['books'].insert(book)
        books.append(created_book)
    
    return db_tables, test_user, test_shelf, books


@pytest.fixture
def db_with_permissions(db_with_shelf):
    """Database with user, shelf, and various permission levels."""
    from models import User, Permission
    
    db_tables, owner, shelf = db_with_shelf
    
    # Create users with different roles
    users = {}
    roles = ['viewer', 'contributor', 'moderator']
    
    for role in roles:
        user = User(
            did=f"did:plc:{role}user123",
            handle=f"{role}user.bsky.social",
            display_name=f"{role.title()} User",
            created_at=datetime.now(timezone.utc),
            last_login=datetime.now(timezone.utc)
        )
        db_tables['users'].insert(user)
        
        # Create permission for this user
        permission = Permission(
            bookshelf_id=shelf.id,
            user_did=user.did,
            role=role,
            status='active',
            granted_by_did=owner.did,
            granted_at=datetime.now(timezone.utc),
            joined_at=datetime.now(timezone.utc)
        )
        db_tables['permissions'].insert(permission)
        
        users[role] = user
    
    users['owner'] = owner
    
    return db_tables, shelf, users


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def mock_auth_data() -> Dict[str, Any]:
    """Create mock authentication data for a logged-in user."""
    return {
        'did': 'did:plc:testuser123',
        'handle': 'testuser.bsky.social',
        'display_name': 'Test User',
        'avatar_url': 'https://example.com/avatar.jpg',
        'session_string': 'mock_session_string_for_testing',
        'access_jwt': 'mock_access_jwt',
        'refresh_jwt': 'mock_refresh_jwt'
    }


@pytest.fixture
def mock_admin_auth_data(mock_auth_data) -> Dict[str, Any]:
    """Create mock authentication data for an admin user."""
    admin_data = mock_auth_data.copy()
    admin_data['handle'] = 'admin.bsky.social'
    admin_data['did'] = 'did:plc:adminuser123'
    return admin_data


@pytest.fixture
def mock_bluesky_auth():
    """Mock BlueskyAuth class for testing without real API calls."""
    with patch('auth.BlueskyAuth') as MockAuth:
        instance = MockAuth.return_value
        
        # Mock authenticate_user
        instance.authenticate_user = AsyncMock(return_value={
            'did': 'did:plc:testuser123',
            'handle': 'testuser.bsky.social',
            'display_name': 'Test User',
            'avatar_url': 'https://example.com/avatar.jpg',
            'session_string': 'mock_session',
            'access_jwt': 'mock_access',
            'refresh_jwt': 'mock_refresh'
        })
        
        # Mock get_following_list
        instance.get_following_list = MagicMock(return_value=[
            'did:plc:following1',
            'did:plc:following2',
            'did:plc:following3'
        ])
        
        # Mock get_profiles_batch
        instance.get_profiles_batch = MagicMock(return_value={
            'did:plc:following1': {
                'did': 'did:plc:following1',
                'handle': 'user1.bsky.social',
                'display_name': 'User 1',
                'avatar_url': ''
            }
        })
        
        # Mock get_client_from_session
        mock_client = MagicMock()
        mock_client.me = MagicMock(did='did:plc:testuser123')
        instance.get_client_from_session = MagicMock(return_value=mock_client)
        
        yield instance


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def mock_book_api():
    """Mock BookAPIClient for testing without real API calls."""
    with patch('api_clients.BookAPIClient') as MockAPI:
        instance = MockAPI.return_value
        
        # Mock search_books
        instance.search_books = AsyncMock(return_value=[
            {
                'title': 'The Great Gatsby',
                'author': 'F. Scott Fitzgerald',
                'isbn': '9780743273565',
                'cover_url': 'https://example.com/gatsby.jpg',
                'description': 'A classic novel',
                'publisher': 'Scribner',
                'published_date': '1925',
                'page_count': 180
            },
            {
                'title': '1984',
                'author': 'George Orwell',
                'isbn': '9780451524935',
                'cover_url': 'https://example.com/1984.jpg',
                'description': 'A dystopian novel',
                'publisher': 'Signet Classic',
                'published_date': '1949',
                'page_count': 328
            }
        ])
        
        yield instance


@pytest.fixture
def mock_atproto_client():
    """Mock AT Protocol client for testing record operations."""
    mock_client = MagicMock()
    
    # Mock me property
    mock_client.me = MagicMock()
    mock_client.me.did = 'did:plc:testuser123'
    
    # Mock get_current_time_iso
    mock_client.get_current_time_iso = MagicMock(
        return_value=datetime.now(timezone.utc).isoformat()
    )
    
    # Mock repo operations
    mock_put_response = MagicMock()
    mock_put_response.uri = 'at://did:plc:testuser123/com.bibliome.bookshelf/abc123'
    mock_client.com.atproto.repo.put_record = MagicMock(return_value=mock_put_response)
    mock_client.com.atproto.repo.delete_record = MagicMock()
    mock_client.com.atproto.repo.get_record = MagicMock()
    
    return mock_client


# ============================================================================
# Test Data Factories
# ============================================================================

class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user(
        did: str = None,
        handle: str = None,
        display_name: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a test user dictionary."""
        from models import User
        import secrets
        
        did = did or f"did:plc:test{secrets.token_hex(6)}"
        handle = handle or f"testuser{secrets.token_hex(3)}.bsky.social"
        
        return User(
            did=did,
            handle=handle,
            display_name=display_name or handle.split('.')[0].title(),
            avatar_url=kwargs.get('avatar_url', ''),
            created_at=kwargs.get('created_at', datetime.now(timezone.utc)),
            last_login=kwargs.get('last_login', datetime.now(timezone.utc))
        )
    
    @staticmethod
    def create_bookshelf(
        owner_did: str,
        name: str = None,
        privacy: str = "public",
        **kwargs
    ):
        """Create a test bookshelf."""
        from models import Bookshelf, generate_slug
        import secrets
        
        return Bookshelf(
            name=name or f"Test Shelf {secrets.token_hex(3)}",
            slug=kwargs.get('slug', generate_slug()),
            description=kwargs.get('description', 'A test bookshelf'),
            owner_did=owner_did,
            privacy=privacy,
            self_join=kwargs.get('self_join', False),
            created_at=kwargs.get('created_at', datetime.now(timezone.utc)),
            updated_at=kwargs.get('updated_at', datetime.now(timezone.utc))
        )
    
    @staticmethod
    def create_book(
        bookshelf_id: int,
        added_by_did: str,
        title: str = None,
        **kwargs
    ):
        """Create a test book."""
        from models import Book
        import secrets
        
        return Book(
            bookshelf_id=bookshelf_id,
            title=title or f"Test Book {secrets.token_hex(3)}",
            author=kwargs.get('author', 'Test Author'),
            isbn=kwargs.get('isbn', f"978{secrets.token_hex(5)}"),
            cover_url=kwargs.get('cover_url', ''),
            description=kwargs.get('description', 'A test book'),
            added_by_did=added_by_did,
            added_at=kwargs.get('added_at', datetime.now(timezone.utc))
        )
    
    @staticmethod
    def create_invite(
        bookshelf_id: int,
        created_by_did: str,
        role: str = "contributor",
        **kwargs
    ):
        """Create a test bookshelf invite."""
        from models import BookshelfInvite, generate_invite_code
        
        return BookshelfInvite(
            bookshelf_id=bookshelf_id,
            invite_code=kwargs.get('invite_code', generate_invite_code()),
            role=role,
            created_by_did=created_by_did,
            created_at=kwargs.get('created_at', datetime.now(timezone.utc)),
            expires_at=kwargs.get('expires_at'),
            max_uses=kwargs.get('max_uses'),
            uses_count=kwargs.get('uses_count', 0),
            is_active=kwargs.get('is_active', True)
        )


@pytest.fixture
def factory():
    """Provide access to the test data factory."""
    return TestDataFactory()


# ============================================================================
# Session/Request Mocking
# ============================================================================

@pytest.fixture
def mock_session():
    """Create a mock session object for testing."""
    session_data = {}
    
    class MockSession:
        def get(self, key, default=None):
            return session_data.get(key, default)
        
        def __setitem__(self, key, value):
            session_data[key] = value
        
        def __getitem__(self, key):
            return session_data[key]
        
        def pop(self, key, default=None):
            return session_data.pop(key, default)
        
        def clear(self):
            session_data.clear()
    
    return MockSession()


@pytest.fixture
def mock_request(mock_auth_data):
    """Create a mock request object for testing routes."""
    class MockURL:
        scheme = 'http'
        netloc = 'localhost:5001'
        path = '/'
    
    class MockRequest:
        url = MockURL()
        scope = {'auth': mock_auth_data}
    
    return MockRequest()


# ============================================================================
# Environment Variable Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv('ADMIN_USERNAMES', 'admin.bsky.social,testadmin.bsky.social')
    monkeypatch.setenv('BLUESKY_POST_THRESHOLD', '3')
    monkeypatch.setenv('OAUTH_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('OAUTH_REDIRECT_URI', 'http://localhost:5001/auth/oauth/callback')
    monkeypatch.setenv('CONTACT_EMAIL', 'test@example.com')
    monkeypatch.setenv('SENDER_EMAIL', 'noreply@example.com')
    yield


# ============================================================================
# Async Test Helpers
# ============================================================================

@pytest.fixture
def run_async():
    """Helper fixture to run async functions in sync tests."""
    def _run_async(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
    return _run_async
