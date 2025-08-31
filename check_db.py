import asyncio
from models import get_database

def check_sync_logs():
    """Connects to the database and prints the 10 most recent sync logs."""
    print("Connecting to database to check sync logs...")
    try:
        db_tables = get_database()
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
