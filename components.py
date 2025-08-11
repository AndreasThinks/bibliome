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
    """Render a bookshelf card."""
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗', 
        'private': '🔒'
    }.get(bookshelf.privacy, '🌍')
    
    actions = []
    if can_edit:
        actions.append(
            A("Edit", href=f"/shelf/{bookshelf.slug}/edit", cls="secondary")
        )
    actions.append(
        A("View", href=f"/shelf/{bookshelf.slug}", cls="primary")
    )
    
    return Article(
        cls="bookshelf-card"
    )(
        Header(
            H3(bookshelf.name),
            P(f"{privacy_icon} {bookshelf.privacy.replace('-', ' ').title()}", cls="privacy-badge")
        ),
        P(bookshelf.description) if bookshelf.description else None,
        Footer(*actions) if actions else None
    )

def BookCard(book, can_upvote=True, user_has_upvoted=False):
    """Render a book card."""
    upvote_btn = Button(
        f"👍 {book.upvotes}",
        hx_post=f"/book/{book.id}/upvote",
        hx_target=f"#book-{book.id}",
        hx_swap="outerHTML",
        disabled=not can_upvote or user_has_upvoted,
        cls="upvote-btn" + (" upvoted" if user_has_upvoted else "")
    ) if can_upvote else Span(f"👍 {book.upvotes}", cls="upvote-count")
    
    return Article(
        Div(
            Img(
                src=book.cover_url or "/static/default-book-cover.png",
                alt=f"Cover of {book.title}",
                cls="book-cover",
                loading="lazy"
            ) if book.cover_url else Div("📖", cls="book-cover-placeholder"),
            cls="book-cover-container"
        ),
        Div(
            H4(book.title, cls="book-title"),
            P(book.author, cls="book-author") if book.author else None,
            P(book.description[:100] + "..." if len(book.description) > 100 else book.description, 
              cls="book-description") if book.description else None,
            Div(upvote_btn, cls="book-actions"),
            cls="book-info"
        ),
        cls="book-card",
        id=f"book-{book.id}"
    )

def BookSearchForm(bookshelf_id: int):
    """Book search component with HTMX."""
    return Div(
        H3("Add Books"),
        Form(
            Input(
                name="query",
                placeholder="Search for books to add...",
                hx_post="/api/search-books",
                hx_trigger="keyup changed delay:500ms",
                hx_target="#search-results",
                hx_vals=f'{{"bookshelf_id": {bookshelf_id}}}',
                autocomplete="off"
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
            Button(
                "Add to Shelf",
                hx_post="/api/add-book",
                hx_vals='{{' + f'''
                    "bookshelf_id": {bookshelf_id},
                    "title": "{book_data.get('title', '').replace('"', '&quot;')}",
                    "author": "{book_data.get('author', '').replace('"', '&quot;')}",
                    "isbn": "{book_data.get('isbn', '')}",
                    "description": "{book_data.get('description', '').replace('"', '&quot;')[:500]}",
                    "cover_url": "{book_data.get('cover_url', '')}",
                    "publisher": "{book_data.get('publisher', '').replace('"', '&quot;')}",
                    "published_date": "{book_data.get('published_date', '')}",
                    "page_count": {book_data.get('page_count', 0)}
                ''' + '}}',
                hx_target="#book-grid",
                hx_swap="afterbegin",
                cls="add-book-btn"
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
