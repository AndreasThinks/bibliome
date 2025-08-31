"""AT-Proto client for fetching Bibliome records."""
import httpx
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
from atproto import Client, models
from fastcore.xtras import flexicache, time_policy

# Configure logging
logger = logging.getLogger(__name__)

class BiblioMeATProtoClient:
    """Client for fetching Bibliome records from the AT-Proto network."""
    
    def __init__(self, client: Client = None):
        self.relays = [
            "https://relay1.us-west.bsky.network",
            "https://bsky.network",
        ]
        self.nsid_bookshelf = "com.bibliome.bookshelf"
        self.nsid_book = "com.bibliome.book"
        self.client = client or Client()

    @flexicache(time_policy(1800))  # Cache for 30 minutes
    async def discover_bibliome_users(self, batch_size: int = 1000) -> List[str]:
        """Discover DIDs that have published Bibliome records, paginating through all users."""
        last_err = None
        all_dids = set()
        processed_relays = set()

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
                    discovered_count = len(data.get("repos", []))
                    logger.info(f"Found {discovered_count} users in this batch from {base}.")
                    
                    for entry in data.get("repos", []):
                        all_dids.add(entry["did"])
                    
                    cursor = data.get("cursor")
                    if not cursor or discovered_count == 0:
                        logger.info(f"Finished scanning relay {base}.")
                        processed_relays.add(base)
                        break # Move to the next relay
            except Exception as e:
                logger.error(f"Relay {base} failed during discovery: {e}", exc_info=True)
                last_err = e
                continue
        
        if not all_dids and last_err:
            raise RuntimeError("All relays failed during user discovery.") from last_err
            
        logger.info(f"Total unique Bibliome users discovered across all relays: {len(all_dids)}")
        return list(all_dids)

    @flexicache(time_policy(7200))  # Cache for 2 hours
    async def get_user_profile(self, did: str) -> Optional[Dict[str, Any]]:
        """Get a user's profile information from their DID."""
        try:
            profile = self.client.get_profile(did)
            if profile:
                return {
                    "did": profile.did,
                    "handle": profile.handle,
                    "display_name": profile.display_name,
                    "avatar_url": profile.avatar,
                }
        except Exception as e:
            logger.error(f"Failed to get profile for DID {did}: {e}")
        return None

    @flexicache(time_policy(900))  # Cache for 15 minutes
    async def get_all_records(self, did: str, collection_nsid: str) -> List[Dict[str, Any]]:
        """Get all records of a specific type from a user's repo."""
        records = []
        try:
            # We don't need to resolve the PDS, the client should handle it.
            # The key is to use a client that is NOT authenticated with our own credentials
            # when looking at other people's data.
            client = Client()

            cursor = None
            while True:
                params = models.ComAtprotoRepoListRecords.Params(
                    repo=did,
                    collection=collection_nsid,
                    limit=100,
                    cursor=cursor
                )
                response = client.com.atproto.repo.list_records(params)

                if not response or not response.records:
                    break
                
                for record in response.records:
                    records.append({
                        "uri": record.uri,
                        "cid": str(record.cid),
                        "value": record.value,
                        "rkey": record.uri.split('/')[-1]
                    })
                
                cursor = response.cursor
                if not cursor:
                    break
        except Exception as e:
            # A 400 error often means the collection doesn't exist for this user, which is normal.
            if 'Bad Request' not in str(e):
                logger.error(f"Error listing records for {did} in {collection_nsid}: {e}")
        return records

    async def get_user_bookshelves(self, did: str) -> List[Dict[str, Any]]:
        """Get all bookshelf records for a user."""
        return await self.get_all_records(did, self.nsid_bookshelf)

    async def get_user_books(self, did: str) -> List[Dict[str, Any]]:
        """Get all book records for a user."""
        return await self.get_all_records(did, self.nsid_book)
