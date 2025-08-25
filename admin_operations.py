"""Admin database operations for Bibliome."""

import os
import sqlite3
from datetime import datetime

def get_database_path() -> str:
    """Gets the path to the application's database file."""
    # This path is based on the setup_database function in models.py
    return 'data/bookdit.db'

def backup_database(db_path: str, backup_dir: str = "backups") -> str:
    """
    Create a backup of the database.
    
    Args:
        db_path: Path to the database file
        backup_dir: Directory to store backups in
        
    Returns:
        Path to the backup file
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
        
    # Create backup directory if it doesn't exist
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{os.path.basename(db_path)}.{timestamp}.bak"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Create backup using SQLite's backup API
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(backup_path)
    source.backup(dest)
    source.close()
    dest.close()
    
    return backup_path

def upload_database(db_path: str, file_content: bytes):
    """
    Upload and replace the current database with the provided file content.
    
    Args:
        db_path: Path to the target database file
        file_content: Binary content of the uploaded database file
        
    Returns:
        True if successful
        
    Raises:
        ValueError: If the file is not a valid SQLite database
        Exception: If the upload fails
    """
    # Create a temporary file for the uploaded content
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = f"{os.path.dirname(db_path)}/upload_temp_{timestamp}.db"
    backup_path = None
    
    try:
        # Save uploaded content to temporary file
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        # Verify it's a valid SQLite database
        try:
            temp_conn = sqlite3.connect(temp_path)
            temp_conn.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'")
            temp_conn.close()
        except sqlite3.Error:
            os.remove(temp_path)
            raise ValueError("Invalid SQLite database file.")
        
        # Create backup of current database
        backup_path = f"{os.path.dirname(db_path)}/backup_{timestamp}.db"
        source = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)
        source.backup(backup_conn)
        source.close()
        backup_conn.close()
        
        try:
            # Replace current database with uploaded one
            dest_conn = sqlite3.connect(db_path)
            source_conn = sqlite3.connect(temp_path)
            source_conn.backup(dest_conn)
            source_conn.close()
            dest_conn.close()
            
            # Clean up temporary files
            os.remove(temp_path)
            os.remove(backup_path)
            
            return True
            
        except Exception as e:
            # Restore from backup if something went wrong
            if os.path.exists(backup_path):
                restore_conn = sqlite3.connect(db_path)
                backup_conn = sqlite3.connect(backup_path)
                backup_conn.backup(restore_conn)
                backup_conn.close()
                restore_conn.close()
                os.remove(backup_path)
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise Exception(f"Failed to upload database: {str(e)}")
            
    except Exception as e:
        # Clean up temporary files
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        raise e
