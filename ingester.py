import asyncio
import logging
from datetime import datetime
from atproto_firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_core.cid import CID
from models import setup_database, log_activity
from atproto import models

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

async def on_message_handler(message):
    """Handle incoming firehose messages with error handling."""
    try:
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return
        if not commit.blocks:
            return

        for op in commit.ops:
            try:
                if op.action == 'create':
                    record_cid = CID.decode(op.cid)
                    record = commit.blocks.get(record_cid)
                    
                    if record and record.get('$type') == 'com.bibliome.bookshelf':
                        store_bookshelf_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")
                    
                    elif record and record.get('$type') == 'com.bibliome.book':
                        store_book_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")
                        
            except Exception as e:
                logger.error(f"Error processing operation {op.action} for {commit.repo}: {e}")
                continue  # Continue processing other operations
                
    except Exception as e:
        logger.error(f"Error handling firehose message: {e}", exc_info=True)

async def main():
    """Main firehose monitoring loop with reconnection logic."""
    logger.info("Starting AT-Proto firehose monitoring for Bibliome records...")
    
    max_retries = 5
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to firehose (attempt {attempt + 1}/{max_retries})...")
            firehose = FirehoseSubscribeReposClient()
            await firehose.start(on_message_handler)
            
        except KeyboardInterrupt:
            logger.info("Firehose monitoring stopped by user")
            break
            
        except Exception as e:
            logger.error(f"Firehose connection failed (attempt {attempt + 1}): {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached. Firehose monitoring stopped.")
                break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Firehose monitoring terminated")
