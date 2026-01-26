"""
Retry logic for Bibliome authentication.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.auth import retry_on_network_error` instead.
"""

# Re-export from the new location
from bibliome.auth.retry import retry_on_network_error

__all__ = ['retry_on_network_error']
