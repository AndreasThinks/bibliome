#!/usr/bin/env python3
"""
Utility script to check database sync logs.
Run from project root: python scripts/check_db.py
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import setup_database


def check_sync_logs():
    """Connects to the database and prints the 10 most recent sync logs."""
    print("Connecting to database to check sync logs...")
    try:
        db_tables = setup_database()
        sync_logs = db_tables['sync_logs'](order_by='timestamp DESC', limit=10)
        
        if not sync_logs:
            print("The 'sync_log' table is empty.")
            return

        print("\n--- Recent Sync Logs ---")
        for log in sync_logs:
            print(
                f"ID: {log.id}, "
                f"Type: {log.sync_type}, "
                f"Target: {log.target_id}, "
                f"Action: {log.action}, "
                f"Timestamp: {log.timestamp}"
            )
        print("------------------------\n")

    except Exception as e:
        print(f"An error occurred while checking the database: {e}")


if __name__ == "__main__":
    check_sync_logs()
