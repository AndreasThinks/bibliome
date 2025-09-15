"""Book cover caching system for Bibliome."""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import httpx
from PIL import Image
import io

logger = logging.getLogger(__name__)

class CoverCacheManager:
    """Manages local caching of book cover images."""
    
    def __init__(self, cache_dir: str = "data/covers", max_size_mb: int = 1000, 
                 cover_dimensions: Tuple[int, int] = (300, 450), quality: int = 85):
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self.cover_dimensions = cover_dimensions
        self.quality = quality
        self.ensure_cache_directory()
    
    def ensure_cache_directory(self):
        """Create the cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cover cache directory ensured: {self.cache_dir}")
    
    def generate_cache_filename(self, book_id: int, cover_url: str, format: str = "webp") -> str:
        """Generate a consistent filename for cached covers."""
        # Create hash of URL for cache busting when URL changes
        url_hash = hashlib.md5(cover_url.encode()).hexdigest()[:8]
        return f"{book_id}_{url_hash}.{format}"
    
    def get_cached_cover_path(self, book_id: int, cover_url: str) -> Optional[Path]:
        """Get the local path for a cached cover, checking both WebP and JPEG."""
        # Check WebP first (preferred format)
        webp_filename = self.generate_cache_filename(book_id, cover_url, "webp")
        webp_path = self.cache_dir / webp_filename
        if webp_path.exists():
            return webp_path
        
        # Fallback to JPEG
        jpeg_filename = self.generate_cache_filename(book_id, cover_url, "jpg")
        jpeg_path = self.cache_dir / jpeg_filename
        if jpeg_path.exists():
            return jpeg_path
        
        return None
    
    def is_cover_cached(self, book_id: int, cover_url: str) -> bool:
        """Check if a cover is already cached locally."""
        return self.get_cached_cover_path(book_id, cover_url) is not None
    
    async def download_and_cache_cover(self, book_id: int, cover_url: str, 
                                     timeout: float = 10.0) -> Dict[str, Any]:
        """
        Download a cover image and cache it locally.
        
        Returns:
            Dict with keys:
            - 'success': bool - whether caching succeeded
            - 'cached_path': str or None - relative path to cached file if successful
            - 'rate_limited_until': datetime or None - when rate limit expires (for 429 errors)
            - 'error_type': str - type of error ('rate_limit', 'timeout', 'http_error', 'processing_error', etc.)
            - 'retry_after': int or None - seconds to wait before retry (from Retry-After header)
        """
        result = {
            'success': False,
            'cached_path': None,
            'rate_limited_until': None,
            'error_type': None,
            'retry_after': None
        }
        
        if not cover_url or not cover_url.strip():
            logger.debug(f"No cover URL provided for book {book_id}")
            result['error_type'] = 'no_url'
            return result
        
        try:
            # Check if already cached
            if self.is_cover_cached(book_id, cover_url):
                cached_path = self.get_cached_cover_path(book_id, cover_url)
                logger.debug(f"Cover already cached for book {book_id}: {cached_path}")
                result['success'] = True
                result['cached_path'] = str(cached_path.resolve().relative_to(Path.cwd().resolve()))
                return result
            
            logger.info(f"Downloading cover for book {book_id}: {cover_url}")
            
            # Download the image with redirect following
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(cover_url)
                response.raise_for_status()
                
                if not response.content:
                    logger.warning(f"Empty response for cover URL: {cover_url}")
                    result['error_type'] = 'empty_response'
                    return result
                
                # Process and save the image
                cached_path = await self._process_and_save_image(
                    book_id, cover_url, response.content
                )
                
                if cached_path:
                    result['success'] = True
                    result['cached_path'] = cached_path
                else:
                    result['error_type'] = 'processing_error'
                
                return result
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout downloading cover for book {book_id}: {cover_url}")
            result['error_type'] = 'timeout'
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Handle rate limiting specially
                logger.warning(f"Rate limited downloading cover for book {book_id}: {cover_url}")
                result['error_type'] = 'rate_limit'
                
                # Parse Retry-After header if available
                retry_after = self._parse_retry_after_header(e.response)
                if retry_after:
                    result['retry_after'] = retry_after
                    result['rate_limited_until'] = datetime.now() + timedelta(seconds=retry_after)
                    logger.info(f"Rate limit expires in {retry_after} seconds for book {book_id}")
                else:
                    # Default to 24 hours if no Retry-After header
                    default_hours = int(os.getenv('COVER_CACHE_DEFAULT_RATE_LIMIT_HOURS', '24'))
                    result['rate_limited_until'] = datetime.now() + timedelta(hours=default_hours)
                    logger.info(f"Rate limit set to {default_hours} hours (default) for book {book_id}")
            else:
                logger.warning(f"HTTP error downloading cover for book {book_id}: {e.response.status_code}")
                result['error_type'] = 'http_error'
        except Exception as e:
            logger.error(f"Error downloading cover for book {book_id}: {e}", exc_info=True)
            result['error_type'] = 'unknown_error'
        
        return result
    
    def _parse_retry_after_header(self, response: httpx.Response) -> Optional[int]:
        """Parse the Retry-After header from an HTTP response."""
        try:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                # Retry-After can be in seconds (integer) or HTTP date
                try:
                    # Try parsing as seconds first
                    return int(retry_after)
                except ValueError:
                    # Try parsing as HTTP date
                    try:
                        from email.utils import parsedate_to_datetime
                        retry_date = parsedate_to_datetime(retry_after)
                        if retry_date:
                            # Make sure both datetimes are timezone-aware or naive
                            now = datetime.now()
                            if retry_date.tzinfo is not None:
                                # retry_date is timezone-aware, make now timezone-aware too
                                from datetime import timezone
                                now = now.replace(tzinfo=timezone.utc)
                            delta = retry_date - now
                            return max(0, int(delta.total_seconds()))
                    except Exception as date_error:
                        logger.debug(f"Error parsing HTTP date in Retry-After: {date_error}")
        except Exception as e:
            logger.debug(f"Error parsing Retry-After header: {e}")
        
        return None
    
    async def _process_and_save_image(self, book_id: int, cover_url: str, 
                                    image_data: bytes) -> Optional[str]:
        """Process and save an image with optimization."""
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary (for WebP compatibility)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize image while maintaining aspect ratio
            image = self._resize_image(image)
            
            # Try to save as WebP first (better compression)
            webp_filename = self.generate_cache_filename(book_id, cover_url, "webp")
            webp_path = self.cache_dir / webp_filename
            
            try:
                image.save(webp_path, 'WebP', quality=self.quality, optimize=True)
                logger.debug(f"Saved WebP cover: {webp_path}")
                # Use absolute path resolution to avoid relative path issues
                return str(webp_path.resolve().relative_to(Path.cwd().resolve()))
            except Exception as webp_error:
                logger.debug(f"WebP save failed, falling back to JPEG: {webp_error}")
                
                # Fallback to JPEG
                jpeg_filename = self.generate_cache_filename(book_id, cover_url, "jpg")
                jpeg_path = self.cache_dir / jpeg_filename
                image.save(jpeg_path, 'JPEG', quality=self.quality, optimize=True)
                logger.debug(f"Saved JPEG cover: {jpeg_path}")
                # Use absolute path resolution to avoid relative path issues
                return str(jpeg_path.resolve().relative_to(Path.cwd().resolve()))
                
        except Exception as e:
            logger.error(f"Error processing image for book {book_id}: {e}", exc_info=True)
            return None
    
    def _resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to target dimensions while maintaining aspect ratio."""
        target_width, target_height = self.cover_dimensions
        
        # Calculate scaling factor
        width_ratio = target_width / image.width
        height_ratio = target_height / image.height
        scale_factor = min(width_ratio, height_ratio)
        
        # Only resize if image is larger than target
        if scale_factor < 1:
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image
    
    def get_cover_url(self, book_id: int, original_url: str, base_url: str = "") -> str:
        """
        Get the best available URL for a book cover (cached or original).
        
        Args:
            book_id: Book ID
            original_url: Original external cover URL
            base_url: Base URL for the application (for local URLs)
            
        Returns:
            str: URL to use for the cover (local or external)
        """
        if not original_url:
            return ""
        
        try:
            # Check if we have a cached version
            cached_path = self.get_cached_cover_path(book_id, original_url)
            if cached_path and cached_path.exists():
                # Verify the cached file is valid and not corrupted
                try:
                    if cached_path.stat().st_size > 0:  # File has content
                        # Return local URL
                        relative_path = cached_path.resolve().relative_to(Path.cwd().resolve())
                        return f"{base_url.rstrip('/')}/{relative_path}"
                    else:
                        logger.warning(f"Cached cover file is empty: {cached_path}")
                except Exception as e:
                    logger.warning(f"Error checking cached cover file {cached_path}: {e}")
            
        except Exception as e:
            logger.warning(f"Error getting cached cover for book {book_id}: {e}")
        
        # Fallback to original URL
        return original_url
    
    def cleanup_orphaned_covers(self, valid_book_ids: set) -> int:
        """
        Remove cached covers for books that no longer exist.
        
        Args:
            valid_book_ids: Set of book IDs that should be kept
            
        Returns:
            int: Number of files removed
        """
        removed_count = 0
        
        try:
            for cover_file in self.cache_dir.glob("*.webp"):
                # Extract book ID from filename
                try:
                    book_id = int(cover_file.stem.split('_')[0])
                    if book_id not in valid_book_ids:
                        cover_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed orphaned cover: {cover_file}")
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse book ID from filename: {cover_file}")
            
            # Also check JPEG files
            for cover_file in self.cache_dir.glob("*.jpg"):
                try:
                    book_id = int(cover_file.stem.split('_')[0])
                    if book_id not in valid_book_ids:
                        cover_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed orphaned cover: {cover_file}")
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse book ID from filename: {cover_file}")
                    
        except Exception as e:
            logger.error(f"Error during cover cleanup: {e}", exc_info=True)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} orphaned cover files")
        
        return removed_count
    
    def get_cache_stats(self) -> dict:
        """Get statistics about the cover cache."""
        try:
            total_files = 0
            total_size = 0
            
            for cover_file in self.cache_dir.glob("*"):
                if cover_file.is_file():
                    total_files += 1
                    total_size += cover_file.stat().st_size
            
            return {
                "total_files": total_files,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir),
                "max_size_mb": self.max_size_mb
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Global instance
cover_cache = CoverCacheManager()
