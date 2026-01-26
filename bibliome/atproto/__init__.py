"""AT Protocol integration package for Bibliome.

This package handles all AT Protocol operations including record
creation, updates, deletion, and OAuth authentication.
"""

from .records import (
    generate_tid,
    create_bookshelf_record,
    add_book_record,
    update_bookshelf_record,
    delete_bookshelf_record,
    delete_book_record,
    create_comment_record,
    update_comment_record,
    delete_comment_record,
)

__all__ = [
    'generate_tid',
    'create_bookshelf_record',
    'add_book_record',
    'update_bookshelf_record',
    'delete_bookshelf_record',
    'delete_book_record',
    'create_comment_record',
    'update_comment_record',
    'delete_comment_record',
]
