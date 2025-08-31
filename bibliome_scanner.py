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

from atproto import Client
from apswutils.db import NotFoundError
from models import get_database, SyncLog, User, Bookshelf, Book, generate_slug
from scanner_client import BiblioMeATProtoClient
from circuit_breaker import CircuitBreaker

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
        self.client = BiblioMeATProtoClient()
        self.db_tables = get_database()
        self.scan_interval_hours = int(os.getenv('BIBLIOME_SCAN_INTERVAL_HOURS', '6'))
        self.rate_limit_per_minute = int(os.getenv('BIBLIOME_RATE_LIMIT_PER_MINUTE', '60'))
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
        
        # Authenticate the client if not already authenticated
        if not self.client.client.me:
            try:
                username = os.getenv('BLUESKY_HANDLE')
                password = os.getenv('BLUESKY_PASSWORD')
                if not username or not password:
                    raise ValueError("BLUESKY_HANDLE and BLUESKY_PASSWORD must be set in .env")
                
                atproto_client = Client()
                atproto_client.login(username, password)
                self.client.client = atproto_client
                logger.info("AT-Proto client authenticated successfully.")
            except Exception as e:
                logger.error(f"Failed to authenticate AT-Proto client: {e}")
                return # Stop if authentication fails
        
        # 1. Discover users with Bibliome records
        discovered_dids = await self.client.discover_bibliome_users()
        logger.info(f"Discovered a total of {len(discovered_dids)} Bibliome users.")
        
        # 2. Sync profiles for each discovered user in batches
        for i in range(0, len(discovered_dids), self.user_batch_size):
            batch = discovered_dids[i:i + self.user_batch_size]
            logger.info(f"Processing user profile batch {i//self.user_batch_size + 1}/{(len(discovered_dids) + self.user_batch_size - 1)//self.user_batch_size}...")
            for did in batch:
                await self.sync_user_profile(did)
                await asyncio.sleep(60 / self.rate_limit_per_minute)
            logger.info(f"Completed profile sync for batch of {len(batch)} users.")

        # 3. Sync bookshelves and books for all remote users in batches
        remote_users = self.db_tables['users']("is_remote=1")
        logger.info(f"Found {len(remote_users)} remote users to sync content for.")
        for i in range(0, len(remote_users), self.user_batch_size):
            batch = remote_users[i:i + self.user_batch_size]
            logger.info(f"Processing user content batch {i//self.user_batch_size + 1}/{(len(remote_users) + self.user_batch_size - 1)//self.user_batch_size}...")
            for user in batch:
                await self.sync_user_content(user.did)
                await asyncio.sleep(60 / self.rate_limit_per_minute)
            logger.info(f"Completed content sync for batch of {len(batch)} users.")

    async def sync_user_profile(self, did: str):
        """Sync a single user's profile."""
        try:
            profile_data = await self.client.get_user_profile(did)
            if not profile_data:
                self.log_sync_activity('user', did, 'failed', 'Profile not found')
                return

            try:
                user = self.db_tables['users'][did]
                # User exists, update if needed
                user.is_remote = True
                user.last_seen_remote = datetime.now(timezone.utc)
                user.handle = profile_data['handle']
                user.display_name = profile_data['display_name']
                user.avatar_url = profile_data['avatar_url']
                self.db_tables['users'].update(user)
                self.log_sync_activity('user', did, 'updated', 'Profile updated')
            except NotFoundError:
                # New user, insert into DB
                new_user = User(
                    did=did,
                    handle=profile_data['handle'],
                    display_name=profile_data['display_name'],
                    avatar_url=profile_data['avatar_url'],
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
        
        # Sync bookshelves
        remote_bookshelves = await self.client.get_user_bookshelves(did)
        for shelf_data in remote_bookshelves:
            await self.sync_bookshelf(did, shelf_data)
            await asyncio.sleep(1) # Small delay

        # Sync books
        remote_books = await self.client.get_user_books(did)
        for book_data in remote_books:
            await self.sync_book(did, book_data)
            await asyncio.sleep(1) # Small delay

    async def sync_bookshelf(self, did: str, shelf_data: Dict):
        """Sync a single bookshelf record."""
        uri = shelf_data['uri']
        value = shelf_data['value']
        
        if self.import_public_only and value.get('privacy', 'public') != 'public':
            self.log_sync_activity('bookshelf', uri, 'skipped', 'Not a public shelf')
            return

        try:
            # Deduplication check
            existing_shelf_list = self.db_tables['bookshelves']("original_atproto_uri=?", (uri,))
            if existing_shelf_list:
                # Update existing shelf
                shelf = existing_shelf_list[0]
                shelf.name = value.get('name', shelf.name)
                shelf.description = value.get('description', shelf.description)
                shelf.privacy = value.get('privacy', shelf.privacy)
                shelf.last_synced = datetime.now(timezone.utc)
                self.db_tables['bookshelves'].update(shelf)
                self.log_sync_activity('bookshelf', uri, 'updated')
            else:
                # Create new shelf
                new_shelf = Bookshelf(
                    name=value.get('name', 'Untitled Shelf'),
                    owner_did=did, # Local owner is the same as remote for now
                    slug=generate_slug(),
                    description=value.get('description', ''),
                    privacy=value.get('privacy', 'public'),
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
        uri = book_data['uri']
        value = book_data['value']
        bookshelf_ref_uri = value.get('bookshelfRef')

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
                book.title = value.get('title', book.title)
                book.author = value.get('author', book.author)
                book.isbn = value.get('isbn', book.isbn)
                self.db_tables['books'].update(book)
                self.log_sync_activity('book', uri, 'updated')
            else:
                # Create new book
                new_book = Book(
                    bookshelf_id=parent_shelf_id,
                    title=value.get('title', 'Untitled Book'),
                    added_by_did=did,
                    isbn=value.get('isbn', ''),
                    author=value.get('author', ''),
                    is_remote=True,
                    remote_added_by_did=did,
                    discovered_at=datetime.now(timezone.utc),
                    original_atproto_uri=uri,
                    remote_sync_status='synced',
                    added_at=value.get('addedAt')
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
