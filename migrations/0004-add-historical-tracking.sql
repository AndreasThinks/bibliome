-- Migration 0004: Add historical tracking and profile discovery system
-- This enables background scanning of AT Protocol user repositories for historical data

-- Profile tracking for historical data discovery
CREATE TABLE IF NOT EXISTS tracked_profiles (
    did TEXT PRIMARY KEY,
    handle TEXT,
    display_name TEXT,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    discovery_source TEXT NOT NULL, -- 'user', 'follows', 'network'
    last_scanned_at DATETIME,
    scan_priority INTEGER DEFAULT 1, -- 1=high, 2=medium, 3=low  
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT
);

-- Queue for historical scanning jobs
CREATE TABLE IF NOT EXISTS historical_scan_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_did TEXT NOT NULL,
    collection_type TEXT NOT NULL, -- 'bookshelf', 'book', 'both'
    priority INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (profile_did) REFERENCES tracked_profiles (did)
);

-- Add source tracking to existing tables
ALTER TABLE bookshelves ADD COLUMN data_source TEXT DEFAULT 'local'; -- 'local', 'network', 'historical'
ALTER TABLE books ADD COLUMN data_source TEXT DEFAULT 'local';
ALTER TABLE users ADD COLUMN data_source TEXT DEFAULT 'local';

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_tracked_profiles_priority ON tracked_profiles (scan_priority, last_scanned_at);
CREATE INDEX IF NOT EXISTS idx_scan_queue_status ON historical_scan_queue (status, priority);
CREATE INDEX IF NOT EXISTS idx_bookshelves_source ON bookshelves (data_source);
CREATE INDEX IF NOT EXISTS idx_books_source ON books (data_source);

-- Update existing records to have 'local' data source by default
UPDATE bookshelves SET data_source = 'local' WHERE data_source IS NULL;
UPDATE books SET data_source = 'local' WHERE data_source IS NULL;
UPDATE users SET data_source = 'local' WHERE data_source IS NULL;
