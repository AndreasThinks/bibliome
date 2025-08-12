"""Reusable UI components for BookdIt."""

from fasthtml.common import *
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

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
    
    return Card(
        H3(bookshelf.name),
        P(f"{privacy_icon} {bookshelf.privacy.replace('-', ' ').title()}", cls="privacy-badge"),
        P(bookshelf.description) if bookshelf.description else None,
        footer=A("View", href=f"/shelf/{bookshelf.slug}", cls="primary")
    )

def BookCard(book, can_upvote=True, user_has_upvoted=False):
    """Render a book card."""
    # Get upvote count from the book object (should be set by get_books_with_upvotes)
    upvote_count = getattr(book, 'upvote_count', 0)
    
    if can_upvote:
        # Use the interactive version with upvote functionality
        return book.as_interactive_card(can_upvote=can_upvote, user_has_upvoted=user_has_upvoted, upvote_count=upvote_count)
    else:
        # Use the model's built-in __ft__ method (which will use getattr for upvote_count)
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

def MemberCard(user, permission, is_owner=False, can_manage=False, bookshelf_slug=""):
    """Render a member card with role management."""
    role_badge_colors = {
        'owner': 'badge-owner',
        'admin': 'badge-admin', 
        'editor': 'badge-editor',
        'viewer': 'badge-viewer',
        'pending': 'badge-pending'
    }
    
    # Determine display role
    display_role = 'owner' if is_owner else permission.role
    status_text = f" ({permission.status})" if permission.status == 'pending' else ""
    
    avatar = Img(
        src=user.avatar_url,
        alt=user.display_name or user.handle,
        cls="member-avatar"
    ) if user.avatar_url else Div("👤", cls="member-avatar-placeholder")
    
    # Role management controls
    role_controls = None
    if can_manage and not is_owner and permission.status == 'active':
        role_controls = Div(
            Select(
                Option("Admin", value="admin", selected=(permission.role == "admin")),
                Option("Editor", value="editor", selected=(permission.role == "editor")),
                Option("Viewer", value="viewer", selected=(permission.role == "viewer")),
                name="role",
                hx_post=f"/api/shelf/{bookshelf_slug}/member/{user.did}/role",
                hx_target=f"#member-{user.did}",
                hx_swap="outerHTML"
            ),
            Button(
                "Remove",
                hx_delete=f"/api/shelf/{bookshelf_slug}/member/{user.did}",
                hx_target=f"#member-{user.did}",
                hx_swap="outerHTML",
                hx_confirm="Are you sure you want to remove this member?",
                cls="secondary small"
            ),
            cls="member-controls"
        )
    elif can_manage and permission.status == 'pending':
        role_controls = Div(
            Button(
                "Approve",
                hx_post=f"/api/shelf/{bookshelf_slug}/member/{user.did}/approve",
                hx_target=f"#member-{user.did}",
                hx_swap="outerHTML",
                cls="primary small"
            ),
            Button(
                "Reject",
                hx_delete=f"/api/shelf/{bookshelf_slug}/member/{user.did}",
                hx_target=f"#member-{user.did}",
                hx_swap="outerHTML",
                cls="secondary small"
            ),
            cls="member-controls"
        )
    
    return Div(
        avatar,
        Div(
            H4(user.display_name or user.handle, cls="member-name"),
            P(f"@{user.handle}", cls="member-handle"),
            Span(display_role.title() + status_text, cls=f"role-badge {role_badge_colors.get(display_role, 'badge-viewer')}"),
            cls="member-info"
        ),
        role_controls,
        cls="member-card",
        id=f"member-{user.did}"
    )

def ShareInterface(bookshelf, members, pending_members, invites, can_manage=False, can_generate_invites=False):
    """Complete share interface for a bookshelf."""
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗', 
        'private': '🔒'
    }.get(bookshelf.privacy, '🌍')
    
    # Privacy settings section - build all children first
    privacy_children = [
        H3("Privacy Settings"),
        Div(
            Span(f"{privacy_icon} {bookshelf.privacy.replace('-', ' ').title()}", cls="current-privacy"),
            P({
                'public': "Anyone can find and view this bookshelf",
                'link-only': "Only people with the link can view this bookshelf", 
                'private': "Only invited members can view this bookshelf"
            }.get(bookshelf.privacy, "")),
            cls="privacy-info"
        )
    ]
    
    if can_manage:
        privacy_children.append(
            Form(
                Select(
                    Option("🌍 Public - Anyone can find and view", value="public", selected=(bookshelf.privacy == "public")),
                    Option("🔗 Link Only - Only people with the link can view", value="link-only", selected=(bookshelf.privacy == "link-only")),
                    Option("🔒 Private - Only invited members can view", value="private", selected=(bookshelf.privacy == "private")),
                    name="privacy",
                    hx_post=f"/api/shelf/{bookshelf.slug}/privacy",
                    hx_target="#privacy-section",
                    hx_swap="outerHTML"
                ),
                cls="privacy-form"
            )
        )
    
    privacy_section = Div(*privacy_children, cls="privacy-section")
    
    # Members section
    member_cards = [MemberCard(member['user'], member['permission'], 
                              is_owner=(member['user'].did == bookshelf.owner_did),
                              can_manage=can_manage, bookshelf_slug=bookshelf.slug) 
                   for member in members]
    
    members_section = Div(
        H3(f"Members ({len(members)})"),
        Div(*member_cards, cls="members-grid", id="members-list") if member_cards else P("No members yet.", cls="empty-message"),
        cls="members-section"
    )
    
    # Pending members section (for private shelves)
    pending_section = None
    if bookshelf.privacy == 'private' and (pending_members or can_manage):
        pending_cards = [MemberCard(member['user'], member['permission'], 
                                   can_manage=can_manage, bookshelf_slug=bookshelf.slug) 
                        for member in pending_members]
        
        pending_section = Div(
            H3(f"Pending Invitations ({len(pending_members)})"),
            Div(*pending_cards, cls="members-grid", id="pending-list") if pending_cards else P("No pending invitations.", cls="empty-message"),
            cls="pending-section"
        )
    
    # Invite generation section
    invite_section = None
    if can_generate_invites:
        active_invites = [invite for invite in invites if invite.is_active]
        
        invite_section = Div(
            H3("Invite Links"),
            Form(
                Div(
                    Label("Role for new members:", Select(
                        Option("Viewer", value="viewer", selected=True),
                        Option("Editor", value="editor"),
                        Option("Admin", value="admin") if can_manage else None,
                        name="role"
                    )),
                    Label("Expires in:", Select(
                        Option("Never", value="", selected=True),
                        Option("1 day", value="1"),
                        Option("7 days", value="7"),
                        Option("30 days", value="30"),
                        name="expires_days"
                    )),
                    Label("Max uses:", Input(
                        type="number",
                        name="max_uses",
                        placeholder="Unlimited",
                        min="1"
                    )),
                    cls="invite-form-fields"
                ),
                Button("Generate Invite Link", type="submit", cls="primary"),
                hx_post=f"/api/shelf/{bookshelf.slug}/invite",
                hx_target="#active-invites",
                hx_swap="beforeend",
                cls="invite-form"
            ),
            Div(
                H4("Active Invite Links"),
                Div(*[InviteCard(invite, bookshelf.slug) for invite in active_invites], 
                    id="active-invites") if active_invites else P("No active invites.", cls="empty-message"),
                cls="invites-list"
            ),
            cls="invite-section"
        )
    
    return Div(
        privacy_section,
        members_section,
        pending_section,
        invite_section,
        cls="share-interface"
    )

def InviteCard(invite, bookshelf_slug):
    """Render an invite link card."""
    # Use BASE_URL from environment variable
    base_url = os.getenv('BASE_URL', 'http://0.0.0.0:5001/').rstrip('/')
    invite_url = f"{base_url}/shelf/join/{invite.invite_code}"
    
    expires_text = ""
    if invite.expires_at:
        expires_text = f"Expires: {invite.expires_at.strftime('%Y-%m-%d %H:%M')}"
    
    uses_text = ""
    if invite.max_uses:
        uses_text = f"Uses: {invite.uses_count}/{invite.max_uses}"
    else:
        uses_text = f"Uses: {invite.uses_count}"
    
    return Div(
        Div(
            Strong(f"{invite.role.title()} Invite"),
            P(expires_text) if expires_text else None,
            P(uses_text),
            cls="invite-info"
        ),
        Div(
            Input(
                value=invite_url,
                readonly=True,
                cls="invite-url",
                onclick="this.select()"
            ),
            Button(
                "Copy",
                onclick=f"navigator.clipboard.writeText('{invite_url}'); this.textContent='Copied!'; setTimeout(() => this.textContent='Copy', 2000)",
                cls="secondary small"
            ),
            cls="invite-url-section"
        ),
        Button(
            "Revoke",
            hx_delete=f"/api/shelf/{bookshelf_slug}/invite/{invite.id}",
            hx_target="closest .invite-card",
            hx_swap="outerHTML",
            hx_confirm="Are you sure you want to revoke this invite?",
            cls="secondary small"
        ),
        cls="invite-card",
        id=f"invite-{invite.id}"
    )
