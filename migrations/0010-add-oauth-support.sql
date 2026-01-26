-- Add OAuth 2.0 support to the User table
-- This migration adds fields for storing OAuth tokens and DPoP keys

-- Add OAuth token fields
ALTER TABLE user ADD COLUMN oauth_access_token TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_refresh_token TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_token_expires_at DATETIME DEFAULT NULL;

-- Add DPoP key and nonce storage (stored as JSON)
ALTER TABLE user ADD COLUMN oauth_dpop_private_jwk TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_dpop_nonce_authserver TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_dpop_nonce_pds TEXT DEFAULT NULL;

-- Add OAuth server metadata
ALTER TABLE user ADD COLUMN oauth_issuer TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_pds_url TEXT DEFAULT NULL;

-- Add OAuth flow state management
ALTER TABLE user ADD COLUMN oauth_state TEXT DEFAULT NULL;
ALTER TABLE user ADD COLUMN oauth_code_verifier TEXT DEFAULT NULL;

-- Add index for token expiration queries
CREATE INDEX idx_user_oauth_token_expiry ON user(oauth_token_expires_at)
WHERE oauth_token_expires_at IS NOT NULL;
