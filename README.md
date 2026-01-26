# Bibliome - Collaborative Bookshelf Platform

A decentralized, collaborative bookshelf platform with Bluesky (AT-Proto) authentication. Users can create and manage collections of books, set privacy levels, and collaborate with others through role-based permissions.

## 🚀 Features

### ✅ Implemented Features

#### Core Functionality
- **Bookshelf Creation & Management**: Create named bookshelves with unique URLs
- **Advanced Search**: Search shelves by name, description, and contained books (title, author, ISBN)
- **Book Search & Addition**: Integrated Google Books API for rich book metadata
- **Upvoting System**: Community-driven book curation through upvotes
- **Privacy Controls**: Public, Link-only, and Private bookshelf options
- **Role-Based Permissions**: Owner, Admin, Editor, and Viewer roles

#### Discovery & Social
- **Network Activity Feed**: See recent activity from users you follow on Bluesky
- **Explore Page**: Browse all public bookshelves in the community
- **Community Reading Section**: Discover recently added books from public shelves

#### Authentication & User Management
- **Bluesky Authentication**: Secure login via AT-Proto
- **User Profiles**: Display names, handles, and avatars from Bluesky
- **Session Management**: Persistent login sessions

#### Sharing & Collaboration
- **Invite System**: Generate invite links with role assignments and expiration
- **Member Management**: Add, remove, and manage member permissions
- **Privacy Settings**: Dynamic privacy level changes

#### User Interface
- **Responsive Design**: Mobile-friendly interface with PicoCSS
- **Interactive Book Cards**: Clickable books linking to Google Books
- **Real-time Search**: HTMX-powered book search with instant results
- **Unified Management**: Combined edit, share, and delete interface
- **Delete Confirmation**: Type-to-confirm deletion for safety

#### Recent Improvements
- **Advanced Search**: Implemented hybrid search for shelves and books (title, author, ISBN)
- **Network Activity Feed**: Added a social feed based on Bluesky connections
- **Community Discovery**: New "Explore" page and community reading sections
- **Enhanced Navigation**: Integrated search and discovery into the main navigation
- **Improved UI/UX**: Redesigned search page, better empty states, and clearer titles
- **Fixed Table Name Bug**: Resolved database query errors in search

## 🛠️ Tech Stack

- **Backend & Frontend**: FastHTML
- **Authentication**: AT-Proto (Bluesky)
- **Database**: SQLite with FastLite + FastMigrate
- **APIs**: Google Books API
- **Styling**: PicoCSS + Custom CSS
- **JavaScript**: HTMX for dynamic interactions

## 🗄️ Database Migrations

Bibliome uses **fastmigrate** for database schema management, providing version control for your database structure and safe schema evolution.

### How It Works

FastMigrate follows the standard database migration pattern:
- **Migration scripts** define database versions (e.g., `0001-initialize.sql`, `0002-add-feature.sql`)
- **Automatic application** of pending migrations on startup
- **Version tracking** ensures each migration runs exactly once
- **Safe evolution** from any previous version to the latest

### Migration Files

Migration scripts are stored in the `migrations/` directory:

```
migrations/
└── 0001-initialize.sql    # Initial database schema
```

Each migration file:
- **Must be numbered sequentially** (0001, 0002, 0003, etc.)
- **Should have a descriptive name** after the number
- **Contains SQL statements** to modify the database
- **Runs exactly once** when the application starts

### Current Schema (Version 1)

The initial migration (`0001-initialize.sql`) creates all necessary tables:
- `user` - Bluesky user profiles and authentication data
- `bookshelf` - Book collections with privacy and metadata  
- `book` - Individual books with metadata from Google Books API
- `permission` - Role-based access control for bookshelves
- `bookshelf_invite` - Invitation system for sharing
- `upvote` - User votes on books for curation
- `activity` - Tracks user actions for the social feed

### Adding New Migrations

When you need to modify the database schema:

1. **Create a new migration file** in the `migrations/` directory:
   ```bash
   # Example: Adding a new column to the book table
   touch migrations/0002-add-book-rating.sql
   ```

2. **Write the SQL changes**:
   ```sql
   -- migrations/0002-add-book-rating.sql
   -- Add rating column to books table
   
   ALTER TABLE book ADD COLUMN rating INTEGER DEFAULT 0;
   CREATE INDEX idx_book_rating ON book(rating);
   ```

3. **Test the migration**:
   ```bash
   # The migration will run automatically when you start the app
   python app.py
   ```

4. **Verify the changes**:
   ```bash
   # Check current database version
   python -c "from fastmigrate.core import get_db_version; print(f'Database version: {get_db_version(\"data/bookdit.db\")}')"
   ```

### Migration Best Practices

#### ✅ Do's
- **Always backup** your database before running migrations in production
- **Test migrations** on a copy of production data first
- **Use descriptive names** for migration files
- **Keep migrations small** and focused on one change
- **Add indexes** for new columns that will be queried
- **Use transactions** for complex multi-step migrations

#### ❌ Don'ts
- **Never modify existing migration files** once they've been applied
- **Don't skip version numbers** (use sequential numbering)
- **Avoid destructive operations** without careful consideration
- **Don't mix schema and data changes** in the same migration

### CLI Commands

FastMigrate provides command-line tools for database management:

```bash
# Check current database version
fastmigrate_check_version --db data/bookdit.db

# Create a new managed database (if needed)
fastmigrate_create_db --db data/bookdit.db

# Run pending migrations manually
fastmigrate_run_migrations --db data/bookdit.db --migrations migrations/

# Check what migrations would run
ls migrations/ | sort
```

### Example Migration Scenarios

#### Adding a New Feature
```sql
-- migrations/0002-add-book-reviews.sql
-- Add book reviews functionality

CREATE TABLE book_review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    user_did TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT DEFAULT '',
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (book_id) REFERENCES book(id),
    FOREIGN KEY (user_did) REFERENCES user(did)
);

CREATE INDEX idx_book_review_book ON book_review(book_id);
CREATE INDEX idx_book_review_user ON book_review(user_did);
CREATE INDEX idx_book_review_rating ON book_review(rating);
```

#### Modifying Existing Data
```sql
-- migrations/0003-normalize-book-authors.sql
-- Split author field into separate authors table

CREATE TABLE book_author (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    author_name TEXT NOT NULL,
    author_order INTEGER DEFAULT 1,
    FOREIGN KEY (book_id) REFERENCES book(id)
);

-- Migrate existing author data
INSERT INTO book_author (book_id, author_name, author_order)
SELECT id, author, 1 
FROM book 
WHERE author IS NOT NULL AND author != '';

CREATE INDEX idx_book_author_book ON book_author(book_id);
CREATE INDEX idx_book_author_name ON book_author(author_name);
```

### Troubleshooting Migrations

#### Migration Failed
If a migration fails:
1. **Check the error message** in the application logs
2. **Fix the SQL syntax** in the migration file
3. **Restore from backup** if the database is corrupted
4. **Test the fixed migration** on a copy first

#### Database Version Mismatch
If you see version-related errors:
```bash
# Check current version
fastmigrate_check_version --db data/bookdit.db

# List available migrations
ls -la migrations/

# Manually run migrations if needed
fastmigrate_run_migrations --db data/bookdit.db --migrations migrations/
```

#### Rolling Back Changes
FastMigrate doesn't support automatic rollbacks, but you can:
1. **Create a new migration** that reverses the changes
2. **Restore from a backup** taken before the migration
3. **Manually fix** the database if the change was small

### Production Deployment

For production deployments:

1. **Backup the database** before deploying:
   ```bash
   cp data/bookdit.db data/bookdit.db.backup.$(date +%Y%m%d_%H%M%S)
   ```

2. **Test migrations** on a copy of production data first

3. **Deploy with automatic migrations**:
   - Migrations run automatically when the application starts
   - Monitor logs for migration success/failure
   - Have a rollback plan ready

4. **Verify the deployment**:
   ```bash
   # Check database version after deployment
   fastmigrate_check_version --db data/bookdit.db
   ```

## 📋 Setup Instructions

### Prerequisites
- Python 3.8+
- A Google Books API key
- A Bluesky account for testing

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Bibliome
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your configuration:
   ```env
   # Bluesky/AT-Proto Configuration
   BLUESKY_HANDLE=your-handle.bsky.social
   BLUESKY_PASSWORD=your-app-password

   # Google Books API
   GOOGLE_BOOKS_API_KEY=your-google-books-api-key

   # Application Settings
   SECRET_KEY=your-secret-key-here
   DEBUG=true
   HOST=localhost
   PORT=5001
   BASE_URL=http://0.0.0.0:5001/
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser to `http://localhost:5001`

### Getting API Keys

#### Google Books API Key
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Books API
4. Create credentials (API Key)
5. Add the API key to your `.env` file

#### Bluesky App Password
1. Log into Bluesky
2. Go to Settings → Privacy and Security → App Passwords
3. Generate a new app password
4. Use your handle and app password in the `.env` file

## 🎯 Usage Guide

### Creating Your First Bookshelf

1. **Login** with your Bluesky account
2. **Click "Create New Shelf"** on the homepage
3. **Fill in details**:
   - Name: Give your bookshelf a descriptive name
   - Description: Optional description of what the shelf is about
   - Privacy: Choose who can see your shelf
4. **Click "Create Bookshelf"**

### Adding Books

1. **Navigate to your bookshelf**
2. **Use the search box** to find books by title, author, or ISBN
3. **Click "Add to Shelf"** on any search result
4. **Books appear immediately** in your collection

### Discovering Bookshelves

- **Explore Page**: Click "Explore" in the navigation to browse all public bookshelves.
- **Search Page**: Click "Search" to find specific shelves.
  - Use the main search bar to search by shelf name, description, or contained books.
  - Click "Advanced Search" to filter by specific book titles, authors, or ISBNs.
- **Network Feed**: On your dashboard, see shelves recently created or added to by people you follow on Bluesky.

### Managing Your Bookshelf

1. **Click "Manage"** on any bookshelf you own or have admin access to
2. **Edit Details**: Change name, description, or privacy settings
3. **Share & Members**: 
   - Generate invite links with specific roles
   - Manage existing members and their permissions
   - View pending invitations
4. **Delete Shelf** (owners only): Permanently delete with confirmation

### Collaboration Features

#### Inviting Others
1. Go to the **Manage** page of your bookshelf
2. In the **Share & Members** section, set:
   - Role for new members (Viewer, Editor, Admin)
   - Expiration time (optional)
   - Maximum uses (optional)
3. **Generate Invite Link** and share it

#### Role Permissions
- **Owner**: Full control, can delete shelf
- **Admin**: Manage members, edit shelf, add books
- **Editor**: Add books and upvote
- **Viewer**: View books only

### Privacy Levels

- **Public**: Anyone can find and view your bookshelf
- **Link-only**: Only people with the direct link can view
- **Private**: Only invited members can view

## 🏗️ Architecture

### Database Models
- **User**: Bluesky user profiles and authentication data
- **Bookshelf**: Book collections with privacy and metadata
- **Book**: Individual books with metadata from Google Books API
- **Permission**: Role-based access control for bookshelves
- **BookshelfInvite**: Invitation system for sharing
- **Upvote**: User votes on books for curation
- **Activity**: Tracks user actions for the social feed

### Key Components
- **Authentication** (`auth.py`): Bluesky AT-Proto integration
- **API Clients** (`api_clients.py`): Google Books API wrapper
- **Models** (`models.py`): Database models and business logic
- **Components** (`components.py`): Reusable UI components
- **Main App** (`app.py`): FastHTML routes and application logic

## 🔧 Development

### Project Structure

The codebase is organized into a modular `bibliome/` package with clear separation of concerns:

```
Bibliome/
├── main.py                 # Application entry point (used by Procfile)
├── app.py                  # Main FastHTML routes and application logic
│
├── bibliome/               # Core package with modular structure
│   ├── __init__.py
│   │
│   ├── models/             # Data models and database operations
│   │   ├── __init__.py     # Re-exports all models
│   │   ├── entities.py     # User, Bookshelf, Book, Permission dataclasses
│   │   └── database.py     # Database setup and utility functions
│   │
│   ├── services/           # Business logic and permissions
│   │   ├── __init__.py     # Re-exports all services
│   │   └── permissions.py  # RBAC permission functions (14 helpers)
│   │
│   ├── auth/               # Authentication and authorization
│   │   ├── __init__.py     # Re-exports all auth components
│   │   ├── bluesky.py      # BlueskyAuth class for AT-Proto login
│   │   ├── oauth.py        # OAuth 2.0 with PKCE, DPoP, PAR
│   │   ├── middleware.py   # auth_beforeware, require_auth, require_admin
│   │   ├── diagnostics.py  # Auth logging and error formatting
│   │   └── retry.py        # Network retry with exponential backoff
│   │
│   ├── clients/            # External API clients
│   │   ├── __init__.py     # Re-exports all clients
│   │   ├── books.py        # BookAPIClient (Google Books & Open Library)
│   │   └── pds.py          # DirectPDSClient for AT-Proto PDS access
│   │
│   ├── components/         # UI components (60+ components)
│   │   ├── __init__.py     # Re-exports all components
│   │   ├── navigation.py   # NavBar, AlphaBadge
│   │   ├── forms.py        # BookSearchForm, CreateBookshelfForm, etc.
│   │   ├── cards.py        # BookCard, BookshelfCard, MemberCard, etc.
│   │   ├── modals.py       # ContactModal, ShareModal, CommentModal
│   │   ├── pages.py        # LandingPageHero, FeaturesSection, etc.
│   │   ├── admin.py        # AdminDashboard, AdminStatsCard
│   │   └── utils.py        # Alert, Modal, EmptyState, Pagination
│   │
│   ├── atproto/            # AT Protocol record operations
│   │   ├── __init__.py     # Re-exports all AT-Proto functions
│   │   └── records.py      # put_record, delete_record for books/shelves
│   │
│   └── infrastructure/     # Core infrastructure utilities
│       ├── __init__.py     # Re-exports infrastructure components
│       ├── circuit_breaker.py  # CircuitBreaker for fault tolerance
│       └── rate_limiter.py     # RateLimiter with exponential backoff
│
├── # Legacy root files (backward-compatible re-exports)
├── auth.py                 # → bibliome.auth
├── api_clients.py          # → bibliome.clients
├── models.py               # → bibliome.models
├── components.py           # → bibliome.components
├── circuit_breaker.py      # → bibliome.infrastructure
├── rate_limiter.py         # → bibliome.infrastructure
│
├── # Application services
├── database_manager.py     # Async database connection management
├── service_manager.py      # Background service coordination
├── process_monitor.py      # Process health monitoring
├── cover_cache.py          # Book cover caching system
├── bibliome_scanner.py     # AT-Proto network scanning
├── ingester.py             # Bluesky firehose content ingestion
├── bluesky_automation.py   # Automated Bluesky posting
├── db_write_queue.py       # Concurrent SQLite write handling
├── logging_config.py       # Centralized logging configuration
│
├── migrations/             # Database migration scripts
│   ├── 0001-initialize.sql
│   ├── 0002-add-self-join.sql
│   └── ...
│
├── tests/                  # Test suite (143 tests)
│   ├── conftest.py         # Test fixtures
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── services/           # Service tests
│
├── static/                 # Static assets
│   └── css/styles.css
│
├── lexicons/               # AT-Proto lexicon definitions
│   ├── com.bibliome.book.json
│   ├── com.bibliome.bookshelf.json
│   └── com.bibliome.comment.json
│
└── data/                   # SQLite database and cached covers
```

### Import Examples

**New modular imports (recommended):**
```python
from bibliome.auth import BlueskyAuth, require_auth, is_admin
from bibliome.clients import BookAPIClient, DirectPDSClient
from bibliome.models import User, Bookshelf, Book, Permission
from bibliome.services import can_view_bookshelf, can_add_books
from bibliome.components import NavBar, BookCard, BookshelfCard
from bibliome.infrastructure import CircuitBreaker, RateLimiter
from bibliome.atproto import put_book_record, delete_book_record
```

**Legacy imports (still supported):**
```python
from auth import BlueskyAuth  # Works via re-export
from models import User, Bookshelf  # Works via re-export
from components import NavBar  # Works via re-export
```

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v        # Unit tests only
python -m pytest tests/integration/ -v # Integration tests only
python -m pytest tests/services/ -v    # Service tests only

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 🐛 Troubleshooting

### Common Issues

#### Google Books API Not Working
- Verify your API key is correct in `.env`
- Check that the Books API is enabled in Google Cloud Console
- Ensure you haven't exceeded API quotas

#### Books Not Appearing in Search
- Check the console for API errors
- Verify your internet connection
- Try different search terms (title, author, ISBN)

#### Invite Links Not Working
- Ensure `BASE_URL` is set correctly in `.env`
- Check that the invite hasn't expired or reached max uses
- Verify the bookshelf privacy settings

#### Authentication Issues
- Verify your Bluesky handle and app password
- Check that you're using an app password, not your main password
- Ensure the Bluesky service is accessible

## 🚀 Deployment

### Environment Variables for Production
```env
DEBUG=false
HOST=0.0.0.0
PORT=5001
BASE_URL=https://yourdomain.com/
SECRET_KEY=your-production-secret-key
```

### Security Considerations
- Use a strong, unique `SECRET_KEY` in production
- Enable HTTPS for production deployments
- Regularly rotate API keys
- Monitor for unusual activity

## 📈 Future Enhancements

### Planned Features
- **Export/Import**: Backup and restore bookshelves
- **Enhanced Search**: Filter by genre, publication date, etc.
- **Reading Lists**: Track reading progress and status (e.g., "To Read", "Reading", "Read")
- **Book Reviews & Ratings**: Allow users to write reviews and give star ratings
- **Notifications**: In-app notifications for invites, new books, etc.
- **Mobile App**: Native mobile applications for iOS and Android
- **Public API**: A public API for third-party integrations and extensions

### Technical Improvements
- **Performance**: Database optimization and caching
- **Scalability**: PostgreSQL migration for larger deployments
- **Testing**: Comprehensive test suite
- **Documentation**: API documentation and user guides

## 📄 License

This project is open source. See the LICENSE file for details.

## 🤝 Support

- **Issues**: Report bugs and request features on GitHub
- **Community**: Join discussions on Bluesky
- **Documentation**: Check this README and inline code comments

---

Built with ❤️ using FastHTML and the AT-Proto ecosystem.
