-- Add rate limit tracking to the book table
-- This migration adds a field to track when rate limits expire for cover downloads

ALTER TABLE book ADD COLUMN cover_rate_limited_until DATETIME DEFAULT NULL;

-- Add index for efficient rate limit queries
CREATE INDEX idx_book_cover_rate_limited ON book(cover_rate_limited_until) WHERE cover_rate_limited_until IS NOT NULL;

-- Add index for books that need rate limit recovery
CREATE INDEX idx_book_rate_limit_recovery ON book(cover_rate_limited_until, cached_cover_path) 
WHERE cover_rate_limited_until IS NOT NULL AND (cached_cover_path = '' OR cached_cover_path IS NULL);
