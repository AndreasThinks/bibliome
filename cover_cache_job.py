"""Background job to cache covers for existing books and retry failed attempts."""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv

from database_manager import db_manager
from cover_cache import cover_cache

# Configure logging
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, log_level_str, logging.INFO)
formatter = logging.Formatter('[cover_cache_job] %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(level)
# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Create a new handler with the custom formatter
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()

class CoverCacheJob:
    """Background job to cache book covers and retry failed attempts."""
    
    def __init__(self):
        self.db_tables = None
        self.running = True
        self.job_interval_hours = int(os.getenv('COVER_CACHE_JOB_INTERVAL_HOURS', '24'))
        self.batch_size = int(os.getenv('COVER_CACHE_BATCH_SIZE', '50'))
        self.retry_failed_after_hours = int(os.getenv('COVER_CACHE_RETRY_AFTER_HOURS', '168'))  # 1 week
        self.max_concurrent_downloads = int(os.getenv('COVER_CACHE_MAX_CONCURRENT', '5'))
        self.rate_limit_recovery_interval_hours = int(os.getenv('COVER_CACHE_RATE_LIMIT_RECOVERY_HOURS', '1'))  # Check hourly
        
    async def run(self):
        """Main loop for the cover cache job."""
        logger.info("Starting Cover Cache Job...")
        
        # Run the first job cycle immediately
        asyncio.create_task(self.run_job_cycle())
        
        while self.running:
            try:
                logger.info(f"Next cover cache job scheduled in {self.job_interval_hours} hours.")
                await asyncio.sleep(self.job_interval_hours * 3600)
                if self.running:
                    await self.run_job_cycle()
            except Exception as e:
                logger.error(f"Error in cover cache job scheduling loop: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Wait an hour before retrying on major failure
    
    async def run_job_cycle(self):
        """Run a complete cover caching cycle."""
        logger.info("Starting cover cache job cycle...")
        self.db_tables = await db_manager.get_connection()
        
        try:
            # 1. Cache covers for books without cached covers (skip rate-limited ones)
            await self.cache_missing_covers()
            
            # 2. Retry failed cover downloads (skip rate-limited ones)
            await self.retry_failed_covers()
            
            # 3. Recover from rate limits (check if rate limit periods have expired)
            await self.recover_rate_limited_covers()
            
            # 4. Clean up orphaned cover files
            await self.cleanup_orphaned_covers()
            
            # 5. Log cache statistics
            await self.log_cache_stats()
            
            logger.info("Cover cache job cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in cover cache job cycle: {e}", exc_info=True)
    
    async def cache_missing_covers(self):
        """Cache covers for books that have cover URLs but no cached covers."""
        logger.info("Caching covers for books without cached covers...")
        
        try:
            # Find books with cover URLs but no cached covers
            query = """
                SELECT id, cover_url 
                FROM book 
                WHERE cover_url != '' 
                AND cover_url IS NOT NULL 
                AND (cached_cover_path = '' OR cached_cover_path IS NULL)
                ORDER BY added_at DESC
                LIMIT ?
            """
            
            cursor = self.db_tables['db'].execute(query, (self.batch_size,))
            books_to_cache = cursor.fetchall()
            
            if not books_to_cache:
                logger.info("No books found that need cover caching")
                return
            
            logger.info(f"Found {len(books_to_cache)} books that need cover caching")
            
            # Process books in smaller concurrent batches
            semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
            tasks = []
            
            for book_id, cover_url in books_to_cache:
                task = self._cache_book_cover_with_semaphore(semaphore, book_id, cover_url)
                tasks.append(task)
            
            # Wait for all downloads to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if result is True)
            failures = sum(1 for result in results if result is not True)
            
            logger.info(f"Cover caching completed: {successes} successful, {failures} failed")
            
        except Exception as e:
            logger.error(f"Error caching missing covers: {e}", exc_info=True)
    
    async def _cache_book_cover_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                             book_id: int, cover_url: str) -> bool:
        """Cache a single book cover with concurrency control."""
        async with semaphore:
            try:
                logger.debug(f"Caching cover for book {book_id}: {cover_url}")
                
                cache_result = await cover_cache.download_and_cache_cover(book_id, cover_url)
                
                if cache_result['success']:
                    # Successfully cached
                    self.db_tables['books'].update({
                        'cached_cover_path': cache_result['cached_path'],
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': None  # Clear any previous rate limit
                    }, book_id)
                    logger.debug(f"Successfully cached cover for book {book_id}: {cache_result['cached_path']}")
                    return True
                elif cache_result['error_type'] == 'rate_limit':
                    # Rate limited - mark for later retry
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': cache_result['rate_limited_until']
                    }, book_id)
                    logger.info(f"Cover download rate limited for book {book_id}, will retry after {cache_result['rate_limited_until']}")
                    return False
                else:
                    # Other error - mark as attempted
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now()
                    }, book_id)
                    logger.debug(f"Cover caching failed for book {book_id}: {cache_result['error_type']}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error caching cover for book {book_id}: {e}")
                return False
    
    async def retry_failed_covers(self):
        """Retry caching covers for books that failed previously."""
        logger.info("Retrying failed cover downloads...")
        
        try:
            # Find books that have cover URLs but failed caching attempts
            # (books with cover_url but no cached_cover_path and old cover_cached_at)
            retry_cutoff = datetime.now() - timedelta(hours=self.retry_failed_after_hours)
            
            query = """
                SELECT id, cover_url 
                FROM book 
                WHERE cover_url != '' 
                AND cover_url IS NOT NULL 
                AND (cached_cover_path = '' OR cached_cover_path IS NULL)
                AND cover_cached_at IS NOT NULL
                AND cover_cached_at < ?
                ORDER BY cover_cached_at ASC
                LIMIT ?
            """
            
            cursor = self.db_tables['db'].execute(query, (retry_cutoff.isoformat(), self.batch_size // 2))
            books_to_retry = cursor.fetchall()
            
            if not books_to_retry:
                logger.info("No failed cover downloads found to retry")
                return
            
            logger.info(f"Found {len(books_to_retry)} failed cover downloads to retry")
            
            # Process retries with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
            tasks = []
            
            for book_id, cover_url in books_to_retry:
                task = self._retry_book_cover_with_semaphore(semaphore, book_id, cover_url)
                tasks.append(task)
            
            # Wait for all retries to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if result is True)
            failures = sum(1 for result in results if result is not True)
            
            logger.info(f"Cover retry completed: {successes} successful, {failures} failed")
            
        except Exception as e:
            logger.error(f"Error retrying failed covers: {e}", exc_info=True)
    
    async def _retry_book_cover_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                             book_id: int, cover_url: str) -> bool:
        """Retry caching a single book cover with concurrency control."""
        async with semaphore:
            try:
                logger.debug(f"Retrying cover cache for book {book_id}: {cover_url}")
                
                cache_result = await cover_cache.download_and_cache_cover(book_id, cover_url)
                
                if cache_result['success']:
                    # Successfully cached
                    self.db_tables['books'].update({
                        'cached_cover_path': cache_result['cached_path'],
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': None  # Clear any previous rate limit
                    }, book_id)
                    logger.debug(f"Successfully retried cover cache for book {book_id}: {cache_result['cached_path']}")
                    return True
                elif cache_result['error_type'] == 'rate_limit':
                    # Rate limited again - update the rate limit period
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': cache_result['rate_limited_until']
                    }, book_id)
                    logger.info(f"Cover retry rate limited for book {book_id}, will retry after {cache_result['rate_limited_until']}")
                    return False
                else:
                    # Other error - update the retry timestamp
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now()
                    }, book_id)
                    logger.debug(f"Cover retry failed for book {book_id}: {cache_result['error_type']}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error retrying cover cache for book {book_id}: {e}")
                # Update the retry timestamp even if failed
                try:
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now()
                    }, book_id)
                except:
                    pass
                return False
    
    async def recover_rate_limited_covers(self):
        """Recover covers that were rate limited but the rate limit period has expired."""
        logger.info("Checking for rate limit recovery opportunities...")
        
        try:
            # Find books that were rate limited but the rate limit period has expired
            current_time = datetime.now()
            
            query = """
                SELECT id, cover_url 
                FROM book 
                WHERE cover_url != '' 
                AND cover_url IS NOT NULL 
                AND (cached_cover_path = '' OR cached_cover_path IS NULL)
                AND cover_rate_limited_until IS NOT NULL
                AND cover_rate_limited_until <= ?
                ORDER BY cover_rate_limited_until ASC
                LIMIT ?
            """
            
            cursor = self.db_tables['db'].execute(query, (current_time.isoformat(), self.batch_size // 4))
            books_to_recover = cursor.fetchall()
            
            if not books_to_recover:
                logger.info("No rate-limited covers ready for recovery")
                return
            
            logger.info(f"Found {len(books_to_recover)} rate-limited covers ready for recovery")
            
            # Process recoveries with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
            tasks = []
            
            for book_id, cover_url in books_to_recover:
                task = self._recover_rate_limited_cover_with_semaphore(semaphore, book_id, cover_url)
                tasks.append(task)
            
            # Wait for all recoveries to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if result is True)
            failures = sum(1 for result in results if result is not True)
            
            logger.info(f"Rate limit recovery completed: {successes} successful, {failures} failed")
            
        except Exception as e:
            logger.error(f"Error recovering rate limited covers: {e}", exc_info=True)
    
    async def _recover_rate_limited_cover_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                                       book_id: int, cover_url: str) -> bool:
        """Recover a single rate-limited cover with concurrency control."""
        async with semaphore:
            try:
                logger.debug(f"Recovering rate-limited cover for book {book_id}: {cover_url}")
                
                cache_result = await cover_cache.download_and_cache_cover(book_id, cover_url)
                
                if cache_result['success']:
                    # Successfully cached
                    self.db_tables['books'].update({
                        'cached_cover_path': cache_result['cached_path'],
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': None  # Clear the rate limit
                    }, book_id)
                    logger.info(f"Successfully recovered rate-limited cover for book {book_id}: {cache_result['cached_path']}")
                    return True
                elif cache_result['error_type'] == 'rate_limit':
                    # Still rate limited - update the rate limit period
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': cache_result['rate_limited_until']
                    }, book_id)
                    logger.info(f"Cover still rate limited for book {book_id}, will retry after {cache_result['rate_limited_until']}")
                    return False
                else:
                    # Other error - clear rate limit but mark as failed
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': None  # Clear rate limit since it's not a rate limit error
                    }, book_id)
                    logger.debug(f"Cover recovery failed for book {book_id}: {cache_result['error_type']}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error recovering rate-limited cover for book {book_id}: {e}")
                # Clear rate limit on exception
                try:
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now(),
                        'cover_rate_limited_until': None
                    }, book_id)
                except:
                    pass
                return False
    
    async def cleanup_orphaned_covers(self):
        """Clean up cached cover files for books that no longer exist."""
        logger.info("Cleaning up orphaned cover files...")
        
        try:
            # Get all valid book IDs
            cursor = self.db_tables['db'].execute("SELECT id FROM book")
            valid_book_ids = {row[0] for row in cursor.fetchall()}
            
            # Use the cover cache manager to clean up orphaned files
            removed_count = cover_cache.cleanup_orphaned_covers(valid_book_ids)
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} orphaned cover files")
            else:
                logger.info("No orphaned cover files found")
                
        except Exception as e:
            logger.error(f"Error cleaning up orphaned covers: {e}", exc_info=True)
    
    async def log_cache_stats(self):
        """Log statistics about the cover cache."""
        try:
            stats = cover_cache.get_cache_stats()
            
            if 'error' in stats:
                logger.warning(f"Error getting cache stats: {stats['error']}")
                return
            
            # Get database stats
            cursor = self.db_tables['db'].execute("""
                SELECT 
                    COUNT(*) as total_books,
                    COUNT(CASE WHEN cover_url != '' AND cover_url IS NOT NULL THEN 1 END) as books_with_urls,
                    COUNT(CASE WHEN cached_cover_path != '' AND cached_cover_path IS NOT NULL THEN 1 END) as books_with_cached_covers
                FROM book
            """)
            db_stats = cursor.fetchone()
            
            logger.info(f"Cover cache statistics:")
            logger.info(f"  - Total cached files: {stats['total_files']}")
            logger.info(f"  - Total cache size: {stats['total_size_mb']} MB")
            logger.info(f"  - Cache directory: {stats['cache_dir']}")
            logger.info(f"  - Total books in database: {db_stats[0]}")
            logger.info(f"  - Books with cover URLs: {db_stats[1]}")
            logger.info(f"  - Books with cached covers: {db_stats[2]}")
            
            if db_stats[1] > 0:
                cache_percentage = (db_stats[2] / db_stats[1]) * 100
                logger.info(f"  - Cache coverage: {cache_percentage:.1f}%")
            
        except Exception as e:
            logger.error(f"Error logging cache stats: {e}", exc_info=True)
    
    def stop(self):
        """Stop the cover cache job."""
        logger.info("Stopping cover cache job...")
        self.running = False

async def main():
    """Run a single cover cache job cycle for debugging."""
    job = CoverCacheJob()
    print("Running a single cover cache job cycle for debugging...")
    await job.run_job_cycle()
    print("Debug cover cache job cycle complete.")

if __name__ == "__main__":
    # This allows running the script directly for a one-off job
    # The service manager will still use the `run` method in the background
    if os.getenv("RUN_ONCE"):
        asyncio.run(main())
    else:
        # Default behavior for the service manager
        job = CoverCacheJob()
        asyncio.run(job.run())
