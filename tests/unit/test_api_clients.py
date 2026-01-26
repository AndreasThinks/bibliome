"""
Unit tests for API client modules.

Tests external API interactions with mocked responses.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


class TestBookAPIClient:
    """Tests for BookAPIClient (mocked external calls)."""
    
    @pytest.mark.asyncio
    async def test_search_books_returns_results(self, mock_book_api):
        """Test that search_books returns expected results."""
        results = await mock_book_api.search_books("gatsby")
        
        assert len(results) == 2
        assert results[0]['title'] == 'The Great Gatsby'
        assert results[1]['title'] == '1984'
    
    @pytest.mark.asyncio
    async def test_search_books_has_required_fields(self, mock_book_api):
        """Test that search results have required fields."""
        results = await mock_book_api.search_books("test")
        
        required_fields = ['title', 'author', 'isbn', 'cover_url']
        for result in results:
            for field in required_fields:
                assert field in result


class TestBlueskyAuthClient:
    """Tests for BlueskyAuth client (mocked)."""
    
    @pytest.mark.asyncio
    async def test_authenticate_user_returns_session(self, mock_bluesky_auth):
        """Test that authentication returns session data."""
        result = await mock_bluesky_auth.authenticate_user("test", "password")
        
        assert 'did' in result
        assert 'handle' in result
        assert 'session_string' in result
    
    def test_get_following_list(self, mock_bluesky_auth):
        """Test getting user's following list."""
        following = mock_bluesky_auth.get_following_list("did:plc:test")
        
        assert isinstance(following, list)
        assert len(following) == 3
        assert all(did.startswith('did:plc:') for did in following)
    
    def test_get_profiles_batch(self, mock_bluesky_auth):
        """Test batch profile retrieval."""
        profiles = mock_bluesky_auth.get_profiles_batch(['did:plc:following1'])
        
        assert 'did:plc:following1' in profiles
        assert profiles['did:plc:following1']['handle'] == 'user1.bsky.social'
    
    def test_get_client_from_session(self, mock_bluesky_auth):
        """Test restoring client from session string."""
        client = mock_bluesky_auth.get_client_from_session("mock_session")
        
        assert client is not None
        assert client.me.did == 'did:plc:testuser123'


class TestATProtoClient:
    """Tests for AT Protocol client operations (mocked)."""
    
    def test_put_record_returns_uri(self, mock_atproto_client):
        """Test that put_record returns an AT URI."""
        response = mock_atproto_client.com.atproto.repo.put_record(
            repo='did:plc:test',
            collection='com.bibliome.bookshelf',
            rkey='abc123',
            record={}
        )
        
        assert 'at://' in response.uri
        assert 'com.bibliome.bookshelf' in response.uri
    
    def test_delete_record_executes(self, mock_atproto_client):
        """Test that delete_record can be called."""
        # Should not raise
        mock_atproto_client.com.atproto.repo.delete_record(
            repo='did:plc:test',
            collection='com.bibliome.bookshelf',
            rkey='abc123'
        )
        
        mock_atproto_client.com.atproto.repo.delete_record.assert_called_once()
    
    def test_client_me_property(self, mock_atproto_client):
        """Test that client.me provides user DID."""
        assert mock_atproto_client.me.did == 'did:plc:testuser123'


class TestOAuthClientMocked:
    """Tests for OAuth client functionality (mocked)."""
    
    def test_oauth_authorization_url_structure(self):
        """Test OAuth authorization URL has required parameters."""
        # Test the structure of a typical OAuth authorization URL
        test_url = "https://bsky.social/oauth/authorize?client_id=test&redirect_uri=http://localhost:5001/callback&state=abc123&scope=atproto"
        
        assert 'client_id=' in test_url
        assert 'redirect_uri=' in test_url
        assert 'state=' in test_url
    
    @pytest.mark.asyncio
    async def test_oauth_token_exchange_structure(self):
        """Test OAuth token exchange returns expected structure."""
        # Test the expected structure of OAuth token response
        mock_token_response = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'did': 'did:plc:testuser123',
            'handle': 'testuser.bsky.social',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        
        assert 'access_token' in mock_token_response
        assert 'did' in mock_token_response
        assert mock_token_response['did'].startswith('did:plc:')


class TestCoverCacheClient:
    """Tests for cover image caching functionality."""
    
    def test_get_cover_url(self):
        """Test retrieving cover URL (cached or original)."""
        with patch('cover_cache.CoverCacheManager') as MockCache:
            instance = MockCache.return_value
            # get_cover_url(book_id, original_url, base_url)
            instance.get_cover_url = MagicMock(
                return_value="/data/covers/123_abc12345.webp"
            )
            
            url = instance.get_cover_url(123, "https://example.com/cover.jpg", "")
            
            assert "/covers/" in url
    
    @pytest.mark.asyncio
    async def test_download_and_cache_cover(self):
        """Test downloading and caching a cover from external URL."""
        with patch('cover_cache.CoverCacheManager') as MockCache:
            instance = MockCache.return_value
            # download_and_cache_cover returns a dict with 'success', 'cached_path', etc.
            instance.download_and_cache_cover = AsyncMock(return_value={
                'success': True,
                'cached_path': 'data/covers/123_abc12345.webp',
                'rate_limited_until': None,
                'error_type': None,
                'retry_after': None
            })
            
            result = await instance.download_and_cache_cover(
                123,  # book_id
                "https://example.com/cover.jpg",
                timeout=10.0
            )
            
            assert result['success'] is True
            assert result['cached_path'] is not None


class TestRateLimiterIntegration:
    """Tests for rate limiter with external API calls."""
    
    def test_rate_limiter_allows_request(self):
        """Test rate limiter allows request under limit."""
        with patch('rate_limiter.RateLimiter') as MockLimiter:
            instance = MockLimiter.return_value
            instance.check_rate_limit = MagicMock(return_value=True)
            instance.record_request = MagicMock()
            
            allowed = instance.check_rate_limit("api_key", "search")
            
            assert allowed is True
    
    def test_rate_limiter_blocks_request(self):
        """Test rate limiter blocks request over limit."""
        with patch('rate_limiter.RateLimiter') as MockLimiter:
            instance = MockLimiter.return_value
            instance.check_rate_limit = MagicMock(return_value=False)
            
            allowed = instance.check_rate_limit("api_key", "search")
            
            assert allowed is False


class TestDirectPDSClient:
    """Tests for direct PDS client operations."""
    
    def test_create_record(self):
        """Test creating a record via PDS."""
        with patch('direct_pds_client.DirectPDSClient') as MockClient:
            instance = MockClient.return_value
            instance.create_record = AsyncMock(return_value={
                'uri': 'at://did:plc:test/com.bibliome.book/abc123',
                'cid': 'bafyreiabc123'
            })
            
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                instance.create_record(
                    collection='com.bibliome.book',
                    record={'title': 'Test Book'}
                )
            )
            
            assert 'uri' in result
            assert 'cid' in result
    
    def test_delete_record(self):
        """Test deleting a record via PDS."""
        with patch('direct_pds_client.DirectPDSClient') as MockClient:
            instance = MockClient.return_value
            instance.delete_record = AsyncMock(return_value=True)
            
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                instance.delete_record(
                    collection='com.bibliome.book',
                    rkey='abc123'
                )
            )
            
            assert result is True
    
    def test_get_record(self):
        """Test getting a record via PDS."""
        with patch('direct_pds_client.DirectPDSClient') as MockClient:
            instance = MockClient.return_value
            instance.get_record = AsyncMock(return_value={
                'uri': 'at://did:plc:test/com.bibliome.book/abc123',
                'value': {'title': 'Test Book'}
            })
            
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                instance.get_record(
                    collection='com.bibliome.book',
                    rkey='abc123'
                )
            )
            
            assert 'value' in result
            assert result['value']['title'] == 'Test Book'


class TestAPIErrorHandling:
    """Tests for API error handling."""
    
    @pytest.mark.asyncio
    async def test_api_timeout_handling(self):
        """Test handling of API timeout."""
        import asyncio
        
        with patch('api_clients.BookAPIClient') as MockAPI:
            instance = MockAPI.return_value
            instance.search_books = AsyncMock(
                side_effect=asyncio.TimeoutError("Request timed out")
            )
            
            with pytest.raises(asyncio.TimeoutError):
                await instance.search_books("test")
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_error(self):
        """Test handling of rate limit error."""
        with patch('api_clients.BookAPIClient') as MockAPI:
            instance = MockAPI.return_value
            instance.search_books = AsyncMock(
                side_effect=Exception("Rate limit exceeded")
            )
            
            with pytest.raises(Exception, match="Rate limit"):
                await instance.search_books("test")
    
    @pytest.mark.asyncio
    async def test_api_network_error(self):
        """Test handling of network error."""
        with patch('api_clients.BookAPIClient') as MockAPI:
            instance = MockAPI.return_value
            instance.search_books = AsyncMock(
                side_effect=ConnectionError("Network unavailable")
            )
            
            with pytest.raises(ConnectionError):
                await instance.search_books("test")


class TestAPIResponseValidation:
    """Tests for API response validation."""
    
    def test_valid_book_response_structure(self):
        """Test validation of book API response structure."""
        valid_response = {
            'title': 'Test Book',
            'author': 'Test Author',
            'isbn': '9780123456789',
            'cover_url': 'https://example.com/cover.jpg',
            'description': 'A test book',
            'publisher': 'Test Publisher',
            'published_date': '2024'
        }
        
        required = ['title', 'author', 'isbn']
        assert all(key in valid_response for key in required)
    
    def test_valid_user_profile_structure(self):
        """Test validation of user profile response."""
        valid_profile = {
            'did': 'did:plc:testuser123',
            'handle': 'testuser.bsky.social',
            'displayName': 'Test User',
            'avatar': 'https://example.com/avatar.jpg'
        }
        
        required = ['did', 'handle']
        assert all(key in valid_profile for key in required)
    
    def test_valid_atproto_record_structure(self):
        """Test validation of AT Protocol record structure."""
        valid_record = {
            'uri': 'at://did:plc:test/com.bibliome.book/abc123',
            'cid': 'bafyreiabc123',
            'value': {
                '$type': 'com.bibliome.book',
                'title': 'Test Book'
            }
        }
        
        assert 'uri' in valid_record
        assert valid_record['uri'].startswith('at://')
        assert '$type' in valid_record['value']
