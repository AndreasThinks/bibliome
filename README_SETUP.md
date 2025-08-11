# BookdIt Setup Guide

## Quick Start

1. **Install UV** (if you haven't already):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the application**:
   ```bash
   uv run python app.py
   ```

5. **Open your browser** to `http://localhost:5001`

## Environment Variables

Create a `.env` file with the following variables:

- `GOOGLE_BOOKS_API_KEY`: (Optional) Google Books API key for better search results
- `SECRET_KEY`: Random secret key for session encryption (auto-generated if not provided)
- `DEBUG`: Set to `true` for development
- `HOST`: Server host (default: `localhost`)
- `PORT`: Server port (default: `5001`)

## Bluesky App Password

To use BookdIt, you'll need a Bluesky app password:

1. Go to [bsky.app](https://bsky.app)
2. Sign in to your account
3. Go to Settings → Privacy and Security → App Passwords
4. Click "Add App Password"
5. Give it a name (e.g., "BookdIt")
6. Use this password when logging into BookdIt (not your main password)

## Features

- **Bluesky Authentication**: Login with your Bluesky account using app passwords
- **Create Bookshelves**: Organize books into collections with custom names and descriptions
- **Privacy Controls**: 
  - **Public**: Anyone can find and view
  - **Link-only**: Only people with the direct link can view
  - **Private**: Only invited users can view
- **Book Search**: Search and add books using Google Books API with Open Library fallback
- **Upvoting**: Vote for your favorite books in collections
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: HTMX-powered interface for smooth interactions

## Architecture

The application uses:

- **FastHTML**: Python web framework with HTMX for reactive UI
- **FastLite**: SQLite database with dataclass models
- **AT-Proto**: Bluesky authentication protocol
- **Google Books API**: Primary source for book metadata
- **Open Library API**: Fallback for book search
- **PicoCSS**: Minimal CSS framework for styling

## Development

### Project Structure

```
BookdIt/
├── app.py              # Main application with routes
├── models.py           # Database models and setup
├── auth.py             # Bluesky authentication
├── api_clients.py      # External API clients
├── components.py       # Reusable UI components
├── pyproject.toml      # UV project configuration
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
└── data/               # SQLite database (auto-created)
```

### Key Components

1. **Models**: FastLite dataclasses for User, Bookshelf, Book, Permission, and Upvote
2. **Authentication**: Bluesky/AT-Proto integration with session management
3. **API Integration**: Google Books and Open Library for book metadata
4. **UI Components**: Reusable FastHTML components for consistent design
5. **Permissions**: Role-based access control (admin, editor, viewer)

### Running in Development

```bash
# Install dependencies
uv sync

# Run with auto-reload
uv run python app.py

# The app will be available at http://localhost:5001
```

### Database

The application uses SQLite with FastLite for:
- Simple setup and deployment
- Automatic schema migrations
- Type-safe database operations
- No additional database server required

### API Keys

While the app works without API keys, you can improve book search results by:

1. Getting a Google Books API key:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable the Books API
   - Create credentials (API key)
   - Add to your `.env` file

## Deployment

### Local Deployment

The app is ready to run locally with minimal setup. Just follow the Quick Start guide above.

### Production Deployment

For production deployment, consider:

1. **Environment Variables**: Set production values for all environment variables
2. **Database**: The SQLite database will be created in the `data/` directory
3. **Static Files**: Ensure the `static/` directory is accessible
4. **HTTPS**: Use a reverse proxy like nginx for HTTPS termination
5. **Process Management**: Use a process manager like systemd or supervisor

### Docker Deployment (Optional)

You can create a simple Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 5001

# Run the application
CMD ["uv", "run", "python", "app.py"]
```

## Contributing

This is an MVP implementation. Areas for future enhancement:

1. **User Management**: Invite system for private bookshelves
2. **Search**: Full-text search across books and shelves
3. **Export**: Export bookshelves to various formats
4. **Social Features**: Following users, bookshelf recommendations
5. **Mobile App**: Native mobile applications
6. **Analytics**: Reading statistics and insights
7. **Import**: Import from Goodreads, CSV, etc.

## License

This project is open source. See the main README.md for license information.
