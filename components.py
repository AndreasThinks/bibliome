"""Reusable UI components for BookdIt."""

from fasthtml.common import *
from datetime import datetime
from typing import Optional, List, Dict, Any

def NavBar(auth=None):
    """Main navigation bar."""
    if auth:
        user_menu = Div(
            Span(f"👋 {auth.get('display_name', auth.get('handle', 'User'))}"),
            A("My Shelves", href="/"),
            A("Create Shelf", href="/shelf/new"),
            A("Logout", href="/auth/logout"),
            cls="user-menu"
        )
    else:
        user_menu = A("Login", href="/auth/login", cls="login-btn")
    
    return Nav(
        Div(
            A("📚 BookdIt", href="/", cls="logo"),
            user_menu,
            cls="nav-container"
        ),
        cls="main-nav"
    )

def BookshelfCard(bookshelf, is_owner=False, can_edit=False):
    """Render a bookshelf card with edit options if needed."""
    if can_edit:
        # For owners, add edit button to the footer
        privacy_icon = {
            'public': '🌍',
            'link-only': '🔗', 
            'private': '🔒'
        }.get(bookshelf.privacy, '🌍')
        
        return Card(
            H3(bookshelf.name),
            P(f"{privacy_icon} {bookshelf.privacy.replace('-', ' ').title()}", cls="privacy-badge"),
            P(bookshelf.description) if bookshelf.description else None,
            footer=Div(
                A("Edit", href=f"/shelf/{bookshelf.slug}/edit", cls="secondary"),
                A("View", href=f"/shelf/{bookshelf.slug}", cls="primary"),
                style="display: flex; gap: 0.5rem;"
            )
        )
    else:
        # Use the model's built-in __ft__ method
        return bookshelf

def BookCard(book, can_upvote=True, user_has_upvoted=False):
    """Render a book card."""
    if can_upvote:
        # Use the interactive version with upvote functionality
        return book.as_interactive_card(can_upvote=can_upvote, user_has_upvoted=user_has_upvoted)
    else:
        # Use the model's built-in __ft__ method
        return book

def BookSearchForm(bookshelf_id: int):
    """Book search component with HTMX."""
    return Div(
        H3("Add Books"),
        Form(
            Div(
                Input(
                    name="query",
                    placeholder="Search for books to add...",
                    hx_post="/api/search-books",
                    hx_trigger="keyup changed delay:500ms",
                    hx_target="#search-results",
                    hx_vals=f'{{"bookshelf_id": {bookshelf_id}}}',
                    hx_indicator="#search-loading",
                    autocomplete="off"
                ),
                Div(
                    Div(cls="spinner"),
                    "Searching...",
                    id="search-loading",
                    cls="htmx-indicator loading-container",
                    style="display: none;"
                ),
                style="position: relative;"
            ),
            cls="search-form"
        ),
        Div(id="search-results", cls="search-results"),
        cls="book-search"
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
                hx_post="/api/add-book",
                hx_target="#book-grid",
                hx_swap="afterbegin",
                hx_on_after_request="const emptyState = document.getElementById('empty-state-container'); if (emptyState) { emptyState.remove(); }"
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
                Option("Public - Anyone can find and view", value="public", selected=True),
                Option("Link Only - Only people with the link can view", value="link-only"),
                Option("Private - Only invited people can view", value="private"),
                name="privacy"
            ))
        ),
        Button("Create Bookshelf", type="submit", cls="primary")
    )

def Alert(message: str, type: str = "info"):
    """Alert component for messages."""
    return Div(
        message,
        cls=f"alert alert-{type}",
        role="alert"
    )

def Modal(title: str, content, id: str = "modal"):
    """Modal dialog component."""
    return Div(
        Div(
            Header(
                H3(title),
                Button("×", cls="close-btn", onclick=f"document.getElementById('{id}').style.display='none'")
            ),
            Div(content, cls="modal-content"),
            cls="modal-dialog"
        ),
        cls="modal",
        id=id,
        style="display: none;"
    )

def EmptyState(title: str, description: str, action_text: str = None, action_href: str = None):
    """Empty state component."""
    action = A(action_text, href=action_href, cls="primary") if action_text and action_href else None
    
    return Div(
        H3(title),
        P(description),
        action,
        cls="empty-state"
    )

def LoadingSpinner():
    """Loading spinner component."""
    return Div(
        Div(cls="spinner"),
        "Loading...",
        cls="loading-container"
    )

def Pagination(current_page: int, total_pages: int, base_url: str):
    """Pagination component."""
    if total_pages <= 1:
        return None
    
    links = []
    
    # Previous page
    if current_page > 1:
        links.append(A("← Previous", href=f"{base_url}?page={current_page - 1}"))
    
    # Page numbers (show up to 5 pages around current)
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    for page in range(start_page, end_page + 1):
        if page == current_page:
            links.append(Span(str(page), cls="current-page"))
        else:
            links.append(A(str(page), href=f"{base_url}?page={page}"))
    
    # Next page
    if current_page < total_pages:
        links.append(A("Next →", href=f"{base_url}?page={current_page + 1}"))
    
    return Nav(*links, cls="pagination")
