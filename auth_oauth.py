"""
OAuth-based authentication for Bibliome.
Replaces app password authentication with atproto OAuth.
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from authlib.jose import JsonWebKey

from oauth_identity import (
    resolve_identity, is_valid_did, is_valid_handle,
    pds_endpoint, resolve_pds_authserver, fetch_authserver_meta
)
from oauth_helpers import (
    send_par_auth_request, retry_par_with_nonce, initial_token_request,
    refresh_token_request, generate_dpop_key, OAuthError
)
from oauth_security import is_safe_url

logger = logging.getLogger(__name__)

class OAuthAuth:
    """Handle atproto OAuth authentication."""

    def __init__(self):
        self.client_secret_jwk = None
        self.client_pub_jwk = None
        self._load_client_keys()

    def _load_client_keys(self):
        """Load client secret and public keys from environment."""
        import os

        jwk_json = os.getenv('CLIENT_SECRET_JWK')
        if not jwk_json:
            logger.warning("CLIENT_SECRET_JWK not configured - OAuth disabled")
            return

        try:
            self.client_secret_jwk = JsonWebKey.import_key(jwk_json)
            self.client_pub_jwk = json.loads(self.client_secret_jwk.as_json(is_private=False))

            # Validate keys
            if 'd' not in json.loads(self.client_secret_jwk.as_json(is_private=True)):
                raise ValueError("Private key missing secret component")

            logger.info("OAuth client keys loaded successfully")
            logger.debug(f"Client key ID: {self.client_secret_jwk.thumbprint()}")

        except Exception as e:
            logger.error(f"Failed to load OAuth client keys: {e}")
            self.client_secret_jwk = None
            self.client_pub_jwk = None

    def is_oauth_enabled(self) -> bool:
        """Check if OAuth is properly configured."""
        return self.client_secret_jwk is not None

    def create_oauth_login_form(self, error_msg: str = None):
        """Create OAuth login form."""
        from fasthtml.common import (
            Title, Favicon, NavBar, Div, H1, P, Form, Input, Button, Label
        )

        return (
            Title("Login with OAuth - Bibliome"),
            Favicon(light_icon='/static/bibliome.ico', dark_icon='/static/bibliome.ico'),
            NavBar(),
            Div(
                Div(
                    # Logo and branding
                    Div(
                        H1("Sign In", cls="login-title"),
                        P("Enter your Bluesky handle or DID to continue with OAuth", cls="login-subtitle"),
                        cls="login-header"
                    ),

                    # Error message if present
                    Div(error_msg, cls="alert alert-error") if error_msg else None,

                    # OAuth login form
                    Form(
                        Label("Bluesky Handle or DID", Input(
                            name="username",
                            type="text",
                            placeholder="your-handle.bsky.social or did:plc:...",
                            required=True,
                            cls="login-input"
                        )),
                        Button("Continue with OAuth", type="submit", cls="login-btn-primary"),
                        action="/oauth/login",
                        method="post",
                        cls="login-form"
                    ),

                    # Help text
                    Div(
                        P(
                            "Don't have a Bluesky account? ",
                            "Sign up at ",
                            "https://bsky.app"
                        ),
                        P(
                            "This app uses OAuth for enhanced security. ",
                            "Your credentials are never stored on our servers."
                        ),
                        cls="login-help"
                    ),

                    cls="login-card"
                ),
                cls="login-container"
            )
        )

    def initiate_oauth_flow(self, username: str, request) -> str:
        """
        Initiate OAuth flow for user.

        Args:
            username: Handle or DID entered by user
            request: FastHTML request object

        Returns:
            Redirect URL for authorization

        Raises:
            OAuthError: If OAuth flow initiation fails
        """
        if not self.is_oauth_enabled():
            raise OAuthError("OAuth not configured")

        logger.info(f"Initiating OAuth flow for: {username}")

        try:
            # Step 1: Validate and resolve identity
            did, handle, did_doc = resolve_identity(username)

            # Step 2: Get PDS endpoint
            pds_url = pds_endpoint(did_doc)

            # Step 3: Resolve authorization server
            authserver_url = resolve_pds_authserver(pds_url)

            # Step 4: Fetch authorization server metadata
            authserver_meta = fetch_authserver_meta(authserver_url)

            # Step 5: Generate DPoP keypair for this session
            dpop_private_jwk = generate_dpop_key()

            # Step 6: Determine client_id and redirect_uri
            # In FastHTML, we need to construct URLs from request info
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port

            # Ensure HTTPS for OAuth (required)
            if scheme == 'http' and port == 5001:
                scheme = 'https'  # Assume HTTPS in production

            app_url = f"{scheme}://{host}"
            if scheme == 'https' and port != 443:
                app_url += f":{port}"
            elif scheme == 'http' and port != 80:
                app_url += f":{port}"

            redirect_uri = f"{app_url}/oauth/callback"
            client_id = f"{app_url}/oauth/client-metadata.json"

            # Step 7: Send PAR request
            pkce_verifier, state, dpop_nonce, response = send_par_auth_request(
                authserver_url,
                authserver_meta,
                login_hint=username,
                client_id=client_id,
                redirect_uri=redirect_uri,
                client_secret_jwk=self.client_secret_jwk,
                dpop_private_jwk=dpop_private_jwk
            )

            # Step 8: Handle DPoP nonce (retry if needed)
            if response.status_code == 401 and 'use_dpop_nonce' in str(response.text):
                logger.debug("Retrying PAR with DPoP nonce")
                response = retry_par_with_nonce(
                    authserver_url,
                    authserver_meta,
                    response.request.body,
                    dpop_private_jwk,
                    dpop_nonce
                )

            response.raise_for_status()
            request_uri = response.json()['request_uri']

            # Step 9: Store auth request in database
            from app import db_tables
            db_tables['oauth_auth_request'].insert({
                'state': state,
                'authserver_iss': authserver_meta['issuer'],
                'did': did,
                'handle': handle,
                'pds_url': pds_url,
                'pkce_verifier': pkce_verifier,
                'scope': 'atproto transition:generic',
                'dpop_authserver_nonce': dpop_nonce,
                'dpop_private_jwk': dpop_private_jwk.as_json(is_private=True)
            })

            # Step 10: Redirect to authorization endpoint
            auth_url = authserver_meta['authorization_endpoint']
            params = {
                'client_id': client_id,
                'request_uri': request_uri
            }

            from urllib.parse import urlencode
            redirect_url = f"{auth_url}?{urlencode(params)}"

            logger.info(f"OAuth flow initiated successfully for {handle}")
            return redirect_url

        except Exception as e:
            logger.error(f"OAuth flow initiation failed for {username}: {e}")
            raise OAuthError(f"OAuth flow failed: {e}")

    def handle_oauth_callback(self, state: str, authserver_iss: str,
                            authorization_code: str, request) -> Dict[str, Any]:
        """
        Handle OAuth callback and complete authentication.

        Args:
            state: State parameter from callback
            authserver_iss: Authorization server issuer
            authorization_code: Authorization code
            request: FastHTML request object

        Returns:
            User session data

        Raises:
            OAuthError: If callback handling fails
        """
        if not self.is_oauth_enabled():
            raise OAuthError("OAuth not configured")

        logger.info(f"Handling OAuth callback for state: {state}")

        try:
            # Step 1: Retrieve auth request from database
            from app import db_tables
            auth_request = db_tables['oauth_auth_request']("state=?", (state,))

            if not auth_request:
                raise OAuthError("Invalid or expired OAuth request")

            # Step 2: Validate authserver_iss matches
            if auth_request['authserver_iss'] != authserver_iss:
                raise OAuthError("Authorization server mismatch")

            # Step 3: Exchange code for tokens
            # In FastHTML, we need to construct URLs from request info
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port

            # Ensure HTTPS for OAuth (required)
            if scheme == 'http' and port == 5001:
                scheme = 'https'  # Assume HTTPS in production

            app_url = f"{scheme}://{host}"
            if scheme == 'https' and port != 443:
                app_url += f":{port}"
            elif scheme == 'http' and port != 80:
                app_url += f":{port}"

            tokens, dpop_nonce = initial_token_request(
                auth_request,
                authorization_code,
                app_url,
                self.client_secret_jwk
            )

            # Step 4: Validate user identity
            user_did = tokens['sub']

            if auth_request['did']:
                # If we started with account identifier, verify it matches
                if auth_request['did'] != user_did:
                    raise OAuthError("User identity mismatch")
                user_handle = auth_request['handle']
                pds_url = auth_request['pds_url']
            else:
                # If we started with auth server, resolve identity now
                did, handle, did_doc = resolve_identity(user_did)
                pds_url = pds_endpoint(did_doc)

                # Verify authorization server matches
                expected_authserver = resolve_pds_authserver(pds_url)
                if expected_authserver != authserver_iss:
                    raise OAuthError("Authorization server verification failed")

                user_handle = handle

            # Step 5: Store OAuth session in database
            db_tables['oauth_session'].insert({
                'did': user_did,
                'handle': user_handle,
                'pds_url': pds_url,
                'authserver_iss': authserver_iss,
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'dpop_authserver_nonce': dpop_nonce,
                'dpop_private_jwk': auth_request['dpop_private_jwk']
            })

            # Step 6: Clean up auth request
            db_tables['oauth_auth_request'].delete_where("state=?", (state,))

            # Step 7: Return user session data
            user_data = {
                'did': user_did,
                'handle': user_handle,
                'pds_url': pds_url,
                'authserver_iss': authserver_iss,
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token']
            }

            logger.info(f"OAuth authentication completed for {user_handle}")
            return user_data

        except Exception as e:
            logger.error(f"OAuth callback handling failed: {e}")
            raise OAuthError(f"OAuth callback failed: {e}")

    def refresh_user_session(self, user_did: str, request) -> Dict[str, Any]:
        """
        Refresh OAuth tokens for user.

        Args:
            user_did: User DID
            request: FastHTML request object

        Returns:
            Updated user session data

        Raises:
            OAuthError: If refresh fails
        """
        if not self.is_oauth_enabled():
            raise OAuthError("OAuth not configured")

        logger.debug(f"Refreshing OAuth session for: {user_did}")

        try:
            # Step 1: Get current session from database
            from app import db_tables
            session = db_tables['oauth_session']("did=?", (user_did,))

            if not session:
                raise OAuthError("No OAuth session found")

            # Step 2: Refresh tokens
            # In FastHTML, we need to construct URLs from request info
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port

            # Ensure HTTPS for OAuth (required)
            if scheme == 'http' and port == 5001:
                scheme = 'https'  # Assume HTTPS in production

            app_url = f"{scheme}://{host}"
            if scheme == 'https' and port != 443:
                app_url += f":{port}"
            elif scheme == 'http' and port != 80:
                app_url += f":{port}"

            tokens, dpop_nonce = refresh_token_request(
                session,
                app_url,
                self.client_secret_jwk
            )

            # Step 3: Update session in database
            db_tables['oauth_session'].update({
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'dpop_authserver_nonce': dpop_nonce,
                'updated_at': datetime.now()
            }, user_did)

            # Step 4: Return updated session data
            updated_session = {
                'did': session['did'],
                'handle': session['handle'],
                'pds_url': session['pds_url'],
                'authserver_iss': session['authserver_iss'],
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token']
            }

            logger.info(f"OAuth session refreshed for {session['handle']}")
            return updated_session

        except Exception as e:
            logger.error(f"OAuth session refresh failed for {user_did}: {e}")
            raise OAuthError(f"Session refresh failed: {e}")

    def logout_user(self, user_did: str):
        """Logout user by removing OAuth session."""
        logger.info(f"Logging out OAuth user: {user_did}")

        try:
            from app import db_tables
            db_tables['oauth_session'].delete_where("did=?", (user_did,))
            logger.info(f"OAuth session removed for {user_did}")
        except Exception as e:
            logger.error(f"Error removing OAuth session for {user_did}: {e}")

    def get_user_session(self, user_did: str) -> Optional[Dict[str, Any]]:
        """Get OAuth session data for user."""
        try:
            from app import db_tables
            session = db_tables['oauth_session']("did=?", (user_did,))
            return dict(session) if session else None
        except Exception as e:
            logger.error(f"Error getting OAuth session for {user_did}: {e}")
            return None

# Global OAuth auth instance
oauth_auth = OAuthAuth()
