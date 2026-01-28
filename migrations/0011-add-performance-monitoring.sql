-- Migration to add performance monitoring tables
-- Created: 2026-01-28

-- Table to track request performance metrics
CREATE TABLE IF NOT EXISTS request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET',
    status_code INTEGER,
    duration_ms REAL NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_did TEXT,
    request_size INTEGER,
    response_size INTEGER
);

-- Table to track slow database queries
CREATE TABLE IF NOT EXISTS query_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type TEXT NOT NULL,  -- 'select', 'insert', 'update', 'delete'
    query_name TEXT,  -- friendly name like 'get_public_shelves'
    duration_ms REAL NOT NULL,
    row_count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    caller TEXT  -- function name that executed the query
);

-- Table to track external API call performance
CREATE TABLE IF NOT EXISTS api_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,  -- 'google_books', 'bluesky', 'open_library'
    endpoint TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    status_code INTEGER,
    success INTEGER NOT NULL DEFAULT 1,  -- 1 = success, 0 = failure
    error_message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance and querying
CREATE INDEX IF NOT EXISTS idx_request_metrics_route ON request_metrics(route);
CREATE INDEX IF NOT EXISTS idx_request_metrics_timestamp ON request_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_request_metrics_duration ON request_metrics(duration_ms);

CREATE INDEX IF NOT EXISTS idx_query_metrics_name ON query_metrics(query_name);
CREATE INDEX IF NOT EXISTS idx_query_metrics_timestamp ON query_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_metrics_duration ON query_metrics(duration_ms);

CREATE INDEX IF NOT EXISTS idx_api_metrics_service ON api_metrics(service);
CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON api_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_metrics_duration ON api_metrics(duration_ms);
