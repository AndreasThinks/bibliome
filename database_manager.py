import asyncio
from models import setup_database

class DatabaseManager:
    def __init__(self):
        self._db = None
        self._lock = asyncio.Lock()
    
    async def get_connection(self):
        async with self._lock:
            if self._db is None:
                self._db = setup_database()
            return self._db

db_manager = DatabaseManager()
