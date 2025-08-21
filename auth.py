"""Bluesky/AT-Proto authentication for BookdIt."""
import requests
from atproto import models
from atproto import Client as AtprotoClient
from fasthtml.common import *
from fastcore.xtras import flexicache, time_policy
from typing import Optional, Dict, Any

from uvicorn.protocols.http.flow_control import service_unavailable

from components import Alert, NavBar
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
        
        return (
            Title("Login - Bibliome"),
            Favicon(light_icon='static/bibliome.ico', dark_icon='static/bibliome.ico'),
            NavBar(),
            Div(
                Div(
                    # Logo and branding
                    Div(
                        Img(src="/static/bibliome_transparent_no_text.png", alt="Bibliome", cls="login-logo"),
                        H1("Welcome Back", cls="login-title"),
                        P("Sign in with your Bluesky account", cls="login-subtitle"),
                        cls="login-header"
                    ),
                    
                    # Error message if present
                    Alert(error_msg, "error") if error_msg else None,
                    
                    # Login form with proper autocomplete
                    Form(
                        Fieldset(
                            Label("Bluesky Handle", Input(
                                name="handle",
                                id="username",
                                type="text",
                                placeholder="your-handle.bsky.social",
                                autocomplete="username",
                                required=True,
                                cls="login-input"
                            )),
                            Label("App Password", Input(
                                name="password",
                                id="password",
                                type="password",
                                placeholder="Your Bluesky app password",
                                autocomplete="current-password",
                                required=True,
                                cls="login-input"
                            )),
                            cls="login-fieldset"
                        ),
                        Button("Sign In", type="submit", cls="login-btn-primary"),
                        action="/auth/login",
                        method="post",
                        autocomplete="on",
                        cls="login-form"
                    ),
                    
                    # Help text and links
                    Div(
                        P(
                            "Need an app password? ",
                            A("Create one in your Bluesky settings", 
                              href="https://bsky.app/settings/app-passwords", 
                              target="_blank", 
                              rel="noopener noreferrer",
                              cls="login-help-link")
                        ),
                        P(
                            "Don't have a Bluesky account? ",
                            A("Sign up here", href="https://bsky.app", target="_blank", rel="noopener noreferrer", cls="login-help-link")
                        ),
                        cls="login-help"
                    ),
                    
                    cls="login-card"
                ),
                cls="login-container"
            )
        )
    
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
            if not (service := self.get_service_from_handle(handle)).endswith(".bsky.network"):
                self.client = AtprotoClient(service)
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
                'session_string': self.client.export_session_string(),
                'access_jwt': getattr(self.client.me, 'access_jwt', ''),
                'refresh_jwt': getattr(self.client.me, 'refresh_jwt', '')
            }
            logger.info(f"Authentication successful for user: {user_data['handle']}")
            return user_data
        except Exception as e:
            # Import the specific exception type
            from atproto_client.exceptions import UnauthorizedError
            
            if isinstance(e, UnauthorizedError):
                # This is expected for wrong credentials - log as warning, not error
                logger.warning(f"Authentication failed for handle {handle}: Invalid credentials")
                return None
            else:
                # Unexpected error (network, service down, etc.) - log as error with traceback
                logger.error(f"Authentication system error for handle {handle}: {e}", exc_info=True)
                return None

    def get_service_from_handle(self, handle: str) -> str:
        did = self.client.com.atproto.identity.resolve_handle({"handle": handle})
        logger.debug(f"Resolved identity: {did.did}")
        did_doc = requests.get(f"https://plc.directory/{did.did}").json()
        service = did_doc['service'][0]['serviceEndpoint']
        logger.debug(f"Resolved service endpoint: {service}")
        return service

    def get_client_from_session(self, session_data: dict) -> AtprotoClient:
        """Restore a client instance from a session string."""
        client = AtprotoClient()
        client.login(session_string=session_data['session_string'])
        return client
    
    @flexicache(time_policy(3600))  # Cache for 1 hour
    def _get_all_following_paginated(self, user_did: str, session_string: str) -> list[str]:
        """Get all DIDs that a user follows with pagination and caching."""
        try:
            # Create a fresh client for this operation
            client = AtprotoClient()
            client.login(session_string=session_string)
            
            if not client.me:
                logger.warning("Could not authenticate client for following list.")
                return []

            all_following = []
            cursor = None
            max_pages = 50  # Safety limit: 50 * 100 = 5000 max followers
            page_count = 0
            
            logger.info(f"Starting paginated fetch of followers for user {user_did}")
            
            while page_count < max_pages:
                params = {
                    'actor': user_did,
                    'limit': 100
                }
                if cursor:
                    params['cursor'] = cursor
                
                try:
                    response = client.app.bsky.graph.get_follows(params)
                    
                    if response and response.follows:
                        page_followers = [follow.did for follow in response.follows]
                        all_following.extend(page_followers)
                        page_count += 1
                        
                        logger.debug(f"Page {page_count}: Retrieved {len(page_followers)} followers (total: {len(all_following)})")
                        
                        # Check if there are more pages
                        cursor = getattr(response, 'cursor', None)
                        if not cursor:
                            logger.info(f"Reached end of followers list at page {page_count}")
                            break
                    else:
                        logger.info(f"No more followers found at page {page_count}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Error fetching page {page_count + 1}: {e}")
                    break
            
            logger.info(f"Retrieved {len(all_following)} total following DIDs across {page_count} pages")
            return all_following
            
        except Exception as e:
            logger.error(f"Error getting paginated following list for {user_did}: {e}", exc_info=True)
            return []

    def get_following_list(self, auth_data: Dict[str, Any], limit: int = None) -> list[str]:
        """Get list of DIDs that a user follows (with caching and pagination)."""
        try:
            user_did = auth_data['did']
            session_string = auth_data['session_string']
            handle = auth_data.get('handle', 'unknown')
            
            # Use the cached paginated method
            following_dids = self._get_all_following_paginated(user_did, session_string)
            
            logger.info(f"Retrieved {len(following_dids)} following DIDs for {handle}")
            return following_dids
            
        except Exception as e:
            logger.error(f"Error getting following list for {auth_data.get('handle', 'unknown')}: {e}", exc_info=True)
            return []

    def get_profiles_batch(self, dids: list[str], auth_data: dict) -> dict[str, dict]:
        """Get profile info for multiple DIDs."""
        try:
            if not dids:
                return {}

            client = self.get_client_from_session(auth_data)
            if not client:
                logger.warning("Could not get authenticated client for profiles batch.")
                return {}

            profiles = {}
            batch_size = 25
            for i in range(0, len(dids), batch_size):
                batch_dids = dids[i:i + batch_size]
                try:
                    response = client.app.bsky.actor.get_profiles({'actors': batch_dids})
                    if response and response.profiles:
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
            logger.error(f"Error getting profiles batch: {e}", exc_info=True)
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
