"""
Bibliome Authentication Package.

This package provides authentication and authorization functionality:
- BlueskyAuth: Bluesky/AT-Proto authentication
- OAuth: AT Protocol OAuth 2.0 with PKCE, DPoP, and PAR
- Middleware: Authentication beforeware and decorators
- Diagnostics: Logging and error formatting utilities
- Retry: Network error retry logic
"""

# Bluesky authentication
from .bluesky import BlueskyAuth

# Middleware and decorators
from .middleware import (
    auth_beforeware,
    require_auth,
    require_admin,
    get_current_user_did,
    is_admin,
)

# Retry decorator
from .retry import retry_on_network_error

# Diagnostics utilities
from .diagnostics import (
    log_auth_flow,
    sanitize_for_logging,
    format_error_for_user,
)

# OAuth - may not be available if dependencies not installed
from .oauth import (
    OAuthClient,
    ATProtoOAuthError,
    generate_state,
    get_client_metadata,
    OAUTH_AVAILABLE,
)

__all__ = [
    # Bluesky auth
    'BlueskyAuth',
    
    # Middleware and decorators
    'auth_beforeware',
    'require_auth',
    'require_admin',
    'get_current_user_did',
    'is_admin',
    
    # Retry
    'retry_on_network_error',
    
    # Diagnostics
    'log_auth_flow',
    'sanitize_for_logging',
    'format_error_for_user',
    
    # OAuth
    'OAuthClient',
    'ATProtoOAuthError',
    'generate_state',
    'get_client_metadata',
    'OAUTH_AVAILABLE',
]
