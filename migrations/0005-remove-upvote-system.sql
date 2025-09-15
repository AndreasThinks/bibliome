-- migrations/0005-remove-upvote-system.sql
-- Remove the upvote system in favor of using Book records as votes
-- Each book record now represents a user's +1 vote for that book on that shelf

-- Drop upvote-related indexes first
DROP INDEX IF EXISTS idx_upvote_book;

-- Drop the upvote table entirely
DROP TABLE IF EXISTS upvote;

-- The book table already contains all the information we need:
-- - bookshelf_id: which shelf the book is on
-- - added_by_did: which user added it (their "vote")
-- - title, author, isbn: to identify duplicate books
-- - atproto_uri: for AT Protocol sync when removing

-- No new tables needed - we'll count book records grouped by title/author/isbn
-- to determine how many users have "voted" for each unique book
