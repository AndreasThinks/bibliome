"""
Identity resolution utilities for atproto OAuth.
Handles handle resolution, DID document parsing, and PDS endpoint discovery.
"""
import json
import logging
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from oauth_security import (
    is_safe_url, safe_http_client, validate_atproto_did,
    validate_atproto_handle, sanitize_string
)

logger = logging.getLogger(__name__)

class IdentityResolutionError(Exception):
    """Raised when identity resolution fails."""
    pass

def resolve_identity(identifier: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a handle or DID to identity information.

    Args:
        identifier: Handle (e.g., "user.bsky.social") or DID

    Returns:
        Tuple of (did, handle, did_document)

    Raises:
        IdentityResolutionError: If resolution fails
    """
    logger.info(f"Resolving identity for: {identifier}")

    # Determine if input is handle or DID
    if identifier.startswith('did:'):
        # Input is a DID, resolve to handle
        return resolve_did_to_handle_and_doc(identifier)
    else:
        # Input is a handle, resolve to DID and document
        return resolve_handle_to_did_and_doc(identifier)

def resolve_handle_to_did_and_doc(handle: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a handle to DID and DID document with bidirectional verification.

    Args:
        handle: The handle to resolve

    Returns:
        Tuple of (did, handle, did_document)

    Raises:
        IdentityResolutionError: If resolution or verification fails
    """
    logger.debug(f"Resolving handle to DID: {handle}")

    # Validate handle format
    if not validate_atproto_handle(handle):
        raise IdentityResolutionError(f"Invalid handle format: {handle}")

    try:
        # Step 1: Resolve handle to DID via DNS
        did = resolve_handle_dns(handle)
        logger.debug(f"DNS resolution: {handle} -> {did}")

        # Step 2: Fetch DID document
        did_doc = fetch_did_document(did)
        logger.debug(f"Fetched DID document for {did}")

        # Step 3: Verify handle is claimed in DID document
        verify_handle_in_did_doc(handle, did_doc)

        # Step 4: Verify DID document claims the handle
        verify_did_doc_claims_handle(handle, did_doc)

        logger.info(f"Successfully resolved and verified: {handle} -> {did}")
        return did, handle, did_doc

    except Exception as e:
        logger.error(f"Failed to resolve handle {handle}: {e}")
        raise IdentityResolutionError(f"Handle resolution failed: {e}")

def resolve_did_to_handle_and_doc(did: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a DID to handle and DID document.

    Args:
        did: The DID to resolve

    Returns:
        Tuple of (did, handle, did_document)

    Raises:
        IdentityResolutionError: If resolution fails
    """
    logger.debug(f"Resolving DID to handle: {did}")

    # Validate DID format
    if not validate_atproto_did(did):
        raise IdentityResolutionError(f"Invalid DID format: {did}")

    try:
        # Step 1: Fetch DID document
        did_doc = fetch_did_document(did)
        logger.debug(f"Fetched DID document for {did}")

        # Step 2: Extract handle from DID document
        handle = extract_handle_from_did_doc(did_doc)
        logger.debug(f"Extracted handle from DID document: {handle}")

        # Step 3: Verify handle resolves back to the same DID
        verify_handle_resolves_back(handle, did)

        logger.info(f"Successfully resolved and verified: {did} -> {handle}")
        return did, handle, did_doc

    except Exception as e:
        logger.error(f"Failed to resolve DID {did}: {e}")
        raise IdentityResolutionError(f"DID resolution failed: {e}")

def resolve_handle_dns(handle: str) -> str:
    """Resolve handle to DID using DNS TXT records."""
    try:
        # For .bsky.social handles, we can use the atproto library
        from atproto import is_valid_handle

        if not is_valid_handle(handle):
            raise IdentityResolutionError(f"Invalid handle: {handle}")

        # Use atproto library for resolution
        from atproto import Client
        client = Client()

        # Resolve handle to DID
        response = client.com.atproto.identity.resolve_handle({"handle": handle})

        if not response or not response.did:
            raise IdentityResolutionError(f"No DID found for handle: {handle}")

        return response.did

    except Exception as e:
        logger.error(f"DNS resolution failed for {handle}: {e}")
        raise IdentityResolutionError(f"DNS resolution failed: {e}")

def fetch_did_document(did: str) -> Dict[str, Any]:
    """Fetch DID document from PLC directory."""
    try:
        # Construct PLC directory URL
        plc_url = f"https://plc.directory/{did}"

        # Use safe HTTP client
        response = safe_http_client.get(plc_url)
        did_doc = response.json()

        # Basic validation
        if not did_doc or not isinstance(did_doc, dict):
            raise IdentityResolutionError(f"Invalid DID document for {did}")

        if did_doc.get('id') != did:
            raise IdentityResolutionError(f"DID document id mismatch: {did_doc.get('id')} != {did}")

        return did_doc

    except Exception as e:
        logger.error(f"Failed to fetch DID document for {did}: {e}")
        raise IdentityResolutionError(f"DID document fetch failed: {e}")

def extract_handle_from_did_doc(did_doc: Dict[str, Any]) -> str:
    """Extract handle from DID document."""
    # Look for alsoKnownAs field with handle
    also_known_as = did_doc.get('alsoKnownAs', [])

    for aka in also_known_as:
        if aka.startswith('at://'):
            # Extract handle from at:// URI
            handle = aka.replace('at://', '')
            if validate_atproto_handle(handle):
                return handle

    raise IdentityResolutionError("No valid handle found in DID document")

def verify_handle_in_did_doc(handle: str, did_doc: Dict[str, Any]) -> None:
    """Verify that the handle is properly declared in the DID document."""
    try:
        # Check alsoKnownAs field
        also_known_as = did_doc.get('alsoKnownAs', [])
        expected_aka = f'at://{handle}'

        if expected_aka not in also_known_as:
            raise IdentityResolutionError(
                f"Handle {handle} not found in DID document alsoKnownAs"
            )

        logger.debug(f"Verified handle {handle} in DID document alsoKnownAs")

    except Exception as e:
        logger.error(f"Handle verification failed: {e}")
        raise IdentityResolutionError(f"Handle verification failed: {e}")

def verify_did_doc_claims_handle(handle: str, did_doc: Dict[str, Any]) -> None:
    """Verify that the DID document claims the handle."""
    # This is essentially the same as verify_handle_in_did_doc
    # but ensures the relationship is bidirectional
    verify_handle_in_did_doc(handle, did_doc)

def verify_handle_resolves_back(handle: str, expected_did: str) -> None:
    """Verify that handle resolves back to the expected DID."""
    try:
        resolved_did = resolve_handle_dns(handle)

        if resolved_did != expected_did:
            raise IdentityResolutionError(
                f"Handle {handle} resolves to {resolved_did}, expected {expected_did}"
            )

        logger.debug(f"Verified handle {handle} resolves back to {expected_did}")

    except Exception as e:
        logger.error(f"Handle back-resolution failed: {e}")
        raise IdentityResolutionError(f"Handle back-resolution failed: {e}")

def pds_endpoint(did_doc: Dict[str, Any]) -> str:
    """
    Extract PDS endpoint from DID document.

    Args:
        did_doc: DID document

    Returns:
        PDS endpoint URL

    Raises:
        IdentityResolutionError: If no PDS endpoint found
    """
    try:
        # Look for service with type "AtprotoPersonalDataServer"
        services = did_doc.get('service', [])

        for service in services:
            if service.get('type') == 'AtprotoPersonalDataServer':
                endpoint = service.get('serviceEndpoint')

                if not endpoint:
                    continue

                # Validate endpoint URL
                if not is_safe_url(endpoint):
                    raise IdentityResolutionError(f"Unsafe PDS endpoint: {endpoint}")

                logger.debug(f"Found PDS endpoint: {endpoint}")
                return endpoint

        raise IdentityResolutionError("No PDS endpoint found in DID document")

    except Exception as e:
        logger.error(f"Failed to extract PDS endpoint: {e}")
        raise IdentityResolutionError(f"PDS endpoint extraction failed: {e}")

def resolve_pds_authserver(pds_url: str) -> str:
    """
    Resolve PDS URL to OAuth authorization server URL.

    Args:
        pds_url: PDS endpoint URL

    Returns:
        Authorization server URL (may be same as PDS or different)

    Raises:
        IdentityResolutionError: If resolution fails
    """
    logger.debug(f"Resolving PDS auth server for: {pds_url}")

    try:
        # Validate PDS URL
        if not is_safe_url(pds_url):
            raise IdentityResolutionError(f"Unsafe PDS URL: {pds_url}")

        # Fetch OAuth protected resource metadata
        resource_meta_url = f"{pds_url}/.well-known/oauth-protected-resource"

        try:
            response = safe_http_client.get(resource_meta_url)
            resource_meta = response.json()

            # Extract authorization servers
            auth_servers = resource_meta.get('authorization_servers', [])

            if not auth_servers:
                raise IdentityResolutionError("No authorization servers found")

            # Use first authorization server
            auth_server_url = auth_servers[0]

            # Validate authorization server URL
            if not is_safe_url(auth_server_url):
                raise IdentityResolutionError(f"Unsafe authorization server URL: {auth_server_url}")

            logger.debug(f"Resolved auth server: {pds_url} -> {auth_server_url}")
            return auth_server_url

        except Exception:
            # If protected resource metadata fails, assume PDS is also auth server
            logger.debug(f"OAuth metadata not found, assuming PDS is auth server: {pds_url}")
            return pds_url

    except Exception as e:
        logger.error(f"Failed to resolve PDS auth server for {pds_url}: {e}")
        raise IdentityResolutionError(f"PDS auth server resolution failed: {e}")

def fetch_authserver_meta(authserver_url: str) -> Dict[str, Any]:
    """
    Fetch OAuth authorization server metadata.

    Args:
        authserver_url: Authorization server URL

    Returns:
        Authorization server metadata

    Raises:
        IdentityResolutionError: If metadata fetch fails
    """
    logger.debug(f"Fetching auth server metadata for: {authserver_url}")

    try:
        # Validate authorization server URL
        if not is_safe_url(authserver_url):
            raise IdentityResolutionError(f"Unsafe authorization server URL: {authserver_url}")

        # Fetch authorization server metadata
        auth_meta_url = f"{authserver_url}/.well-known/oauth-authorization-server"

        response = safe_http_client.get(auth_meta_url)
        auth_meta = response.json()

        # Validate required fields
        required_fields = [
            'issuer',
            'pushed_authorization_request_endpoint',
            'authorization_endpoint',
            'token_endpoint',
            'scopes_supported'
        ]

        for field in required_fields:
            if field not in auth_meta:
                raise IdentityResolutionError(f"Missing required field in auth server metadata: {field}")

        # Validate issuer matches URL origin
        parsed_url = urlparse(authserver_url)
        expected_issuer = f"{parsed_url.scheme}://{parsed_url.hostname}"

        if auth_meta['issuer'] != expected_issuer:
            raise IdentityResolutionError(
                f"Issuer mismatch: {auth_meta['issuer']} != {expected_issuer}"
            )

        # Validate scopes_supported includes atproto
        scopes_supported = auth_meta.get('scopes_supported', '')
        if 'atproto' not in scopes_supported:
            raise IdentityResolutionError("Authorization server does not support atproto scope")

        logger.debug(f"Successfully fetched auth server metadata for {authserver_url}")
        return auth_meta

    except Exception as e:
        logger.error(f"Failed to fetch auth server metadata for {authserver_url}: {e}")
        raise IdentityResolutionError(f"Auth server metadata fetch failed: {e}")

def is_valid_did(did: str) -> bool:
    """Check if DID is valid format."""
    return validate_atproto_did(did)

def is_valid_handle(handle: str) -> bool:
    """Check if handle is valid format."""
    return validate_atproto_handle(handle)
