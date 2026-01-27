"""Authentication middleware and decorators for Bibliome."""
import os
import logging
from typing import Optional, Any
from datetime import datetime, timedelta, timezone

from fasthtml.common import RedirectResponse

logger = logging.getLogger(__name__)

# Token refresh buffer - refresh tokens 5 minutes before expiry
TOKEN_REFRESH_BUFFER_SECONDS = 300


def refresh_oauth_tokens(user, db_tables, oauth_client, sess):
    """
    Refresh OAuth tokens if they're about to expire.

    Returns True if tokens were refreshed successfully, False otherwise.
    """
    try:
        # Get current token data from user record
        refresh_token = getattr(user, 'oauth_refresh_token', None)
        dpop_private_key = getattr(user, 'oauth_dpop_private_jwk', None)
        dpop_nonce = getattr(user, 'oauth_dpop_nonce_authserver', None)
        pds_url = getattr(user, 'oauth_pds_url', None)

        if not all([refresh_token, dpop_private_key, pds_url]):
            logger.warning(f"Missing OAuth data for token refresh: user={user.did}")
            return False

        # Get authorization server metadata
        auth_metadata = oauth_client.get_authorization_server_metadata(pds_url)

        # Refresh the tokens
        token_response = oauth_client.refresh_access_token(
            auth_metadata=auth_metadata,
            refresh_token=refresh_token,
            dpop_private_key=dpop_private_key,
            dpop_nonce=dpop_nonce
        )

        # Calculate new expiration time
        expires_in = token_response.get('expires_in', 3600)
        new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Update database with new tokens
        update_data = {
            'oauth_access_token': token_response.get('access_token'),
            'oauth_token_expires_at': new_expires_at
        }

        # Update refresh token if a new one was provided
        if token_response.get('refresh_token'):
            update_data['oauth_refresh_token'] = token_response['refresh_token']

        # Update DPoP nonce if provided
        if token_response.get('dpop_nonce'):
            update_data['oauth_dpop_nonce_authserver'] = token_response['dpop_nonce']

        db_tables['users'].update(update_data, user.did)

        # Update session with new access token
        auth_data = sess.get('auth', {})
        auth_data['oauth_access_token'] = token_response.get('access_token')
        sess['auth'] = auth_data

        logger.info(f"Successfully refreshed OAuth tokens for user: {user.handle}")
        return True

    except Exception as e:
        logger.error(f"Failed to refresh OAuth tokens for user {user.did}: {e}", exc_info=True)
        return False


def auth_beforeware(req, sess, db_tables, oauth_client=None):
    """Beforeware to handle authentication state."""
    # Skip auth for static files and login pages
    skip_paths = ['/static/', '/auth/login', '/favicon.ico', '/', '/shelf/', '/auth/oauth']

    if any(req.url.path.startswith(path) for path in skip_paths):
        req.scope['auth'] = sess.get('auth')
        return None

    # Check if user is authenticated
    auth_data = sess.get('auth')
    if not auth_data:
        return RedirectResponse('/auth/login', status_code=303)

    # Validate session is still good (optional - could be expensive)
    # For now, just trust the session data
    req.scope['auth'] = auth_data

    # Check OAuth token expiration and refresh if needed
    try:
        user = db_tables['users'][auth_data['did']]
        now_utc = datetime.now(timezone.utc)

        # Check if this is an OAuth session that needs token refresh
        if auth_data.get('oauth_enabled') and oauth_client:
            token_expires_at = getattr(user, 'oauth_token_expires_at', None)

            if token_expires_at:
                # Handle timezone-aware and naive datetimes
                if token_expires_at.tzinfo is None:
                    token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)

                # Check if token expires within buffer period
                time_until_expiry = (token_expires_at - now_utc).total_seconds()

                if time_until_expiry <= TOKEN_REFRESH_BUFFER_SECONDS:
                    logger.info(f"OAuth token expiring soon for user {user.handle}, refreshing...")
                    if not refresh_oauth_tokens(user, db_tables, oauth_client, sess):
                        # Token refresh failed - force re-authentication
                        logger.warning(f"Token refresh failed for user {user.handle}, requiring re-auth")
                        sess.clear()
                        return RedirectResponse('/auth/login', status_code=303)

        # Update user's last login time periodically
        # Handle both timezone-aware and naive datetimes for backward compatibility
        last_login = user.last_login
        if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=timezone.utc)
        if now_utc - last_login > timedelta(hours=1):
            db_tables['users'].update({'last_login': now_utc}, auth_data['did'])
    except:
        pass  # User might not exist in DB yet

    return None


def require_auth(f):
    """Decorator to require authentication for a route."""
    def wrapper(*args, **kwargs):
        auth = kwargs.get('auth')
        if not auth:
            return RedirectResponse('/auth/login', status_code=303)
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator to require admin privileges for a route."""
    def wrapper(*args, **kwargs):
        auth = kwargs.get('auth')
        if not is_admin(auth):
            return RedirectResponse('/', status_code=303)
        return f(*args, **kwargs)
    return wrapper


def get_current_user_did(auth) -> Optional[str]:
    """Extract user DID from auth data."""
    return auth.get('did') if auth else None


def is_admin(auth) -> bool:
    """Check if the current user is an admin."""
    if not auth:
        return False
    
    admin_usernames = os.getenv('ADMIN_USERNAMES', '').split(',')
    return auth.get('handle') in admin_usernames
