import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from atproto_firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_core.cid import CID
from models import get_database, log_activity
from atproto import models, CAR
from process_monitor import (
    log_process_event, record_process_metric, process_heartbeat, 
    update_process_status, get_process_monitor
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Process name for monitoring
PROCESS_NAME = "firehose_ingester"

# Use shared database instance
db_tables = get_database()

# Cursor file for resume functionality
CURSOR_FILE = Path("firehose.cursor")

# Collections we're interested in
WANTED = {"com.bibliome.bookshelf", "com.bibliome.book"}

def collection_of(op_path: str) -> str:
    """Extract collection from operation path (e.g., 'com.bibliome.bookshelf/3l6abc...')"""
    return op_path.split("/", 1)[0] if op_path else ""

def load_cursor():
    """Load the last processed sequence number from cursor file."""
    try:
        return int(CURSOR_FILE.read_text().strip())
    except Exception:
        return None

def save_cursor(seq: int):
    """Save the current sequence number to cursor file."""
    try:
        CURSOR_FILE.write_text(str(seq))
    except Exception as e:
        logger.warning(f"Failed saving cursor: {e}")

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

def on_message_handler(message):
    """Handle incoming firehose messages with optimized filtering and error handling."""
    global message_count, bookshelf_count, book_count, error_count
    
    try:
        evt = parse_subscribe_repos_message(message)
        if not isinstance(evt, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        if not evt.ops:
            return

        # Save cursor for resume functionality
        save_cursor(evt.seq)

        message_count += 1
        message_processed = False

        # Fast pre-filter: do we have any CREATEs in collections we care about?
        wanted_ops = [op for op in evt.ops
                      if op.action == "create" and collection_of(op.path) in WANTED and op.cid]

        if not wanted_ops:
            # No relevant creates: send heartbeat periodically without CAR decode overhead
            if message_count % 100 == 0:
                process_heartbeat(PROCESS_NAME, {
                    "messages_processed": message_count,
                    "bookshelves_found": bookshelf_count,
                    "books_found": book_count,
                    "errors_count": error_count
                }, db_tables=db_tables)
            return

        # Decode CAR once, only when necessary
        try:
            car = CAR.from_bytes(evt.blocks)
        except Exception as car_error:
            logger.warning(f"CAR decode error for {evt.repo}: {car_error}")
            log_process_event(PROCESS_NAME, f"CAR decode error: {car_error}", "WARNING", "error", db_tables=db_tables)
            return

        for op in wanted_ops:
            try:
                record = car.blocks.get(op.cid)  # op.cid is already a CID
                if not record:
                    logger.debug(f"No record for CID {op.cid}")
                    continue

                path_collection = collection_of(op.path)
                rec_type = record.get("$type")

                # defensive: ensure collection matches $type
                if rec_type and rec_type != path_collection:
                    logger.debug(f"Type mismatch {rec_type} vs {path_collection}")
                    continue

                record_uri = f"at://{evt.repo}/{op.path}"

                if path_collection == "com.bibliome.bookshelf":
                    store_bookshelf_from_network(record, evt.repo, record_uri)
                    bookshelf_count += 1
                    message_processed = True
                    log_process_event(PROCESS_NAME, f"Processed bookshelf: {record.get('name')}", "INFO", "activity", db_tables=db_tables)

                elif path_collection == "com.bibliome.book":
                    store_book_from_network(record, evt.repo, record_uri)
                    book_count += 1
                    message_processed = True
                    log_process_event(PROCESS_NAME, f"Processed book: {record.get('title')}", "INFO", "activity", db_tables=db_tables)

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing op for {evt.repo}: {e}", exc_info=True)
                log_process_event(PROCESS_NAME, f"Error processing operation: {e}", "ERROR", "error", db_tables=db_tables)
                continue

        # Heartbeat on activity or every 100 messages
        if message_count % 100 == 0 or message_processed:
            process_heartbeat(PROCESS_NAME, {
                "messages_processed": message_count,
                "bookshelves_found": bookshelf_count,
                "books_found": book_count,
                "errors_count": error_count
            }, db_tables=db_tables)
            
            if message_count % 100 == 0:
                log_process_event(PROCESS_NAME, f"Processed {message_count} messages total", "INFO", "activity", db_tables=db_tables)

    except Exception as e:
        error_count += 1
        logger.error(f"Error handling firehose message: {e}", exc_info=True)
        log_process_event(PROCESS_NAME, f"Critical error in message handler: {e}", "ERROR", "error", db_tables=db_tables)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        update_process_status(PROCESS_NAME, "stopped", db_tables=db_tables)
        log_process_event(PROCESS_NAME, "Process shutdown via signal", "INFO", "stop", db_tables=db_tables)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

async def main():
    """Main firehose monitoring loop with reconnection logic."""
    global message_count, bookshelf_count, book_count, error_count
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Update process status to starting
    update_process_status(PROCESS_NAME, "starting", pid=os.getpid(), db_tables=db_tables)
    log_process_event(PROCESS_NAME, "Firehose ingester starting", "INFO", "start", db_tables=db_tables)
    
    logger.info("Starting AT-Proto firehose monitoring for Bibliome records...")
    
    max_retries = 5
    retry_delay = 5  # seconds
    
    # Update status to running
    update_process_status(PROCESS_NAME, "running", pid=os.getpid(), db_tables=db_tables)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to firehose (attempt {attempt + 1}/{max_retries})...")
            log_process_event(PROCESS_NAME, f"Connecting to firehose (attempt {attempt + 1}/{max_retries})", "INFO", "activity", db_tables=db_tables)
            
            firehose = FirehoseSubscribeReposClient()
            
            # Reset counters on new connection
            message_count = 0
            bookshelf_count = 0
            book_count = 0
            error_count = 0
            
            # Load cursor for resume functionality
            cursor = load_cursor()
            if cursor:
                logger.info(f"Resuming from cursor position: {cursor}")
                log_process_event(PROCESS_NAME, f"Resuming from cursor: {cursor}", "INFO", "activity", db_tables=db_tables)
                params = models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor)
            else:
                logger.info("Starting from beginning (no cursor found)")
                log_process_event(PROCESS_NAME, "Starting from beginning", "INFO", "activity", db_tables=db_tables)
                params = models.ComAtprotoSyncSubscribeRepos.Params()
            
            log_process_event(PROCESS_NAME, "Connected to AT-Proto firehose", "INFO", "activity", db_tables=db_tables)
            await firehose.start(on_message_handler, params)
            
        except KeyboardInterrupt:
            logger.info("Firehose monitoring stopped by user")
            update_process_status(PROCESS_NAME, "stopped", db_tables=db_tables)
            log_process_event(PROCESS_NAME, "Process stopped by user", "INFO", "stop", db_tables=db_tables)
            break
            
        except Exception as e:
            error_count += 1
            logger.error(f"Firehose connection failed (attempt {attempt + 1}): {e}")
            log_process_event(PROCESS_NAME, f"Connection failed: {e}", "ERROR", "error", db_tables=db_tables)
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                log_process_event(PROCESS_NAME, f"Retrying in {retry_delay} seconds", "INFO", "activity", db_tables=db_tables)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached. Firehose monitoring stopped.")
                log_process_event(PROCESS_NAME, "Max retries reached, stopping", "ERROR", "error", db_tables=db_tables)
                update_process_status(PROCESS_NAME, "failed", error_message="Max retries reached", db_tables=db_tables)
                break
    
    # Final status update
    update_process_status(PROCESS_NAME, "stopped", db_tables=db_tables)
    log_process_event(PROCESS_NAME, "Firehose monitoring terminated", "INFO", "stop", db_tables=db_tables)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Firehose monitoring terminated")
        update_process_status(PROCESS_NAME, "stopped", db_tables=db_tables)
        log_process_event(PROCESS_NAME, "Process terminated by interrupt", "INFO", "stop", db_tables=db_tables)
