# Bibliome Deployment Guide

This guide covers deploying Bibliome with Nixpacks on Railway, Render, or other platforms.

## Prerequisites

- Git repository pushed to GitHub
- Railway/Render account
- Environment variables configured

## Nixpacks Configuration

Bibliome uses [Nixpacks](https://nixpacks.com/) for automated builds and deployments.

### Files

- **`nixpacks.toml`** - Main Nixpacks configuration
- **`.python-version`** - Specifies Python 3.11
- **`runtime.txt`** - Fallback Python version specification
- **`requirements.txt`** - Python dependencies (including OAuth libraries)
- **`Procfile`** - Backup start command

### How It Works

1. **Detection**: Nixpacks detects this is a Python project
2. **Python Version**: Uses Python 3.11 from `.python-version`
3. **Dependencies**: Installs from `requirements.txt` automatically
4. **Build**: Nixpacks handles the build process
5. **Start**: Runs `python main.py` as specified in `nixpacks.toml`

## Required Environment Variables

Create these environment variables in your deployment platform:

### Core Application
```bash
SECRET_KEY=your-random-secret-key-here
DEBUG=false
HOST=0.0.0.0
PORT=5001
BASE_URL=https://your-domain.com
```

### OAuth 2.0 (Recommended)
```bash
OAUTH_CLIENT_ID=https://your-domain.com/client-metadata.json
OAUTH_REDIRECT_URI=https://your-domain.com/auth/oauth/callback
OAUTH_SCOPE=atproto
```

### Bluesky/AT-Proto (Legacy fallback)
```bash
BLUESKY_HANDLE=your-handle.bsky.social
BLUESKY_PASSWORD=your-app-password
```

### Optional Services
```bash
# Google Books API
GOOGLE_BOOKS_API_KEY=your-api-key

# Email (contact form)
CONTACT_EMAIL=your-email@domain.com
SENDER_EMAIL=noreply@domain.com
SMTP2GO_API_KEY=your-smtp2go-key

# Admin access
ADMIN_USERNAMES=admin.bsky.social,moderator.bsky.social

# Automation (optional)
BLUESKY_AUTOMATION_ENABLED=true
BLUESKY_AUTOMATION_HANDLE=bot.bsky.social
BLUESKY_AUTOMATION_PASSWORD=bot-app-password
BLUESKY_POST_THRESHOLD=3
BLUESKY_MAX_POSTS_PER_HOUR=3

# Network scanner (optional)
BIBLIOME_SCANNER_ENABLED=false
BIBLIOME_SCAN_INTERVAL_HOURS=6
BIBLIOME_RATE_LIMIT_PER_MINUTE=30
BIBLIOME_IMPORT_PUBLIC_ONLY=true
BIBLIOME_MAX_USERS_PER_SCAN=100
```

## Railway Deployment

### Quick Deploy

1. **Connect Repository**:
   ```bash
   # Push your code to GitHub
   git push origin main
   ```

2. **Create New Project** on Railway:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your bibliome repository

3. **Configure**:
   - Railway will automatically detect nixpacks.toml
   - Add environment variables in the Variables tab
   - Set domain in the Settings tab

4. **Deploy**:
   - Railway will automatically build and deploy
   - Dependencies from requirements.txt are installed automatically
   - OAuth libraries (authlib, cryptography) are included

### Manual Configuration

If you need to configure manually:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Set variables
railway variables set SECRET_KEY=your-secret-key
railway variables set OAUTH_CLIENT_ID=https://your-domain.com/client-metadata.json
# ... set other variables

# Deploy
git push
```

## Render Deployment

1. **Create Web Service**:
   - Go to Render Dashboard
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

2. **Configure Build**:
   - **Environment**: Python 3
   - **Build Command**: (auto-detected from nixpacks.toml)
   - **Start Command**: `python main.py`

3. **Set Environment Variables**:
   - Add all required variables in the Environment tab

4. **Deploy**:
   - Click "Create Web Service"
   - Render will automatically build and deploy

## Vercel/Other Platforms

For platforms that don't support long-running processes:

1. You may need to adapt the application for serverless
2. Consider using Railway or Render for full application hosting
3. Nixpacks configuration will work on most Python-supporting platforms

## Dependency Installation

Nixpacks automatically installs all dependencies from `requirements.txt`:

- ✅ python-fasthtml
- ✅ httpx with HTTP/2 support
- ✅ atproto (Bluesky SDK)
- ✅ **authlib** (OAuth 2.0 library) ← NEW
- ✅ **cryptography** (cryptographic primitives) ← NEW
- ✅ fastlite (database)
- ✅ fastmigrate (migrations)
- ✅ And all other dependencies

No manual installation needed - Nixpacks handles everything!

## Database

The application uses SQLite with automatic migrations:

- Database stored in `data/bookdit.db`
- Migrations in `migrations/` folder run automatically
- OAuth migration (0010-add-oauth-support.sql) runs on first deployment

**Important**: Configure persistent storage for the `data/` directory:
- **Railway**: Add volume at `/app/data`
- **Render**: Add disk at `/app/data`

## Post-Deployment Checklist

- [ ] Application starts without errors
- [ ] Environment variables are set
- [ ] Database migrations ran successfully
- [ ] OAuth client metadata accessible at `/client-metadata.json`
- [ ] Login page shows OAuth option (if configured)
- [ ] App password login works
- [ ] Static files load correctly
- [ ] Admin dashboard accessible (if admin user set)

## Troubleshooting

### Dependencies Not Installing

**Problem**: OAuth dependencies (authlib, cryptography) not found

**Solution**:
1. Check that `requirements.txt` includes:
   ```
   authlib>=1.3.0
   cryptography>=42.0.0
   ```
2. Redeploy to trigger fresh build
3. Check build logs for installation errors

### OAuth Not Available

**Problem**: Login page doesn't show OAuth option

**Solution**:
1. Verify `OAUTH_CLIENT_ID` and `OAUTH_REDIRECT_URI` are set
2. Check logs for OAuth initialization warnings
3. Ensure dependencies are installed (see above)

### Application Won't Start

**Problem**: Application crashes on startup

**Solution**:
1. Check environment variables are set
2. Review deployment logs
3. Verify `PORT` environment variable matches platform
4. Check that `main.py` is being executed

### Database Issues

**Problem**: "Table not found" errors

**Solution**:
1. Delete database file to force recreation
2. Ensure migrations directory is included in deployment
3. Check that data directory has write permissions

## Monitoring

The application includes built-in monitoring:

- **Process Monitor**: `/admin/processes`
- **Health Check**: `/api/auth/health`
- **Logs**: Check platform logs for application output

## Scaling

For production deployments:

1. **Database**: Consider PostgreSQL for multi-instance deployments
2. **File Storage**: Use S3/R2 for book covers instead of local storage
3. **Sessions**: Consider Redis for session storage
4. **Workers**: Background services run in the main process

## Security

Production security checklist:

- [ ] `DEBUG=false` in production
- [ ] `SECRET_KEY` is random and secure
- [ ] HTTPS enabled (automatic on Railway/Render)
- [ ] OAuth redirect URIs use HTTPS
- [ ] Admin usernames configured
- [ ] Database backups enabled

## Support

- Documentation: `OAUTH_SETUP.md`
- Issues: GitHub repository
- Logs: Platform logging dashboard

---

**Last Updated**: November 2025
**Nixpacks Version**: Latest
**Python Version**: 3.11
