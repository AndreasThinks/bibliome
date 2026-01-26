"""Database setup and connection management for Bibliome.

This module handles database initialization, migrations, and provides
the setup_database function for creating table connections.
"""

import os
import logging
from typing import Dict, Any

from fastlite import database

from .entities import (
    User, Bookshelf, Book, Permission, BookshelfInvite,
    Comment, Activity, SyncLog, ProcessStatus, ProcessLog, ProcessMetric
)

logger = logging.getLogger(__name__)


def validate_primary_key_setup(db, table_name: str, expected_pk_column: str) -> bool:
    """Validate that a table has the correct primary key setup.
    
    Args:
        db: Database connection object
        table_name: Name of the table to validate
        expected_pk_column: Expected primary key column name
        
    Returns:
        True if validation passes
        
    Raises:
        RuntimeError: If validation fails
    """
    try:
        # Check table info
        table_info = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        
        # Find primary key columns
        pk_columns = [col for col in table_info if col[5] == 1]  # is_pk == 1
        
        if len(pk_columns) != 1:
            raise RuntimeError(f"Table {table_name} should have exactly 1 primary key, found {len(pk_columns)}")
        
        if pk_columns[0][1] != expected_pk_column:
            raise RuntimeError(f"Table {table_name} primary key should be {expected_pk_column}, found {pk_columns[0][1]}")
        
        if 'INTEGER' not in pk_columns[0][2].upper():
            raise RuntimeError(f"Table {table_name} primary key should be INTEGER, found {pk_columns[0][2]}")
        
        print(f"✓ Table {table_name} primary key validation passed")
        return True
        
    except Exception as e:
        print(f"✗ Table {table_name} primary key validation failed: {e}")
        raise


def setup_database(db_path: str = 'data/bookdit.db', migrations_dir: str = 'migrations', memory: bool = False) -> Dict[str, Any]:
    """Initialize the database with fastmigrate and all tables.
    
    Args:
        db_path: Path to the SQLite database file
        migrations_dir: Path to the migrations directory
        memory: If True, use an in-memory database (for testing)
        
    Returns:
        Dictionary containing database connection and table objects
    """
    if memory:
        db_path = ':memory:'
        print("Setting up in-memory database for testing.")
        db = database(db_path)
    else:
        from fastmigrate.core import create_db, run_migrations, get_db_version
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize fastmigrate managed database
        create_db(db_path)
        
        # Apply any pending migrations from migrations_dir
        success = run_migrations(db_path, migrations_dir)
        if not success:
            raise RuntimeError("Database migration failed! Application cannot continue.")
        
        # Get current database version for logging
        version = get_db_version(db_path)
        print(f"Database initialized at version {version}")
        
        # Create FastLite database connection
        db = database(db_path)
    
    # Configure SQLite for better concurrency
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL") 
    db.execute("PRAGMA wal_autocheckpoint=1000")
    db.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    db.execute("PRAGMA cache_size=10000")
    db.execute("PRAGMA temp_store=memory")
    db.execute("PRAGMA mmap_size=268435456")
    
    # Create table objects for FastLite operations with explicit primary keys
    # These will connect to existing tables created by migrations
    users = db.create(User, pk='did', transform=True, if_not_exists=True)
    bookshelves = db.create(Bookshelf, pk='id', transform=True, if_not_exists=True)
    books = db.create(Book, pk='id', transform=True, if_not_exists=True)
    permissions = db.create(Permission, pk='id', transform=True, if_not_exists=True)
    bookshelf_invites = db.create(BookshelfInvite, pk='id', transform=True, if_not_exists=True)
    comments = db.create(Comment, pk='id', transform=True, if_not_exists=True)
    activities = db.create(Activity, pk='id', transform=True, if_not_exists=True)
    sync_logs = db.create(SyncLog, pk='id', transform=True, if_not_exists=True)
    
    # Connect to process monitoring tables created by migrations with explicit primary keys
    # Use FastLite's object transformation but specify correct table names and primary keys
    try:
        # For process_status, we need to connect to the existing table
        process_status = db.t.process_status
        # Wrap it with the ProcessStatus class for object transformation
        process_status = db.create(ProcessStatus, pk='process_name', transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_status = db["process_status"]
    
    try:
        # For process_logs, connect to existing table
        process_logs = db.t.process_logs
        # Wrap it with the ProcessLog class for object transformation
        process_logs = db.create(ProcessLog, pk='id', transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_logs = db["process_logs"]
    
    try:
        # For process_metrics, connect to existing table
        process_metrics = db.t.process_metrics
        # Wrap it with the ProcessMetric class for object transformation
        process_metrics = db.create(ProcessMetric, pk='id', transform=True, if_not_exists=True)
    except Exception:
        # Fallback: create with correct table name
        process_metrics = db["process_metrics"]
    
    # Validate primary keys for critical process monitoring tables
    try:
        validate_primary_key_setup(db, 'process_metrics', 'id')
        validate_primary_key_setup(db, 'process_logs', 'id')
        print("✓ Process monitoring table primary key validation completed")
    except Exception as e:
        print(f"⚠ Warning: Process monitoring table validation failed: {e}")
        # Don't fail the entire setup, just log the warning
    
    return {
        'db': db,
        'users': users,
        'bookshelves': bookshelves,
        'books': books,
        'permissions': permissions,
        'bookshelf_invites': bookshelf_invites,
        'comments': comments,
        'activities': activities,
        'sync_logs': sync_logs,
        'process_status': process_status,
        'process_logs': process_logs,
        'process_metrics': process_metrics
    }


def get_database():
    """This function is deprecated. Use database_manager.db_manager instead."""
    raise DeprecationWarning("get_database() is deprecated. Use database_manager.db_manager instead.")
