-- Add AT Protocol sync fields to comments table
-- Note: atproto_uri already exists from migration 0006
ALTER TABLE comment ADD COLUMN is_remote BOOLEAN DEFAULT FALSE;
ALTER TABLE comment ADD COLUMN remote_user_did TEXT DEFAULT '';
ALTER TABLE comment ADD COLUMN discovered_at DATETIME;
ALTER TABLE comment ADD COLUMN original_atproto_uri TEXT DEFAULT '';
ALTER TABLE comment ADD COLUMN remote_sync_status TEXT DEFAULT 'local';

-- Create index for efficient AT Protocol URI lookups
CREATE INDEX IF NOT EXISTS idx_comment_atproto_uri ON comment(atproto_uri);
CREATE INDEX IF NOT EXISTS idx_comment_original_atproto_uri ON comment(original_atproto_uri);
CREATE INDEX IF NOT EXISTS idx_comment_remote_sync ON comment(is_remote, remote_sync_status);
