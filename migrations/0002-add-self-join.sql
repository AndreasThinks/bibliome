-- migrations/0002-add-self-join.sql
-- Add self_join column to bookshelf table to enable open collaboration

-- Add self_join column to bookshelf table
ALTER TABLE bookshelf ADD COLUMN self_join BOOLEAN DEFAULT 0;

-- Create index for performance when querying self-join enabled shelves
CREATE INDEX idx_bookshelf_self_join ON bookshelf(self_join);
