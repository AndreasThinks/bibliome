"""Book cover caching system for Bibliome."""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
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
                                     timeout: float = 10.0) -> Optional[str]:
        """
        Download a cover image and cache it locally.
        
        Returns:
            str: Relative path to cached file, or None if failed
        """
        if not cover_url or not cover_url.strip():
            logger.debug(f"No cover URL provided for book {book_id}")
            return None
        
        try:
            # Check if already cached
            if self.is_cover_cached(book_id, cover_url):
                cached_path = self.get_cached_cover_path(book_id, cover_url)
                logger.debug(f"Cover already cached for book {book_id}: {cached_path}")
                return str(cached_path.resolve().relative_to(Path.cwd().resolve()))
            
            logger.info(f"Downloading cover for book {book_id}: {cover_url}")
            
            # Download the image with redirect following
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(cover_url)
                response.raise_for_status()
                
                if not response.content:
                    logger.warning(f"Empty response for cover URL: {cover_url}")
                    return None
                
                # Process and save the image
                return await self._process_and_save_image(
                    book_id, cover_url, response.content
                )
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout downloading cover for book {book_id}: {cover_url}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error downloading cover for book {book_id}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading cover for book {book_id}: {e}", exc_info=True)
        
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
