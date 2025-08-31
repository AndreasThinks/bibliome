-- Migration to add remote origin tracking to existing tables
-- This allows the app to store and manage data discovered from the AT-Proto network
-- while distinguishing it from locally created content.

-- Add remote tracking columns to the 'user' table
ALTER TABLE user ADD COLUMN is_remote BOOLEAN DEFAULT 0;
ALTER TABLE user ADD COLUMN discovered_at DATETIME;
ALTER TABLE user ADD COLUMN last_seen_remote DATETIME;
ALTER TABLE user ADD COLUMN remote_sync_status TEXT DEFAULT 'local';

-- Add remote tracking columns to the 'bookshelf' table
ALTER TABLE bookshelf ADD COLUMN is_remote BOOLEAN DEFAULT 0;
ALTER TABLE bookshelf ADD COLUMN remote_owner_did TEXT;
ALTER TABLE bookshelf ADD COLUMN discovered_at DATETIME;
ALTER TABLE bookshelf ADD COLUMN last_synced DATETIME;
ALTER TABLE bookshelf ADD COLUMN remote_sync_status TEXT DEFAULT 'local';
ALTER TABLE bookshelf ADD COLUMN original_atproto_uri TEXT;

-- Add remote tracking columns to the 'book' table
ALTER TABLE book ADD COLUMN is_remote BOOLEAN DEFAULT 0;
ALTER TABLE book ADD COLUMN remote_added_by_did TEXT;
ALTER TABLE book ADD COLUMN discovered_at DATETIME;
ALTER TABLE book ADD COLUMN original_atproto_uri TEXT;
ALTER TABLE book ADD COLUMN remote_sync_status TEXT DEFAULT 'local';

-- Create a new table to log synchronization activities
CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL, -- e.g., 'user', 'bookshelf', 'book'
    target_id TEXT NOT NULL, -- The DID or URI of the synced record
    action TEXT NOT NULL,    -- e.g., 'discovered', 'imported', 'updated', 'failed'
    details TEXT DEFAULT '', -- JSON string for additional context
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes to optimize queries related to remote records
CREATE INDEX idx_user_is_remote ON user(is_remote);
CREATE INDEX idx_bookshelf_is_remote ON bookshelf(is_remote);
CREATE UNIQUE INDEX idx_bookshelf_original_uri ON bookshelf(original_atproto_uri);
CREATE INDEX idx_book_is_remote ON book(is_remote);
CREATE UNIQUE INDEX idx_book_original_uri ON book(original_atproto_uri);
CREATE INDEX idx_sync_log_type_timestamp ON sync_log(sync_type, timestamp);
