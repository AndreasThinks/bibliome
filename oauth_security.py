"""
Security utilities for atproto OAuth implementation.
Provides SSRF protection, URL validation, and safe HTTP client.
"""
import re
import socket
import ipaddress
import httpx
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Raised when security validation fails."""
    pass

class SSRFProtection:
    """Protect against Server-Side Request Forgery attacks."""

    # Block these IP ranges (RFC 1918 + others)
    BLOCKED_IP_RANGES = [
        '0.0.0.0/8',           # "This" network
        '10.0.0.0/8',          # Private network
        '127.0.0.0/8',         # Loopback
        '169.254.0.0/16',      # Link-local
        '172.16.0.0/12',       # Private network
        '192.168.0.0/16',      # Private network
        '224.0.0.0/4',         # Multicast
        '240.0.0.0/4',         # Reserved
        '255.255.255.255/32',  # Broadcast
        '::/128',              # IPv6 loopback
        '::1/128',             # IPv6 loopback
        'fc00::/7',            # IPv6 private
        'fe80::/10',           # IPv6 link-local
    ]

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Check if an IP address is in a blocked range."""
        try:
            ip = ipaddress.ip_address(ip_str)
            for blocked_range in cls.BLOCKED_IP_RANGES:
                if '/' in blocked_range:
                    network = ipaddress.ip_network(blocked_range, strict=False)
                else:
                    network = ipaddress.ip_network(f"{blocked_range}/32")

                if ip in network:
                    return True
        except ValueError:
            # Invalid IP, treat as blocked for safety
            return True
        return False

    @classmethod
    def resolve_hostname_safely(cls, hostname: str) -> Optional[str]:
        """Safely resolve hostname to IP, checking for blocked ranges."""
        try:
            # Validate hostname format
            if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
                raise SecurityError(f"Invalid hostname format: {hostname}")

            # Resolve to IP
            ip = socket.gethostbyname(hostname)

            # Check if IP is blocked
            if cls.is_ip_blocked(ip):
                raise SecurityError(f"Hostname resolves to blocked IP: {hostname} -> {ip}")

            logger.debug(f"Hostname {hostname} safely resolved to {ip}")
            return ip

        except socket.gaierror as e:
            raise SecurityError(f"Failed to resolve hostname {hostname}: {e}")
        except Exception as e:
            raise SecurityError(f"Security check failed for {hostname}: {e}")

def is_safe_url(url: str, allowed_schemes: tuple = ('https',)) -> bool:
    """
    Validate URL for safety (no SSRF, proper scheme, etc.).

    Args:
        url: URL to validate
        allowed_schemes: Tuple of allowed URL schemes

    Returns:
        True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in allowed_schemes:
            logger.warning(f"URL scheme not allowed: {parsed.scheme}")
            return False

        # Check hostname
        if not parsed.hostname:
            logger.warning("URL missing hostname")
            return False

        # For HTTPS URLs, check if hostname resolves to safe IP
        if parsed.scheme == 'https':
            SSRFProtection.resolve_hostname_safely(parsed.hostname)

        # Additional checks
        if parsed.port and parsed.port not in (80, 443, None):
            logger.warning(f"Non-standard port detected: {parsed.port}")
            # Allow non-standard ports for now, but log

        return True

    except SecurityError as e:
        logger.warning(f"Security validation failed for URL {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error validating URL {url}: {e}")
        return False

class SafeHTTPClient:
    """HTTP client with security protections and timeouts."""

    def __init__(self, timeout: float = 10.0, max_redirects: int = 5):
        self.timeout = timeout
        self.max_redirects = max_redirects

        # Create client with security settings
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            max_redirects=max_redirects,
            headers={
                'User-Agent': 'Bibliome/1.0 (atproto-oauth-client)'
            }
        )

    def get(self, url: str) -> httpx.Response:
        """Make safe GET request."""
        if not is_safe_url(url):
            raise SecurityError(f"Unsafe URL: {url}")

        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise SecurityError(f"Request timeout for URL: {url}")
        except httpx.ConnectError as e:
            raise SecurityError(f"Connection failed for URL {url}: {e}")

    def post(self, url: str, json: Dict[str, Any] = None, data: Dict[str, Any] = None) -> httpx.Response:
        """Make safe POST request."""
        if not is_safe_url(url):
            raise SecurityError(f"Unsafe URL: {url}")

        try:
            response = self.client.post(url, json=json, data=data)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise SecurityError(f"Request timeout for URL: {url}")
        except httpx.ConnectError as e:
            raise SecurityError(f"Connection failed for URL {url}: {e}")

    def close(self):
        """Close the HTTP client."""
        self.client.close()

def validate_atproto_did(did: str) -> bool:
    """Validate atproto DID format."""
    if not did or not isinstance(did, str):
        return False

    # DID format: did:method:method-specific-id
    did_pattern = r'^did:[a-z0-9]+:[a-zA-Z0-9._-]+$'
    return bool(re.match(did_pattern, did))

def validate_atproto_handle(handle: str) -> bool:
    """Validate atproto handle format."""
    if not handle or not isinstance(handle, str):
        return False

    # Handle format: must be valid domain-like string
    handle_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(handle_pattern, handle))

def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input."""
    if not isinstance(value, str):
        return ""

    # Remove null bytes and control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', value)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized.strip()

# Global HTTP client instance
safe_http_client = SafeHTTPClient()
