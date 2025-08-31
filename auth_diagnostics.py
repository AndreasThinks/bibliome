"""Diagnostic utilities for Bibliome authentication."""
import logging
import traceback
from functools import wraps
from time import perf_counter

logger = logging.getLogger(__name__)

def log_auth_flow(func):
    """Decorator to log the authentication flow with detailed diagnostics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        class_instance = args[0]
        handle = kwargs.get('handle') or (args[1] if len(args) > 1 else "unknown")
        
        logger.info(f"[AUTH_FLOW] Starting authentication for handle: {handle}")
        start_time = perf_counter()
        
        try:
            result = await func(*args, **kwargs)
            end_time = perf_counter()
            duration = end_time - start_time
            
            if result:
                logger.info(f"[AUTH_FLOW] SUCCESS: Authentication for '{handle}' completed in {duration:.4f} seconds.")
            else:
                logger.warning(f"[AUTH_FLOW] FAILED: Authentication for '{handle}' failed. Duration: {duration:.4f} seconds.")
            
            return result
            
        except Exception as e:
            end_time = perf_counter()
            duration = end_time - start_time
            
            error_type = type(e).__name__
            error_msg = str(e)
            
            logger.error(
                f"[AUTH_FLOW] CRITICAL_ERROR: Authentication for '{handle}' raised an unhandled exception "
                f"after {duration:.4f} seconds. Error Type: {error_type}, Message: {error_msg}",
                exc_info=True
            )
            
            # Optionally, re-raise or return a specific error object
            raise
            
    return wrapper

def sanitize_for_logging(data, max_length=100):
    """Sanitize data for logging, truncating long strings."""
    if isinstance(data, str):
        return data[:max_length] + '...' if len(data) > max_length else data
    if isinstance(data, dict):
        return {k: sanitize_for_logging(v, max_length) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_logging(i, max_length) for i in data]
    return data

def format_error_for_user(error: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    from atproto_client.exceptions import UnauthorizedError, NetworkError
    
    if isinstance(error, UnauthorizedError):
        return "Invalid handle or app password. Please double-check your credentials and ensure you're using a valid app password."
    elif isinstance(error, NetworkError):
        return "Could not connect to the Bluesky network. Please check your internet connection and try again."
    elif "Cannot resolve handle" in str(error):
        return f"The handle '{sanitize_for_logging(str(error).split(':')[-1].strip())}' could not be found. Please check the spelling."
    else:
        # Generic error for unexpected issues
        error_id = traceback.format_id(error)
        logger.error(f"Unhandled authentication error (ID: {error_id}): {error}", exc_info=True)
        return f"An unexpected error occurred. If this persists, please contact support with error ID: {error_id}"
