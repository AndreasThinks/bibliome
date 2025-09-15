def get_dependencies():
    """
    Returns a dictionary representing the service dependency graph.
    """
    return {
        "firehose_ingester": ["database"],
        "bluesky_automation": ["database", "bluesky_api"],
        "bibliome_scanner": ["database", "atproto_api"],
        "database": [],
        "bluesky_api": [],
        "atproto_api": [],
    }
