"""Bluesky/AT-Proto authentication for BookdIt."""

from atproto import models
from atproto import Client as AtprotoClient
from fasthtml.common import *
from typing import Optional, Dict, Any
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class BlueskyAuth:
    """Handle Bluesky authentication and session management."""
    
    def __init__(self):
        self.client = AtprotoClient()
    
    def create_login_form(self, error_msg: str = None):
        """Create the login form with optional error message."""
        
        content = []
        if error_msg:
            content.append(Alert(error_msg, "error"))
        
        content.extend([
            Form(
                action="/auth/login",
                method="post"
            )(
                Fieldset(
                    Label("Bluesky Handle", Input(
                        name="handle",
                        type="text",
                        placeholder="your-handle.bsky.social",
                        required=True
                    )),
                    Label("App Password", Input(
                        name="password",
                        type="password",
                        placeholder="Your Bluesky app password",
                        required=True
                    )),
                    Small(
                        "You'll need to create an app password in your Bluesky settings. ",
                        A("Get your app password here", 
                          href="https://bsky.app/settings/app-passwords", 
                          target="_blank", 
                          rel="noopener noreferrer",
                          style="color: var(--brand-amber); text-decoration: underline;")
                    )
                ),
                Button("Login", type="submit", cls="primary")
            ),
            P("Don't have a Bluesky account? ", 
              A("Sign up here", href="https://bsky.app", target="_blank"))
        ])
        
        return Titled("Login with Bluesky", *content)
    
    async def authenticate_user(self, handle: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Bluesky and return user info."""
        try:
            logger.info(f"Starting authentication for handle: {handle}")
            
            # Ensure handle has proper format
            if not handle.endswith('.bsky.social') and '.' not in handle:
                handle = f"{handle}.bsky.social"
                logger.debug(f"Formatted handle: {handle}")
            
            # Login to Bluesky - this returns a profile object
            logger.info("Attempting Bluesky login...")
            profile = self.client.login(handle, password)
            logger.debug(f"Login successful, profile: {profile is not None}")
            
            # The client.me contains the session info after login
            if not self.client.me:
                logger.error("No client.me after login")
                return None
            
            logger.debug(f"Client.me found: {self.client.me.handle}")
            
            user_data = {
                'did': self.client.me.did,
                'handle': self.client.me.handle,
                'display_name': profile.display_name or self.client.me.handle,
                'avatar_url': profile.avatar or '',
                'access_jwt': getattr(self.client.me, 'access_jwt', ''),
                'refresh_jwt': getattr(self.client.me, 'refresh_jwt', '')
            }
            logger.info(f"Authentication successful for user: {user_data['handle']}")
            return user_data
        except Exception as e:
            logger.error(f"Authentication error for handle {handle}: {e}", exc_info=True)
            return None
    
    async def get_following_list(self, auth_data: Dict[str, Any], limit: int = 100) -> list[str]:
        """Get list of DIDs that a user follows."""
        try:
            # Create a new client instance for this request
            client = AtprotoClient()
            
            # Restore session using stored tokens
            if auth_data.get('access_jwt') and auth_data.get('refresh_jwt'):
                # Try to restore session with tokens
                try:
                    # This is a simplified approach - in production you'd want proper token refresh
                    client.login(auth_data['handle'], "")  # This might not work without password
                except:
                    logger.warning("Could not restore AT Proto session for following list")
                    return []
            
            # Get following list
            response = client.get_follows(auth_data['did'], limit=limit)
            following_dids = [follow.did for follow in response.follows]
            
            logger.info(f"Retrieved {len(following_dids)} following DIDs for {auth_data['handle']}")
            return following_dids
            
        except Exception as e:
            logger.error(f"Error getting following list for {auth_data.get('handle', 'unknown')}: {e}")
            return []
    
    async def get_profiles_batch(self, dids: list[str]) -> dict[str, dict]:
        """Get profile info for multiple DIDs."""
        try:
            if not dids:
                return {}
            
            # Create a new client for this request
            client = AtprotoClient()
            
            profiles = {}
            # Process in batches to avoid API limits
            batch_size = 25
            for i in range(0, len(dids), batch_size):
                batch_dids = dids[i:i + batch_size]
                try:
                    response = client.get_profiles(batch_dids)
                    for profile in response.profiles:
                        profiles[profile.did] = {
                            'did': profile.did,
                            'handle': profile.handle,
                            'display_name': profile.display_name or profile.handle,
                            'avatar_url': profile.avatar or ''
                        }
                except Exception as e:
                    logger.warning(f"Error fetching profile batch: {e}")
                    continue
            
            logger.info(f"Retrieved {len(profiles)} profiles from {len(dids)} DIDs")
            return profiles
            
        except Exception as e:
            logger.error(f"Error getting profiles batch: {e}")
            return {}
    
    def restore_session(self, auth_data: Dict[str, Any]) -> bool:
        """Restore a session from stored auth data."""
        try:
            # For now, we'll just validate that the auth data looks correct
            # In a production app, you might want to validate the JWT tokens
            required_fields = ['did', 'handle']
            if all(field in auth_data for field in required_fields):
                logger.debug(f"Session restored for user: {auth_data.get('handle')}")
                return True
            logger.warning("Session restore failed: missing required fields")
            return False
        except Exception as e:
            logger.error(f"Session restore error: {e}", exc_info=True)
            return False

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
        from datetime import datetime, timedelta
        if datetime.now() - user.last_login > timedelta(hours=1):
            db_tables['users'].update({'last_login': datetime.now()}, auth_data['did'])
    except:
        pass  # User might not exist in DB yet
    
    return None

def require_auth(f):
    """Decorator to require authentication for a route."""
    def wrapper(*args, **kwargs):
        # This assumes auth is passed as a parameter
        auth = kwargs.get('auth')
        if not auth:
            return RedirectResponse('/auth/login', status_code=303)
        return f(*args, **kwargs)
    return wrapper

def get_current_user_did(auth) -> Optional[str]:
    """Extract user DID from auth data."""
    return auth.get('did') if auth else None
