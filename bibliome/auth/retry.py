"""Retry logic for Bibliome authentication."""
import asyncio
import logging
from functools import wraps
from atproto_client.exceptions import NetworkError

logger = logging.getLogger(__name__)


def retry_on_network_error(max_attempts: int = 3, backoff_seconds: int = 1):
    """
    A decorator to retry a function upon encountering a NetworkError.
    Implements exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_seconds: Initial backoff duration in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except NetworkError as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(f"Final attempt failed for {func.__name__} after {max_attempts} retries. Error: {e}")
                        raise
                    
                    sleep_duration = backoff_seconds * (2 ** (attempts - 1))
                    logger.warning(
                        f"NetworkError in {func.__name__}, attempt {attempts}/{max_attempts}. "
                        f"Retrying in {sleep_duration} seconds..."
                    )
                    await asyncio.sleep(sleep_duration)
        return wrapper
    return decorator
