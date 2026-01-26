"""
atproto OAuth 2.0 Implementation with PKCE, DPoP, and PAR support.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.auth import ...` instead.
"""

# Re-export everything from the new location
from bibliome.auth.oauth import (
    OAuthClient,
    ATProtoOAuthError,
    generate_state,
    get_client_metadata,
    OAUTH_AVAILABLE,
)

__all__ = ['OAuthClient', 'ATProtoOAuthError', 'generate_state', 'get_client_metadata', 'OAUTH_AVAILABLE']
