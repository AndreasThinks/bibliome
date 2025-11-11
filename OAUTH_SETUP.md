# OAuth 2.0 Setup Guide for Bibliome

This document explains how to configure and use the new AT Protocol OAuth 2.0 authentication system.

## What is OAuth?

OAuth provides a more secure authentication method compared to app passwords. With OAuth:
- Users don't need to create app-specific passwords
- Better security with token-based authentication
- Support for token refresh and revocation
- Full compliance with AT Protocol OAuth specification

## Configuration

### Environment Variables

Add the following to your `.env` file:

```env
# OAuth 2.0 Configuration
OAUTH_CLIENT_ID=https://yourdomain.com/client-metadata.json
OAUTH_REDIRECT_URI=https://yourdomain.com/auth/oauth/callback
OAUTH_SCOPE=atproto
```

**Important Notes:**
- `OAUTH_CLIENT_ID` must be an HTTPS URL pointing to your publicly accessible server
- The client metadata will be served at `/client-metadata.json`
- `OAUTH_REDIRECT_URI` must match your configured callback URL exactly
- For local development, you can use `http://localhost:5001` (localhost exception in spec)

### For Local Development

```env
OAUTH_CLIENT_ID=http://localhost:5001/client-metadata.json
OAUTH_REDIRECT_URI=http://localhost:5001/auth/oauth/callback
OAUTH_SCOPE=atproto
```

### For Production

```env
OAUTH_CLIENT_ID=https://bibliome.club/client-metadata.json
OAUTH_REDIRECT_URI=https://bibliome.club/auth/oauth/callback
OAUTH_SCOPE=atproto
```

## How It Works

### OAuth Flow

1. **User enters their handle**: User provides their Bluesky handle (e.g., `user.bsky.social`)
2. **Handle resolution**: System resolves the handle to a DID and discovers the user's PDS
3. **Server discovery**: System discovers the authorization server from the PDS
4. **PAR request**: Client sends Pushed Authorization Request with PKCE challenge
5. **User authorization**: User is redirected to their PDS to authorize the app
6. **Token exchange**: Authorization code is exchanged for access and refresh tokens
7. **Session creation**: User is logged in with OAuth tokens

### Security Features

The implementation includes all required AT Protocol OAuth security measures:

- **PKCE (Proof Key for Code Exchange)**: S256 challenge method
- **DPoP (Demonstration of Proof-of-Possession)**: Cryptographic binding of tokens
- **PAR (Pushed Authorization Requests)**: Required for all authorization requests
- **Token refresh**: Automatic token refresh when expired
- **State validation**: CSRF protection with state parameter

## Database Schema

OAuth tokens are stored in the `user` table with the following fields:

- `oauth_access_token`: Current access token
- `oauth_refresh_token`: Refresh token for getting new access tokens
- `oauth_token_expires_at`: Token expiration timestamp
- `oauth_dpop_private_jwk`: DPoP signing key (JSON)
- `oauth_dpop_nonce_authserver`: Authorization server nonce
- `oauth_dpop_nonce_pds`: PDS nonce
- `oauth_issuer`: Authorization server URL
- `oauth_pds_url`: User's PDS URL

## Using OAuth

### Login Page

The login page now shows two options:

1. **OAuth Login (Recommended)**: Secure login without app password
2. **App Password Login**: Legacy method using Bluesky app passwords

Both methods are supported for backward compatibility.

### API Usage

When OAuth is configured, authenticated API requests will use:
- Bearer token authentication with DPoP
- Automatic token refresh when expired
- Proper nonce management

## Endpoints

### Public Endpoints

- `GET /client-metadata.json`: OAuth client metadata (public)
- `GET /auth/oauth/start?handle=<handle>`: Start OAuth flow
- `GET /auth/oauth/callback?code=<code>&state=<state>`: OAuth callback

### Legacy Endpoints

- `GET /auth/login`: Login page (supports both OAuth and app passwords)
- `POST /auth/login`: App password authentication
- `GET /auth/logout`: Logout (clears session)

## Troubleshooting

### OAuth is not available on login page

- Check that `OAUTH_CLIENT_ID` and `OAUTH_REDIRECT_URI` are set in `.env`
- Restart the application after setting environment variables

### "OAuth authentication failed" error

- Verify your domain is publicly accessible (for production)
- Check that client metadata is accessible at `/client-metadata.json`
- Ensure your redirect URI matches exactly

### Token refresh issues

- Tokens are automatically refreshed when expired
- Check logs for refresh errors
- Users may need to re-authenticate if refresh token is invalid

## Migration from App Passwords

Existing users with app passwords can:
1. Continue using app password login
2. Switch to OAuth by logging out and logging in with OAuth
3. Both methods work simultaneously

When a user authenticates with OAuth:
- Their existing account is updated with OAuth tokens
- Previous app password sessions remain valid until logout
- OAuth tokens take precedence for new sessions

## References

- [AT Protocol OAuth Specification](https://atproto.com/specs/oauth)
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [DPoP RFC 9449](https://tools.ietf.org/html/rfc9449)
- [PAR RFC 9126](https://tools.ietf.org/html/rfc9126)
