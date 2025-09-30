"""
OAuth flow utilities for atproto OAuth implementation.
Handles PAR, DPoP, token requests, and client authentication.
"""
import json
import time
import secrets
import hashlib
import base64
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode

from authlib.jose import JsonWebKey, jwt
import httpx

from atproto_security import is_safe_url, safe_http_client
from atproto_identity import IdentityResolutionError

logger = logging.getLogger(__name__)

class OAuthError(Exception):
    """Raised when OAuth flow fails."""
    pass

def generate_pkce_verifier() -> str:
    """Generate PKCE code verifier."""
    # Generate 32-96 random bytes, base64url encode
    random_bytes = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(random_bytes).decode().rstrip('=')

def generate_pkce_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier."""
    # SHA256 hash, then base64url encode
    hash_bytes = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(hash_bytes).decode().rstrip('=')

def generate_state() -> str:
    """Generate OAuth state parameter."""
    return secrets.token_urlsafe(32)

def generate_dpop_key() -> JsonWebKey:
    """Generate DPoP keypair for session."""
    return JsonWebKey.generate_key("EC", "P-256", is_private=True)

def create_client_assertion_jwt(
    client_secret_jwk: JsonWebKey,
    client_id: str,
    authserver_issuer: str
) -> str:
    """
    Create client assertion JWT for confidential client authentication.

    Args:
        client_secret_jwk: Client's secret JWK
        client_id: OAuth client ID
        authserver_issuer: Authorization server issuer URL

    Returns:
        Signed JWT string
    """
    now = int(time.time())

    # JWT header
    headers = {
        'alg': 'ES256',
        'kid': client_secret_jwk.thumbprint()
    }

    # JWT payload
    payload = {
        'iss': client_id,
        'sub': client_id,
        'aud': authserver_issuer,
        'jti': secrets.token_urlsafe(16),
        'iat': now,
        'exp': now + 300  # 5 minutes
    }

    # Sign JWT
    return jwt.encode(headers, payload, client_secret_jwk)

def create_dpop_jwt(
    dpop_private_jwk: JsonWebKey,
    htm: str,  # HTTP method
    htu: str,  # HTTP URL
    nonce: str = None,
    access_token: str = None
) -> str:
    """
    Create DPoP proof JWT.

    Args:
        dpop_private_jwk: DPoP private key
        htm: HTTP method (GET, POST, etc.)
        htu: HTTP URL
        nonce: Server-provided nonce (optional)
        access_token: Access token for ath calculation (optional)

    Returns:
        Signed JWT string
    """
    now = int(time.time())

    # JWT header
    headers = {
        'typ': 'dpop+jwt',
        'alg': 'ES256',
        'jwk': json.loads(dpop_private_jwk.as_json(is_private=False))
    }

    # JWT payload
    payload = {
        'jti': secrets.token_urlsafe(16),
        'htm': htm,
        'htu': htu,
        'iat': now,
        'exp': now + 300  # 5 minutes
    }

    # Add nonce if provided
    if nonce:
        payload['nonce'] = nonce

    # Add access token hash if provided (for PDS requests)
    if access_token:
        # Calculate SHA256 hash of access token, base64url encode
        token_hash = hashlib.sha256(access_token.encode()).digest()
        payload['ath'] = base64.urlsafe_b64encode(token_hash).decode().rstrip('=')

    # Sign JWT
    return jwt.encode(headers, payload, dpop_private_jwk)

def send_par_auth_request(
    authserver_url: str,
    authserver_meta: Dict[str, Any],
    login_hint: str = None,
    client_id: str = None,
    redirect_uri: str = None,
    scope: str = "atproto transition:generic",
    client_secret_jwk: JsonWebKey = None,
    dpop_private_jwk: JsonWebKey = None
) -> Tuple[str, str, str, httpx.Response]:
    """
    Send Pushed Authorization Request (PAR).

    Returns:
        Tuple of (pkce_verifier, state, dpop_nonce, response)
    """
    logger.debug(f"Sending PAR to {authserver_url}")

    try:
        # Generate PKCE and state
        pkce_verifier = generate_pkce_verifier()
        pkce_challenge = generate_pkce_challenge(pkce_verifier)
        state = generate_state()

        # Prepare PAR request body
        par_data = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'state': state,
            'code_challenge': pkce_challenge,
            'code_challenge_method': 'S256',
            'dpop_bound_access_tokens': 'true'
        }

        # Add login_hint if provided
        if login_hint:
            par_data['login_hint'] = login_hint

        # Add client assertion for confidential clients
        if client_secret_jwk:
            client_assertion = create_client_assertion_jwt(
                client_secret_jwk, client_id, authserver_meta['issuer']
            )
            par_data['client_assertion_type'] = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
            par_data['client_assertion'] = client_assertion

        # Create initial DPoP proof for PAR request
        par_endpoint = authserver_meta['pushed_authorization_request_endpoint']
        dpop_jwt = create_dpop_jwt(dpop_private_jwk, 'POST', par_endpoint)

        # Send PAR request with DPoP header
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        response = safe_http_client.post(par_endpoint, data=par_data, headers=headers)

        # Check for DPoP nonce in response headers
        dpop_nonce = response.headers.get('DPoP-Nonce', '')

        logger.debug(f"PAR response status: {response.status_code}")
        logger.debug(f"PAR response: {response.text}")

        return pkce_verifier, state, dpop_nonce, response

    except Exception as e:
        logger.error(f"PAR request failed: {e}")
        raise OAuthError(f"PAR request failed: {e}")

def retry_par_with_nonce(
    authserver_url: str,
    authserver_meta: Dict[str, Any],
    par_data: Dict[str, Any],
    dpop_private_jwk: JsonWebKey,
    dpop_nonce: str
) -> httpx.Response:
    """Retry PAR request with DPoP nonce."""
    logger.debug("Retrying PAR with DPoP nonce")

    try:
        # Create DPoP proof with nonce
        par_endpoint = authserver_meta['pushed_authorization_request_endpoint']
        dpop_jwt = create_dpop_jwt(dpop_private_jwk, 'POST', par_endpoint, nonce=dpop_nonce)

        # Send PAR request with updated DPoP header
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        response = safe_http_client.post(par_endpoint, data=par_data, headers=headers)

        logger.debug(f"PAR retry response status: {response.status_code}")
        return response

    except Exception as e:
        logger.error(f"PAR retry failed: {e}")
        raise OAuthError(f"PAR retry failed: {e}")

def initial_token_request(
    auth_request_row: Dict[str, Any],
    authorization_code: str,
    app_url: str,
    client_secret_jwk: JsonWebKey
) -> Tuple[Dict[str, Any], str]:
    """
    Exchange authorization code for tokens.

    Args:
        auth_request_row: Database row with auth request data
        authorization_code: Authorization code from callback
        app_url: Application base URL
        client_secret_jwk: Client secret JWK

    Returns:
        Tuple of (tokens_dict, dpop_nonce)
    """
    logger.debug("Requesting initial tokens")

    try:
        # Parse authserver metadata from stored issuer
        authserver_iss = auth_request_row['authserver_iss']
        token_endpoint = f"{authserver_iss}/oauth/token"

        # Prepare token request
        token_data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': f"{app_url}oauth/callback",
            'code_verifier': auth_request_row['pkce_verifier'],
            'client_id': f"{app_url}oauth/client-metadata.json"
        }

        # Add client assertion for confidential clients
        if client_secret_jwk:
            # We need to fetch authserver metadata for issuer
            from atproto_identity import fetch_authserver_meta
            authserver_meta = fetch_authserver_meta(authserver_iss)

            client_assertion = create_client_assertion_jwt(
                client_secret_jwk, token_data['client_id'], authserver_meta['issuer']
            )
            token_data['client_assertion_type'] = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
            token_data['client_assertion'] = client_assertion

        # Create DPoP proof for token request
        dpop_private_jwk = JsonWebKey.import_key(auth_request_row['dpop_private_jwk'])
        dpop_jwt = create_dpop_jwt(
            dpop_private_jwk, 'POST', token_endpoint,
            nonce=auth_request_row['dpop_authserver_nonce']
        )

        # Send token request with DPoP
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        response = safe_http_client.post(token_endpoint, data=token_data, headers=headers)

        # Check for updated DPoP nonce
        new_dpop_nonce = response.headers.get('DPoP-Nonce', auth_request_row['dpop_authserver_nonce'])

        # Parse token response
        tokens = response.json()

        # Validate token response
        if 'access_token' not in tokens or 'refresh_token' not in tokens:
            raise OAuthError("Invalid token response: missing tokens")

        if tokens.get('token_type') != 'DPoP':
            raise OAuthError(f"Invalid token type: {tokens.get('token_type')}")

        logger.info("Successfully obtained initial tokens")
        return tokens, new_dpop_nonce

    except Exception as e:
        logger.error(f"Initial token request failed: {e}")
        raise OAuthError(f"Token request failed: {e}")

def refresh_token_request(
    user_session_row: Dict[str, Any],
    app_url: str,
    client_secret_jwk: JsonWebKey
) -> Tuple[Dict[str, Any], str]:
    """
    Refresh access token using refresh token.

    Args:
        user_session_row: Database row with user session data
        app_url: Application base URL
        client_secret_jwk: Client secret JWK

    Returns:
        Tuple of (tokens_dict, dpop_nonce)
    """
    logger.debug("Refreshing access token")

    try:
        # Parse authserver metadata from stored issuer
        authserver_iss = user_session_row['authserver_iss']
        token_endpoint = f"{authserver_iss}/oauth/token"

        # Prepare refresh request
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': user_session_row['refresh_token'],
            'client_id': f"{app_url}oauth/client-metadata.json"
        }

        # Add client assertion for confidential clients
        if client_secret_jwk:
            # We need to fetch authserver metadata for issuer
            from atproto_identity import fetch_authserver_meta
            authserver_meta = fetch_authserver_meta(authserver_iss)

            client_assertion = create_client_assertion_jwt(
                client_secret_jwk, refresh_data['client_id'], authserver_meta['issuer']
            )
            refresh_data['client_assertion_type'] = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
            refresh_data['client_assertion'] = client_assertion

        # Create DPoP proof for refresh request
        dpop_private_jwk = JsonWebKey.import_key(user_session_row['dpop_private_jwk'])
        dpop_jwt = create_dpop_jwt(
            dpop_private_jwk, 'POST', token_endpoint,
            nonce=user_session_row['dpop_authserver_nonce']
        )

        # Send refresh request with DPoP
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        response = safe_http_client.post(token_endpoint, data=refresh_data, headers=headers)

        # Check for updated DPoP nonce
        new_dpop_nonce = response.headers.get('DPoP-Nonce', user_session_row['dpop_authserver_nonce'])

        # Parse token response
        tokens = response.json()

        # Validate token response
        if 'access_token' not in tokens:
            raise OAuthError("Invalid token response: missing access_token")

        logger.info("Successfully refreshed access token")
        return tokens, new_dpop_nonce

    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise OAuthError(f"Token refresh failed: {e}")

def pds_authed_req(
    method: str,
    url: str,
    body: Dict[str, Any] = None,
    user_session_row: Dict[str, Any] = None,
    db = None
) -> httpx.Response:
    """
    Make authenticated request to PDS with DPoP.

    Args:
        method: HTTP method
        url: PDS endpoint URL
        body: Request body (for POST/PUT)
        user_session_row: User session data from database
        db: Database connection (for token refresh if needed)

    Returns:
        HTTP response
    """
    logger.debug(f"Making authenticated request: {method} {url}")

    try:
        # Validate URL
        if not is_safe_url(url):
            raise OAuthError(f"Unsafe PDS URL: {url}")

        # Get tokens from session
        access_token = user_session_row['access_token']
        dpop_private_jwk = JsonWebKey.import_key(user_session_row['dpop_private_jwk'])
        dpop_nonce = user_session_row['dpop_authserver_nonce']

        # Check if token needs refresh (simple check - in production, decode JWT)
        if needs_token_refresh(access_token):
            logger.info("Access token may need refresh, attempting refresh")

            # Import here to avoid circular imports
            from app import app
            app_url = "http://localhost:5001"  # TODO: Get from request context

            # Refresh token
            try:
                tokens, new_dpop_nonce = refresh_token_request(
                    user_session_row, app_url, get_client_secret_jwk()
                )

                # Update database with new tokens
                if db:
                    db.execute("""
                        UPDATE oauth_session
                        SET access_token = ?, refresh_token = ?, dpop_authserver_nonce = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE did = ?
                    """, (tokens['access_token'], tokens['refresh_token'], new_dpop_nonce, user_session_row['did']))

                # Update local variables
                access_token = tokens['access_token']
                dpop_nonce = new_dpop_nonce

            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise OAuthError(f"Token refresh failed: {e}")

        # Create DPoP proof for PDS request
        dpop_jwt = create_dpop_jwt(
            dpop_private_jwk, method, url,
            nonce=dpop_nonce, access_token=access_token
        )

        # Prepare headers
        headers = {
            'Authorization': f'DPoP {access_token}',
            'DPoP': dpop_jwt,
            'Content-Type': 'application/json'
        }

        # Make request
        if method.upper() == 'GET':
            response = safe_http_client.client.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = safe_http_client.client.post(url, headers=headers, json=body)
        elif method.upper() == 'PUT':
            response = safe_http_client.client.put(url, headers=headers, json=body)
        else:
            raise OAuthError(f"Unsupported HTTP method: {method}")

        # Check for DPoP nonce update
        if response.headers.get('DPoP-Nonce') and db:
            new_nonce = response.headers['DPoP-Nonce']
            if new_nonce != dpop_nonce:
                db.execute("""
                    UPDATE oauth_session
                    SET dpop_authserver_nonce = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE did = ?
                """, (new_nonce, user_session_row['did']))

        response.raise_for_status()
        return response

    except Exception as e:
        logger.error(f"Authenticated PDS request failed: {e}")
        raise OAuthError(f"PDS request failed: {e}")

def needs_token_refresh(access_token: str) -> bool:
    """
    Check if access token needs refresh.
    This is a simple implementation - in production, decode JWT and check exp claim.
    """
    try:
        # For now, assume tokens need refresh if they're "old"
        # In production, decode JWT and check expiration
        # header = jwt.get_unverified_header(access_token)
        # payload = jwt.decode(access_token, options={"verify_exp": False})
        # return payload['exp'] < (time.time() + 300)  # Refresh if < 5 min left

        # Simple heuristic: assume tokens older than 1 hour need refresh
        # This should be replaced with proper JWT expiration checking
        return False  # For now, don't auto-refresh

    except Exception:
        # If we can't decode, assume it needs refresh
        return True

def get_client_secret_jwk() -> JsonWebKey:
    """Get client secret JWK from environment."""
    import os
    jwk_json = os.getenv('CLIENT_SECRET_JWK')
    if not jwk_json:
        raise OAuthError("CLIENT_SECRET_JWK not configured")

    return JsonWebKey.import_key(jwk_json)
