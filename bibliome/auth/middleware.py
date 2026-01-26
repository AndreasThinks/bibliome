"""Authentication middleware and decorators for Bibliome."""
import os
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from fasthtml.common import RedirectResponse

logger = logging.getLogger(__name__)


def auth_beforeware(req, sess, db_tables):
    """Beforeware to handle authentication state."""
    # Skip auth for static files and login pages
    skip_paths = ['/static/', '/auth/login', '/favicon.ico', '/', '/shelf/']
    
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
    
    # Update user's last login time periodically
    try:
        user = db_tables['users'][auth_data['did']]
        # Update last login if it's been more than an hour
        now_utc = datetime.now(timezone.utc)
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
