-- Add cover caching fields to the book table
-- This migration adds optional fields to track cached covers

ALTER TABLE book ADD COLUMN cached_cover_path TEXT DEFAULT '';
ALTER TABLE book ADD COLUMN cover_cached_at DATETIME DEFAULT NULL;

-- Add index for efficient lookups of cached covers
CREATE INDEX idx_book_cached_cover ON book(cached_cover_path) WHERE cached_cover_path != '';
CREATE INDEX idx_book_cover_cached_at ON book(cover_cached_at) WHERE cover_cached_at IS NOT NULL;
