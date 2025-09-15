"""
Hybrid discovery service for finding Bibliome users (robust v2).
"""
import asyncio
import logging
from typing import Iterable, List, Set, Dict, Any, Optional
import httpx

from direct_pds_client import DirectPDSClient

logger = logging.getLogger(__name__)

LIST_BY_COLLECTION = "com.atproto.sync.listReposByCollection"
LIST_REPOS = "com.atproto.sync.listRepos"
LIST_HOSTS = "com.atproto.sync.listHosts"
LIST_RECORDS = "com.atproto.repo.listRecords"
DESCRIBE_REPO = "com.atproto.repo.describeRepo"  # for sanity checks if needed

class HybridDiscoveryService:
    """
    Combines relay-based discovery with direct PDS validation.
    """
    def __init__(
        self,
        pds_client: Optional[DirectPDSClient] = None,
        nsid_bookshelf: str = "com.bibliome.bookshelf",
    ):
        
        
        self.pds_client = pds_client
        self.nsid_bookshelf = nsid_bookshelf

        if not isinstance(self.nsid_bookshelf, str) or "." not in self.nsid_bookshelf:
            raise TypeError(
                "nsid_bookshelf must be an NSID string like 'com.bibliome.bookshelf'"
            )
        self.nsid_bookshelf = nsid_bookshelf

        # Use BOTH new relays; keep legacy as a best-effort fallback.
        self.relays = [
            "https://relay1.us-west.bsky.network",
            "https://relay1.us-east.bsky.network",
            "https://bsky.network",  # soft fallback
        ]

        # Single shared client; enable HTTP/2 and sane limits.
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            http2=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

    async def _get_json(self, base: str, xrpc: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = f"{base}/xrpc/{xrpc}"
        # simple retry/backoff
        delay = 0.5
        for attempt in range(5):
            try:
                r = await self.client.get(url, params=params)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 6)
                    continue
                raise
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError):
                await asyncio.sleep(delay)
                delay = min(delay * 2, 6)
        logger.warning(f"Giving up on {url}")
        return None

    async def _page_list_by_collection(self, base: str, limit: int = 1000) -> Set[str]:
        dids: Set[str] = set()
        cursor: Optional[str] = None
        while True:
            params = {"collection": self.nsid_bookshelf, "limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            data = await self._get_json(base, LIST_BY_COLLECTION, params)
            if not data:
                break
            for entry in data.get("repos", []):
                did = entry.get("did")
                if did:
                    dids.add(did)
            new_cursor = data.get("cursor")
            if not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor
        return dids

    async def _list_hosts(self, base: str) -> List[str]:
        data = await self._get_json(base, LIST_HOSTS, {})
        if not data:
            return []
        # typical shape: {"hosts": [{"host": "https://pds.foo"}, ...], "cursor": "..."}
        hosts = [h["host"] for h in data.get("hosts", []) if "host" in h]
        return hosts

    async def _pds_list_by_collection_or_fallback(self, pds_base: str, limit: int = 1000) -> Set[str]:
        """
        Try PDS listReposByCollection; if not implemented, fall back to listRepos + targeted listRecords.
        """
        dids: Set[str] = set()

        # Try the fast path.
        fast = await self._page_list_by_collection(pds_base, limit=limit)
        if fast:
            return fast

        # Fallback: listRepos then test listRecords per did (limit=1).
        # This stays within the PDS boundary (no relay assumptions).
        cursor: Optional[str] = None
        while True:
            params = {"limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            data = await self._get_json(pds_base, LIST_REPOS, params)
            if not data:
                break
            repos = data.get("repos", [])
            async def check_repo(repo: Dict[str, Any]) -> Optional[str]:
                did = repo.get("did")
                if not did:
                    return None
                params = {"repo": did, "collection": self.nsid_bookshelf, "limit": "1"}
                recs = await self._get_json(pds_base, LIST_RECORDS, params)
                if recs and recs.get("records"):
                    return did
                return None

            # Limit concurrency to avoid hammering.
            sem = asyncio.Semaphore(20)
            async def guarded(repo):
                async with sem:
                    return await check_repo(repo)

            results = await asyncio.gather(*[guarded(r) for r in repos], return_exceptions=True)
            for res in results:
                if isinstance(res, str):
                    dids.add(res)

            new_cursor = data.get("cursor")
            if not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor

        return dids

    async def discover_users(self, batch_size: int = 1000) -> List[str]:
        """
        Discover DIDs that have published Bibliome records by querying:
        1) relays (listReposByCollection),
        2) relay->PDS (listHosts) then PDS (listReposByCollection or fallback),
        and de-duplicating.
        """
        all_dids: Set[str] = set()

        # 1) Relay sweeps
        for relay in self.relays:
            logger.info(f"[relay] {relay} listReposByCollection {self.nsid_bookshelf}")
            try:
                dids = await self._page_list_by_collection(relay, limit=batch_size)
                all_dids.update(dids)
            except Exception:
                logger.exception(f"Relay sweep failed for {relay}")

        # 2) Discover PDS hosts from each relay and sweep PDS
        pds_hosts: Set[str] = set()
        for relay in self.relays:
            try:
                hosts = await self._list_hosts(relay)
                pds_hosts.update(hosts)
            except Exception:
                logger.exception(f"listHosts failed for {relay}")

        # Normalize host bases (ensure scheme)
        norm_hosts = []
        for h in pds_hosts:
            if h.startswith("http://") or h.startswith("https://"):
                norm_hosts.append(h.rstrip("/"))
            else:
                norm_hosts.append(f"https://{h}".rstrip("/"))

        # Concurrency for PDS sweep
        sem = asyncio.Semaphore(12)
        async def sweep_pds(base: str) -> Set[str]:
            async with sem:
                try:
                    logger.info(f"[pds] {base} sweep for {self.nsid_bookshelf}")
                    return await self._pds_list_by_collection_or_fallback(base, limit=batch_size)
                except Exception:
                    logger.exception(f"PDS sweep failed for {base}")
                    return set()

        pds_results = await asyncio.gather(*[sweep_pds(b) for b in norm_hosts])
        for s in pds_results:
            all_dids.update(s)

        logger.info(f"Total unique Bibliome users discovered: {len(all_dids)}")
        return sorted(all_dids)

    async def aclose(self):
        await self.client.aclose()
