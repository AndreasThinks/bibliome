"""
Circuit breaker implementation for protecting services from cascading failures.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.infrastructure import CircuitBreaker` instead.
"""

# Re-export from the new location
from bibliome.infrastructure.circuit_breaker import CircuitBreaker

__all__ = ['CircuitBreaker']
