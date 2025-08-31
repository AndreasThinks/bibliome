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

from atproto import Client
from models import get_database, SyncLog, User, Bookshelf, Book, generate_slug
from scanner_client import BiblioMeATProtoClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BiblioMeScanner:
    """Scans the AT-Proto network for Bibliome records and imports them locally."""
    
    def __init__(self):
        self.client = BiblioMeATProtoClient(Client())
        self.db_tables = get_database()
        self.scan_interval_hours = int(os.getenv('BIBLIOME_SCAN_INTERVAL_HOURS', '6'))
        self.rate_limit_per_minute = int(os.getenv('BIBLIOME_RATE_LIMIT_PER_MINUTE', '30'))
        self.import_public_only = os.getenv('BIBLIOME_IMPORT_PUBLIC_ONLY', 'true').lower() == 'true'
        self.max_users_per_scan = int(os.getenv('BIBLIOME_MAX_USERS_PER_SCAN', '100'))
        self.running = True

    async def run(self):
        """Main loop for the scanner service."""
        logger.info("Starting Bibliome Scanner Service...")
        while self.running:
            try:
                await self.run_scan_cycle()
                logger.info(f"Scan cycle complete. Waiting {self.scan_interval_hours} hours for the next scan.")
                await asyncio.sleep(self.scan_interval_hours * 3600)
            except Exception as e:
                logger.error(f"Error in scan cycle: {e}", exc_info=True)
                await asyncio.sleep(3600) # Wait an hour before retrying on major failure

    async def run_scan_cycle(self):
        """Runs a complete scan and import cycle."""
        logger.info("Starting new scan cycle...")
        
        # 1. Discover users with Bibliome records
        discovered_dids = await self.client.discover_bibliome_users(limit=self.max_users_per_scan)
        logger.info(f"Discovered {len(discovered_dids)} potential Bibliome users.")
        
        # 2. Sync profiles for each discovered user
        for did in discovered_dids:
            await self.sync_user_profile(did)
            await asyncio.sleep(60 / self.rate_limit_per_minute) # Rate limit

        # 3. Sync bookshelves and books for all remote users
        remote_users = self.db_tables['users']("is_remote=1")
        logger.info(f"Found {len(remote_users)} remote users to sync.")
        for user in remote_users:
            await self.sync_user_content(user.did)
            await asyncio.sleep(60 / self.rate_limit_per_minute) # Rate limit

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
            except IndexError:
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
            logger.error(f"Error syncing profile for {did}: {e}")
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
            existing_shelf = self.db_tables['bookshelves']("original_atproto_uri=?", (uri,))
            if existing_shelf:
                # Update existing shelf
                shelf = existing_shelf[0]
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

            existing_book = self.db_tables['books']("original_atproto_uri=?", (uri,))
            if existing_book:
                # Update existing book
                book = existing_book[0]
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
    await scanner.run()

if __name__ == "__main__":
    asyncio.run(main())
