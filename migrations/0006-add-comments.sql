-- Migration 0006: Add comments table for book discussions
-- This migration adds support for commenting on books

CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    bookshelf_id INTEGER NOT NULL,
    user_did TEXT NOT NULL,
    content TEXT NOT NULL,
    parent_comment_id INTEGER NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL,
    is_edited BOOLEAN NOT NULL DEFAULT 0,
    atproto_uri TEXT DEFAULT '',
    
    -- Foreign key constraints
    FOREIGN KEY (book_id) REFERENCES book(id) ON DELETE CASCADE,
    FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(id) ON DELETE CASCADE,
    FOREIGN KEY (user_did) REFERENCES user(did) ON DELETE CASCADE,
    FOREIGN KEY (parent_comment_id) REFERENCES comment(id) ON DELETE CASCADE
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_comment_book_id ON comment(book_id);
CREATE INDEX IF NOT EXISTS idx_comment_bookshelf_id ON comment(bookshelf_id);
CREATE INDEX IF NOT EXISTS idx_comment_user_did ON comment(user_did);
CREATE INDEX IF NOT EXISTS idx_comment_created_at ON comment(created_at);
CREATE INDEX IF NOT EXISTS idx_comment_parent ON comment(parent_comment_id);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_comment_book_created ON comment(book_id, created_at DESC);
