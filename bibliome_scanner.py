"""
Background service to scan the AT-Proto network for Bibliome records,
and import them into the local database.
"""
import asyncio
import logging
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv

from apswutils.db import NotFoundError
from models import get_database, SyncLog, User, Bookshelf, Book, generate_slug
from direct_pds_client import DirectPDSClient
from hybrid_discovery import HybridDiscoveryService
from circuit_breaker import CircuitBreaker
from rate_limiter import RateLimiter

# Configure logging with service name prefix
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, log_level_str, logging.INFO)
# Create a custom formatter
formatter = logging.Formatter('[bibliome_scanner] %(asctime)s - %(levelname)s - %(message)s')
# Get the root logger
logger = logging.getLogger()
logger.setLevel(level)
# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Create a new handler with the custom formatter
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Load environment variables from .env file
load_dotenv()

class BiblioMeScanner:
    """Scans the AT-Proto network for Bibliome records and imports them locally."""
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        rate_limiter = RateLimiter(
            tokens_per_second=int(os.getenv('BIBLIOME_RATE_LIMIT_PER_MINUTE', '60')) / 60,
            max_tokens=int(os.getenv('BIBLIOME_RATE_LIMIT_PER_MINUTE', '60'))
        )
        self.pds_client = DirectPDSClient(rate_limiter)
        self.discovery = HybridDiscoveryService(self.pds_client)
        self.db_tables = get_database()
        self.scan_interval_hours = int(os.getenv('BIBLIOME_SCAN_INTERVAL_HOURS', '6'))
        self.import_public_only = os.getenv('BIBLIOME_IMPORT_PUBLIC_ONLY', 'true').lower() == 'true'
        self.user_batch_size = int(os.getenv('BIBLIOME_USER_BATCH_SIZE', '50'))
        self.running = True

        # Apply circuit breaker to methods
        self.run_scan_cycle = self.circuit_breaker(self.run_scan_cycle)
        self.sync_user_profile = self.circuit_breaker(self.sync_user_profile)
        self.sync_user_content = self.circuit_breaker(self.sync_user_content)

    async def run(self):
        """Main loop for the scanner service."""
        logger.info("Starting Bibliome Scanner Service...")

        # Run the first scan in the background without blocking
        asyncio.create_task(self.run_scan_cycle())

        while self.running:
            try:
                # The loop now only schedules subsequent scans
                logger.info(f"Next scan scheduled in {self.scan_interval_hours} hours.")
                await asyncio.sleep(self.scan_interval_hours * 3600)
                if self.running:
                    await self.run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in scan scheduling loop: {e}", exc_info=True)
                await asyncio.sleep(3600) # Wait an hour before retrying on major failure

    async def run_scan_cycle(self):
        """Runs a complete scan and import cycle."""
        logger.info("Starting new scan cycle...")
        
        # 1. Discover users with Bibliome records
        discovered_dids = await self.discovery.discover_users()
        logger.info(f"Discovered a total of {len(discovered_dids)} Bibliome users.")
        
        # 2. Sync bookshelves and books for all remote users in batches
        remote_users = self.db_tables['users']("is_remote=1")
        logger.info(f"Found {len(remote_users)} remote users to sync content for.")
        for i in range(0, len(remote_users), self.user_batch_size):
            batch = remote_users[i:i + self.user_batch_size]
            logger.info(f"Processing user content batch {i//self.user_batch_size + 1}/{(len(remote_users) + self.user_batch_size - 1)//self.user_batch_size}...")
            for user in batch:
                await self.sync_user_content(user.did)
            logger.info(f"Completed content sync for batch of {len(batch)} users.")

    async def sync_user_profile(self, did: str, profile_data: Dict):
        """Sync a single user's profile."""
        try:
            if not profile_data:
                self.log_sync_activity('user', did, 'failed', 'Profile not found')
                return

            try:
                user = self.db_tables['users'][did]
                # User exists, update if needed
                user.is_remote = True
                user.last_seen_remote = datetime.now(timezone.utc)
                user.display_name = getattr(profile_data, 'displayName', None)
                avatar = getattr(profile_data, 'avatar', None)
                user.avatar_url = str(avatar) if avatar else None
                self.db_tables['users'].update(user)
                self.log_sync_activity('user', did, 'updated', 'Profile updated')
            except NotFoundError:
                # New user, insert into DB
                avatar = getattr(profile_data, 'avatar', None)
                new_user = User(
                    did=did,
                    handle=f"{did}", # Placeholder, will be updated
                    display_name=getattr(profile_data, 'displayName', None),
                    avatar_url=str(avatar) if avatar else None,
                    is_remote=True,
                    discovered_at=datetime.now(timezone.utc),
                    last_seen_remote=datetime.now(timezone.utc),
                    remote_sync_status='synced'
                )
                self.db_tables['users'].insert(new_user)
                self.log_sync_activity('user', did, 'imported', 'New remote user discovered')

        except Exception as e:
            logger.error(f"Error syncing profile for {did}: {e}", exc_info=True)
            self.log_sync_activity('user', did, 'failed', str(e))

    async def sync_user_content(self, did: str):
        """Sync all bookshelves and books for a given user."""
        logger.info(f"Syncing content for user {did}...")
        try:
            data = await self.pds_client.get_repo_records(did, ["com.bibliome.book", "com.bibliome.bookshelf", "app.bsky.actor.profile"])
            
            # Sync profile
            profile_data = data.get("collections", {}).get("app.bsky.actor.profile", [])
            if profile_data:
                await self.sync_user_profile(did, profile_data[0]['value'])

            # Sync bookshelves
            for shelf_data in data.get("collections", {}).get("com.bibliome.bookshelf", []):
                await self.sync_bookshelf(did, shelf_data)

            # Sync books
            for book_data in data.get("collections", {}).get("com.bibliome.book", []):
                await self.sync_book(did, book_data)
        except Exception as e:
            logger.error(f"Error syncing content for {did}: {e}", exc_info=True)
            self.log_sync_activity('content', did, 'failed', str(e))

    async def sync_bookshelf(self, did: str, shelf_data: Dict):
        """Sync a single bookshelf record."""
        uri = shelf_data['uri']
        value = shelf_data['value']

        if value is None:
            self.log_sync_activity('bookshelf', uri, 'skipped', 'Record value is None')
            return
        
        # TODO reintroduce once private shelves fixed.
        #if self.import_public_only and value.get('privacy', 'public') != 'public':
        #    self.log_sync_activity('bookshelf', uri, 'skipped', 'Not a public shelf')
        #    return

        try:
            # Deduplication check
            existing_shelf_list = self.db_tables['bookshelves']("original_atproto_uri=?", (uri,))
            if existing_shelf_list:
                # Update existing shelf
                shelf = existing_shelf_list[0]
                shelf.name = getattr(value, 'name', shelf.name)
                shelf.description = getattr(value, 'description', shelf.description)
                shelf.privacy = getattr(value, 'privacy', shelf.privacy)
                shelf.last_synced = datetime.now(timezone.utc)
                self.db_tables['bookshelves'].update(shelf)
                self.log_sync_activity('bookshelf', uri, 'updated')
            else:
                # Create new shelf
                new_shelf = Bookshelf(
                    name=getattr(value, 'name', 'Untitled Shelf'),
                    owner_did=did, # Local owner is the same as remote for now
                    slug=generate_slug(),
                    description=getattr(value, 'description', ''),
                    privacy=getattr(value, 'privacy', 'public'),
                    is_remote=True,
                    remote_owner_did=did,
                    discovered_at=datetime.now(timezone.utc),
                    last_synced=datetime.now(timezone.utc),
                    remote_sync_status='synced',
                    original_atproto_uri=uri
                )
                self.db_tables['bookshelves'].insert(new_shelf)
                self.log_sync_activity('bookshelf', uri, 'imported')
        except Exception as e:
            logger.error(f"Error syncing bookshelf {uri}: {e}")
            self.log_sync_activity('bookshelf', uri, 'failed', str(e))

    async def sync_book(self, did: str, book_data: Dict):
        """Sync a single book record."""
        if book_data is None:
            self.log_sync_activity('book', 'unknown', 'skipped', 'Record data is None')
            return

        uri = book_data['uri']
        value = book_data['value']

        if value is None:
            self.log_sync_activity('book', uri, 'skipped', 'Record value is None')
            return

        bookshelf_ref_uri = getattr(value, 'bookshelfRef', None)

        if not bookshelf_ref_uri:
            self.log_sync_activity('book', uri, 'skipped', 'No bookshelf reference')
            return

        try:
            # Find the local bookshelf this book belongs to
            parent_shelf_list = self.db_tables['bookshelves']("original_atproto_uri=?", (bookshelf_ref_uri,))
            if not parent_shelf_list:
                self.log_sync_activity('book', uri, 'skipped', 'Parent bookshelf not found locally')
                return
            parent_shelf_id = parent_shelf_list[0].id

            # Deduplication check
            existing_book_list = self.db_tables['books']("original_atproto_uri=?", (uri,))
            if existing_book_list:
                # Update existing book
                book = existing_book_list[0]
                book.title = getattr(value, 'title', book.title)
                book.author = getattr(value, 'author', book.author)
                book.isbn = getattr(value, 'isbn', book.isbn)
                self.db_tables['books'].update(book)
                self.log_sync_activity('book', uri, 'updated')
            else:
                # Create new book
                new_book = Book(
                    bookshelf_id=parent_shelf_id,
                    title=getattr(value, 'title', 'Untitled Book'),
                    added_by_did=did,
                    isbn=getattr(value, 'isbn', ''),
                    author=getattr(value, 'author', ''),
                    is_remote=True,
                    remote_added_by_did=did,
                    discovered_at=datetime.now(timezone.utc),
                    original_atproto_uri=uri,
                    remote_sync_status='synced',
                    added_at=getattr(value, 'addedAt', None)
                )
                self.db_tables['books'].insert(new_book)
                self.log_sync_activity('book', uri, 'imported')
        except Exception as e:
            logger.error(f"Error syncing book {uri}: {e}")
            self.log_sync_activity('book', uri, 'failed', str(e))

    def log_sync_activity(self, sync_type: str, target_id: str, action: str, details: str = ""):
        """Logs synchronization activity to the database."""
        try:
            log_entry = SyncLog(
                sync_type=sync_type,
                target_id=target_id,
                action=action,
                details=details,
                timestamp=datetime.now(timezone.utc)
            )
            self.db_tables['sync_logs'].insert(log_entry)
        except Exception as e:
            logger.error(f"Failed to log sync activity: {e}")

async def main():
    scanner = BiblioMeScanner()
    # Run a single scan cycle for debugging purposes
    print("Running a single scan cycle for debugging...")
    await scanner.run_scan_cycle()
    print("Debug scan cycle complete.")

if __name__ == "__main__":
    # This allows running the script directly for a one-off scan
    # The service manager will still use the `run` method in the background
    if os.getenv("RUN_ONCE"):
        asyncio.run(main())
    else:
        # Default behavior for the service manager
        scanner = BiblioMeScanner()
        asyncio.run(scanner.run())
