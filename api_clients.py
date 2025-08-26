"""External API clients for book metadata."""

import httpx
from typing import Optional, List, Dict, Any
import os
import logging
from dotenv import load_dotenv
from fastcore.xtras import flexicache, time_policy

load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class BookAPIClient:
    """Client for fetching book metadata from external APIs."""
    
    def __init__(self):
        self.google_books_url = "https://www.googleapis.com/books/v1/volumes"
        self.open_library_url = "https://openlibrary.org/api/books"
        self.google_api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
    
    @flexicache(time_policy(3600), maxsize=200)  # 1 hour cache, 200 unique searches
    async def search_books(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for books using Google Books API with Open Library fallback. Results cached for 1 hour."""
        logger.debug(f"Cache miss for book search: '{query}' (max_results: {max_results})")
        
        # Try Google Books first
        google_results = await self._search_google_books(query, max_results)
        if google_results:
            return google_results
        
        # Fallback to Open Library
        return await self._search_open_library(query, max_results)
    
    async def _search_google_books(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Google Books API with title-focused search."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # First try a title-focused search using proper Google Books API format
                # According to the docs, intitle: should be used with proper spacing
                title_query = f"intitle:{query.replace(' ', '+')}"
                params = {
                    "q": title_query,
                    "maxResults": min(max_results, 40),  # Google Books limit
                    "printType": "books"
                }
                
                if self.google_api_key:
                    params["key"] = self.google_api_key
                
                logger.info(f"Trying Google Books title search with query: '{title_query}'")
                response = await client.get(self.google_books_url, params=params)
                logger.debug(f"Title search response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_google_books(data.get('items', []))
                    
                    # If title search returns results, use them
                    if results:
                        logger.info(f"Google Books title search returned {len(results)} results")
                        return results
                    else:
                        logger.debug("Title search returned 0 results")
                elif response.status_code == 400:
                    logger.warning(f"Title search got 400 error, response: {response.text[:200]}")
                else:
                    logger.warning(f"Title search failed with status {response.status_code}")
                
                # If title search fails or returns no results, try general search
                logger.info("Trying Google Books general search...")
                general_query = query.replace(' ', '+')
                general_params = {
                    "q": general_query,
                    "maxResults": min(max_results, 40),
                    "printType": "books"
                }
                
                if self.google_api_key:
                    general_params["key"] = self.google_api_key
                
                logger.debug(f"General search query: '{general_query}'")
                general_response = await client.get(self.google_books_url, params=general_params)
                logger.debug(f"General search response status: {general_response.status_code}")
                
                if general_response.status_code == 200:
                    general_data = general_response.json()
                    general_results = self._parse_google_books(general_data.get('items', []))
                    logger.info(f"Google Books general search returned {len(general_results)} results")
                    return general_results
                else:
                    logger.error(f"Google Books API error: {general_response.status_code}")
                    if general_response.status_code == 400:
                        logger.error(f"General search 400 error: {general_response.text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"Google Books search error: {e}", exc_info=True)
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
            
            # Extract ISBN
            isbn = self._extract_isbn(info.get('industryIdentifiers', []))
            
            # Get cover image
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
            # Get cover image
            cover_id = doc.get('cover_i')
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ''
            
            # Get ISBN
            isbn_list = doc.get('isbn', [])
            isbn = isbn_list[0] if isbn_list else ''
            
            books.append({
                'title': doc.get('title', 'Unknown Title'),
                'author': ', '.join(doc.get('author_name', ['Unknown Author'])),
                'isbn': isbn,
                'description': '',  # Open Library search doesn't include descriptions
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
        
        # Fallback to ISBN_10
        for identifier in identifiers:
            if identifier.get('type') == 'ISBN_10':
                return identifier.get('identifier', '')
        
        return ''
    
    @flexicache(time_policy(7200), maxsize=500)  # 2 hour cache, 500 ISBN lookups
    async def get_book_details(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Get detailed book information by ISBN. Results cached for 2 hours."""
        logger.debug(f"Cache miss for ISBN lookup: {isbn}")
        if not isbn:
            return None
        
        # Try Google Books first
        try:
            params = {"q": f"isbn:{isbn}"}
            if self.google_api_key:
                params["key"] = self.google_api_key
            
            logger.info(f"Looking up book by ISBN: {isbn}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.google_books_url, params=params)
                logger.debug(f"ISBN lookup response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    if items:
                        parsed = self._parse_google_books(items)
                        logger.info(f"Found book details for ISBN {isbn}")
                        return parsed[0] if parsed else None
                    else:
                        logger.warning(f"No book found for ISBN {isbn}")
                else:
                    logger.error(f"ISBN lookup failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"ISBN lookup error: {e}", exc_info=True)
        
        return None
