import asyncio
from atproto_firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto_core.cid import CID
from models import setup_database
from atproto import models

db_tables = setup_database()

def store_bookshelf_from_network(record: dict, repo_did: str, record_uri: str):
    """Stores a bookshelf discovered on the network."""
    print(f"Discovered new bookshelf from {repo_did}: {record.get('name')}")
    # Avoid duplicates
    if db_tables['bookshelves'](where="atproto_uri=?", params=(record_uri,)):
        return

    shelf = {
        'name': record.get('name'),
        'description': record.get('description', ''),
        'privacy': record.get('privacy', 'public'),
        'owner_did': repo_did,
        'atproto_uri': record_uri,
        'slug': f"net-{record_uri.split('/')[-1]}", # Create a unique slug
        'created_at': record.get('createdAt'),
        'updated_at': record.get('createdAt')
    }
    db_tables['bookshelves'].insert(shelf)

def store_book_from_network(record: dict, repo_did: str, record_uri: str):
    """Stores a book discovered on the network."""
    print(f"Discovered new book from {repo_did}: {record.get('title')}")
    # Avoid duplicates
    if db_tables['books'](where="atproto_uri=?", params=(record_uri,)):
        return

    # Find the bookshelf in the local DB
    bookshelf = db_tables['bookshelves'](where="atproto_uri=?", params=(record.get('bookshelfRef'),))
    if not bookshelf:
        return

    book = {
        'bookshelf_id': bookshelf[0].id,
        'title': record.get('title'),
        'author': record.get('author', ''),
        'isbn': record.get('isbn', ''),
        'added_by_did': repo_did,
        'atproto_uri': record_uri,
        'added_at': record.get('addedAt')
    }
    db_tables['books'].insert(book)

async def on_message_handler(message):
    commit = parse_subscribe_repos_message(message)
    if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
        return
    if not commit.blocks:
        return

    for op in commit.ops:
        if op.action == 'create':
            record_cid = CID.decode(op.cid)
            record = commit.blocks.get(record_cid)
            
            if record and record.get('$type') == 'com.bibliome.bookshelf':
                store_bookshelf_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")
            
            if record and record.get('$type') == 'com.bibliome.book':
                store_book_from_network(record, commit.repo, f"at://{commit.repo}/{op.path}")

async def main():
    firehose = FirehoseSubscribeReposClient()
    await firehose.start(on_message_handler)

if __name__ == "__main__":
    asyncio.run(main())
