"""
External API clients for book metadata.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.clients import BookAPIClient` instead.
"""

# Re-export from the new location
from bibliome.clients.books import BookAPIClient

__all__ = ['BookAPIClient']
