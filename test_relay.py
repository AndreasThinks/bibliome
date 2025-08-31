import httpx

NSID = "com.bibliome.bookshelf"
RELAYS = [
    "https://relay1.us-west.bsky.network",
    "https://bsky.network",  # may 404 depending on migration state
]

def discover_by_collection(limit=100):
    last_err = None
    for base in RELAYS:
        try:
            cursor = None
            while True:
                params = {"collection": NSID, "limit": str(limit)}
                if cursor:
                    params["cursor"] = cursor
                r = httpx.get(f"{base}/xrpc/com.atproto.sync.listReposByCollection",
                              params=params, timeout=30)
                if r.status_code == 404:
                    # host doesn't implement it; try next relay
                    break
                r.raise_for_status()
                data = r.json()
                for entry in data.get("repos", []):
                    yield entry["did"]
                cursor = data.get("cursor")
                if not cursor:
                    return
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise RuntimeError("No relay with listReposByCollection available") from last_err

dids = list(discover_by_collection())
print(dids)
