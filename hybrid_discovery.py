"""
Hybrid discovery service for finding Bibliome users.
"""
import logging
import httpx
from typing import List, Set
from direct_pds_client import DirectPDSClient

# Configure logging
logger = logging.getLogger(__name__)

class HybridDiscoveryService:
    """
    Combines relay-based discovery with direct PDS validation.
    """
    def __init__(self, pds_client: DirectPDSClient):
        self.pds_client = pds_client
        self.relays = [
            "https://relay1.us-west.bsky.network",
            "https://bsky.network",
        ]
        self.nsid_bookshelf = "com.bibliome.bookshelf"

    async def discover_users(self, batch_size: int = 1000) -> List[str]:
        """
        Discover DIDs that have published Bibliome records.
        """
        all_dids: Set[str] = set()
        processed_relays: Set[str] = set()

        for base in self.relays:
            if base in processed_relays:
                continue
            
            logger.info(f"Discovering users from relay: {base}")
            try:
                cursor = None
                while True:
                    params = {"collection": self.nsid_bookshelf, "limit": str(batch_size)}
                    if cursor:
                        params["cursor"] = cursor
                    
                    url = f"{base}/xrpc/com.atproto.sync.listReposByCollection"
                    async with httpx.AsyncClient(timeout=60) as http_client:
                        r = await http_client.get(url, params=params)
                    
                    if r.status_code == 404:
                        logger.warning(f"Relay {base} does not support listReposByCollection.")
                        break
                    r.raise_for_status()
                    
                    data = r.json()
                    for entry in data.get("repos", []):
                        all_dids.add(entry["did"])
                    
                    new_cursor = data.get("cursor")
                    if not new_cursor or new_cursor == cursor:
                        processed_relays.add(base)
                        break
                    cursor = new_cursor
            except Exception as e:
                logger.error(f"Relay {base} failed during discovery: {e}", exc_info=True)
                continue
        
        logger.info(f"Total unique Bibliome users discovered: {len(all_dids)}")
        return list(all_dids)
