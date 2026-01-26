"""AT Protocol record operations for Bibliome.

This module provides functions for creating, updating, and deleting
records on AT Protocol (Bluesky) user repositories.
"""

import time
import random
import logging
from typing import Optional

from atproto import Client, models as at_models
from atproto_client.exceptions import UnauthorizedError, BadRequestError

logger = logging.getLogger(__name__)


def generate_tid() -> str:
    """Generate a TID (Timestamp Identifier) for AT Protocol records.
    
    TIDs are 13-character base32 strings that encode a timestamp and random clock ID.
    They're used as record keys (rkeys) in AT Protocol.
    
    Returns:
        13-character TID string
    """
    chars = '234567abcdefghijklmnopqrstuvwxyz'
    
    timestamp = int(time.time() * 1_000_000)
    clock_id = random.randint(0, 1023)
    
    tid_int = (timestamp << 10) | clock_id
    
    tid_str = ''
    for _ in range(13):
        tid_str = chars[tid_int % 32] + tid_str
        tid_int //= 32
        
    return tid_str


def create_bookshelf_record(client: Client, name: str, description: str, privacy: str, open_to_contributions: bool = False) -> str:
    """Creates a bookshelf record on the user's repo and returns its AT-URI.
    
    Args:
        client: Authenticated AT Protocol client
        name: Name of the bookshelf
        description: Description of the bookshelf
        privacy: Privacy setting ('public', 'link-only', 'private')
        open_to_contributions: Whether anyone can contribute to this shelf
        
    Returns:
        AT Protocol URI of the created record
    """
    record = {
        '$type': 'com.bibliome.bookshelf',
        'name': name,
        'description': description,
        'privacy': privacy,
        'openToContributions': open_to_contributions,
        'createdAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.bookshelf',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri


def add_book_record(client: Client, bookshelf_uri: str, title: str, author: str, isbn: str) -> str:
    """Creates a book record on the user's repo and returns its AT-URI.
    
    Args:
        client: Authenticated AT Protocol client
        bookshelf_uri: AT Protocol URI of the bookshelf this book belongs to
        title: Book title
        author: Book author
        isbn: Book ISBN
        
    Returns:
        AT Protocol URI of the created record
    """
    record = {
        '$type': 'com.bibliome.book',
        'title': title,
        'author': author,
        'isbn': isbn,
        'bookshelfRef': bookshelf_uri,
        'addedAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.book',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri


def update_bookshelf_record(client: Client, atproto_uri: str, name: str = None, description: str = None, privacy: str = None, open_to_contributions: bool = None) -> str:
    """Update a bookshelf record on AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the bookshelf record to update
        name: New name for the bookshelf (optional)
        description: New description for the bookshelf (optional)
        privacy: New privacy setting for the bookshelf (optional)
        open_to_contributions: New open to contributions setting (optional)

    Returns:
        Updated AT-URI of the record, empty string if failed
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return ""

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return ""

        repo, collection, rkey = parts

        # Get the existing record first to preserve other fields
        existing_record = client.com.atproto.repo.get_record(
            at_models.ComAtprotoRepoGetRecord.Params(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        # Update the record with new values and editedAt timestamp
        updated_record = dict(existing_record.value)
        
        # Only update fields that were provided
        if name is not None:
            updated_record['name'] = name
        if description is not None:
            updated_record['description'] = description
        if privacy is not None:
            updated_record['privacy'] = privacy
        if open_to_contributions is not None:
            updated_record['openToContributions'] = open_to_contributions
            
        updated_record['editedAt'] = client.get_current_time_iso()

        response = client.com.atproto.repo.put_record(
            at_models.ComAtprotoRepoPutRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey,
                record=updated_record
            )
        )
        
        logger.info(f"Successfully updated bookshelf record: {atproto_uri}")
        return response.uri

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Bookshelf record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error updating bookshelf {atproto_uri}: {e}")
        return ""
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to update bookshelf record {atproto_uri}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error updating bookshelf record {atproto_uri}: {e}")
        return ""


def delete_bookshelf_record(client: Client, atproto_uri: str) -> bool:
    """Delete a bookshelf record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the bookshelf record to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Call the delete_record method
        logger.info(f"Deleting bookshelf record: {atproto_uri}")
        client.com.atproto.repo.delete_record(
            at_models.ComAtprotoRepoDeleteRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        logger.info(f"Successfully deleted bookshelf record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Bookshelf record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting bookshelf {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete bookshelf record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting bookshelf record {atproto_uri}: {e}")
        return False


def delete_book_record(client: Client, atproto_uri: str) -> bool:
    """Delete a book record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the book record to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Call the delete_record method
        logger.info(f"Deleting book record: {atproto_uri}")
        client.com.atproto.repo.delete_record(
            at_models.ComAtprotoRepoDeleteRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        logger.info(f"Successfully deleted book record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Book record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting book {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete book record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting book record {atproto_uri}: {e}")
        return False


def create_comment_record(client: Client, book_uri: str, bookshelf_uri: str, content: str) -> str:
    """Creates a comment record on the user's repo and returns its AT-URI.
    
    Args:
        client: Authenticated AT Protocol client
        book_uri: AT Protocol URI of the book being commented on
        bookshelf_uri: AT Protocol URI of the bookshelf for context
        content: Comment content text
        
    Returns:
        AT Protocol URI of the created record
    """
    record = {
        '$type': 'com.bibliome.comment',
        'content': content,
        'bookRef': book_uri,
        'bookshelfRef': bookshelf_uri,
        'createdAt': client.get_current_time_iso()
    }
    response = client.com.atproto.repo.put_record(
        at_models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection='com.bibliome.comment',
            rkey=generate_tid(),
            record=record
        )
    )
    return response.uri


def update_comment_record(client: Client, comment_uri: str, content: str) -> str:
    """Updates a comment record on AT Protocol and returns its AT-URI.
    
    Args:
        client: Authenticated AT Protocol client
        comment_uri: AT Protocol URI of the comment to update
        content: New comment content
        
    Returns:
        Updated AT-URI of the record, empty string if failed
    """
    try:
        # Parse the URI into components
        if not comment_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {comment_uri}")
            return ""

        parts = comment_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {comment_uri}")
            return ""

        repo, collection, rkey = parts

        # Get the existing record first to preserve other fields
        existing_record = client.com.atproto.repo.get_record(
            at_models.ComAtprotoRepoGetRecord.Params(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        # Update the record with new content and editedAt timestamp
        updated_record = existing_record.value
        updated_record['content'] = content
        updated_record['editedAt'] = client.get_current_time_iso()

        response = client.com.atproto.repo.put_record(
            at_models.ComAtprotoRepoPutRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey,
                record=updated_record
            )
        )
        return response.uri

    except Exception as e:
        logger.error(f"Error updating comment record {comment_uri}: {e}")
        return ""


def delete_comment_record(client: Client, atproto_uri: str) -> bool:
    """Delete a comment record from AT Protocol.

    Args:
        client: Authenticated AT Protocol client
        atproto_uri: AT Protocol URI of the comment record to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Parse the URI into components
        if not atproto_uri.startswith('at://'):
            logger.warning(f"Invalid AT URI format: {atproto_uri}")
            return False

        parts = atproto_uri[5:].split('/')
        if len(parts) != 3:
            logger.warning(f"Invalid AT URI structure: {atproto_uri}")
            return False

        repo, collection, rkey = parts

        # Call the delete_record method
        logger.info(f"Deleting comment record: {atproto_uri}")
        client.com.atproto.repo.delete_record(
            at_models.ComAtprotoRepoDeleteRecord.Data(
                repo=repo,
                collection=collection,
                rkey=rkey
            )
        )

        logger.info(f"Successfully deleted comment record: {atproto_uri}")
        return True

    except BadRequestError as e:
        if "RecordNotFound" in str(e):
            logger.warning(f"Comment record not found: {atproto_uri}")
        else:
            logger.error(f"Bad request error deleting comment {atproto_uri}: {e}")
        return False
    except UnauthorizedError as e:
        logger.error(f"Unauthorized to delete comment record {atproto_uri}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error deleting comment record {atproto_uri}: {e}")
        return False
