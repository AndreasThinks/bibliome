"""AT-Proto client for fetching Bibliome records."""
import httpx
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
from atproto import Client, models

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

    async def discover_bibliome_users(self, limit: int = 100) -> List[str]:
        """Discover DIDs that have published Bibliome records."""
        last_err = None
        all_dids = set()

        for base in self.relays:
            try:
                cursor = None
                while True:
                    params = {"collection": self.nsid_bookshelf, "limit": str(limit)}
                    if cursor:
                        params["cursor"] = cursor
                    
                    url = f"{base}/xrpc/com.atproto.sync.listReposByCollection"
                    async with httpx.AsyncClient(timeout=30) as http_client:
                        r = await http_client.get(url, params=params)
                    
                    if r.status_code == 404:
                        break 
                    r.raise_for_status()
                    
                    data = r.json()
                    for entry in data.get("repos", []):
                        all_dids.add(entry["did"])
                    
                    cursor = data.get("cursor")
                    if not cursor:
                        return list(all_dids)
            except Exception as e:
                logger.warning(f"Relay {base} failed for listReposByCollection: {e}")
                last_err = e
                continue
        
        if not all_dids and last_err:
            raise RuntimeError("No relays with listReposByCollection available") from last_err
            
        return list(all_dids)

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

    async def get_all_records(self, did: str, collection_nsid: str) -> List[Dict[str, Any]]:
        """Get all records of a specific type from a user's repo."""
        records = []
        try:
            cursor = None
            while True:
                response = self.client.com.atproto.repo.list_records(
                    models.ComAtprotoRepoListRecords.Data(
                        repo=did,
                        collection=collection_nsid,
                        limit=100,
                        cursor=cursor
                    )
                )
                if not response.records:
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
