"""
Bibliome Infrastructure Package.

This package provides infrastructure utilities:
- CircuitBreaker: Protects services from cascading failures
- RateLimiter: Token bucket algorithm with async support
- ExponentialBackoffRateLimiter: Rate limiting with automatic retry and backoff

Note: db_write_queue is imported from the root module for backward compatibility.
"""

# Circuit breaker
from .circuit_breaker import CircuitBreaker

# Rate limiters
from .rate_limiter import RateLimiter, ExponentialBackoffRateLimiter

__all__ = [
    'CircuitBreaker',
    'RateLimiter',
    'ExponentialBackoffRateLimiter',
]
