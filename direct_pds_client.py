"""
AT-Proto client for fetching Bibliome records directly from user PDS.
"""
import logging
import time
from functools import lru_cache
from typing import Iterable, Union, Dict, List, Any, Tuple
from atproto import Client, IdResolver
from circuit_breaker import CircuitBreaker
from rate_limiter import RateLimiter

# Configure logging
logger = logging.getLogger(__name__)


class PDSClientPool:
    """Simple LRU-based client pool for PDS connections with TTL."""
    
    def __init__(self, max_size: int = 50, ttl_seconds: int = 300):
        """
        Initialize client pool.
        
        Args:
            max_size: Maximum number of clients to cache
            ttl_seconds: Time-to-live for cached clients (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Client, float]] = {}
        self._access_order: List[str] = []
    
    def get_client(self, pds_xrpc: str) -> Client:
        """
        Get or create a client for the given PDS endpoint.
        
        Args:
            pds_xrpc: PDS XRPC endpoint URL
            
        Returns:
            AT Protocol Client instance
        """
        current_time = time.time()
        
        # Check if we have a cached client
        if pds_xrpc in self._cache:
            client, cached_time = self._cache[pds_xrpc]
            
            # Check TTL
            if current_time - cached_time < self.ttl_seconds:
                # Move to end of access order (most recently used)
                if pds_xrpc in self._access_order:
                    self._access_order.remove(pds_xrpc)
                self._access_order.append(pds_xrpc)
                logger.debug(f"Reusing cached client for {pds_xrpc}")
                return client
            else:
                # TTL expired, remove from cache
                del self._cache[pds_xrpc]
                if pds_xrpc in self._access_order:
                    self._access_order.remove(pds_xrpc)
                logger.debug(f"Cache expired for {pds_xrpc}")
        
        # Create new client
        client = Client(pds_xrpc)
        
        # Evict oldest clients if at capacity
        while len(self._cache) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
                logger.debug(f"Evicted oldest client: {oldest_key}")
        
        # Cache the new client
        self._cache[pds_xrpc] = (client, current_time)
        self._access_order.append(pds_xrpc)
        logger.debug(f"Created and cached new client for {pds_xrpc}")
        
        return client
    
    def clear(self):
        """Clear all cached clients."""
        self._cache.clear()
        self._access_order.clear()
        logger.debug("Client pool cleared")
    
    def __len__(self) -> int:
        """Return number of cached clients."""
        return len(self._cache)


class DirectPDSClient:
    """Client for fetching Bibliome records directly from user PDS."""

    def __init__(self, rate_limiter: RateLimiter = None):
        self.resolver = IdResolver()
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.rate_limiter = rate_limiter or RateLimiter(tokens_per_second=10, max_tokens=100)
        # Use pooled client connections
        self._client_pool = PDSClientPool(max_size=50, ttl_seconds=300)

    def _ensure_xrpc(self, url: str) -> str:
        url = url.rstrip("/")
        return url if url.endswith("/xrpc") else url + "/xrpc"

    def _extract_pds_endpoint(self, did_doc: Any) -> str:
        if hasattr(did_doc, "service"):
            services = getattr(did_doc, "service") or []
        elif isinstance(did_doc, dict):
            services = (did_doc.get("service") or [])
        else:
            services = []

        for svc in services:
            typ = getattr(svc, "type", None) if not isinstance(svc, dict) else svc.get("type")
            endpoint = (
                getattr(svc, "service_endpoint", None)
                if not isinstance(svc, dict)
                else (svc.get("service_endpoint") or svc.get("serviceEndpoint"))
            )
            if typ == "AtprotoPersonalDataServer" and endpoint:
                return self._ensure_xrpc(endpoint)

        raise RuntimeError("PDS serviceEndpoint not found in DID document")

    def _resolve_did_and_pds(self, identifier: str) -> Tuple[str, str]:
        try:
            did = identifier if identifier.startswith("did:") else self.resolver.handle.resolve(identifier)
            if not isinstance(did, str) or not did.startswith("did:"):
                raise RuntimeError(f"Failed to resolve handle to DID: {identifier}")

            did_doc = self.resolver.did.resolve(did)
            if not did_doc:
                raise RuntimeError(f"Failed to resolve DID document for {did}")

            pds_xrpc = self._extract_pds_endpoint(did_doc)
            return did, pds_xrpc
        except Exception as e:
            logger.error(f"Error resolving DID and PDS for {identifier}: {e}")
            raise

    def _to_list(self, x: Union[str, Iterable[str]]) -> List[str]:
        if isinstance(x, str):
            return [x]
        return list(x)

    async def get_repo_records(
        self,
        identifier: str,
        collections: Union[str, Iterable[str]],
        *,
        page_size: int = 100,
        _client: Client = None,
    ) -> Dict[str, Any]:
        """
        Fetch *all* records for one repo (handle or DID) across one or more collections.
        Uses pooled client connections to reduce overhead.
        """
        async def _get_records():
            try:
                did, pds_xrpc = self._resolve_did_and_pds(identifier)
                # Use client pool for connection reuse
                pds = _client or self._client_pool.get_client(pds_xrpc)

                desc = pds.com.atproto.repo.describe_repo({"repo": did})
                available = set(desc.collections or [])

                wanted = self._to_list(collections)
                results: Dict[str, List[dict]] = {}
                missing: List[str] = [nsid for nsid in wanted if nsid not in available]

                for nsid in wanted:
                    if nsid not in available:
                        results[nsid] = []
                        continue

                    cursor = None
                    all_recs: List[dict] = []

                    while True:
                        params = {"repo": did, "collection": nsid, "limit": page_size}
                        if cursor:
                            params["cursor"] = cursor

                        resp = pds.com.atproto.repo.list_records(params)

                        for rec in resp.records or []:
                            uri = rec.uri
                            all_recs.append(
                                {
                                    "uri": uri,
                                    "rkey": uri.rsplit("/", 1)[-1] if uri else None,
                                    "cid": getattr(rec, "cid", None),
                                    "value": rec.value,
                                }
                            )

                        cursor = getattr(resp, "cursor", None)
                        if not cursor:
                            break

                    results[nsid] = all_recs

                return {"did": did, "pds": pds_xrpc, "collections": results, "missing": missing}
            except Exception as e:
                logger.error(f"Error getting repo records for {identifier}: {e}")
                raise
        
        return await self.rate_limiter(_get_records())
