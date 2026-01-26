#!/usr/bin/env python3
"""
Migration script to cache covers for existing books.
This script can be run once to populate the cover cache for books that were added before the caching system was implemented.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database_manager import db_manager
from cover_cache import cover_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migrate_covers.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CoverMigration:
    """Migrates existing books to use the cover caching system."""
    
    def __init__(self):
        self.db_tables = None
        self.batch_size = 50
        self.max_concurrent = 5
        
    async def run_migration(self):
        """Run the cover migration for existing books."""
        logger.info("Starting cover migration for existing books...")
        
        try:
            # Initialize database connection
            self.db_tables = await db_manager.get_connection()
            
            # Get statistics before migration
            await self.log_migration_stats("before")
            
            # Find books that need cover caching
            books_to_migrate = await self.find_books_to_migrate()
            
            if not books_to_migrate:
                logger.info("No books found that need cover migration")
                return
            
            logger.info(f"Found {len(books_to_migrate)} books that need cover caching")
            
            # Process books in batches
            total_processed = 0
            total_successful = 0
            
            for i in range(0, len(books_to_migrate), self.batch_size):
                batch = books_to_migrate[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(books_to_migrate) + self.batch_size - 1) // self.batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} books)")
                
                # Process batch with concurrency control
                semaphore = asyncio.Semaphore(self.max_concurrent)
                tasks = []
                
                for book_id, cover_url in batch:
                    task = self._migrate_book_cover(semaphore, book_id, cover_url)
                    tasks.append(task)
                
                # Wait for batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count results
                batch_successful = sum(1 for result in results if result is True)
                batch_failed = len(results) - batch_successful
                
                total_processed += len(batch)
                total_successful += batch_successful
                
                logger.info(f"Batch {batch_num} completed: {batch_successful} successful, {batch_failed} failed")
                
                # Small delay between batches to be nice to external APIs
                if i + self.batch_size < len(books_to_migrate):
                    await asyncio.sleep(2)
            
            # Get statistics after migration
            await self.log_migration_stats("after")
            
            logger.info(f"Cover migration completed!")
            logger.info(f"Total books processed: {total_processed}")
            logger.info(f"Successfully cached: {total_successful}")
            logger.info(f"Failed: {total_processed - total_successful}")
            
            if total_successful > 0:
                success_rate = (total_successful / total_processed) * 100
                logger.info(f"Success rate: {success_rate:.1f}%")
            
        except Exception as e:
            logger.error(f"Error during cover migration: {e}", exc_info=True)
            raise
    
    async def find_books_to_migrate(self):
        """Find books that have cover URLs but no cached covers."""
        try:
            query = """
                SELECT id, cover_url 
                FROM book 
                WHERE cover_url != '' 
                AND cover_url IS NOT NULL 
                AND (cached_cover_path = '' OR cached_cover_path IS NULL)
                ORDER BY added_at DESC
            """
            
            cursor = self.db_tables['db'].execute(query)
            books = cursor.fetchall()
            
            logger.info(f"Found {len(books)} books with cover URLs but no cached covers")
            return books
            
        except Exception as e:
            logger.error(f"Error finding books to migrate: {e}")
            return []
    
    async def _migrate_book_cover(self, semaphore: asyncio.Semaphore, book_id: int, cover_url: str) -> bool:
        """Migrate a single book's cover with concurrency control."""
        async with semaphore:
            try:
                logger.debug(f"Migrating cover for book {book_id}: {cover_url}")
                
                # Use the cover cache system to download and cache the cover
                cached_path = await cover_cache.download_and_cache_cover(book_id, cover_url)
                
                if cached_path:
                    # Update the book record with cache info
                    self.db_tables['books'].update({
                        'cached_cover_path': cached_path,
                        'cover_cached_at': datetime.now()
                    }, book_id)
                    logger.debug(f"Successfully migrated cover for book {book_id}: {cached_path}")
                    return True
                else:
                    # Mark as attempted even if failed
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now()
                    }, book_id)
                    logger.warning(f"Failed to migrate cover for book {book_id}: {cover_url}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error migrating cover for book {book_id}: {e}")
                # Mark as attempted even if failed
                try:
                    self.db_tables['books'].update({
                        'cover_cached_at': datetime.now()
                    }, book_id)
                except:
                    pass
                return False
    
    async def log_migration_stats(self, phase: str):
        """Log statistics about the migration."""
        try:
            # Get database stats
            cursor = self.db_tables['db'].execute("""
                SELECT 
                    COUNT(*) as total_books,
                    COUNT(CASE WHEN cover_url != '' AND cover_url IS NOT NULL THEN 1 END) as books_with_urls,
                    COUNT(CASE WHEN cached_cover_path != '' AND cached_cover_path IS NOT NULL THEN 1 END) as books_with_cached_covers,
                    COUNT(CASE WHEN cover_cached_at IS NOT NULL THEN 1 END) as books_with_cache_attempts
                FROM book
            """)
            db_stats = cursor.fetchone()
            
            # Get cache stats
            cache_stats = cover_cache.get_cache_stats()
            
            logger.info(f"Migration statistics ({phase}):")
            logger.info(f"  - Total books in database: {db_stats[0]}")
            logger.info(f"  - Books with cover URLs: {db_stats[1]}")
            logger.info(f"  - Books with cached covers: {db_stats[2]}")
            logger.info(f"  - Books with cache attempts: {db_stats[3]}")
            
            if not cache_stats.get('error'):
                logger.info(f"  - Total cached files: {cache_stats['total_files']}")
                logger.info(f"  - Total cache size: {cache_stats['total_size_mb']} MB")
            
            if db_stats[1] > 0:
                cache_percentage = (db_stats[2] / db_stats[1]) * 100
                logger.info(f"  - Cache coverage: {cache_percentage:.1f}%")
            
        except Exception as e:
            logger.error(f"Error logging migration stats: {e}")

async def main():
    """Main entry point for the migration script."""
    print("=" * 60)
    print("Bibliome Cover Cache Migration")
    print("=" * 60)
    print()
    print("This script will cache covers for existing books that don't have cached covers yet.")
    print("It will download cover images and store them locally for faster loading.")
    print()
    
    # Check if user wants to proceed
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        proceed = True
    else:
        response = input("Do you want to proceed with the migration? (y/N): ").strip().lower()
        proceed = response in ['y', 'yes']
    
    if not proceed:
        print("Migration cancelled.")
        return
    
    print("\nStarting migration...")
    
    try:
        migration = CoverMigration()
        await migration.run_migration()
        print("\nMigration completed successfully!")
        
    except KeyboardInterrupt:
        print("\nMigration interrupted by user.")
    except Exception as e:
        print(f"\nMigration failed: {e}")
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
