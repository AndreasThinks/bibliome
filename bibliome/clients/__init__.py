"""
Bibliome API Clients Package.

This package provides client interfaces for external APIs:
- BookAPIClient: Google Books and Open Library APIs
- DirectPDSClient: AT Protocol PDS record fetching
- PDSClientPool: Connection pooling for PDS clients
"""

# Book metadata clients
from .books import BookAPIClient

# PDS/AT Protocol clients
from .pds import (
    DirectPDSClient,
    PDSClientPool,
    PDSError,
    NonCompliantPDSError,
    TransientDIDResolutionError,
)

__all__ = [
    # Book clients
    'BookAPIClient',
    
    # PDS clients
    'DirectPDSClient',
    'PDSClientPool',
    
    # Exceptions
    'PDSError',
    'NonCompliantPDSError',
    'TransientDIDResolutionError',
]
