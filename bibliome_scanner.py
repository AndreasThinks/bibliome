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
from models import SyncLog, User, Bookshelf, Book, generate_slug
from database_manager import db_manager
from direct_pds_client import DirectPDSClient
from hybrid_discovery import HybridDiscoveryService
from circuit_breaker import CircuitBreaker
from rate_limiter import RateLimiter
from api_clients import BookAPIClient
from atproto import IdResolver

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
        self.db_tables = None
        self.scan_interval_hours = int(os.getenv('BIBLIOME_SCAN_INTERVAL_HOURS', '6'))
        self.import_public_only = os.getenv('BIBLIOME_IMPORT_PUBLIC_ONLY', 'true').lower() == 'true'
        self.user_batch_size = int(os.getenv('BIBLIOME_USER_BATCH_SIZE', '50'))
        self.running = True
        
        # Initialize ID resolver for handle resolution
        self.id_resolver = IdResolver()
        
        # Initialize persistent BookAPIClient with rate limiting
        self.book_api_client = BookAPIClient()

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
        self.db_tables = await db_manager.get_connection()
        
        # 1. Discover users with Bibliome records
        discovered_dids = await self.discovery.discover_users()
        logger.info(f"Discovered a total of {len(discovered_dids)} Bibliome users.")
        
        # 2. Process discovered users and create database entries
        logger.info(f"Processing {len(discovered_dids)} discovered users to create database entries...")
        processed_count = 0
        for i, did in enumerate(discovered_dids):
            try:
                # Get user profile data
                data = await self.pds_client.get_repo_records(did, ["app.bsky.actor.profile"])
                profile_data = data.get("collections", {}).get("app.bsky.actor.profile", [])
                pds_endpoint = data.get("pds")
                
                if profile_data and pds_endpoint:
                    await self.sync_user_profile(did, profile_data[0]['value'], pds_endpoint)
                    processed_count += 1
                
                if (i + 1) % 10 == 0:  # Log progress every 10 users
                    logger.info(f"Processed {i + 1}/{len(discovered_dids)} users ({processed_count} successfully)...")
                    
            except Exception as e:
                logger.error(f"Error processing user {did}: {e}")
                continue
        
        logger.info(f"Completed processing discovered users. Successfully processed {processed_count}/{len(discovered_dids)} users.")
        
        # 3. Sync bookshelves and books for all discovered users (both local and remote)
        # This ensures local users who create content on other instances get it synced back
        logger.info(f"Syncing content for all {len(discovered_dids)} discovered users (local + remote)...")
        for i in range(0, len(discovered_dids), self.user_batch_size):
            batch = discovered_dids[i:i + self.user_batch_size]
            logger.info(f"Processing user content batch {i//self.user_batch_size + 1}/{(len(discovered_dids) + self.user_batch_size - 1)//self.user_batch_size}...")
            for did in batch:
                await self.sync_user_content(did)
            logger.info(f"Completed content sync for batch of {len(batch)} users.")

    def _construct_blob_url(self, did: str, cid: str, pds_endpoint: str) -> str:
        """Constructs a proper blob URL from a PDS endpoint, DID, and CID."""
        base_url = pds_endpoint.rstrip('/xrpc')
        return f"{base_url}/xrpc/com.atproto.sync.getBlob?did={did}&cid={cid}"

    def _resolve_did_to_handle(self, did: str) -> str:
        """Resolve a DID to its handle using AT Protocol Identity resolver.
        
        Args:
            did: The DID to resolve (e.g., 'did:plc:abc123...')
            
        Returns:
            The resolved handle (e.g., 'alice.bsky.social') or the DID as fallback
        """
        try:
            # Use the IdResolver to get the DID document
            did_doc = self.id_resolver.did.resolve(did)
            
            # Extract handle from alsoKnownAs field
            if did_doc and hasattr(did_doc, 'also_known_as') and did_doc.also_known_as:
                for aka in did_doc.also_known_as:
                    if isinstance(aka, str) and aka.startswith('at://'):
                        # Extract handle from at:// URI (e.g., 'at://alice.bsky.social' -> 'alice.bsky.social')
                        handle = aka[5:]  # Remove 'at://' prefix
                        logger.debug(f"Resolved DID {did} to handle {handle}")
                        return handle
            
            # If no handle found in alsoKnownAs, try to resolve directly
            # This is a fallback that might work in some cases
            try:
                atproto_data = self.id_resolver.did.resolve_atproto_data(did)
                if atproto_data and hasattr(atproto_data, 'handle') and atproto_data.handle:
                    logger.debug(f"Resolved DID {did} to handle {atproto_data.handle} via atproto_data")
                    return atproto_data.handle
            except Exception as e:
                logger.debug(f"Failed to resolve handle via atproto_data for {did}: {e}")
            
            logger.warning(f"Could not resolve handle for DID {did}, using DID as fallback")
            return did
            
        except Exception as e:
            logger.warning(f"Error resolving handle for DID {did}: {e}, using DID as fallback")
            return did

    async def sync_user_profile(self, did: str, profile_data: any, pds_endpoint: str):
        """Sync a single user's profile."""
        try:
            if not profile_data:
                self.log_sync_activity('user', did, 'failed', 'Profile not found')
                return

            display_name = getattr(profile_data, 'displayName', None)
            avatar = getattr(profile_data, 'avatar', None)
            avatar_url = self._construct_blob_url(did, str(avatar.ref.link), pds_endpoint) if avatar and hasattr(avatar, 'ref') and hasattr(avatar.ref, 'link') else None

            # Resolve DID to handle
            resolved_handle = self._resolve_did_to_handle(did)

            try:
                user = self.db_tables['users'][did]
                # User exists, update if needed
                user.is_remote = True
                user.last_seen_remote = datetime.now(timezone.utc)
                user.display_name = display_name
                user.avatar_url = avatar_url
                user.handle = resolved_handle  # Update handle with resolved value
                self.db_tables['users'].update(user)
                self.log_sync_activity('user', did, 'updated', f'Profile updated, handle resolved to {resolved_handle}')
            except NotFoundError:
                # New user, insert into DB
                new_user = User(
                    did=did,
                    handle=resolved_handle,  # Use resolved handle instead of DID
                    display_name=display_name,
                    avatar_url=avatar_url,
                    is_remote=True,
                    discovered_at=datetime.now(timezone.utc),
                    last_seen_remote=datetime.now(timezone.utc),
                    remote_sync_status='synced'
                )
                self.db_tables['users'].insert(new_user)
                self.log_sync_activity('user', did, 'imported', f'New remote user discovered, handle resolved to {resolved_handle}')

        except Exception as e:
            logger.error(f"Error syncing profile for {did}: {e}", exc_info=True)
            self.log_sync_activity('user', did, 'failed', str(e))

    async def sync_user_content(self, did: str):
        """Sync all bookshelves and books for a given user."""
        logger.info(f"Syncing content for user {did}...")
        try:
            data = await self.pds_client.get_repo_records(did, ["com.bibliome.book", "com.bibliome.bookshelf", "app.bsky.actor.profile"])
            pds_endpoint = data.get("pds")
            
            # Sync profile
            profile_data = data.get("collections", {}).get("app.bsky.actor.profile", [])
            if profile_data and pds_endpoint:
                await self.sync_user_profile(did, profile_data[0]['value'], pds_endpoint)

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
            # Extract createdAt from AT-Proto record
            created_at = None
            created_at_raw = getattr(value, 'createdAt', None)
            if created_at_raw:
                try:
                    # Parse the ISO timestamp - use dateutil for robust parsing
                    from dateutil.parser import parse as dateutil_parse
                    created_at = dateutil_parse(str(created_at_raw))
                except ImportError:
                    # Fallback to manual parsing if dateutil not available
                    try:
                        if isinstance(created_at_raw, str):
                            # Remove microseconds and timezone for basic parsing
                            clean_string = created_at_raw.split('.')[0]  # Remove microseconds
                            if '+' in clean_string:
                                clean_string = clean_string.split('+')[0]  # Remove timezone
                            created_at = datetime.strptime(clean_string, '%Y-%m-%dT%H:%M:%S')
                            # Add UTC timezone
                            created_at = created_at.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Failed to parse createdAt '{created_at_raw}' for bookshelf {uri}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to parse createdAt '{created_at_raw}' for bookshelf {uri}: {e}")

            # Deduplication check
            existing_shelf_list = self.db_tables['bookshelves']("original_atproto_uri=?", (uri,))
            if existing_shelf_list:
                # Update existing shelf
                shelf = existing_shelf_list[0]
                shelf.name = getattr(value, 'name', shelf.name)
                shelf.description = getattr(value, 'description', shelf.description)
                shelf.privacy = getattr(value, 'privacy', shelf.privacy)
                shelf.self_join = getattr(value, 'openToContributions', shelf.self_join)
                shelf.last_synced = datetime.now(timezone.utc)
                # Update created_at if we have it and it's not already set
                if created_at and not shelf.created_at:
                    shelf.created_at = created_at
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
                    self_join=getattr(value, 'openToContributions', False),
                    created_at=created_at,  # Set the original creation date
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

    async def enrich_book_with_cover(self, book_data: dict) -> dict:
        """Enrich book data with cover image from external APIs using persistent rate-limited client."""
        try:
            # Use the persistent BookAPIClient with rate limiting
            # Try to get book details by ISBN first (most reliable)
            if book_data.get('isbn'):
                logger.debug(f"Looking up cover for ISBN: {book_data['isbn']}")
                details = await self.book_api_client.get_book_details(book_data['isbn'])
                if details and details.get('cover_url'):
                    book_data['cover_url'] = details['cover_url']
                    logger.debug(f"Found cover via ISBN lookup: {details['cover_url']}")
                    return book_data

            # Fallback: search by title and author
            if book_data.get('title'):
                search_query = f"{book_data['title']}"
                if book_data.get('author'):
                    search_query += f" {book_data['author']}"

                logger.debug(f"Searching for cover with query: '{search_query}'")
                results = await self.book_api_client.search_books(search_query, max_results=1)
                if results and results[0].get('cover_url'):
                    book_data['cover_url'] = results[0]['cover_url']
                    logger.debug(f"Found cover via search: {results[0]['cover_url']}")
                    return book_data

            logger.debug(f"No cover found for book: {book_data.get('title', 'Unknown')}")
            return book_data

        except Exception as e:
            logger.warning(f"Error enriching book with cover: {e}")
            return book_data

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
                # Create new book with cover enrichment
                book_dict = {
                    'bookshelf_id': parent_shelf_id,
                    'title': getattr(value, 'title', 'Untitled Book'),
                    'added_by_did': did,
                    'isbn': getattr(value, 'isbn', ''),
                    'author': getattr(value, 'author', ''),
                    'cover_url': '',  # Will be populated by enrichment
                    'is_remote': True,
                    'remote_added_by_did': did,
                    'discovered_at': datetime.now(timezone.utc),
                    'original_atproto_uri': uri,
                    'remote_sync_status': 'synced',
                    'added_at': getattr(value, 'addedAt', None)
                }

                # Try to enrich with cover image (but don't fail if it doesn't work)
                try:
                    enriched_data = await self.enrich_book_with_cover(book_dict)
                    book_dict.update(enriched_data)
                except Exception as e:
                    logger.warning(f"Failed to enrich book with cover, proceeding without: {e}")

                new_book = Book(**book_dict)
                created_book = self.db_tables['books'].insert(new_book)
                
                # Cache the cover image if available
                if book_dict.get('cover_url') and book_dict['cover_url'].strip():
                    try:
                        from cover_cache import cover_cache
                        
                        # Cache the cover asynchronously
                        cached_path = await cover_cache.download_and_cache_cover(
                            created_book.id, book_dict['cover_url']
                        )
                        
                        # Update the book record with cache info if successful
                        if cached_path:
                            self.db_tables['books'].update({
                                'cached_cover_path': cached_path,
                                'cover_cached_at': datetime.now(timezone.utc)
                            }, created_book.id)
                            logger.debug(f"Cover cached for book {created_book.id}: {cached_path}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to cache cover for book {created_book.id}: {e}")
                        # Don't fail the whole sync, just log the error
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
