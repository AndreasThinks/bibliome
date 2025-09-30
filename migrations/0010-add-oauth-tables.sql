-- Migration: Add OAuth tables for atproto OAuth implementation
-- This migration adds tables to support OAuth authentication flow

-- Store pending OAuth authorization requests
-- These are temporary records that get deleted after successful auth
CREATE TABLE IF NOT EXISTS oauth_auth_request (
    state TEXT PRIMARY KEY,
    authserver_iss TEXT NOT NULL,
    did TEXT,                    -- User's DID (if starting with account identifier)
    handle TEXT,                 -- User's handle (if starting with account identifier)
    pds_url TEXT,               -- User's PDS URL (if starting with account identifier)
    pkce_verifier TEXT NOT NULL,
    scope TEXT NOT NULL,
    dpop_authserver_nonce TEXT, -- DPoP nonce from authorization server
    dpop_private_jwk TEXT NOT NULL, -- DPoP keypair for this session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store OAuth sessions (replaces app password sessions)
-- These are long-lived records for authenticated users
CREATE TABLE IF NOT EXISTS oauth_session (
    did TEXT PRIMARY KEY,
    handle TEXT NOT NULL,
    pds_url TEXT NOT NULL,
    authserver_iss TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    dpop_authserver_nonce TEXT, -- Current DPoP nonce from authorization server
    dpop_private_jwk TEXT NOT NULL, -- DPoP keypair for this session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for cleanup of old auth requests (older than 1 hour)
CREATE INDEX IF NOT EXISTS idx_oauth_auth_request_created
ON oauth_auth_request(created_at);

-- Index for efficient session lookups
CREATE INDEX IF NOT EXISTS idx_oauth_session_updated
ON oauth_session(updated_at);

-- Add comments for documentation
COMMENT ON TABLE oauth_auth_request IS 'Temporary storage for OAuth authorization requests - records deleted after successful authentication';
COMMENT ON TABLE oauth_session IS 'Long-term storage for OAuth user sessions - replaces app password authentication';

COMMENT ON COLUMN oauth_auth_request.state IS 'Unique state parameter for OAuth flow';
COMMENT ON COLUMN oauth_auth_request.pkce_verifier IS 'PKCE code verifier for this auth request';
COMMENT ON COLUMN oauth_auth_request.dpop_private_jwk IS 'DPoP keypair JSON for this session';

COMMENT ON COLUMN oauth_session.did IS 'User DID (primary key)';
COMMENT ON COLUMN oauth_session.access_token IS 'Current DPoP-bound access token';
COMMENT ON COLUMN oauth_session.refresh_token IS 'Refresh token for obtaining new access tokens';
COMMENT ON COLUMN oauth_session.dpop_private_jwk IS 'DPoP keypair JSON for this session';
