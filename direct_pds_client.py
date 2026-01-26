"""
AT-Proto client for fetching Bibliome records directly from user PDS.

DEPRECATED: This module is kept for backward compatibility.
Use `from bibliome.clients import DirectPDSClient, ...` instead.
"""

# Re-export from the new location
from bibliome.clients.pds import (
    DirectPDSClient,
    PDSClientPool,
    PDSError,
    NonCompliantPDSError,
    TransientDIDResolutionError,
)

__all__ = [
    'DirectPDSClient',
    'PDSClientPool',
    'PDSError',
    'NonCompliantPDSError',
    'TransientDIDResolutionError',
]
