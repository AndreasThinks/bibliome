import asyncio
import logging
import os
from models import setup_database

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages database connections with retry logic and exponential backoff.
    
    This class handles database connection initialization for async services.
    The async lock ensures only one connection is created within a single process,
    and retry logic handles cases where multiple processes compete for database
    access during startup.
    """
    
    def __init__(self):
        self._db = None
        self._lock = asyncio.Lock()
        # Configuration from environment
        self._max_retries = int(os.getenv('DB_CONNECTION_MAX_RETRIES', '5'))
        self._initial_delay = float(os.getenv('DB_CONNECTION_INITIAL_DELAY', '1.0'))
    
    async def get_connection(self, max_retries=None, initial_delay=None):
        """
        Get or create a database connection with retry logic.
        
        Uses exponential backoff when database is locked (e.g., during
        concurrent startup of multiple services).
        
        Args:
            max_retries: Maximum number of retry attempts (default from env or 5)
            initial_delay: Initial delay in seconds before first retry (default from env or 1.0)
            
        Returns:
            Database tables dictionary from setup_database()
            
        Raises:
            Exception: If connection fails after all retries
        """
        max_retries = max_retries or self._max_retries
        initial_delay = initial_delay or self._initial_delay
        
        async with self._lock:
            if self._db is not None:
                return self._db
            
            delay = initial_delay
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
                    self._db = setup_database()
                    logger.info("Database connection established successfully")
                    return self._db
                    
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check if this is a retryable error (database locked/busy)
                    is_lock_error = (
                        'database is locked' in error_msg or 
                        'busy' in error_msg or
                        'busyerror' in error_msg
                    )
                    
                    if is_lock_error and attempt < max_retries - 1:
                        logger.warning(
                            f"Database locked during setup (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 30.0)  # Exponential backoff, max 30s
                    else:
                        # Non-retryable error or exhausted retries
                        if is_lock_error:
                            logger.error(
                                f"Database connection failed after {max_retries} attempts "
                                f"due to persistent locking"
                            )
                        else:
                            logger.error(f"Database connection failed: {e}")
                        raise
            
            # This shouldn't be reached, but just in case
            if last_error:
                raise last_error
            raise RuntimeError("Database connection failed for unknown reason")

# Global singleton instance
db_manager = DatabaseManager()
