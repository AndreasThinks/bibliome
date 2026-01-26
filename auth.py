"""
Bluesky/AT-Proto authentication for Bibliome.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.auth import ...` instead.
"""

# Re-export everything from the new location
from bibliome.auth import (
    BlueskyAuth,
    auth_beforeware,
    require_auth,
    require_admin,
    get_current_user_did,
    is_admin,
)

# Also re-export internal imports for any code that depends on them
from bibliome.auth.diagnostics import log_auth_flow
from bibliome.auth.retry import retry_on_network_error

__all__ = [
    'BlueskyAuth',
    'auth_beforeware',
    'require_auth',
    'require_admin',
    'get_current_user_did',
    'is_admin',
    'log_auth_flow',
    'retry_on_network_error',
]
