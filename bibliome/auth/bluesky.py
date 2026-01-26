"""Bluesky/AT-Proto authentication for Bibliome."""
import httpx
import os
import logging
from typing import Optional, Dict, Any

from atproto import Client as AtprotoClient
from fasthtml.common import *
from fastcore.xtras import flexicache, time_policy
from dotenv import load_dotenv

from .diagnostics import log_auth_flow
from .retry import retry_on_network_error

load_dotenv()

logger = logging.getLogger(__name__)


class BlueskyAuth:
    """Handle Bluesky authentication and session management."""
    
    def __init__(self):
        self.client = AtprotoClient()
    
    def create_login_form(self, error_msg: str = None, oauth_enabled: bool = True):
        """Create the login form with optional error message and OAuth option."""
        # Import here to avoid circular imports
        from bibliome.components import Alert, NavBar

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

                    # OAuth login option
                    (Div(
                        H3("OAuth Login", cls="oauth-section-title"),
                        P("Sign in securely with your Bluesky account", cls="oauth-section-subtitle"),
                        Form(
                            Fieldset(
                                Label("Bluesky Handle", Input(
                                    name="handle",
                                    type="text",
                                    placeholder="your-handle.bsky.social",
                                    required=True,
                                    cls="login-input"
                                )),
                                cls="login-fieldset"
                            ),
                            Button("Sign In with Bluesky", type="submit", cls="login-btn-primary"),
                            action="/auth/oauth/start",
                            method="get",
                            cls="login-form"
                        ),
                        cls="oauth-section"
                    ) if oauth_enabled else None),

                    # Divider
                    (Div(
                        Span("OR", cls="divider-text"),
                        cls="login-divider"
                    ) if oauth_enabled else None),

                    # App password login option (legacy)
                    Div(
                        (H3("App Password Login", cls="legacy-section-title") if oauth_enabled else None),
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
                            Button("Sign In with App Password", type="submit", cls="login-btn-secondary" if oauth_enabled else "login-btn-primary"),
                            action="/auth/login",
                            method="post",
                            autocomplete="on",
                            cls="login-form"
                        ),
                        cls="app-password-section"
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
    
    @log_auth_flow
    @retry_on_network_error(max_attempts=3, backoff_seconds=1)
    async def authenticate_user(self, handle: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Bluesky and return user info."""
        try:
            # Step 1: Format handle
            original_handle = handle
            if not handle.endswith('.bsky.social') and '.' not in handle:
                handle = f"{handle}.bsky.social"
                logger.debug(f"Formatted handle '{original_handle}' to '{handle}'")
            
            # Step 2: Resolve service endpoint
            service = None
            try:
                service = self.get_service_from_handle(handle)
                logger.info(f"Resolved service endpoint for '{handle}': {service}")
            except Exception as e:
                logger.error(f"Failed to resolve service endpoint for '{handle}': {e}", exc_info=True)
                # Fallback for custom domains that might fail resolution
                if not handle.endswith('.bsky.social'):
                    logger.warning(f"Falling back to default Bluesky service for '{handle}'")
                    service = "https://bsky.social"
                else:
                    raise

            # Step 3: Initialize client with the resolved service
            try:
                if service and not service.endswith("bsky.network"):
                    self.client = AtprotoClient(service)
                    logger.debug(f"Initialized AtprotoClient with custom service: {service}")
                else:
                    self.client = AtprotoClient()
                    logger.debug("Initialized AtprotoClient with default service.")
            except Exception as e:
                logger.error(f"Failed to initialize AtprotoClient: {e}", exc_info=True)
                raise

            # Step 4: Attempt login
            logger.info(f"Attempting Bluesky login for '{handle}' on service '{service}'...")
            profile = self.client.login(handle, password)
            logger.debug(f"Login successful, profile returned: {profile is not None}")
            
            # Step 5: Verify session
            if not self.client.me:
                logger.error(f"Login appeared successful but client.me is missing for handle '{handle}'")
                return None
            
            logger.debug(f"Session verified, client.me.handle: {self.client.me.handle}")
            
            # Step 6: Prepare user data
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
            from atproto_client.exceptions import UnauthorizedError
            
            if isinstance(e, UnauthorizedError):
                logger.warning(f"Authentication failed for handle '{handle}': Invalid credentials. Error: {e}")
                return None
            else:
                logger.error(f"An unexpected error occurred during authentication for handle '{handle}': {e}", exc_info=True)
                return None

    def get_service_from_handle(self, handle: str) -> str:
        """Resolve handle to PDS service endpoint using synchronous httpx."""
        did = self.client.com.atproto.identity.resolve_handle({"handle": handle})
        logger.debug(f"Resolved identity: {did.did}")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"https://plc.directory/{did.did}")
            response.raise_for_status()
            did_doc = response.json()
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
            client = AtprotoClient()
            client.login(session_string=session_string)
            
            if not client.me:
                logger.warning("Could not authenticate client for following list.")
                return []

            all_following = []
            cursor = None
            max_pages = 50
            page_count = 0
            max_retries = 3
            retry_count = 0
            
            logger.info(f"Starting paginated fetch of followers for user {user_did}")
            
            while page_count < max_pages and retry_count <= max_retries:
                try:
                    params = {'actor': user_did, 'limit': 100}
                    if cursor:
                        params['cursor'] = cursor
                    
                    response = client.app.bsky.graph.get_follows(params)
                    
                    if not response or not response.follows:
                        if cursor:
                            logger.warning(f"Stale cursor detected for follows of {user_did}, restarting without cursor")
                            cursor = None
                            retry_count += 1
                            continue
                        else:
                            logger.info(f"No more followers found for {user_did}")
                            break
                    
                    page_followers = [follow.did for follow in response.follows]
                    all_following.extend(page_followers)
                    page_count += 1
                    
                    logger.debug(f"Page {page_count}: Retrieved {len(page_followers)} followers (total: {len(all_following)})")
                    
                    new_cursor = getattr(response, 'cursor', None)
                    if not new_cursor or new_cursor == cursor:
                        logger.info(f"Reached end of followers list at page {page_count}")
                        break
                    
                    cursor = new_cursor
                        
                except Exception as e:
                    if 'cursor' in str(e).lower() or 'invalid' in str(e).lower():
                        logger.warning(f"Cursor error for follows of {user_did}: {e}, retrying without cursor")
                        cursor = None
                        retry_count += 1
                        continue
                    else:
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
            required_fields = ['did', 'handle']
            if all(field in auth_data for field in required_fields):
                logger.debug(f"Session restored for user: {auth_data.get('handle')}")
                return True
            logger.warning("Session restore failed: missing required fields")
            return False
        except Exception as e:
            logger.error(f"Session restore error: {e}", exc_info=True)
            return False
