-- migrations/0001-initialize.sql
-- Initial database schema for Bibliome
-- This migration creates all the tables that match the current FastLite models

-- Users table with DID as primary key
CREATE TABLE user (
    did TEXT PRIMARY KEY,
    handle TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at DATETIME,
    last_login DATETIME
);

-- Bookshelves table
CREATE TABLE bookshelf (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_did TEXT NOT NULL,
    slug TEXT DEFAULT '',
    description TEXT DEFAULT '',
    privacy TEXT DEFAULT 'public',
    atproto_uri TEXT DEFAULT '',
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (owner_did) REFERENCES user(did)
);

-- Books table
CREATE TABLE book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookshelf_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    added_by_did TEXT NOT NULL,
    isbn TEXT DEFAULT '',
    author TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    publisher TEXT DEFAULT '',
    published_date TEXT DEFAULT '',
    page_count INTEGER DEFAULT 0,
    atproto_uri TEXT DEFAULT '',
    added_at DATETIME,
    FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(id),
    FOREIGN KEY (added_by_did) REFERENCES user(did)
);

-- Permissions table for role-based access
CREATE TABLE permission (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookshelf_id INTEGER NOT NULL,
    user_did TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    granted_by_did TEXT NOT NULL,
    granted_at DATETIME,
    invited_at DATETIME,
    joined_at DATETIME,
    FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(id),
    FOREIGN KEY (user_did) REFERENCES user(did),
    FOREIGN KEY (granted_by_did) REFERENCES user(did)
);

-- Bookshelf invites table
CREATE TABLE bookshelf_invite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bookshelf_id INTEGER NOT NULL,
    invite_code TEXT NOT NULL,
    role TEXT NOT NULL,
    created_by_did TEXT NOT NULL,
    created_at DATETIME,
    expires_at DATETIME,
    max_uses INTEGER,
    uses_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(id),
    FOREIGN KEY (created_by_did) REFERENCES user(did)
);

-- Upvotes table with composite primary key
CREATE TABLE upvote (
    book_id INTEGER NOT NULL,
    user_did TEXT NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (book_id, user_did),
    FOREIGN KEY (book_id) REFERENCES book(id),
    FOREIGN KEY (user_did) REFERENCES user(did)
);

-- Activity table for social feed
CREATE TABLE activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_did TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    bookshelf_id INTEGER,
    book_id INTEGER,
    created_at DATETIME,
    metadata TEXT DEFAULT '',
    FOREIGN KEY (user_did) REFERENCES user(did),
    FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(id),
    FOREIGN KEY (book_id) REFERENCES book(id)
);

-- Create indexes for better performance
CREATE INDEX idx_bookshelf_owner ON bookshelf(owner_did);
CREATE INDEX idx_bookshelf_slug ON bookshelf(slug);
CREATE INDEX idx_bookshelf_privacy ON bookshelf(privacy);
CREATE INDEX idx_book_bookshelf ON book(bookshelf_id);
CREATE INDEX idx_book_added_by ON book(added_by_did);
CREATE INDEX idx_permission_bookshelf ON permission(bookshelf_id);
CREATE INDEX idx_permission_user ON permission(user_did);
CREATE UNIQUE INDEX idx_bookshelf_invite_code ON bookshelf_invite(invite_code);
CREATE INDEX idx_upvote_book ON upvote(book_id);
CREATE INDEX idx_activity_user ON activity(user_did);
CREATE INDEX idx_activity_type ON activity(activity_type);
CREATE INDEX idx_activity_created ON activity(created_at);
