"""
atproto OAuth 2.0 Implementation with PKCE, DPoP, and PAR support.

This module implements the AT Protocol OAuth profile with:
- PKCE (Proof Key for Code Exchange) with S256
- DPoP (Demonstration of Proof-of-Possession)
- PAR (Pushed Authorization Requests)
- Token management (access, refresh, revocation)
- Identity verification
"""

import base64
import hashlib
import secrets
import time
import json
from typing import Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx

# Try to import OAuth dependencies - gracefully degrade if not available
try:
    from authlib.jose import JsonWebKey, jwt
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False
    # Create dummy classes for type hints
    class JsonWebKey:
        pass
    class jwt:
        pass


class ATProtoOAuthError(Exception):
    """Base exception for ATProto OAuth errors."""
    pass


class OAuthClient:
    """ATProto OAuth 2.0 client implementation."""

    def __init__(self, client_id: str, redirect_uri: str, scope: str = "atproto"):
        """
        Initialize OAuth client.

        Args:
            client_id: Client identifier (HTTPS URL to client metadata)
            redirect_uri: OAuth redirect URI
            scope: OAuth scope (default: "atproto")

        Raises:
            ATProtoOAuthError: If OAuth dependencies are not available
        """
        if not OAUTH_AVAILABLE:
            raise ATProtoOAuthError(
                "OAuth dependencies not installed. "
                "Please install: pip install authlib cryptography"
            )

        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.http_client = httpx.Client(timeout=30.0, follow_redirects=True)

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'http_client'):
            self.http_client.close()

    # PKCE Functions

    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generate a PKCE code verifier (43-128 characters).

        Returns:
            Base64url-encoded random string
        """
        # Generate 48 random bytes (results in ~64 character string)
        random_bytes = secrets.token_bytes(48)
        # Base64url encode without padding
        return base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')

    @staticmethod
    def create_s256_code_challenge(verifier: str) -> str:
        """
        Create S256 PKCE code challenge from verifier.

        Args:
            verifier: PKCE code verifier

        Returns:
            Base64url-encoded SHA256 hash of verifier
        """
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    # DPoP Functions

    @staticmethod
    def generate_dpop_keypair() -> Dict[str, Any]:
        """
        Generate ES256 keypair for DPoP.

        Returns:
            Dict with 'private_key_pem' and 'public_jwk'
        """
        # Generate EC private key (P-256 curve for ES256)
        private_key = ec.generate_private_key(ec.SECP256R1())

        # Export as JWK
        private_pem_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_pem = private_pem_bytes.decode('utf-8')

        # Get public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_jwk = JsonWebKey.import_key(public_pem, {'kty': 'EC'})

        return {
            'private_key_pem': private_pem,
            'public_jwk': public_jwk.as_dict(is_private=False)
        }

    @staticmethod
    def create_dpop_jwt(
        private_key_data: Union[str, Dict[str, Any]],
        htm: str,
        htu: str,
        nonce: Optional[str] = None,
        ath: Optional[str] = None
    ) -> str:
        """
        Create a DPoP JWT proof.

        Args:
            private_key_data: Private key data (PEM string or JWK dict) for signing
            htm: HTTP method (e.g., "POST", "GET")
            htu: HTTP URL (without query or fragment)
            nonce: Server-provided nonce (optional)
            ath: Access token hash for resource requests (optional)

        Returns:
            DPoP JWT string
        """
        # Import private key
        if isinstance(private_key_data, str):
            key = JsonWebKey.import_key(private_key_data)
        else:
            key = JsonWebKey.import_key(private_key_data)

        # Get public JWK for header
        public_jwk = key.as_dict(is_private=False)

        # Prepare header
        header = {
            'typ': 'dpop+jwt',
            'alg': 'ES256',
            'jwk': public_jwk
        }

        # Prepare payload
        now = int(time.time())
        payload = {
            'jti': secrets.token_urlsafe(32),  # Unique identifier
            'htm': htm,
            'htu': htu,
            'iat': now,
            'exp': now + 300  # 5 minute expiry
        }

        if nonce:
            payload['nonce'] = nonce

        if ath:
            payload['ath'] = ath

        # Sign and return
        return jwt.encode(header, payload, key).decode('utf-8')

    @staticmethod
    def create_access_token_hash(access_token: str) -> str:
        """
        Create SHA-256 hash of access token for DPoP ath claim.

        Args:
            access_token: OAuth access token

        Returns:
            Base64url-encoded hash
        """
        digest = hashlib.sha256(access_token.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    # Server Discovery

    def resolve_handle(self, handle: str) -> Dict[str, Any]:
        """
        Resolve handle to DID and PDS.

        Args:
            handle: User's handle (e.g., "user.bsky.social")

        Returns:
            Dict with 'did' and 'pds' URL
        """
        # Try DNS-based resolution first
        try:
            resp = self.http_client.get(
                f"https://{handle}/.well-known/atproto-did",
                headers={'Accept': 'text/plain'}
            )
            if resp.status_code == 200:
                did = resp.text.strip()
                # Now resolve DID document
                return self._resolve_did_document(did)
        except Exception:
            pass

        # Fall back to HTTPS well-known resolution
        try:
            resp = self.http_client.get(
                f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle",
                params={'handle': handle}
            )
            resp.raise_for_status()
            data = resp.json()
            did = data['did']
            return self._resolve_did_document(did)
        except Exception as e:
            raise ATProtoOAuthError(f"Failed to resolve handle {handle}: {e}")

    def _resolve_did_document(self, did: str) -> Dict[str, Any]:
        """
        Resolve DID document to get PDS.

        Args:
            did: User's DID

        Returns:
            Dict with 'did' and 'pds' URL
        """
        try:
            # For did:plc, use the PLC directory
            if did.startswith('did:plc:'):
                resp = self.http_client.get(f"https://plc.directory/{did}")
                resp.raise_for_status()
                doc = resp.json()

                # Find PDS service endpoint
                for service in doc.get('service', []):
                    if service.get('type') == 'AtprotoPersonalDataServer':
                        pds = service.get('serviceEndpoint')
                        return {'did': did, 'pds': pds}

                raise ATProtoOAuthError(f"No PDS found in DID document for {did}")

            # For did:web, resolve via HTTPS
            elif did.startswith('did:web:'):
                domain = did.replace('did:web:', '')
                resp = self.http_client.get(f"https://{domain}/.well-known/did.json")
                resp.raise_for_status()
                doc = resp.json()

                for service in doc.get('service', []):
                    if service.get('type') == 'AtprotoPersonalDataServer':
                        pds = service.get('serviceEndpoint')
                        return {'did': did, 'pds': pds}

                raise ATProtoOAuthError(f"No PDS found in DID document for {did}")

            else:
                raise ATProtoOAuthError(f"Unsupported DID method: {did}")

        except Exception as e:
            raise ATProtoOAuthError(f"Failed to resolve DID {did}: {e}")

    def get_authorization_server_metadata(self, pds_url: str) -> Dict[str, Any]:
        """
        Discover authorization server from PDS.

        Args:
            pds_url: PDS URL

        Returns:
            Authorization server metadata
        """
        try:
            # Get resource server metadata
            resp = self.http_client.get(
                f"{pds_url}/.well-known/oauth-protected-resource"
            )
            resp.raise_for_status()
            resource_metadata = resp.json()

            # Get authorization servers
            auth_servers = resource_metadata.get('authorization_servers', [])
            if not auth_servers:
                raise ATProtoOAuthError("No authorization servers found")

            # Use first authorization server
            issuer = auth_servers[0]

            # Fetch authorization server metadata
            resp = self.http_client.get(
                f"{issuer}/.well-known/oauth-authorization-server"
            )
            resp.raise_for_status()
            auth_metadata = resp.json()

            # Validate required fields
            required_fields = [
                'issuer', 'authorization_endpoint', 'token_endpoint',
                'pushed_authorization_request_endpoint'
            ]
            for field in required_fields:
                if field not in auth_metadata:
                    raise ATProtoOAuthError(f"Missing required field: {field}")

            return auth_metadata

        except Exception as e:
            raise ATProtoOAuthError(f"Failed to get authorization server metadata: {e}")

    # PAR (Pushed Authorization Request)

    def send_par_request(
        self,
        auth_metadata: Dict[str, Any],
        code_challenge: str,
        state: str,
        resource: Optional[str],
        dpop_private_key: Union[str, Dict[str, Any]],
        dpop_nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send Pushed Authorization Request.

        Args:
            auth_metadata: Authorization server metadata
            code_challenge: PKCE code challenge
            state: OAuth state parameter
            resource: Resource server URL (PDS)
            dpop_private_key: Private key data for DPoP
            dpop_nonce: DPoP nonce (optional)

        Returns:
            PAR response with 'request_uri' and 'expires_in'
        """
        par_endpoint = auth_metadata['pushed_authorization_request_endpoint']

        # Create DPoP proof
        dpop_jwt = self.create_dpop_jwt(
            private_key_data=dpop_private_key,
            htm='POST',
            htu=par_endpoint,
            nonce=dpop_nonce
        )

        # Prepare PAR parameters
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }

        if resource:
            params['resource'] = resource

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        try:
            resp = self.http_client.post(
                par_endpoint,
                data=params,
                headers=headers
            )

            # Check for DPoP nonce in response
            new_nonce = resp.headers.get('DPoP-Nonce')

            if resp.status_code in (400, 401, 428) and new_nonce:
                # Retry with new nonce
                dpop_jwt = self.create_dpop_jwt(
                    private_key_data=dpop_private_key,
                    htm='POST',
                    htu=par_endpoint,
                    nonce=new_nonce
                )
                headers['DPoP'] = dpop_jwt

                resp = self.http_client.post(
                    par_endpoint,
                    data=params,
                    headers=headers
                )
                new_nonce = resp.headers.get('DPoP-Nonce', new_nonce)

            # Check for errors and extract detailed error message
            if resp.status_code >= 400:
                error_detail = f"HTTP {resp.status_code}"
                try:
                    error_body = resp.json()
                    error_code = error_body.get('error', 'unknown_error')
                    error_desc = error_body.get('error_description', '')
                    if error_desc:
                        error_detail = f"{error_code}: {error_desc}"
                    else:
                        error_detail = error_code
                except:
                    # If JSON parsing fails, use raw text
                    error_detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
                
                raise ATProtoOAuthError(f"PAR request failed ({resp.status_code}): {error_detail}")

            par_response = resp.json()

            # Add nonce to response if present
            if new_nonce:
                par_response['dpop_nonce'] = new_nonce

            return par_response

        except ATProtoOAuthError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            raise ATProtoOAuthError(f"PAR request failed: {e}")

    def build_authorization_url(
        self,
        auth_metadata: Dict[str, Any],
        request_uri: str
    ) -> str:
        """
        Build authorization URL with request_uri from PAR.

        Args:
            auth_metadata: Authorization server metadata
            request_uri: Request URI from PAR response

        Returns:
            Complete authorization URL
        """
        auth_endpoint = auth_metadata['authorization_endpoint']
        params = {
            'client_id': self.client_id,
            'request_uri': request_uri
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    # Token Exchange

    def exchange_code_for_token(
        self,
        auth_metadata: Dict[str, Any],
        code: str,
        code_verifier: str,
        dpop_private_key: Union[str, Dict[str, Any]],
        dpop_nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.

        Args:
            auth_metadata: Authorization server metadata
            code: Authorization code
            code_verifier: PKCE code verifier
            dpop_private_key: Private key data for DPoP
            dpop_nonce: DPoP nonce (optional)

        Returns:
            Token response with access_token, refresh_token, etc.
        """
        token_endpoint = auth_metadata['token_endpoint']

        # Create DPoP proof
        dpop_jwt = self.create_dpop_jwt(
            private_key_data=dpop_private_key,
            htm='POST',
            htu=token_endpoint,
            nonce=dpop_nonce
        )

        # Prepare token request
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'code_verifier': code_verifier
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        try:
            resp = self.http_client.post(
                token_endpoint,
                data=data,
                headers=headers
            )

            # Check for DPoP nonce
            new_nonce = resp.headers.get('DPoP-Nonce')

            if resp.status_code in (400, 401, 428) and new_nonce:
                # Retry with new nonce
                dpop_jwt = self.create_dpop_jwt(
                    private_key_data=dpop_private_key,
                    htm='POST',
                    htu=token_endpoint,
                    nonce=new_nonce
                )
                headers['DPoP'] = dpop_jwt

                resp = self.http_client.post(
                    token_endpoint,
                    data=data,
                    headers=headers
                )
                new_nonce = resp.headers.get('DPoP-Nonce', new_nonce)

            resp.raise_for_status()
            token_response = resp.json()

            # Add nonce if present
            if new_nonce:
                token_response['dpop_nonce'] = new_nonce

            return token_response

        except Exception as e:
            raise ATProtoOAuthError(f"Token exchange failed: {e}")

    def refresh_access_token(
        self,
        auth_metadata: Dict[str, Any],
        refresh_token: str,
        dpop_private_key: Union[str, Dict[str, Any]],
        dpop_nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            auth_metadata: Authorization server metadata
            refresh_token: Refresh token
            dpop_private_key: Private key data for DPoP
            dpop_nonce: DPoP nonce (optional)

        Returns:
            Token response with new access_token and refresh_token
        """
        token_endpoint = auth_metadata['token_endpoint']

        # Create DPoP proof
        dpop_jwt = self.create_dpop_jwt(
            private_key_data=dpop_private_key,
            htm='POST',
            htu=token_endpoint,
            nonce=dpop_nonce
        )

        # Prepare refresh request
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'DPoP': dpop_jwt
        }

        try:
            resp = self.http_client.post(
                token_endpoint,
                data=data,
                headers=headers
            )

            # Check for DPoP nonce
            new_nonce = resp.headers.get('DPoP-Nonce')

            if resp.status_code in (400, 401, 428) and new_nonce:
                # Retry with new nonce
                dpop_jwt = self.create_dpop_jwt(
                    private_key_data=dpop_private_key,
                    htm='POST',
                    htu=token_endpoint,
                    nonce=new_nonce
                )
                headers['DPoP'] = dpop_jwt

                resp = self.http_client.post(
                    token_endpoint,
                    data=data,
                    headers=headers
                )
                new_nonce = resp.headers.get('DPoP-Nonce', new_nonce)

            resp.raise_for_status()
            token_response = resp.json()

            # Add nonce if present
            if new_nonce:
                token_response['dpop_nonce'] = new_nonce

            return token_response

        except Exception as e:
            raise ATProtoOAuthError(f"Token refresh failed: {e}")

    def revoke_token(
        self,
        auth_metadata: Dict[str, Any],
        token: str,
        token_type_hint: str = 'refresh_token',
        dpop_private_key: Optional[Union[str, Dict[str, Any]]] = None,
        dpop_nonce: Optional[str] = None
    ) -> bool:
        """
        Revoke access or refresh token.

        Args:
            auth_metadata: Authorization server metadata
            token: Token to revoke
            token_type_hint: 'access_token' or 'refresh_token'
            dpop_private_key: Private key data for DPoP (optional)
            dpop_nonce: DPoP nonce (optional)

        Returns:
            True if successful, False otherwise
        """
        revocation_endpoint = auth_metadata.get('revocation_endpoint')
        if not revocation_endpoint:
            return False  # Revocation not supported

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Add DPoP if provided
        if dpop_private_key:
            dpop_jwt = self.create_dpop_jwt(
                private_key_data=dpop_private_key,
                htm='POST',
                htu=revocation_endpoint,
                nonce=dpop_nonce
            )
            headers['DPoP'] = dpop_jwt

        data = {
            'token': token,
            'token_type_hint': token_type_hint,
            'client_id': self.client_id
        }

        try:
            resp = self.http_client.post(
                revocation_endpoint,
                data=data,
                headers=headers
            )
            return resp.status_code == 200
        except Exception:
            return False

    # Authenticated Requests

    def make_authenticated_request(
        self,
        method: str,
        url: str,
        access_token: str,
        dpop_private_key: Union[str, Dict[str, Any]],
        dpop_nonce: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make authenticated request to PDS with DPoP.

        Args:
            method: HTTP method
            url: Request URL
            access_token: OAuth access token
            dpop_private_key: Private key data for DPoP
            dpop_nonce: DPoP nonce (optional)
            **kwargs: Additional arguments for httpx request

        Returns:
            HTTP response
        """
        # Create access token hash
        ath = self.create_access_token_hash(access_token)

        # Create DPoP proof
        dpop_jwt = self.create_dpop_jwt(
            private_key_data=dpop_private_key,
            htm=method.upper(),
            htu=url,
            nonce=dpop_nonce,
            ath=ath
        )

        # Add headers
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'DPoP {access_token}'
        headers['DPoP'] = dpop_jwt

        # Make request
        resp = self.http_client.request(
            method=method,
            url=url,
            headers=headers,
            **kwargs
        )

        # Check for DPoP nonce in response
        new_nonce = resp.headers.get('DPoP-Nonce')
        if new_nonce and resp.status_code == 401:
            # Retry with new nonce
            dpop_jwt = self.create_dpop_jwt(
                private_key_data=dpop_private_key,
                htm=method.upper(),
                htu=url,
                nonce=new_nonce,
                ath=ath
            )
            headers['DPoP'] = dpop_jwt

            resp = self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )

        return resp


def generate_state() -> str:
    """Generate random OAuth state parameter."""
    return secrets.token_urlsafe(32)


def get_client_metadata(client_id: str, redirect_uri: str, scope: str = "atproto") -> Dict[str, Any]:
    """
    Generate client metadata document.

    Args:
        client_id: Client ID (HTTPS URL)
        redirect_uri: OAuth redirect URI
        scope: OAuth scope

    Returns:
        Client metadata document
    """
    return {
        "client_id": client_id,
        "client_name": "Bibliome",
        "client_uri": client_id.rsplit('/client-metadata.json', 1)[0],
        "redirect_uris": [redirect_uri],
        "scope": scope,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",  # Public client
        "application_type": "web",
        "dpop_bound_access_tokens": True
    }


# Export availability flag
__all__ = ['OAuthClient', 'ATProtoOAuthError', 'generate_state', 'get_client_metadata', 'OAUTH_AVAILABLE']
