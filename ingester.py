import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from atproto_firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_core.cid import CID
from models import setup_database, log_activity
from atproto import models
from process_monitor import (
    log_process_event, record_process_metric, process_heartbeat, 
    update_process_status, get_process_monitor
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Process name for monitoring
PROCESS_NAME = "firehose_ingester"

db_tables = setup_database()

def ensure_user_exists(repo_did: str):
    """Ensure user exists in database, create placeholder if needed."""
    try:
        existing_user = db_tables['users'].get(repo_did)
        if existing_user:
            return existing_user
    except:
        pass
    
    # Create placeholder user - will be updated when they log in
    try:
        user_data = {
            'did': repo_did,
            'handle': f"user-{repo_did[-8:]}", # Use last 8 chars of DID as temp handle
            'display_name': f"User {repo_did[-8:]}",
            'avatar_url': '',
            'created_at': datetime.now(),
            'last_login': datetime.now()
        }
        db_tables['users'].insert(user_data)
        logger.info(f"Created placeholder user for DID: {repo_did}")
        return user_data
    except Exception as e:
        logger.error(f"Error creating placeholder user for {repo_did}: {e}")
        return None

def store_bookshelf_from_network(record: dict, repo_did: str, record_uri: str):
    """Stores a bookshelf discovered on the network."""
    try:
        logger.info(f"Discovered new bookshelf from {repo_did}: {record.get('name')}")
        
        # Avoid duplicates
        existing = db_tables['bookshelves'](where="atproto_uri=?", params=(record_uri,))
        if existing:
            logger.debug(f"Bookshelf already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did)

        shelf_data = {
            'name': record.get('name', 'Untitled Bookshelf'),
            'description': record.get('description', ''),
            'privacy': record.get('privacy', 'public'),
            'owner_did': repo_did,
            'atproto_uri': record_uri,
            'slug': f"net-{record_uri.split('/')[-1]}", # Create a unique slug
            'created_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00')),
            'updated_at': datetime.fromisoformat(record.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        result = db_tables['bookshelves'].insert(shelf_data)
        bookshelf_id = result.id if hasattr(result, 'id') else result
        
        # Log activity for network discovery
        log_activity(
            user_did=repo_did,
            activity_type='bookshelf_created',
            db_tables=db_tables,
            bookshelf_id=bookshelf_id,
            metadata='{"source": "network_firehose"}'
        )
        
        logger.info(f"Successfully stored bookshelf: {record.get('name')} (ID: {bookshelf_id})")
        
    except Exception as e:
        logger.error(f"Error storing bookshelf from network: {e}", exc_info=True)

def store_book_from_network(record: dict, repo_did: str, record_uri: str):
    """Stores a book discovered on the network."""
    try:
        logger.info(f"Discovered new book from {repo_did}: {record.get('title')}")
        
        # Avoid duplicates
        existing = db_tables['books'](where="atproto_uri=?", params=(record_uri,))
        if existing:
            logger.debug(f"Book already exists: {record_uri}")
            return

        # Ensure user exists
        ensure_user_exists(repo_did)

        # Find the bookshelf in the local DB
        bookshelf_ref = record.get('bookshelfRef')
        if not bookshelf_ref:
            logger.warning(f"Book {record.get('title')} has no bookshelf reference")
            return
            
        bookshelf = db_tables['bookshelves'](where="atproto_uri=?", params=(bookshelf_ref,))
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
            'added_at': datetime.fromisoformat(record.get('addedAt', datetime.now().isoformat()).replace('Z', '+00:00'))
        }
        
        result = db_tables['books'].insert(book_data)
        book_id = result.id if hasattr(result, 'id') else result
        
        # Log activity for network discovery
        log_activity(
            user_did=repo_did,
            activity_type='book_added',
            db_tables=db_tables,
            bookshelf_id=bookshelf[0].id,
            book_id=book_id,
            metadata='{"source": "network_firehose"}'
        )
        
        logger.info(f"Successfully stored book: {record.get('title')} (ID: {book_id})")
        
    except Exception as e:
        logger.error(f"Error storing book from network: {e}", exc_info=True)

# Global counters for monitoring
message_count = 0
bookshelf_count = 0
book_count = 0
error_count = 0

async def on_message_handler(message):
    """Handle incoming firehose messages with error handling."""
    global message_count, bookshelf_count, book_count, error_count
    
    try:
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        if not commit.blocks:
            return

        message_count += 1
        message_processed = False

        for op in commit.ops:
            try:
                if op.action == 'create':
                    record_cid = CID.decode(op.cid)
                    record = commit.blocks.get(record_cid)
                    
                    if record and record.get('$type') == 'com.bibliome.bookshelf':
                        store_bookshelf_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")
                        bookshelf_count += 1
                        message_processed = True
                        log_process_event(PROCESS_NAME, f"Processed bookshelf: {record.get('name')}", "INFO", "activity")
                    
                    elif record and record.get('$type') == 'com.bibliome.book':
                        store_book_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")
                        book_count += 1
                        message_processed = True
                        log_process_event(PROCESS_NAME, f"Processed book: {record.get('title')}", "INFO", "activity")
                        
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing operation {op.action} for {commit.repo}: {e}")
                log_process_event(PROCESS_NAME, f"Error processing operation: {e}", "ERROR", "error")
                continue  # Continue processing other operations
        
        # Send heartbeat every 100 messages or when we process relevant records
        if message_count % 100 == 0 or message_processed:
            activity_info = {
                "messages_processed": message_count,
                "bookshelves_found": bookshelf_count,
                "books_found": book_count,
                "errors_count": error_count
            }
            process_heartbeat(PROCESS_NAME, activity_info)
            
            if message_count % 100 == 0:
                log_process_event(PROCESS_NAME, f"Processed {message_count} messages total", "INFO", "activity")
                
    except Exception as e:
        error_count += 1
        logger.error(f"Error handling firehose message: {e}", exc_info=True)
        log_process_event(PROCESS_NAME, f"Critical error in message handler: {e}", "ERROR", "error")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        update_process_status(PROCESS_NAME, "stopped")
        log_process_event(PROCESS_NAME, "Process shutdown via signal", "INFO", "stop")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

async def main():
    """Main firehose monitoring loop with reconnection logic."""
    global message_count, bookshelf_count, book_count, error_count
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Update process status to starting
    update_process_status(PROCESS_NAME, "starting", pid=os.getpid())
    log_process_event(PROCESS_NAME, "Firehose ingester starting", "INFO", "start")
    
    logger.info("Starting AT-Proto firehose monitoring for Bibliome records...")
    
    max_retries = 5
    retry_delay = 5  # seconds
    
    # Update status to running
    update_process_status(PROCESS_NAME, "running", pid=os.getpid())
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to firehose (attempt {attempt + 1}/{max_retries})...")
            log_process_event(PROCESS_NAME, f"Connecting to firehose (attempt {attempt + 1}/{max_retries})", "INFO", "activity")
            
            firehose = FirehoseSubscribeReposClient()
            
            # Reset counters on new connection
            message_count = 0
            bookshelf_count = 0
            book_count = 0
            error_count = 0
            
            log_process_event(PROCESS_NAME, "Connected to AT-Proto firehose", "INFO", "activity")
            await firehose.start(on_message_handler)
            
        except KeyboardInterrupt:
            logger.info("Firehose monitoring stopped by user")
            update_process_status(PROCESS_NAME, "stopped")
            log_process_event(PROCESS_NAME, "Process stopped by user", "INFO", "stop")
            break
            
        except Exception as e:
            error_count += 1
            logger.error(f"Firehose connection failed (attempt {attempt + 1}): {e}")
            log_process_event(PROCESS_NAME, f"Connection failed: {e}", "ERROR", "error")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                log_process_event(PROCESS_NAME, f"Retrying in {retry_delay} seconds", "INFO", "activity")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached. Firehose monitoring stopped.")
                log_process_event(PROCESS_NAME, "Max retries reached, stopping", "ERROR", "error")
                update_process_status(PROCESS_NAME, "failed", error_message="Max retries reached")
                break
    
    # Final status update
    update_process_status(PROCESS_NAME, "stopped")
    log_process_event(PROCESS_NAME, "Firehose monitoring terminated", "INFO", "stop")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Firehose monitoring terminated")
        update_process_status(PROCESS_NAME, "stopped")
        log_process_event(PROCESS_NAME, "Process terminated by interrupt", "INFO", "stop")
