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
- **Database**: SQLite with FastLite
- **APIs**: Google Books API
- **Styling**: PicoCSS + Custom CSS
- **JavaScript**: HTMX for dynamic interactions

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
```
Bibliome/
├── app.py              # Main application
├── auth.py             # Authentication logic
├── api_clients.py      # External API integrations
├── models.py           # Database models
├── components.py       # UI components
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── static/
│   └── css/
│       └── styles.css  # Custom styling
└── data/               # SQLite database storage
```

### Running Tests
```bash
python test_basic.py
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
