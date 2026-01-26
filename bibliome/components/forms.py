"""Form components for Bibliome."""

from fasthtml.common import *
from typing import Dict, Any


def AddBooksToggle(bookshelf_id: int):
    """A discrete button to show the book search form."""
    return Div(
        Button(
            "📚 Add Books", 
            hx_get=f"/api/shelf/{bookshelf_id}/add-books-form",
            hx_target="#add-books-container",
            hx_swap="outerHTML",
            cls="add-books-toggle primary"
        ),
        id="add-books-container"
    )


def BookSearchForm(bookshelf_id: int):
    """The collapsible book search form."""
    return Div(
        Card(
            H3("Add Books to Shelf"),
            Form(
                Input(
                    name="query",
                    placeholder="Search for books...",
                    required=True,
                    autofocus=True
                ),
                Button("🔍 Search", type="submit", cls="search-btn primary"),
                Button("✕ Cancel", 
                       hx_get=f"/api/shelf/{bookshelf_id}/add-books-toggle",
                       hx_target="#add-books-container",
                       hx_swap="outerHTML",
                       cls="cancel-btn secondary",
                       type="button"),
                hx_post="/api/search-books",
                hx_target="#search-results",
                hx_vals=f'{{"bookshelf_id": {bookshelf_id}}}',
                hx_indicator="#search-indicator",
                cls="search-form-row"
            ),
            Div(
                Div("🔍 Searching...", cls="htmx-indicator", id="search-indicator"),
                id="search-results"
            ),
            cls="add-books-card"
        ),
        id="add-books-container",
        cls="book-search-expanded"
    )


def SearchResultCard(book_data: Dict[str, Any], bookshelf_id: int):
    """Render a search result that can be added to a bookshelf."""
    return Article(
        cls="search-result-card"
    )(
        Div(
            Img(
                src=book_data.get('cover_url', ''),
                alt=f"Cover of {book_data.get('title', 'Unknown')}",
                cls="search-result-cover",
                loading="lazy"
            ) if book_data.get('cover_url') else Div("📖", cls="cover-placeholder"),
            cls="search-result-cover-container"
        ),
        Div(
            H4(book_data.get('title', 'Unknown Title')),
            P(book_data.get('author', 'Unknown Author'), cls="author"),
            P(book_data.get('description', '')[:150] + "..." if len(book_data.get('description', '')) > 150 
              else book_data.get('description', ''), cls="description") if book_data.get('description') else None,
            Form(
                Hidden(name="bookshelf_id", value=bookshelf_id),
                Hidden(name="title", value=book_data.get('title', '')),
                Hidden(name="author", value=book_data.get('author', '')),
                Hidden(name="isbn", value=book_data.get('isbn', '')),
                Hidden(name="description", value=book_data.get('description', '')[:500]),
                Hidden(name="cover_url", value=book_data.get('cover_url', '')),
                Hidden(name="publisher", value=book_data.get('publisher', '')),
                Hidden(name="published_date", value=book_data.get('published_date', '')),
                Hidden(name="page_count", value=book_data.get('page_count', 0)),
                Button("Add to Shelf", type="submit", cls="add-book-btn"),
                hx_post="/api/add-book-and-close",
                hx_target="#book-grid",
                hx_swap="beforeend"
            ),
            cls="search-result-info"
        )
    )


def CreateBookshelfForm():
    """Form for creating a new bookshelf."""
    return Form(
        action="/shelf/create",
        method="post"
    )(
        Fieldset(
            Label("Shelf Name", Input(
                name="name",
                type="text",
                placeholder="My Awesome Books",
                required=True,
                maxlength=100
            )),
            Label("Description (Optional)", Textarea(
                name="description",
                placeholder="What's this shelf about?",
                rows=3,
                maxlength=500
            )),
            Label("Privacy Level", Select(
                Option("Public - Visible to everyone and appears in search results", value="public", selected=True),
                Option("Link Only - Hidden from search, but viewable by anyone with the link", value="link-only"),
                Option("Private - Coming soon (we're working on true privacy)", value="private", disabled=True),
                name="privacy"
            )),
            P("Note: All shelves are shared across the decentralized network. True private shelves are coming soon!", 
              cls="privacy-explanation", 
              style="font-size: 0.85rem; color: var(--brand-muted); margin-top: 0.5rem; font-style: italic;"),
            Label(
                CheckboxX(
                    id="self_join",
                    name="self_join"
                ),
                Div(
                    Span("Open Collaboration", cls="self-join-primary-label"),
                    Span("Allow anyone to join as a contributor", cls="self-join-secondary-label"),
                    cls="self-join-label-content"
                ),
                cls="self-join-label"
            ),
            P("⚠️ Alpha Version: Data may be reset during development.", 
              cls="alpha-form-disclaimer", 
              style="font-size: 0.8rem; color: var(--brand-warning); margin-top: 1rem; padding: 0.5rem; background: var(--brand-warning-bg); border-radius: 4px; border-left: 3px solid var(--brand-warning);"),
        ),
        Button("Create Bookshelf", type="submit", cls="primary")
    )


def ContactForm():
    """Contact form component."""
    return Div(
        Form(
            Div(
                Label("Your Name", Input(
                    name="name",
                    type="text",
                    placeholder="Enter your full name",
                    required=True,
                    cls="contact-input"
                )),
                Label("Your Email", Input(
                    name="email",
                    type="email",
                    placeholder="your.email@example.com",
                    required=True,
                    cls="contact-input"
                )),
                Label("Subject", Input(
                    name="subject",
                    type="text",
                    placeholder="What's this about?",
                    required=True,
                    cls="contact-input"
                )),
                Label("Message", Textarea(
                    name="message",
                    placeholder="Tell us what's on your mind...",
                    rows=5,
                    required=True,
                    cls="contact-textarea"
                )),
                cls="contact-form-fields"
            ),
            hx_post="/api/contact",
            hx_target="#contact-form-response",
            hx_swap="innerHTML",
            cls="contact-form",
            id="contact-form"
        ),
        # Response container for success/error messages
        Div(id="contact-form-response"),
        cls="contact-form-container"
    )


def ContactFormSuccess():
    """Success message after contact form submission."""
    return Div(
        Div(
            I(cls="fas fa-check-circle", style="color: #28a745; font-size: 3rem; margin-bottom: 1rem;"),
            H3("Message Sent!", cls="contact-success-title"),
            P("Thank you for reaching out! We've received your message and will get back to you as soon as possible.", cls="contact-success-message"),
            cls="contact-success-content"
        ),
        # Auto-close script - closes immediately after showing success
        Script("""
            setTimeout(() => {
                htmx.ajax('GET', '/api/close-contact-modal', {
                    target: '#contact-modal-container',
                    swap: 'innerHTML'
                });
            }, 1000);
        """),
        cls="contact-success-container"
    )


def ContactFormError(error_message: str = "An error occurred while sending your message."):
    """Error message for contact form submission."""
    return Div(
        Div(
            I(cls="fas fa-exclamation-triangle", style="color: #dc3545; font-size: 2rem; margin-bottom: 1rem;"),
            H3("Message Failed to Send", cls="contact-error-title"),
            P(error_message, cls="contact-error-message"),
            P("Please try again or contact us directly at the email address in the footer.", cls="contact-error-suggestion"),
            Button(
                "Try Again",
                hx_get="/api/contact-modal",
                hx_target="#contact-modal-container",
                hx_swap="innerHTML",
                cls="contact-btn-primary",
                style="margin-top: 1rem;"
            ),
            cls="contact-error-content"
        ),
        cls="contact-error-container"
    )


def ExploreSearchForm(query: str = "", privacy: str = "public", sort_by: str = "smart_mix", open_to_contributions: str = "", book_title: str = "", book_author: str = "", book_isbn: str = ""):
    """Enhanced search form for the unified explore page with advanced search capabilities."""
    return Form(
        # Main search row with smart defaults
        Div(
            Input(
                name="query", 
                type="search", 
                placeholder="Search bookshelves and books...", 
                value=query,
                cls="explore-search-input"
            ),
            Select(
                Option("Smart Mix", value="smart_mix", selected=(sort_by == "smart_mix")),
                Option("Recently Active", value="recently_active", selected=(sort_by == "recently_active")),
                Option("Most Contributors", value="most_contributors", selected=(sort_by == "most_contributors")),
                Option("Most Viewers", value="most_viewers", selected=(sort_by == "most_viewers")),
                Option("Newest", value="created_at", selected=(sort_by == "created_at")),
                Option("Alphabetical", value="name", selected=(sort_by == "name")),
                name="sort_by",
                cls="explore-sort-select"
            ),
            Select(
                Option("All Shelves", value="", selected=(open_to_contributions == "")),
                Option("Open to Contributions", value="true", selected=(open_to_contributions == "true")),
                Option("Invite Only", value="false", selected=(open_to_contributions == "false")),
                name="open_to_contributions",
                title="Filter by contribution access",
                cls="explore-filter-select"
            ),
            Button("🔍 Explore", type="submit", cls="explore-search-btn primary"),
            cls="explore-search-row"
        ),
        
        # Advanced search toggle and fields
        A("Advanced Search", href="#", onclick="toggleExploreAdvancedSearch(event)", cls="advanced-search-toggle"),
        Div(
            Fieldset(
                Label("Book Title", Input(name="book_title", type="text", placeholder="e.g., The Hobbit", value=book_title)),
                Label("Book Author", Input(name="book_author", type="text", placeholder="e.g., J.R.R. Tolkien", value=book_author)),
                Label("ISBN", Input(name="book_isbn", type="text", placeholder="e.g., 9780547928227", value=book_isbn)),
                cls="advanced-search-fieldset"
            ),
            id="explore-advanced-search-fields",
            style="display: none; margin-top: 1rem;",
            cls="advanced-search-container"
        ),
        
        # Privacy is always public for explore, but we keep it hidden for consistency
        Hidden(name="privacy", value="public"),
        
        Script("""
            function toggleExploreAdvancedSearch(event) {
                event.preventDefault();
                const advancedFields = document.getElementById('explore-advanced-search-fields');
                const toggleLink = event.target;
                if (advancedFields.style.display === 'none') {
                    advancedFields.style.display = 'block';
                    toggleLink.textContent = 'Hide Advanced Search';
                } else {
                    advancedFields.style.display = 'none';
                    toggleLink.textContent = 'Advanced Search';
                }
            }
            
            // Show advanced search if any advanced fields have values
            document.addEventListener('DOMContentLoaded', function() {
                const bookTitle = document.querySelector('input[name="book_title"]').value;
                const bookAuthor = document.querySelector('input[name="book_author"]').value;
                const bookIsbn = document.querySelector('input[name="book_isbn"]').value;
                
                if (bookTitle || bookAuthor || bookIsbn) {
                    const advancedFields = document.getElementById('explore-advanced-search-fields');
                    const toggleLink = document.querySelector('.advanced-search-toggle');
                    advancedFields.style.display = 'block';
                    toggleLink.textContent = 'Hide Advanced Search';
                }
            });
        """),
        
        action="/explore",
        method="get",
        cls="explore-search-form"
    )


def SearchForm(query: str = "", search_type: str = "all", book_title: str = "", book_author: str = "", book_isbn: str = "", privacy: str = "public", sort_by: str = "updated_at", open_to_contributions: str = ""):
    """Enhanced search form for shelves, books, and users."""
    return Form(
        # Search type tabs
        Div(
            Label(
                Input(type="radio", name="search_type", value="all", checked=(search_type == "all")),
                "All",
                cls="search-type-tab"
            ),
            Label(
                Input(type="radio", name="search_type", value="shelves", checked=(search_type == "shelves")),
                "Shelves",
                cls="search-type-tab"
            ),
            Label(
                Input(type="radio", name="search_type", value="users", checked=(search_type == "users")),
                "Users",
                cls="search-type-tab"
            ),
            cls="search-type-tabs"
        ),
        
        # Main search row
        Div(
            Input(name="query", type="search", placeholder="Search shelves, books, or users...", value=query),
            Select(
                Option("Public", value="public", selected=(privacy == "public")),
                Option("Link Only", value="link-only", selected=(privacy == "link-only")),
                Option("All", value="all", selected=(privacy == "all")),
                name="privacy"
            ),
            Select(
                Option("Most Recent", value="updated_at", selected=(sort_by == "updated_at")),
                Option("Newest", value="created_at", selected=(sort_by == "created_at")),
                Option("Alphabetical", value="name", selected=(sort_by == "name")),
                Option("Most Books", value="book_count", selected=(sort_by == "book_count")),
                name="sort_by"
            ),
            Select(
                Option("All Shelves", value="", selected=(open_to_contributions == "")),
                Option("Open to Contributions", value="true", selected=(open_to_contributions == "true")),
                Option("Invite Only", value="false", selected=(open_to_contributions == "false")),
                name="open_to_contributions",
                title="Filter by contribution access"
            ),
            Button("Search", type="submit"),
            cls="search-form-grid"
        ),
        
        A("Advanced Search", href="#", onclick="toggleAdvancedSearch(event)", cls="advanced-search-toggle"),
        Div(
            Fieldset(
                Label("Book Title", Input(name="book_title", type="text", placeholder="e.g., The Hobbit", value=book_title)),
                Label("Book Author", Input(name="book_author", type="text", placeholder="e.g., J.R.R. Tolkien", value=book_author)),
                Label("ISBN", Input(name="book_isbn", type="text", placeholder="e.g., 9780547928227", value=book_isbn)),
            ),
            id="advanced-search-fields",
            style="display: none; margin-top: 1rem;"
        ),
        Script("""
            function toggleAdvancedSearch(event) {
                event.preventDefault();
                const advancedFields = document.getElementById('advanced-search-fields');
                const toggleLink = event.target;
                if (advancedFields.style.display === 'none') {
                    advancedFields.style.display = 'block';
                    toggleLink.textContent = 'Hide Advanced Search';
                } else {
                    advancedFields.style.display = 'none';
                    toggleLink.textContent = 'Advanced Search';
                }
            }
        """),
        action="/search",
        method="get",
        cls="search-form"
    )


def SelfJoinButton(bookshelf_slug):
    """Component for users to join an open bookshelf as a contributor."""
    return Div(
        Button(
            "🤝 Contribute to this shelf",
            hx_post=f"/api/shelf/{bookshelf_slug}/self-join",
            hx_target="#self-join-container",
            hx_swap="outerHTML",
            cls="self-join-btn primary small"
        ),
        P(
            "This bookshelf is open to the public! Join to add your own book suggestions",
            cls="self-join-subtitle"
        ),
        cls="self-join-container",
        id="self-join-container"
    )


def SelfJoinSuccess(bookshelf_slug):
    """Success state after user joins a bookshelf."""
    return Div(
        Div(
            "✅ You've joined as a contributor!",
            cls="self-join-success-message"
        ),
        P(
            "You can now add books and vote on this shelf.",
            cls="self-join-success-subtitle"
        ),
        cls="self-join-success-container",
        id="self-join-container"
    )
