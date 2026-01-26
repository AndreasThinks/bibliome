"""
Rate limiter using the token bucket algorithm with exponential backoff support.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.infrastructure import RateLimiter, ExponentialBackoffRateLimiter` instead.
"""

# Re-export from the new location
from bibliome.infrastructure.rate_limiter import (
    RateLimiter,
    ExponentialBackoffRateLimiter,
)

__all__ = ['RateLimiter', 'ExponentialBackoffRateLimiter']
