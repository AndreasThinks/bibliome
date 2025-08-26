"""Historical AT Protocol record scanner for Bibliome.

This background service discovers and scans user profiles from the AT Protocol network
to find historical bookshelf and book records that predate our firehose monitoring.
"""

import asyncio
import logging
import os
import signal
import sys
import json
import time
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from atproto import AsyncClient, models as at_models
from atproto_firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_core.cid import CID
from atproto import CAR

# Import our database and monitoring systems
from models import (
    get_database, TrackedProfile, HistoricalScanQueue, 
    ensure_user_exists, store_bookshelf_from_network, store_book_from_network
)
from process_monitor import (
    log_process_event, record_process_metric, process_heartbeat, 
    update_process_status, get_process_monitor
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Process name for monitoring
PROCESS_NAME = "historical_scanner"

# Configuration from environment
SCAN_RATE_LIMIT = int(os.getenv('HISTORICAL_SCAN_RATE_LIMIT', '30'))  # requests per minute
SCAN_BATCH_SIZE = int(os.getenv('HISTORICAL_SCAN_BATCH_SIZE', '10'))  # profiles per batch
MAX_RETRIES = int(os.getenv('HISTORICAL_MAX_RETRIES', '3'))
PRIORITY_DELAY = int(os.getenv('HISTORICAL_PRIORITY_DELAY', '60'))  # seconds between high-priority scans
DISCOVERY_INTERVAL = int(os.getenv('HISTORICAL_DISCOVERY_INTERVAL', '3600'))  # 1 hour

# Rate limiting
REQUEST_DELAY = 60.0 / SCAN_RATE_LIMIT  # Delay between requests to respect rate limits

class HistoricalScanner:
    """Main historical scanner service."""
    
    def __init__(self):
        self.db_tables = get_database()
        self.running = False
        self.client = None
        self.stats = {
            'profiles_scanned': 0,
            'records_discovered': 0,
            'bookshelves_found': 0,
            'books_found': 0,
            'errors': 0,
            'queue_depth': 0
        }
        
        # Initialize process monitoring
        self.init_monitoring()
    
    def init_monitoring(self):
        """Initialize process monitoring registration."""
        try:
            monitor = get_process_monitor(self.db_tables)
            monitor.register_process(PROCESS_NAME, "historical", {
                "description": "AT Protocol historical record scanner",
                "expected_activity_interval": 600,  # 10 minutes
                "restart_policy": "always",
                "rate_limit": f"{SCAN_RATE_LIMIT} req/min",
                "batch_size": SCAN_BATCH_SIZE
            })
            logger.info("Historical scanner registered with process monitor")
        except Exception as e:
            logger.error(f"Failed to register with process monitor: {e}")
    
    async def initialize_client(self):
        """Initialize AT Protocol client for scanning."""
        try:
            self.client = AsyncClient()
            # We don't need to login for reading public records
            logger.info("AT Protocol client initialized for historical scanning")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AT Protocol client: {e}")
            return False
    
    def discover_profiles_from_follows(self) -> List[str]:
        """Discover profiles from user follow relationships."""
        try:
            # Get all users in our system
            users = list(self.db_tables['users']())
            discovered_dids = set()
            
            for user in users:
                try:
                    # This would need to be implemented with proper auth
                    # For now, we'll focus on profiles we already know about
                    # In a full implementation, we'd use the bluesky_auth service
                    # to get following lists for each user
                    pass
                except Exception as e:
                    logger.debug(f"Could not get follows for {user.did}: {e}")
                    continue
            
            return list(discovered_dids)
            
        except Exception as e:
            logger.error(f"Error discovering profiles from follows: {e}")
            return []
    
    def discover_profiles_from_network_activity(self) -> List[str]:
        """Discover profiles from existing network activity records."""
        try:
            # Get DIDs from existing activity records that aren't tracked yet
            query = """
                SELECT DISTINCT a.user_did 
                FROM activity a 
                LEFT JOIN tracked_profiles tp ON a.user_did = tp.did 
                WHERE tp.did IS NULL 
                AND a.user_did IS NOT NULL
                LIMIT 50
            """
            
            cursor = self.db_tables['db'].execute(query)
            discovered_dids = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Discovered {len(discovered_dids)} profiles from network activity")
            return discovered_dids
            
        except Exception as e:
            logger.error(f"Error discovering profiles from network activity: {e}")
            return []
    
    def add_profiles_to_tracking(self, dids: List[str], source: str = "network"):
        """Add discovered profiles to tracking system."""
        try:
            added_count = 0
            
            for did in dids:
                try:
                    # Check if already tracked
                    existing = self.db_tables['tracked_profiles'](f"did='{did}'")
                    if existing:
                        continue
                    
                    # Add to tracking
                    profile = TrackedProfile(
                        did=did,
                        handle="",  # Will be populated when we scan
                        display_name="",
                        discovered_at=datetime.now(),
                        discovery_source=source,
                        last_scanned_at=None,
                        scan_priority=2 if source == "network" else 1,  # network = medium priority
                        is_active=True
                    )
                    
                    self.db_tables['tracked_profiles'].insert(profile)
                    added_count += 1
                    
                    # Add to scan queue
                    scan_job = HistoricalScanQueue(
                        profile_did=did,
                        collection_type="both",  # Scan both bookshelves and books
                        priority=2 if source == "network" else 1,
                        status="pending",
                        created_at=datetime.now(),
                        retry_count=0
                    )
                    
                    self.db_tables['historical_scan_queue'].insert(scan_job)
                    
                except Exception as e:
                    logger.warning(f"Could not add profile {did} to tracking: {e}")
                    continue
            
            logger.info(f"Added {added_count} new profiles to tracking system")
            record_process_metric(PROCESS_NAME, "profiles_discovered", added_count, db_tables=self.db_tables)
            
        except Exception as e:
            logger.error(f"Error adding profiles to tracking: {e}")
    
    async def scan_profile_records(self, profile_did: str) -> Dict[str, int]:
        """Scan a single profile's repository for historical records."""
        if not self.client:
            raise Exception("AT Protocol client not initialized")
        
        stats = {'bookshelves': 0, 'books': 0}
        
        try:
            # Scan bookshelf collection
            try:
                response = await self.client.com.atproto.repo.list_records(
                    at_models.ComAtprotoRepoListRecords.Params(
                        repo=profile_did,
                        collection='com.bibliome.bookshelf',
                        limit=100
                    )
                )
                
                for record in response.records:
                    try:
                        # Store bookshelf with historical data source
                        record_uri = f"at://{profile_did}/{record.uri.split('/')[-2]}/{record.uri.split('/')[-1]}"
                        store_bookshelf_from_network(record.value, profile_did, record_uri, data_source='historical')
                        stats['bookshelves'] += 1
                        
                    except Exception as e:
                        logger.debug(f"Error processing bookshelf record for {profile_did}: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"No bookshelf records found for {profile_did}: {e}")
            
            # Scan book collection
            try:
                response = await self.client.com.atproto.repo.list_records(
                    at_models.ComAtprotoRepoListRecords.Params(
                        repo=profile_did,
                        collection='com.bibliome.book',
                        limit=100
                    )
                )
                
                for record in response.records:
                    try:
                        # Store book with historical data source
                        record_uri = f"at://{profile_did}/{record.uri.split('/')[-2]}/{record.uri.split('/')[-1]}"
                        store_book_from_network(record.value, profile_did, record_uri, data_source='historical')
                        stats['books'] += 1
                        
                    except Exception as e:
                        logger.debug(f"Error processing book record for {profile_did}: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"No book records found for {profile_did}: {e}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error scanning profile {profile_did}: {e}")
            raise
    
    def get_next_scan_jobs(self, limit: int = SCAN_BATCH_SIZE) -> List:
        """Get the next batch of scan jobs from the queue."""
        try:
            # Get pending jobs ordered by priority and creation time
            jobs = list(self.db_tables['historical_scan_queue'](
                "status='pending'",
                order_by="priority ASC, created_at ASC",
                limit=limit
            ))
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting scan jobs: {e}")
            return []
    
    def mark_job_processing(self, job_id: int):
        """Mark a job as being processed."""
        try:
            self.db_tables['historical_scan_queue'].update({
                'status': 'processing',
                'started_at': datetime.now()
            }, job_id)
        except Exception as e:
            logger.error(f"Error marking job {job_id} as processing: {e}")
    
    def complete_job(self, job_id: int, profile_did: str, success: bool = True, error_message: str = None):
        """Mark a job as completed or failed."""
        try:
            if success:
                # Update job status
                self.db_tables['historical_scan_queue'].update({
                    'status': 'completed',
                    'completed_at': datetime.now(),
                    'error_message': None
                }, job_id)
                
                # Update profile last scanned time
                self.db_tables['tracked_profiles'].update({
                    'last_scanned_at': datetime.now()
                }, profile_did)
                
            else:
                # Get current job to check retry count
                job = self.db_tables['historical_scan_queue'][job_id]
                retry_count = (job.retry_count or 0) + 1
                
                if retry_count >= MAX_RETRIES:
                    # Max retries reached, mark as failed
                    self.db_tables['historical_scan_queue'].update({
                        'status': 'failed',
                        'completed_at': datetime.now(),
                        'error_message': error_message,
                        'retry_count': retry_count
                    }, job_id)
                else:
                    # Reset to pending for retry
                    self.db_tables['historical_scan_queue'].update({
                        'status': 'pending',
                        'started_at': None,
                        'error_message': error_message,
                        'retry_count': retry_count
                    }, job_id)
                    
        except Exception as e:
            logger.error(f"Error completing job {job_id}: {e}")
    
    async def process_scan_queue(self):
        """Process the historical scan queue."""
        try:
            jobs = self.get_next_scan_jobs()
            
            if not jobs:
                logger.debug("No pending scan jobs")
                return
            
            logger.info(f"Processing {len(jobs)} scan jobs")
            
            for job in jobs:
                if not self.running:
                    break
                
                try:
                    # Mark as processing
                    self.mark_job_processing(job.id)
                    
                    # Scan the profile
                    logger.info(f"Scanning profile {job.profile_did} for historical records")
                    start_time = time.time()
                    
                    stats = await self.scan_profile_records(job.profile_did)
                    
                    # Update stats
                    self.stats['profiles_scanned'] += 1
                    self.stats['bookshelves_found'] += stats['bookshelves']
                    self.stats['books_found'] += stats['books']
                    self.stats['records_discovered'] += stats['bookshelves'] + stats['books']
                    
                    # Complete job
                    self.complete_job(job.id, job.profile_did, success=True)
                    
                    scan_duration = time.time() - start_time
                    logger.info(f"Scanned {job.profile_did}: {stats['bookshelves']} bookshelves, {stats['books']} books ({scan_duration:.2f}s)")
                    
                    # Log significant discoveries
                    if stats['bookshelves'] > 0 or stats['books'] > 0:
                        log_process_event(
                            PROCESS_NAME,
                            f"Discovered {stats['bookshelves']} bookshelves and {stats['books']} books from {job.profile_did}",
                            "INFO", "activity", db_tables=self.db_tables
                        )
                        
                        record_process_metric(PROCESS_NAME, "historical_records_found", 
                                            stats['bookshelves'] + stats['books'], db_tables=self.db_tables)
                    
                    # Rate limiting delay
                    await asyncio.sleep(REQUEST_DELAY)
                    
                except Exception as e:
                    self.stats['errors'] += 1
                    logger.error(f"Error processing scan job {job.id}: {e}")
                    self.complete_job(job.id, job.profile_did, success=False, error_message=str(e))
                    
                    # Longer delay on error
                    await asyncio.sleep(REQUEST_DELAY * 2)
            
        except Exception as e:
            logger.error(f"Error processing scan queue: {e}")
            self.stats['errors'] += 1
    
    def update_queue_stats(self):
        """Update queue depth statistics."""
        try:
            pending_count = len(list(self.db_tables['historical_scan_queue']("status='pending'")))
            self.stats['queue_depth'] = pending_count
        except Exception as e:
            logger.debug(f"Error updating queue stats: {e}")
    
    async def discovery_cycle(self):
        """Perform profile discovery and queue population."""
        try:
            logger.info("Starting profile discovery cycle")
            
            # Discover from network activity (most reliable source)
            network_dids = self.discover_profiles_from_network_activity()
            if network_dids:
                self.add_profiles_to_tracking(network_dids, source="network")
            
            # Future: Discover from follows when we have proper auth
            # follow_dids = self.discover_profiles_from_follows()
            # if follow_dids:
            #     self.add_profiles_to_tracking(follow_dids, source="follows")
            
            log_process_event(
                PROCESS_NAME,
                f"Discovery cycle completed: {len(network_dids)} new profiles discovered",
                "INFO", "activity", db_tables=self.db_tables
            )
            
        except Exception as e:
            logger.error(f"Error in discovery cycle: {e}")
            log_process_event(PROCESS_NAME, f"Discovery cycle error: {e}", "ERROR", "error", db_tables=self.db_tables)
    
    async def run(self):
        """Main run loop for the historical scanner."""
        logger.info("Starting historical scanner service")
        
        # Update process status
        update_process_status(PROCESS_NAME, "starting", db_tables=self.db_tables)
        
        try:
            # Initialize AT Protocol client
            if not await self.initialize_client():
                raise Exception("Failed to initialize AT Protocol client")
            
            self.running = True
            update_process_status(PROCESS_NAME, "running", pid=os.getpid(), db_tables=self.db_tables)
            
            log_process_event(PROCESS_NAME, "Historical scanner started", "INFO", "start", db_tables=self.db_tables)
            
            last_discovery = 0
            heartbeat_counter = 0
            
            while self.running:
                try:
                    # Periodic profile discovery
                    current_time = time.time()
                    if current_time - last_discovery > DISCOVERY_INTERVAL:
                        await self.discovery_cycle()
                        last_discovery = current_time
                    
                    # Process scan queue
                    await self.process_scan_queue()
                    
                    # Update queue statistics
                    self.update_queue_stats()
                    
                    # Send heartbeat every few cycles
                    heartbeat_counter += 1
                    if heartbeat_counter >= 5:  # Every ~5 cycles
                        process_heartbeat(PROCESS_NAME, {
                            "profiles_scanned": self.stats['profiles_scanned'],
                            "records_discovered": self.stats['records_discovered'],
                            "bookshelves_found": self.stats['bookshelves_found'],
                            "books_found": self.stats['books_found'],
                            "queue_depth": self.stats['queue_depth'],
                            "errors_count": self.stats['errors']
                        }, db_tables=self.db_tables)
                        heartbeat_counter = 0
                    
                    # Sleep between cycles (adjust based on queue depth)
                    if self.stats['queue_depth'] > 0:
                        sleep_time = max(30, PRIORITY_DELAY - (self.stats['queue_depth'] * 2))
                    else:
                        sleep_time = PRIORITY_DELAY * 2  # Longer sleep when queue is empty
                    
                    await asyncio.sleep(sleep_time)
                    
                except Exception as e:
                    self.stats['errors'] += 1
                    logger.error(f"Error in main loop: {e}")
                    log_process_event(PROCESS_NAME, f"Main loop error: {e}", "ERROR", "error", db_tables=self.db_tables)
                    await asyncio.sleep(60)  # Error recovery delay
            
        except Exception as e:
            logger.error(f"Fatal error in historical scanner: {e}")
            update_process_status(PROCESS_NAME, "failed", error_message=str(e), db_tables=self.db_tables)
            log_process_event(PROCESS_NAME, f"Fatal error: {e}", "ERROR", "error", db_tables=self.db_tables)
            raise
        finally:
            self.running = False
            update_process_status(PROCESS_NAME, "stopped", db_tables=self.db_tables)
            log_process_event(PROCESS_NAME, "Historical scanner stopped", "INFO", "stop", db_tables=self.db_tables)

# Enhanced store functions that support data_source parameter
def store_bookshelf_from_network_enhanced(record: dict, repo_did: str, record_uri: str, data_source: str = 'network'):
    """Enhanced version of store_bookshelf_from_network with data_source tracking."""
    try:
        db_tables = get_database()
        logger.info(f"Discovered new bookshelf from {repo_did}: {record.get('name')} (source: {data_source})")
        
        # Avoid duplicates by atproto_uri
        existing = list(db_tables['bookshelves'](f"atproto_uri='{record_uri}'"))
        if existing:
            logger.debug(f"Bookshelf already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did, db_tables, data_source=data_source)

        shelf_data = {
            'name': record.get('name', 'Untitled Bookshelf'),
            'description': record.get('description', ''),
            'privacy': record.get('privacy', 'public'),
            'owner_did': repo_did,
            'atproto_uri': record_uri,
            'slug': f"net-{record_uri.split('/')[-1]}",  # Create a unique slug
            'data_source': data_source,  # Track the source
            'created_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00')),
            'updated_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        from models import Bookshelf
        created_shelf = db_tables['bookshelves'].insert(Bookshelf(**shelf_data))
        bookshelf_id = created_shelf.id if hasattr(created_shelf, 'id') else created_shelf
        
        # Log activity for network discovery
        from models import log_activity
        metadata = json.dumps({"source": data_source})
        log_activity(
            user_did=repo_did,
            activity_type='bookshelf_created',
            db_tables=db_tables,
            bookshelf_id=bookshelf_id,
            metadata=metadata
        )
        
        logger.info(f"Successfully stored {data_source} bookshelf: {record.get('name')} (ID: {bookshelf_id})")
        
    except Exception as e:
        logger.error(f"Error storing bookshelf from {data_source}: {e}", exc_info=True)

def store_book_from_network_enhanced(record: dict, repo_did: str, record_uri: str, data_source: str = 'network'):
    """Enhanced version of store_book_from_network with data_source tracking."""
    try:
        db_tables = get_database()
        logger.info(f"Discovered new book from {repo_did}: {record.get('title')} (source: {data_source})")
        
        # Avoid duplicates by atproto_uri
        existing = list(db_tables['books'](f"atproto_uri='{record_uri}'"))
        if existing:
            logger.debug(f"Book already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did, db_tables, data_source=data_source)

        # Find the bookshelf in the local DB
        bookshelf_ref = record.get('bookshelfRef')
        if not bookshelf_ref:
            logger.warning(f"Book {record.get('title')} has no bookshelf reference")
            return

        bookshelf = list(db_tables['bookshelves'](f"atproto_uri='{bookshelf_ref}'"))
        if not bookshelf:
            logger.warning(f"Bookshelf not found for book {record.get('title')}: {bookshelf_ref}")
            return

        book_data = {
            'bookshelf_id': bookshelf[0].id,
            'title': record.get('title', 'Untitled Book'),
            'author': record.get('author', ''),
            'isbn': record.get('isbn', ''),
            'added_by_did': repo_did,
            'atproto_uri': record_uri,
            'data_source': data_source,  # Track the source
            'added_at': datetime.fromisoformat(record.get('addedAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        from models import Book
        created_book = db_tables['books'].insert(Book(**book_data))
        book_id = created_book.id if hasattr(created_book, 'id') else created_book
        
        # Log activity for network discovery
        from models import log_activity
        metadata = json.dumps({"source": data_source})
        log_activity(
            user_did=repo_did,
            activity_type='book_added',
            db_tables=db_tables,
            bookshelf_id=bookshelf[0].id,
            book_id=book_id,
            metadata=metadata
        )
        
        logger.info(f"Successfully stored {data_source} book: {record.get('title')} (ID: {book_id})")
        
    except Exception as e:
        logger.error(f"Error storing book from {data_source}: {e}", exc_info=True)


def setup_signal_handlers(scanner):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down historical scanner...")
        scanner.running = False
        update_process_status(PROCESS_NAME, "stopped", db_tables=scanner.db_tables)
        log_process_event(PROCESS_NAME, "Process shutdown via signal", "INFO", "stop", db_tables=scanner.db_tables)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main entry point for the historical scanner service."""
    scanner = HistoricalScanner()
    
    # Setup signal handlers
    setup_signal_handlers(scanner)
    
    try:
        await scanner.run()
    except KeyboardInterrupt:
        logger.info("Historical scanner interrupted by user")
        scanner.running = False
    except Exception as e:
        logger.error(f"Historical scanner fatal error: {e}")
        update_process_status(PROCESS_NAME, "failed", error_message=str(e), db_tables=scanner.db_tables)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Historical scanner terminated by user")
    except Exception as e:
        logger.error(f"Historical scanner startup error: {e}")
        sys.exit(1)
