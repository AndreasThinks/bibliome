"""
Diagnostic utilities for Bibliome authentication.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.auth import ...` instead.
"""

# Re-export from the new location
from bibliome.auth.diagnostics import (
    log_auth_flow,
    sanitize_for_logging,
    format_error_for_user,
)

__all__ = ['log_auth_flow', 'sanitize_for_logging', 'format_error_for_user']
