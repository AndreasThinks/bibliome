"""External API clients for book metadata."""

import httpx
import os
import logging
import time
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from rate_limiter import ExponentialBackoffRateLimiter
from performance_monitor import get_performance_monitor

load_dotenv()

logger = logging.getLogger(__name__)


def _track_api_call(service: str, endpoint: str, duration_ms: float,
                    success: bool = True, status_code: int = None,
                    error_message: str = None):
    """Helper to track API calls to the performance monitor."""
    monitor = get_performance_monitor()
    if monitor:
        monitor.record_api_call(
            service=service,
            endpoint=endpoint,
            duration_ms=duration_ms,
            status_code=status_code,
            success=success,
            error_message=error_message
        )


class BookAPIClient:
    """Client for fetching book metadata from external APIs."""
    
    def __init__(self):
        self.google_books_url = "https://www.googleapis.com/books/v1/volumes"
        self.open_library_url = "https://openlibrary.org/api/books"
        self.google_api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
        
        # Configure rate limiting for Google Books API
        google_books_rate_limit = float(os.getenv('GOOGLE_BOOKS_RATE_LIMIT_PER_MINUTE', '100')) / 60
        max_retries = int(os.getenv('GOOGLE_BOOKS_MAX_RETRIES', '5'))
        base_delay = float(os.getenv('GOOGLE_BOOKS_BASE_DELAY', '1.0'))
        max_delay = float(os.getenv('GOOGLE_BOOKS_MAX_DELAY', '60.0'))
        
        self.rate_limiter = ExponentialBackoffRateLimiter(
            tokens_per_second=google_books_rate_limit,
            max_tokens=int(google_books_rate_limit * 10),
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            jitter=True
        )
        
        logger.info(f"[bibliome_scanner] BookAPIClient initialized with rate limit: {google_books_rate_limit:.2f} req/sec, max retries: {max_retries}")
    
    async def search_books(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for books using Google Books API with Open Library fallback."""
        start_time = time.perf_counter()
        try:
            google_results = await self._search_google_books(query, max_results)
            duration_ms = (time.perf_counter() - start_time) * 1000
            if google_results:
                _track_api_call('google_books', 'search', duration_ms, success=True)
                return google_results

            # Google failed or returned empty, try Open Library
            ol_start = time.perf_counter()
            ol_results = await self._search_open_library(query, max_results)
            ol_duration = (time.perf_counter() - ol_start) * 1000
            _track_api_call('open_library', 'search', ol_duration, success=bool(ol_results))
            return ol_results
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _track_api_call('google_books', 'search', duration_ms, success=False, error_message=str(e))
            raise
    
    async def _search_google_books(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Google Books API with title-focused search and rate limiting."""
        try:
            title_query = f"intitle:{query.replace(' ', '+')}"
            params = {
                "q": title_query,
                "maxResults": min(max_results, 40),
                "printType": "books"
            }
            
            if self.google_api_key:
                params["key"] = self.google_api_key
            
            logger.debug(f"[bibliome_scanner] Trying Google Books title search with query: '{title_query}'")
            
            async def make_title_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.google_books_url, params=params)
                    response.raise_for_status()
                    return response
            
            try:
                response = await self.rate_limiter.execute_with_backoff(make_title_request)
                data = response.json()
                results = self._parse_google_books(data.get('items', []))
                
                if results:
                    logger.debug(f"[bibliome_scanner] Google Books title search returned {len(results)} results")
                    return results
                else:
                    logger.debug("[bibliome_scanner] Title search returned 0 results")
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    logger.warning(f"[bibliome_scanner] Title search got 400 error, response: {e.response.text[:200]}")
                else:
                    logger.warning(f"[bibliome_scanner] Title search failed with status {e.response.status_code}")
            except Exception as e:
                logger.warning(f"[bibliome_scanner] Title search failed: {e}")
            
            logger.debug("[bibliome_scanner] Trying Google Books general search...")
            general_query = query.replace(' ', '+')
            general_params = {
                "q": general_query,
                "maxResults": min(max_results, 40),
                "printType": "books"
            }
            
            if self.google_api_key:
                general_params["key"] = self.google_api_key
            
            async def make_general_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.google_books_url, params=general_params)
                    response.raise_for_status()
                    return response
            
            try:
                general_response = await self.rate_limiter.execute_with_backoff(make_general_request)
                general_data = general_response.json()
                general_results = self._parse_google_books(general_data.get('items', []))
                logger.debug(f"[bibliome_scanner] Google Books general search returned {len(general_results)} results")
                return general_results
                
            except httpx.HTTPStatusError as e:
                logger.error(f"[bibliome_scanner] Google Books API error: {e.response.status_code}")
                if e.response.status_code == 400:
                    logger.error(f"[bibliome_scanner] General search 400 error: {e.response.text[:200]}")
                return []
            except Exception as e:
                logger.error(f"[bibliome_scanner] General search failed: {e}")
                return []
                    
        except Exception as e:
            logger.error(f"[bibliome_scanner] Google Books search error: {e}", exc_info=True)
            return []
    
    async def _search_open_library(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Open Library API."""
        try:
            search_url = "https://openlibrary.org/search.json"
            params = {
                "q": query,
                "limit": min(max_results, 100),
                "fields": "key,title,author_name,isbn,cover_i,publisher,publish_date,number_of_pages_median"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info(f"Trying Open Library search with query: '{query}'")
                response = await client.get(search_url, params=params)
                logger.debug(f"Open Library response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_open_library(data.get('docs', []))
                    logger.info(f"Open Library search returned {len(results)} results")
                    return results
                else:
                    logger.error(f"Open Library API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Open Library search error: {e}", exc_info=True)
            return []
    
    def _parse_google_books(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Google Books API response."""
        books = []
        for item in items:
            info = item.get('volumeInfo', {})
            isbn = self._extract_isbn(info.get('industryIdentifiers', []))
            images = info.get('imageLinks', {})
            cover_url = images.get('thumbnail', '').replace('http://', 'https://')
            
            books.append({
                'title': info.get('title', 'Unknown Title'),
                'author': ', '.join(info.get('authors', ['Unknown Author'])),
                'isbn': isbn,
                'description': info.get('description', ''),
                'publisher': info.get('publisher', ''),
                'published_date': info.get('publishedDate', ''),
                'page_count': info.get('pageCount', 0),
                'cover_url': cover_url,
                'source': 'google_books'
            })
        return books
    
    def _parse_open_library(self, docs: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Open Library API response."""
        books = []
        for doc in docs:
            cover_id = doc.get('cover_i')
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ''
            isbn_list = doc.get('isbn', [])
            isbn = isbn_list[0] if isbn_list else ''
            
            books.append({
                'title': doc.get('title', 'Unknown Title'),
                'author': ', '.join(doc.get('author_name', ['Unknown Author'])),
                'isbn': isbn,
                'description': '',
                'publisher': ', '.join(doc.get('publisher', [''])),
                'published_date': ', '.join(doc.get('publish_date', [''])),
                'page_count': doc.get('number_of_pages_median', 0) or 0,
                'cover_url': cover_url,
                'source': 'open_library'
            })
        return books
    
    def _extract_isbn(self, identifiers: List[Dict]) -> str:
        """Extract ISBN from Google Books identifiers."""
        for identifier in identifiers:
            if identifier.get('type') == 'ISBN_13':
                return identifier.get('identifier', '')
        
        for identifier in identifiers:
            if identifier.get('type') == 'ISBN_10':
                return identifier.get('identifier', '')
        
        return ''
    
    async def get_book_details(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Get detailed book information by ISBN with rate limiting."""
        if not isbn:
            return None
        
        try:
            params = {"q": f"isbn:{isbn}"}
            if self.google_api_key:
                params["key"] = self.google_api_key
            
            logger.debug(f"[bibliome_scanner] Looking up book by ISBN: {isbn}")
            
            async def make_isbn_request():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.google_books_url, params=params)
                    response.raise_for_status()
                    return response
            
            try:
                response = await self.rate_limiter.execute_with_backoff(make_isbn_request)
                data = response.json()
                items = data.get('items', [])
                if items:
                    parsed = self._parse_google_books(items)
                    logger.debug(f"[bibliome_scanner] Found book details for ISBN {isbn}")
                    return parsed[0] if parsed else None
                else:
                    logger.debug(f"[bibliome_scanner] No book found for ISBN {isbn}")
                    return None
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"[bibliome_scanner] ISBN lookup failed with status {e.response.status_code}")
                return None
            except Exception as e:
                logger.error(f"[bibliome_scanner] ISBN lookup failed: {e}")
                return None
                
        except Exception as e:
            logger.error(f"[bibliome_scanner] ISBN lookup error: {e}", exc_info=True)
        
        return None
