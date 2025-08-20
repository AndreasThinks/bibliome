"""Reusable UI components for BookdIt."""

from fasthtml.common import *
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

def NavBar(auth=None):
    """Main navigation bar with HTMX-powered mobile hamburger menu."""
    # Define menu links based on auth status
    if auth:
        links = [
            A("My Shelves", href="/"),
            A("Your Network", href="/network"),
            A("Explore", href="/explore"),
            A("Create Shelf", href="/shelf/new"),
        ]
        
        # Create user profile card
        user_avatar = Img(
            src=auth.get('avatar_url', ''),
            alt=auth.get('display_name', auth.get('handle', 'User')),
            cls="nav-user-avatar"
        ) if auth.get('avatar_url') else Div("👤", cls="nav-user-avatar-placeholder")
        
        user_profile_card = Div(
            user_avatar,
            Span(auth.get('display_name', auth.get('handle', 'User')), cls="nav-user-name"),
            A("×", href="/auth/logout", cls="nav-logout-icon", title="Logout"),
            cls="nav-user-profile-card",
            title="Go to Dashboard",
            onclick="window.location.href='/'"
        )
    else:
        links = [
            A("Explore", href="/explore"),
            A("Search", href="/search"),
            A("Login", href="/auth/login", cls="login-btn"),
        ]
        user_profile_card = None

    return Nav(
        Div(
            A(
                Img(src="/static/bibliome_transparent_no_text.png", alt="Bibliome", cls="logo-img"),
                "Bibliome",
                href="/", 
                cls="logo"
            ),
            # Desktop menu
            Div(
                *links,
                user_profile_card,
                cls="user-menu desktop-menu"
            ),
            # Mobile menu button with HTMX
            Button(
                "☰",
                cls="mobile-menu-toggle",
                **{"hx-on:click": "document.getElementById('mobile-menu').classList.toggle('active')"}
            ),
            cls="nav-container"
        ),
        # Mobile menu (hidden by default)
        Div(
            *links,
            A("Logout", href="/auth/logout") if auth else None,
            cls="mobile-menu",
            id="mobile-menu"
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
    
    # Add badges for shelf features
    badges = [P(f"{privacy_icon} {bookshelf.privacy.replace('-', ' ').title()}", cls="privacy-badge")]
    
    # Add "open to contributions" badge if applicable
    if getattr(bookshelf, 'self_join', False):
        badges.append(P("🤝 Open to contributions", cls="contribution-badge"))
    
    return A(
        href=f"/shelf/{bookshelf.slug}",
        cls="bookshelf-card-link"
    )(
        Card(
            H3(bookshelf.name),
            P(bookshelf.description) if bookshelf.description else None,
            Div(*badges, cls="shelf-badges"),
            cls="bookshelf-card-content"
        )
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
                Option("Public - Anyone can find and view", value="public", selected=True),
                Option("Link Only - Only people with the link can view", value="link-only"),
                Option("Private - Only invited people can view", value="private"),
                name="privacy"
            )),
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
            P(
                "When enabled, anyone who can view this shelf will see a 'Join as Contributor' button to add books and vote.",
                cls="self-join-help-text"
            )
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
            Div(
                H2(title),
                Button("×", onclick=f"document.getElementById('{id}').style.display='none'", cls="modal-close"),
                cls="modal-header"
            ),
            Div(content, cls="modal-body"),
            cls="modal-content"
        ),
        cls="modal-overlay",
        id=id,
        onclick=f"if(event.target === this) document.getElementById('{id}').style.display='none'"
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

def EnhancedEmptyState(can_add=False, shelf_id=None, user_auth_status="anonymous"):
    """A more visually appealing empty state for shelves with no books."""
    if can_add:
        # User can add books - show encouraging message with call to action
        return Card(
            Div(
                Div("📚", cls="empty-icon"),
                H3("Your shelf awaits its first book", cls="empty-title"),
                P("Start building your collection by adding books that matter to you.", cls="empty-description"),
                cls="empty-content"
            ),
            cls="empty-state-card"
        )
    elif user_auth_status == "anonymous":
        # Anonymous user - encourage them to sign in
        return Card(
            Div(
                Div("📚", cls="empty-icon"),
                H3("This shelf is waiting for its first book", cls="empty-title"),
                P("Sign in to contribute to this collection and vote on books.", cls="empty-description"),
                A("Sign In", href="/auth/login", cls="primary empty-cta"),
                cls="empty-content"
            ),
            cls="empty-state-card"
        )
    else:
        # Logged in user without permission
        return Card(
            Div(
                Div("📚", cls="empty-icon"),
                H3("This shelf is waiting for its first book", cls="empty-title"),
                P("Only contributors can add books to this shelf. Contact the owner for access.", cls="empty-description"),
                cls="empty-content"
            ),
            cls="empty-state-card"
        )

def ShelfHeader(shelf, action_buttons, current_view="grid", can_share=False, user_is_logged_in=False):
    """A visually appealing header for the shelf page."""
    # Create both toggle buttons - only one will be visible at a time
    grid_toggle_btn = Button(
        "⊞",
        hx_get=f"/api/shelf/{shelf.slug}/toggle-view?view=grid",
        hx_target="#books-section",
        hx_swap="outerHTML",
        cls="action-btn grid-toggle-btn",
        title="Switch to Grid View",
        id="grid-toggle-btn"
    )
    
    list_toggle_btn = Button(
        "☰",
        hx_get=f"/api/shelf/{shelf.slug}/toggle-view?view=list",
        hx_target="#books-section",
        hx_swap="outerHTML",
        cls="action-btn list-toggle-btn",
        title="Switch to List View",
        id="list-toggle-btn"
    )
    
    # Add share button for logged-in users who can view the shelf
    # This allows all users (including viewers/contributors) to access share options
    share_btn = Button(
        I(cls="fas fa-share-alt"),
        hx_get=f"/api/shelf/{shelf.slug}/share-modal",
        hx_target="#share-modal-container",
        hx_swap="innerHTML",
        cls="action-btn share-btn",
        title="Share this shelf"
    ) if user_is_logged_in else None
    
    # Convert action buttons to icon buttons
    icon_action_buttons = []
    for button in action_buttons or []:
        if hasattr(button, 'children') and button.children and "Manage" in str(button.children[0]):
            # Convert manage button to icon
            icon_action_buttons.append(A(
                "⚙️",
                href=button.attrs.get('href', '#'),
                cls="action-btn manage-btn",
                title="Manage Shelf"
            ))
        else:
            icon_action_buttons.append(button)
    
    # Create action button group with toggle buttons, share button, and other actions
    all_actions = [grid_toggle_btn, list_toggle_btn]
    if share_btn:
        all_actions.append(share_btn)
    all_actions.extend(icon_action_buttons)
    
    return Card(
        H1(shelf.name, cls="shelf-title"),
        P(shelf.description, cls="shelf-description") if shelf.description else None,
        Div(
            Div(
                Span(f"🌍 {shelf.privacy.replace('-', ' ').title()}", cls="privacy-badge"),
                Span("🤝 Open to contributions", cls="contribution-badge") if getattr(shelf, 'self_join', False) else None,
                cls="shelf-badges"
            ),
            Div(*all_actions, cls="shelf-actions"),
            cls="shelf-meta"
        ),
        cls="shelf-header-card"
    )

def LoadingSpinner():
    """Loading spinner component."""
    return Div(
        Div(cls="spinner"),
        "Loading...",
        cls="loading-container"
    )

def Pagination(current_page: int, total_pages: int, base_url: str):
    """Enhanced pagination component with accessibility and mobile support."""
    if total_pages <= 1:
        return None

    links = []

    # Previous page with better accessibility
    if current_page > 1:
        prev_url = f"{base_url}?page={current_page - 1}"
        prev_label = "Previous page"
        links.append(A(
            "← Previous",
            href=prev_url,
            title=prev_label,
            aria_label=prev_label,
            cls="pagination-prev"
        ))

    # Page numbers with smart truncation
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)

    # Add ellipsis for large page ranges
    if start_page > 1:
        links.append(Span("…", cls="pagination-ellipsis", aria_hidden="true"))

    for page in range(start_page, end_page + 1):
        if page == current_page:
            links.append(Span(
                str(page),
                cls="current-page",
                title=f"Current page, page {page} of {total_pages}",
                aria_current="page",
                aria_label=f"Current page, page {page} of {total_pages}"
            ))
        else:
            page_url = f"{base_url}?page={page}"
            page_label = f"Go to page {page}"
            links.append(A(
                str(page),
                href=page_url,
                title=page_label,
                aria_label=page_label
            ))

    # Add ellipsis for large page ranges
    if end_page < total_pages:
        links.append(Span("…", cls="pagination-ellipsis", aria_hidden="true"))

    # Next page with better accessibility
    if current_page < total_pages:
        next_url = f"{base_url}?page={current_page + 1}"
        next_label = "Next page"
        links.append(A(
            "Next →",
            href=next_url,
            title=next_label,
            aria_label=next_label,
            cls="pagination-next"
        ))

    # Add screen reader context
    sr_context = Span(
        f"Page {current_page} of {total_pages}",
        cls="sr-only",
        id="pagination-context"
    )

    # Create pagination with ARIA navigation role
    pagination_nav = Nav(
        *links,
        cls="pagination",
        role="navigation",
        aria_labelledby="pagination-context",
        aria_label="Pagination navigation"
    )

    return Div(
        sr_context,
        pagination_nav,
        cls="pagination-container"
    )

def MemberCard(user, permission, is_owner=False, can_manage=False, bookshelf_slug=""):
    """Render a member card with improved role management."""
    role_badge_colors = {
        'owner': 'badge-owner',
        'moderator': 'badge-moderator', 
        'contributor': 'badge-contributor',
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
    
    # Role management controls with improved UX
    role_controls = None
    if can_manage and not is_owner and permission.status == 'active':
        role_controls = Div(
            # Read mode - show current role with edit button
            Div(
                Span(f"{display_role.title()}", cls=f"role-display {role_badge_colors.get(display_role, 'badge-viewer')}"),
                Button(
                    "Edit",
                    hx_get=f"/api/shelf/{bookshelf_slug}/member/{user.did}/edit-role",
                    hx_target=f"#member-controls-{user.did}",
                    hx_swap="outerHTML",
                    cls="edit-role-btn secondary small",
                    title="Change member role"
                ),
                Button(
                    "Remove",
                    hx_delete=f"/api/shelf/{bookshelf_slug}/member/{user.did}",
                    hx_target=f"#member-{user.did}",
                    hx_swap="outerHTML",
                    hx_confirm="Are you sure you want to remove this member?",
                    cls="remove-member-btn secondary small"
                ),
                cls="role-controls-read",
                id=f"member-controls-{user.did}"
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
            H4(A(user.display_name or user.handle, href=f"/user/{user.handle}", cls="member-name-link", title="View profile"), cls="member-name"),
            P(A(f"@{user.handle}", href=f"/user/{user.handle}", cls="member-handle-link", title="View profile"), cls="member-handle"),
            Span(display_role.title() + status_text, cls=f"role-badge {role_badge_colors.get(display_role, 'badge-viewer')}"),
            cls="member-info"
        ),
        role_controls,
        cls="member-card",
        id=f"member-{user.did}"
    )

def MemberRoleEditor(user, current_role, bookshelf_slug):
    """Component for editing a member's role with confirmation flow."""
    role_options = [
        ("viewer", "Viewer", "Can view the bookshelf"),
        ("contributor", "Contributor", "Can add and vote on books"),
        ("moderator", "Moderator", "Can manage books and members")
    ]
    
    return Div(
        Select(
            *[Option(
                f"{title} - {description}", 
                value=value, 
                selected=(current_role == value)
            ) for value, title, description in role_options],
            name="new_role",
            id=f"role-select-{user.did}",
            cls="role-select"
        ),
        Div(
            Button(
                "Save",
                hx_post=f"/api/shelf/{bookshelf_slug}/member/{user.did}/role-preview",
                hx_include=f"#role-select-{user.did}",
                hx_target=f"#member-controls-{user.did}",
                hx_swap="outerHTML",
                cls="save-role-btn primary small",
                title="Preview role change"
            ),
            Button(
                "Cancel",
                hx_get=f"/api/shelf/{bookshelf_slug}/member/{user.did}/cancel-edit",
                hx_target=f"#member-controls-{user.did}",
                hx_swap="outerHTML",
                cls="cancel-role-btn secondary small"
            ),
            cls="role-edit-buttons"
        ),
        cls="role-controls-edit",
        id=f"member-controls-{user.did}"
    )

def RoleChangePreview(user, current_role, new_role, bookshelf_slug):
    """Component showing role change preview with confirmation."""
    role_descriptions = {
        'viewer': "Can view the bookshelf",
        'contributor': "Can add and vote on books", 
        'moderator': "Can manage books and members"
    }
    
    # Determine if this is a sensitive change (role downgrade)
    role_hierarchy = ['viewer', 'contributor', 'moderator']
    current_level = role_hierarchy.index(current_role) if current_role in role_hierarchy else 0
    new_level = role_hierarchy.index(new_role) if new_role in role_hierarchy else 0
    is_downgrade = new_level < current_level
    
    confirmation_text = f"Change {user.display_name or user.handle} from {current_role.title()} to {new_role.title()}?"
    if is_downgrade:
        confirmation_text += f" This will reduce their permissions."
    
    return Div(
        Div(
            P(confirmation_text, cls="role-change-confirmation"),
            P(f"New permissions: {role_descriptions.get(new_role, 'Unknown')}", cls="role-change-description"),
            cls="role-change-preview"
        ),
        Div(
            Button(
                "Confirm",
                hx_post=f"/api/shelf/{bookshelf_slug}/member/{user.did}/role-confirm",
                hx_vals=f'{{"new_role": "{new_role}"}}',
                hx_target=f"#member-{user.did}",
                hx_swap="outerHTML",
                cls="confirm-role-btn primary small"
            ),
            Button(
                "Cancel",
                hx_get=f"/api/shelf/{bookshelf_slug}/member/{user.did}/cancel-edit",
                hx_target=f"#member-controls-{user.did}",
                hx_swap="outerHTML",
                cls="cancel-role-btn secondary small"
            ),
            cls="role-confirm-buttons"
        ),
        cls="role-controls-confirm",
        id=f"member-controls-{user.did}"
    )

def ShareInterface(bookshelf, members, invites, can_manage=False, can_generate_invites=False, req=None):
    """Complete share interface for a bookshelf."""
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
    
    # REMOVED: Pending members section - all invites now create active permissions immediately
    # This functionality is preserved in the backend for future approval workflows
    
    # Invite generation section
    invite_section = None
    if can_generate_invites:
        active_invites = [invite for invite in invites if invite.is_active]
        
        invite_section = Div(
            H3("Invite Links"),
            Form(
                Div(
                    Label("Role for new members:", Select(
                        Option("Viewer - Can view the bookshelf", value="viewer", selected=True),
                        Option("Contributor - Can add and vote on books", value="contributor"),
                        Option("Moderator - Can manage books and members", value="moderator") if can_manage else None,
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
                Div(
                    *[InviteCard(invite, bookshelf.slug, req) for invite in active_invites] if active_invites 
                    else [P("No active invites.", cls="empty-message")],
                    id="active-invites"
                ),
                cls="invites-list"
            ),
            cls="invite-section"
        )
    
    return Div(
        members_section,
        invite_section,
        cls="share-interface"
    )

def get_base_url(req):
    """Get the base URL from the request."""
    if not req:
        return os.getenv('BASE_URL', 'http://localhost:5001').rstrip('/')
    scheme = 'https' if req.url.is_secure else 'http'
    return f"{scheme}://{req.url.netloc}"

def InviteCard(invite, bookshelf_slug, req=None):
    """Render an invite link card."""
    base_url = get_base_url(req)
    invite_url = f"{base_url}/shelf/join/{invite.invite_code}"
    
    expires_text = ""
    if invite.expires_at:
        if isinstance(invite.expires_at, str):
            try:
                expires_dt = datetime.fromisoformat(invite.expires_at.replace('Z', '+00:00'))
            except:
                expires_dt = datetime.now()
        else:
            expires_dt = invite.expires_at
        expires_text = f"Expires: {expires_dt.strftime('%Y-%m-%d %H:%M')}"
    
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

def LandingPageHero():
    """Hero section for the landing page."""
    return Section(
        Div(
            Div(
                H1("Welcome to Bibliome", cls="hero-title"),
                P("The books you love, shared with your network.", cls="hero-subtitle"),
                Div(
                    A("Join the Community", href="/auth/login", cls="primary hero-cta"),
                    A("Browse Collections", href="/explore", cls="secondary hero-cta-secondary"),
                    cls="hero-actions"
                ),
                cls="hero-content"
            ),
            Div(
                Img(src="/static/bibliome_transparent_no_text.png", alt="Bibliome Logo", cls="hero-logo"),
                cls="hero-visual"
            ),
            cls="hero-container"
        ),
        cls="hero-section"
    )

def FeaturesSection():
    """Features section for the landing page."""
    features = [
        {
            "icon": "📚",
            "title": "Curate Collections",
            "description": "Create themed bookshelves for any purpose - reading lists, book club selections, or personal favorites."
        },
        {
            "icon": "🤝",
            "title": "Collaborate & Share",
            "description": "Keep your ists private, or invite your network to contribute: friends, family, your class, or open it to the entire world."
        },
        {
            "icon": "🔗",
            "title": "Decentralised and Open-source",
            "description": "Bibliome is open-source and built on AT-Proto, the protocol behind Bluesky: your followers and your data stays secure and belongs to you."
        }
    ]
    
    feature_cards = [
        Div(
            Div(feature["icon"], cls="feature-icon"),
            H3(feature["title"], cls="feature-title"),
            P(feature["description"], cls="feature-description"),
            cls="feature-card"
        ) for feature in features
    ]
    
    return Section(
        Container(
            Div(*feature_cards, cls="features-grid"),
        ),
        cls="features-section"
    )

def HowItWorksSection():
    """How it works section for the landing page."""
    steps = [
        {
            "number": "1",
            "title": "Sign In",
            "description": "Connect with your Bluesky account - no new passwords needed."
        },
        {
            "number": "2", 
            "title": "Create Collections",
            "description": "Build your first bookshelf with a theme that matters to you."
        },
        {
            "number": "3",
            "title": "Add Books",
            "description": "Search our vast library and add books with rich metadata and covers."
        },
        {
            "number": "4",
            "title": "Share & Collaborate",
            "description": "Invite others to contribute or keep your collections private."
        },
        {
            "number": "5",
            "title": "Discover",
            "description": "Explore public collections and find your next great read."
        }
    ]
    
    step_cards = [
        Div(
            Div(step["number"], cls="step-number"),
            H3(step["title"], cls="step-title"),
            P(step["description"], cls="step-description"),
            cls="step-card"
        ) for step in steps
    ]
    
    return Section(
        Container(
            H2("How It Works", cls="section-title"),
            Div(*step_cards, cls="steps-grid"),
        ),
        cls="how-it-works-section"
    )

def PublicShelvesPreview(public_shelves):
    """Preview of public bookshelves for the landing page."""
    if not public_shelves:
        return None
    
    return Section(
        Container(
            H2("Discover Public Collections", cls="section-title"),
            P("See what the community is reading and sharing", cls="section-subtitle"),
            Div(*[BookshelfCard(shelf) for shelf in public_shelves[:6]], cls="bookshelf-grid"),
            Div(
                A("Explore All Collections", href="/explore", cls="primary"),
                cls="section-cta"
            )
        ),
        cls="public-shelves-section",
        id="public-shelves"
    )

def UniversalFooter():
    """Universal footer that appears across the entire website."""
    return Footer(
        Container(
            Div(
                # Left side: Text content
                Div(
                    P("A project by ", A("AndreasThinks", href="https://andreasthinks.me/", target="_blank", rel="noopener"), ", built with ❤️ using FastHTML, AT-Proto, and some ✨vibes✨", cls="footer-text"),
                    P("© 2025 Bibliome. Open source and decentralized.", cls="footer-copyright"),
                    cls="footer-left"
                ),
                # Right side: Social icons
                Div(
                    A(I(cls="fab fa-github"), href="https://github.com/AndreasThinks/bibliome", target="_blank", rel="noopener", cls="social-icon"),
                    A(I(cls="fab fa-bluesky"), href="https://bsky.app/profile/did:plc:pqtgwoddmusib6v2csjxcskh", target="_blank", rel="noopener", cls="social-icon"),
                    Button(
                        I(cls="fas fa-envelope"),
                        hx_get="/api/contact-modal",
                        hx_target="#contact-modal-container",
                        hx_swap="innerHTML",
                        cls="social-icon contact-icon-btn",
                        title="Contact us"
                    ),
                    cls="footer-right"
                ),
                cls="footer-content"
            ),
            # Container for contact modal
            Div(id="contact-modal-container"),
        ),
        cls="universal-footer"
    )

def ContactModal():
    """Modal content for the contact form."""
    return Div(
        Div(
            # Modal header
            Div(
                Button(
                    I(cls="fas fa-times"),
                    hx_get="/api/close-contact-modal",
                    hx_target="#contact-modal-container",
                    hx_swap="innerHTML",
                    cls="contact-modal-close",
                    title="Close"
                ),
                Div(
                    H2(
                        I(cls="fas fa-envelope"),
                        "Contact Us",
                        cls="contact-modal-title"
                    ),
                    P("We'd love to hear from you! Send us a message and we'll get back to you soon.", cls="contact-modal-subtitle"),
                    cls="contact-modal-title-section"
                ),
                cls="contact-modal-header"
            ),
            
            # Modal body with form
            Div(
                ContactForm(),
                cls="contact-modal-body"
            ),
            
            # Modal footer with form actions (fixed at bottom)
            Div(
                Button(
                    "Cancel",
                    type="button",
                    hx_get="/api/close-contact-modal",
                    hx_target="#contact-modal-container",
                    hx_swap="innerHTML",
                    cls="contact-btn-secondary"
                ),
                Button(
                    I(cls="fas fa-paper-plane"),
                    " Send Message",
                    type="submit",
                    form="contact-form",
                    cls="contact-btn-primary"
                ),
                cls="contact-modal-footer"
            ),
            cls="contact-modal-dialog"
        ),
        cls="contact-modal-overlay"
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

def NetworkActivityFeed(activities: List[Dict], auth=None):
    """Display network activity feed from followed users."""
    if not activities:
        return EmptyNetworkState()
    
    activity_cards = []
    for activity in activities:
        activity_cards.append(ActivityCard(activity))
    
    return Div(
        H2("📚 Activity from your network", style="margin-bottom: 1.5rem;"),
        Div(*activity_cards, cls="network-activity-feed"),
        cls="network-feed-section",
        style="margin-bottom: 3rem;"
    )

def NetworkActivityPreview(activities: List[Dict], auth=None):
    """Display a compact preview of network activity for the homepage dashboard."""
    if not activities:
        return Div(
            P("No recent activity from your network.", cls="preview-empty-text"),
            P("Follow people on Bluesky to see their book activity here!", cls="preview-empty-suggestion"),
            cls="preview-empty-content"
        )
    
    # Show only the 3 most recent activities
    preview_activities = activities[:3]
    activity_cards = []
    for activity in preview_activities:
        activity_cards.append(CompactActivityCard(activity))
    
    return Div(*activity_cards, cls="preview-activity-list")

def NetworkActivityPreviewLoading():
    """Loading state for network activity with HTMX background loading."""
    return Card(
        Div(
            H3("📚 Activity from your network", cls="preview-title"),
            A("View All →", href="/network", cls="preview-view-all"),
            cls="preview-header"
        ),
        Div(
            Div(
                Div(cls="loading-spinner"),
                P("Loading your Network...", cls="loading-text"),
                cls="loading-content"
            ),
            cls="preview-loading-container",
            hx_get="/api/load-network-activity",
            hx_trigger="load",
            hx_swap="outerHTML",
            hx_target="this"
        ),
        cls="network-preview-card"
    )

def NetworkActivityPreviewError():
    """Error state for network activity with retry option."""
    return Div(
        P("Unable to load network activity.", cls="error-text"),
        Button(
            "Try Again",
            hx_get="/api/load-network-activity",
            hx_target="closest .network-preview-card",
            hx_swap="outerHTML",
            cls="retry-btn secondary"
        ),
        cls="preview-error-content"
    )

def CompactActivityCard(activity: Dict):
    """Render a compact activity card for the homepage preview."""
    user_profile = activity['user_profile']
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
        from datetime import datetime
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except:
            created_at = datetime.now()
    
    time_ago = format_time_ago(created_at)
    
    # Smaller user avatar
    avatar = Img(
        src=user_profile['avatar_url'],
        alt=user_profile['display_name'],
        cls="compact-activity-avatar"
    ) if user_profile['avatar_url'] else Div("👤", cls="compact-activity-avatar-placeholder")
    
    # Activity content based on type (compact versions)
    if activity_type == 'bookshelf_created':
        content = CompactActivityBookshelfCreated(activity)
    elif activity_type == 'book_added':
        content = CompactActivityBookAdded(activity)
    else:
        content = Span(f"Unknown activity: {activity_type}", cls="compact-activity-unknown")
    
    return Div(
        Div(
            avatar,
            Div(
                Div(
                    A(Strong(user_profile['display_name']), href=f"/user/{user_profile['handle']}", cls="compact-activity-user-link"),
                    " ",
                    content,
                    cls="compact-activity-content"
                ),
                Span(time_ago, cls="compact-activity-time"),
                cls="compact-activity-text"
            ),
            cls="compact-activity-main"
        ),
        cls="compact-activity-card"
    )

def CompactActivityBookshelfCreated(activity: Dict):
    """Render compact bookshelf creation activity."""
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗',
        'private': '🔒'
    }.get(activity['bookshelf_privacy'], '🌍')
    
    return Span(
        "created ",
        A(bookshelf_name, href=f"/shelf/{bookshelf_slug}", cls="compact-activity-link"),
        f" {privacy_icon}",
        cls="compact-activity-action"
    )

def CompactActivityBookAdded(activity: Dict):
    """Render compact book addition activity."""
    book_title = activity['book_title']
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    
    return Span(
        "added ",
        Span(book_title, cls="compact-activity-book-title"),
        " to ",
        A(bookshelf_name, href=f"/shelf/{bookshelf_slug}", cls="compact-activity-link"),
        cls="compact-activity-action"
    )

def ActivityCard(activity: Dict):
    """Render a single activity card."""
    user_profile = activity['user_profile']
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
        from datetime import datetime
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except:
            created_at = datetime.now()
    
    time_ago = format_time_ago(created_at)
    
    # User avatar and name
    avatar = Img(
        src=user_profile['avatar_url'],
        alt=user_profile['display_name'],
        cls="activity-avatar"
    ) if user_profile['avatar_url'] else Div("👤", cls="activity-avatar-placeholder")
    
    user_info = Div(
        avatar,
        Div(
            A(Strong(user_profile['display_name']), href=f"/user/{user_profile['handle']}", cls="activity-user-link"),
            P(f"@{user_profile['handle']}", cls="activity-handle"),
            cls="activity-user-info"
        ),
        cls="activity-user"
    )
    
    # Activity content based on type
    if activity_type == 'bookshelf_created':
        content = ActivityBookshelfCreated(activity)
    elif activity_type == 'book_added':
        content = ActivityBookAdded(activity)
    else:
        content = P(f"Unknown activity: {activity_type}")
    
    return Div(
        user_info,
        content,
        P(time_ago, cls="activity-timestamp"),
        cls="activity-card"
    )

def ActivityBookshelfCreated(activity: Dict):
    """Render bookshelf creation activity."""
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗',
        'private': '🔒'
    }.get(activity['bookshelf_privacy'], '🌍')
    
    return Div(
        P("created a new bookshelf", cls="activity-action"),
        Div(
            H4(bookshelf_name, cls="activity-bookshelf-name"),
            P(f"{privacy_icon} {activity['bookshelf_privacy'].replace('-', ' ').title()}", cls="activity-privacy"),
            A("View Shelf", href=f"/shelf/{bookshelf_slug}", cls="activity-link"),
            cls="activity-bookshelf-card"
        ),
        cls="activity-content"
    )

def ActivityBookAdded(activity: Dict):
    """Render book addition activity."""
    book_title = activity['book_title']
    book_author = activity['book_author']
    book_cover_url = activity['book_cover_url']
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    
    cover = Img(
        src=book_cover_url,
        alt=f"Cover of {book_title}",
        cls="activity-book-cover"
    ) if book_cover_url else Div("📖", cls="activity-book-cover-placeholder")
    
    return Div(
        P(f"added a book to ", Span(bookshelf_name, cls="activity-bookshelf-ref"), cls="activity-action"),
        Div(
            cover,
            Div(
                H4(book_title, cls="activity-book-title"),
                P(f"by {book_author}", cls="activity-book-author") if book_author else None,
                A("View Shelf", href=f"/shelf/{bookshelf_slug}", cls="activity-link"),
                cls="activity-book-info"
            ),
            cls="activity-book-card"
        ),
        cls="activity-content"
    )

def EmptyNetworkState():
    """Empty state when no network activity is available."""
    return Div(
        Div(
            H3("🌐 Connect with your network!", cls="empty-network-title"),
            P("We don't see any recent activity from people you follow on Bluesky.", cls="empty-network-description"),
            P("Invite your friends to join Bibliome and start sharing book recommendations!", cls="empty-network-suggestion"),
            Div(
                A("Explore Public Shelves", href="/explore", cls="secondary"),
                cls="empty-network-actions"
            ),
            cls="empty-network-content"
        ),
        cls="empty-network-state"
    )

def format_time_ago(dt):
    """Format datetime as 'time ago' string."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    if dt.tzinfo is not None:
        # Convert to naive datetime for comparison
        dt = dt.replace(tzinfo=None)
    
    diff = now - dt
    
    if diff.days > 7:
        return dt.strftime("%b %d")
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    else:
        return "just now"

def UnifiedExploreHero(auth=None):
    """Unified hero section that adapts based on authentication status."""
    if auth:
        # Logged-in users get enhanced explore experience
        return Section(
            Container(
                H1("Explore what the community is reading", cls="explore-title"),
                P("Discover active bookshelves, search by interests, and find your next great read.", cls="explore-subtitle"),
            ),
            cls="explore-hero"
        )
    else:
        # Anonymous users get simple discovery experience
        return Section(
            Container(
                H1("Discover what the community is reading", cls="explore-title"),
                P("Browse curated collections from readers around the world.", cls="explore-subtitle"),
            ),
            cls="explore-hero"
        )

def ExplorePageHero():
    """Hero section for the public explore page."""
    return Section(
        Container(
            H1("Explore Public Bookshelves", cls="explore-title"),
            P("Discover what the community is reading and sharing.", cls="explore-subtitle"),
        ),
        cls="explore-hero"
    )

def PublicShelvesGrid(shelves, page=1, total_pages=1):
    """Grid of public bookshelves with pagination."""
    if not shelves:
        return EmptyState(
            "No Public Shelves Found",
            "There are no public bookshelves to display at the moment. Why not create one?"
        )
    
    grid = Div(*[ShelfPreviewCard(shelf) for shelf in shelves], cls="public-shelves-grid")
    
    pagination = Pagination(current_page=page, total_pages=total_pages, base_url="/explore")
    
    return Div(grid, pagination, id="public-shelves-grid")

def ShelfPreviewCard(shelf):
    """A card for a public bookshelf with book previews."""
    # Mini book cover previews
    if hasattr(shelf, 'recent_covers') and shelf.recent_covers:
        covers = [Img(src=cover_url, alt="Book cover", loading="lazy") for cover_url in shelf.recent_covers]
    else:
        covers = [Div("📚", cls="shelf-preview-placeholder")]
    cover_previews = Div(*covers, cls="shelf-preview-covers")

    # Owner info
    owner_details = []
    if hasattr(shelf, 'owner') and shelf.owner:
        owner_avatar = Img(src=shelf.owner.avatar_url, alt=shelf.owner.display_name, cls="owner-avatar") if shelf.owner.avatar_url else Div("👤", cls="owner-avatar-placeholder")
        owner_details.extend([owner_avatar, Span(shelf.owner.display_name or shelf.owner.handle)])
    owner_info = Div(*owner_details, cls="shelf-owner-info")

    # Add contribution badge if shelf is open to contributions - positioned in footer
    contribution_badge = None
    if getattr(shelf, 'self_join', False):
        contribution_badge = Div("🤝 Open to contributions", cls="shelf-preview-contribution-badge")

    return A(
        href=f"/shelf/{shelf.slug}",
        cls="shelf-preview-card"
    )(
        Card(
            cover_previews,
            H3(shelf.name),
            P(shelf.description, cls="shelf-description") if shelf.description else None,
            footer=Div(
                Div(
                    contribution_badge,
                    owner_info,
                    cls="shelf-footer-left"
                ),
                Span(f"{getattr(shelf, 'book_count', 0)} books", cls="book-count"),
                cls="shelf-card-footer"
            )
        )
    )

def SearchPageHero():
    """Hero section for the search page."""
    return Section(
        Container(
            H1("🔍 Discover Collections", cls="explore-title"),
            P("Find the perfect bookshelf from our community of readers.", cls="explore-subtitle"),
        ),
        cls="explore-hero"
    )

def CommunityReadingSection(books):
    """A section to display recently added books in a scrolling container."""
    if not books:
        return Section(
            Container(
                H2("What the Community is Reading", cls="section-title"),
                EmptyState(
                    "No recent activity to show",
                    "Be the first to add a book to a public shelf and get featured here!",
                    "Explore Public Shelves",
                    "/explore"
                )
            ),
            cls="community-reading-section"
        )

    return Section(
        Container(
            H2("What the Community is Reading", cls="section-title"),
            Div(
                Div(*[BookScrollCard(book) for book in books], cls="book-scroll-container"),
                cls="scroll-wrapper"
            )
        ),
        cls="community-reading-section"
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

def UserSearchResultCard(user):
    """Render a user search result card."""
    avatar = Img(
        src=user.avatar_url,
        alt=user.display_name or user.handle,
        cls="user-search-avatar"
    ) if user.avatar_url else Div("👤", cls="user-search-avatar-placeholder")
    
    # Format join date
    join_date = "Unknown"
    if user.created_at:
        try:
            if isinstance(user.created_at, str):
                join_date_obj = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
            else:
                join_date_obj = user.created_at
            join_date = join_date_obj.strftime("%B %Y")
        except:
            join_date = "Unknown"
    
    return A(
        href=f"/user/{user.handle}",
        cls="user-search-card"
    )(
        Card(
            Div(
                avatar,
                Div(
                    H4(user.display_name or user.handle, cls="user-search-name"),
                    P(f"@{user.handle}", cls="user-search-handle"),
                    Div(
                        Span(f"📚 {getattr(user, 'public_shelves_count', 0)} public shelves", cls="user-search-stat"),
                        Span(f"📅 Joined {join_date}", cls="user-search-stat"),
                        cls="user-search-stats"
                    ),
                    cls="user-search-info"
                ),
                cls="user-search-content"
            ),
            footer=Div(
                P(f"Recent shelf: {getattr(user, 'recent_shelf_name', 'None')}" if getattr(user, 'recent_shelf_name', None) else "No recent activity", cls="user-search-recent"),
                A("View Profile", href=f"/user/{user.handle}", cls="user-search-link"),
                cls="user-search-footer"
            )
        )
    )

def SearchResultsGrid(shelves, users=None, search_type="all", page: int = 1, query: str = "", privacy: str = "public", sort_by: str = "updated_at", open_to_contributions: str = ""):
    """Grid of search results with tabs for different content types."""
    shelf_count = len(shelves) if shelves else 0
    user_count = len(users) if users else 0
    
    # Create result sections
    sections = []
    
    if search_type == "all" or search_type == "shelves":
        if shelves:
            sections.append(Div(
                H3(f"Bookshelves ({shelf_count})", cls="search-section-title"),
                Div(*[ShelfPreviewCard(shelf) for shelf in shelves], cls="search-shelves-grid"),
                cls="search-section"
            ))
        elif search_type == "shelves":
            sections.append(Div(
                H3("Bookshelves (0)", cls="search-section-title"),
                EmptyState("No Shelves Found", "No bookshelves matched your search criteria."),
                cls="search-section"
            ))
    
    if search_type == "all" or search_type == "users":
        if users:
            sections.append(Div(
                H3(f"Users ({user_count})", cls="search-section-title"),
                Div(*[UserSearchResultCard(user) for user in users], cls="search-users-grid"),
                cls="search-section"
            ))
        elif search_type == "users":
            sections.append(Div(
                H3("Users (0)", cls="search-section-title"),
                EmptyState("No Users Found", "No users matched your search criteria."),
                cls="search-section"
            ))
    
    if not sections:
        return EmptyState(
            "No Results Found",
            "No shelves or users matched your search criteria. Try a different search."
        )
    
    # Simple pagination (for now, just for shelves) - include open_to_contributions parameter
    pagination_links = []
    if page > 1:
        pagination_links.append(A("← Previous", href=f"/search?query={query}&search_type={search_type}&privacy={privacy}&sort_by={sort_by}&open_to_contributions={open_to_contributions}&page={page - 1}"))
    if shelf_count == 12: # If we got a full page, there might be a next page
        pagination_links.append(A("Next →", href=f"/search?query={query}&search_type={search_type}&privacy={privacy}&sort_by={sort_by}&open_to_contributions={open_to_contributions}&page={page + 1}"))
    
    pagination = Nav(*pagination_links, cls="pagination") if pagination_links else None
    
    return Div(*sections, pagination, id="search-results-grid")

def BookListView(books, can_upvote=True, can_remove=False, user_auth_status="anonymous"):
    """Render books in a table/list view format."""
    if not books:
        return Div("No books to display", cls="empty-list-message")
    
    # Create table rows
    book_rows = [book.as_table_row(
        can_upvote=can_upvote,
        user_has_upvoted=book.user_has_upvoted,
        upvote_count=book.upvote_count,
        can_remove=can_remove,
        user_auth_status=user_auth_status
    ) for book in books]
    
    return Table(
        Thead(
            Tr(
                Th("Cover", cls="cover-header"),
                Th("Title", cls="title-header"),
                Th("Author", cls="author-header"),
                Th("Description", cls="description-header"),
                Th("Votes", cls="votes-header"),
                Th("Actions", cls="actions-header"),
                cls="book-table-header"
            )
        ),
        Tbody(*book_rows, cls="book-table-body"),
        cls="book-table"
    )

def UserProfileHeader(user, is_own_profile=False, public_shelves_count=0):
    """Header section for user profile pages."""
    avatar = Img(
        src=user.avatar_url,
        alt=user.display_name or user.handle,
        cls="profile-avatar"
    ) if user.avatar_url else Div("👤", cls="profile-avatar-placeholder")
    
    # Format join date
    join_date = "Unknown"
    if user.created_at:
        try:
            if isinstance(user.created_at, str):
                from datetime import datetime
                join_date_obj = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
            else:
                join_date_obj = user.created_at
            join_date = join_date_obj.strftime("%B %Y")
        except:
            join_date = "Unknown"
    
    # Bluesky profile link
    bluesky_link = A(
        I(cls="fab fa-bluesky"),
        href=f"https://bsky.app/profile/{user.handle}",
        target="_blank",
        rel="noopener noreferrer",
        cls="profile-bluesky-link",
        title=f"View @{user.handle} on Bluesky"
    )
    
    return Card(
        Div(
            avatar,
            Div(
                H1(user.display_name or user.handle, cls="profile-name"),
                Div(
                    P(f"@{user.handle}", cls="profile-handle"),
                    bluesky_link,
                    cls="profile-handle-container"
                ),
                Div(
                    Span(f"📚 {public_shelves_count} public shelves", cls="profile-stat"),
                    Span(f"📅 Joined {join_date}", cls="profile-stat"),
                    cls="profile-stats"
                ),
                cls="profile-info"
            ),
            cls="profile-header-content"
        ),
        cls="profile-header-card"
    )

def UserPublicShelves(shelves, user_handle):
    """Display a user's public bookshelves."""
    if not shelves:
        return Div(
            H3("Public Bookshelves"),
            P(f"@{user_handle} hasn't created any public bookshelves yet.", cls="empty-message"),
            cls="user-shelves-section"
        )
    
    return Div(
        H3(f"Public Bookshelves ({len(shelves)})"),
        Div(*[ShelfPreviewCard(shelf) for shelf in shelves], cls="user-shelves-grid"),
        cls="user-shelves-section"
    )

def UserActivityFeed(activities, user_handle, viewer_is_logged_in=False):
    """Display a user's activity feed."""
    if not activities:
        activity_type = "activity" if viewer_is_logged_in else "public activity"
        return Div(
            H3("Recent Activity"),
            P(f"@{user_handle} doesn't have any recent {activity_type} to show.", cls="empty-message"),
            cls="user-activity-section"
        )
    
    activity_cards = []
    for activity in activities:
        # Don't show user info since this is their profile page
        activity_cards.append(UserActivityCard(activity))
    
    return Div(
        H3(f"Recent Activity ({len(activities)})"),
        Div(*activity_cards, cls="user-activity-feed"),
        cls="user-activity-section"
    )

def UserActivityCard(activity):
    """Render a single activity card for user profile (without user info)."""
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
        from datetime import datetime
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except:
            created_at = datetime.now()
    
    time_ago = format_time_ago(created_at)
    
    # Activity content based on type (without user info)
    if activity_type == 'bookshelf_created':
        content = UserActivityBookshelfCreated(activity)
    elif activity_type == 'book_added':
        content = UserActivityBookAdded(activity)
    else:
        content = P(f"Unknown activity: {activity_type}")
    
    return Div(
        content,
        P(time_ago, cls="user-activity-timestamp"),
        cls="user-activity-card"
    )

def UserActivityBookshelfCreated(activity):
    """Render bookshelf creation activity for user profile."""
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗',
        'private': '🔒'
    }.get(activity['bookshelf_privacy'], '🌍')
    
    return Div(
        P("created a new bookshelf", cls="user-activity-action"),
        Div(
            H4(bookshelf_name, cls="activity-bookshelf-name"),
            P(f"{privacy_icon} {activity['bookshelf_privacy'].replace('-', ' ').title()}", cls="activity-privacy"),
            A("View Shelf", href=f"/shelf/{bookshelf_slug}", cls="activity-link"),
            cls="activity-bookshelf-card"
        ),
        cls="user-activity-content"
    )

def UserActivityBookAdded(activity):
    """Render book addition activity for user profile."""
    book_title = activity['book_title']
    book_author = activity['book_author']
    book_cover_url = activity['book_cover_url']
    bookshelf_name = activity['bookshelf_name']
    bookshelf_slug = activity['bookshelf_slug']
    
    cover = Img(
        src=book_cover_url,
        alt=f"Cover of {book_title}",
        cls="activity-book-cover"
    ) if book_cover_url else Div("📖", cls="activity-book-cover-placeholder")
    
    return Div(
        P(f"added a book to ", Span(bookshelf_name, cls="activity-bookshelf-ref"), cls="user-activity-action"),
        Div(
            cover,
            Div(
                H4(book_title, cls="activity-book-title"),
                P(f"by {book_author}", cls="activity-book-author") if book_author else None,
                A("View Shelf", href=f"/shelf/{bookshelf_slug}", cls="activity-link"),
                cls="activity-book-info"
            ),
            cls="activity-book-card"
        ),
        cls="user-activity-content"
    )

def BookScrollCard(book):
    """A card for a book in the community reading scroll section."""
    cover = Img(
        src=book.cover_url,
        alt=f"Cover of {book.title}",
        cls="book-scroll-cover",
        loading="lazy"
    ) if book.cover_url else Div("📖", cls="book-scroll-cover-placeholder")

    return A(
        href=f"/shelf/{book.bookshelf_slug}",
        cls="book-scroll-card"
    )(
        cover,
        Div(
            H4(book.title, cls="book-scroll-title"),
            P(f"in {book.bookshelf_name}", cls="book-scroll-shelf"),
            cls="book-scroll-info"
        )
    )

def NetworkPageHero():
    """Hero section for the network activity page."""
    return Section(
        Container(
            H1("📚 Your Network Activity", cls="explore-title"),
            P("Stay up to date with what your network is reading and sharing.", cls="explore-subtitle"),
        ),
        cls="explore-hero"
    )

def NetworkActivityFilters(activity_type="all", date_filter="all"):
    """Filter controls for network activity."""
    return Div(
        Form(
            Div(
                Label("Activity Type:", Select(
                    Option("All Activity", value="all", selected=(activity_type == "all")),
                    Option("New Bookshelves", value="bookshelf_created", selected=(activity_type == "bookshelf_created")),
                    Option("Books Added", value="book_added", selected=(activity_type == "book_added")),
                    name="activity_type",
                    hx_get="/network",
                    hx_target="#network-content",
                    hx_include="[name='date_filter']",
                    hx_trigger="change"
                )),
                Label("Time Period:", Select(
                    Option("All Time", value="all", selected=(date_filter == "all")),
                    Option("Last 24 Hours", value="1d", selected=(date_filter == "1d")),
                    Option("Last Week", value="7d", selected=(date_filter == "7d")),
                    Option("Last Month", value="30d", selected=(date_filter == "30d")),
                    name="date_filter",
                    hx_get="/network",
                    hx_target="#network-content",
                    hx_include="[name='activity_type']",
                    hx_trigger="change"
                )),
                cls="network-filters-row"
            ),
            cls="network-filters-form"
        ),
        cls="network-filters-section"
    )

def FullNetworkActivityFeed(activities: List[Dict], page: int = 1, total_pages: int = 1, activity_type: str = "all", date_filter: str = "all"):
    """Full-page network activity feed with pagination."""
    if not activities:
        return Div(
            EmptyNetworkState(),
            id="network-content"
        )
    
    activity_cards = []
    for activity in activities:
        activity_cards.append(ActivityCard(activity))
    
    # Pagination
    pagination = None
    if total_pages > 1:
        pagination = Pagination(
            current_page=page, 
            total_pages=total_pages, 
            base_url=f"/network?activity_type={activity_type}&date_filter={date_filter}"
        )
    
    return Div(
        Div(*activity_cards, cls="network-activity-feed"),
        pagination,
        id="network-content"
    )

def EmptyNetworkStateFullPage():
    """Empty state for the full network page when no activity is available."""
    return Div(
        Div(
            H3("🌐 Your network is quiet right now", cls="empty-network-title"),
            P("We don't see any recent activity from people you follow on Bluesky.", cls="empty-network-description"),
            P("Here are some things you can do:", cls="empty-network-suggestion"),
            Div(
                A("Explore Public Shelves", href="/explore", cls="primary"),
                A("Create Your First Shelf", href="/shelf/new", cls="secondary"),
                cls="empty-network-actions"
            ),
            cls="empty-network-content"
        ),
        cls="empty-network-state",
        id="network-content"
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

def ShareModal(shelf, base_url, user_role=None, can_generate_invites=False):
    """Modal content for sharing a bookshelf with permission-based filtering."""
    privacy_icon = {
        'public': '🌍',
        'link-only': '🔗',
        'private': '🔒'
    }.get(shelf.privacy, '🌍')
    
    # Determine available share options based on user permissions
    share_options = []
    
    # Option 1: Share public link (only for public/link-only shelves, available to all roles)
    if shelf.privacy in ['public', 'link-only']:
        share_options.append(
            Label(
                Input(
                    type="radio", 
                    name="share_type", 
                    value="public_link",
                    hx_trigger="change",
                    hx_post=f"/api/shelf/{shelf.slug}/share-preview",
                    hx_target="#share-preview",
                    hx_include="[name='share_type']:checked"
                ),
                Div(
                    Div(
                        Strong("Share public link"),
                        Span("🔗", cls="share-option-icon"),
                        cls="share-option-header"
                    ),
                    P("Anyone can view this shelf immediately", cls="share-option-description"),
                    cls="share-option-content"
                ),
                cls="share-type-option"
            )
        )
    
    # Option 2 & 3: Invite options (only for moderators and owners)
    if can_generate_invites:
        # Invite as viewer
        share_options.append(
            Label(
                Input(
                    type="radio", 
                    name="share_type", 
                    value="invite_viewer",
                    hx_trigger="change",
                    hx_post=f"/api/shelf/{shelf.slug}/share-preview",
                    hx_target="#share-preview",
                    hx_include="[name='share_type']:checked"
                ),
                Div(
                    Div(
                        Strong("Invite as viewer"),
                        Span("👁️", cls="share-option-icon"),
                        cls="share-option-header"
                    ),
                    P("Creates a formal member relationship" if shelf.privacy in ['public', 'link-only'] 
                      else "Give view-only access to this private shelf", cls="share-option-description"),
                    cls="share-option-content"
                ),
                cls="share-type-option"
            )
        )
        
        # Invite as contributor
        share_options.append(
            Label(
                Input(
                    type="radio", 
                    name="share_type", 
                    value="invite_contributor",
                    hx_trigger="change",
                    hx_post=f"/api/shelf/{shelf.slug}/share-preview",
                    hx_target="#share-preview",
                    hx_include="[name='share_type']:checked"
                ),
                Div(
                    Div(
                        Strong("Invite as contributor"),
                        Span("🤝", cls="share-option-icon"),
                        cls="share-option-header"
                    ),
                    P("Allow adding books and voting", cls="share-option-description"),
                    cls="share-option-content"
                ),
                cls="share-type-option"
            )
        )
    
    # If no options are available (shouldn't happen if permissions are checked correctly)
    if not share_options:
        share_options.append(
            Div(
                P("No sharing options available for your role.", cls="no-share-options"),
                cls="share-option-content"
            )
        )
    
    return Div(
        Div(
            # Modal header with improved spacing
            Div(
                Button(
                    I(cls="fas fa-times"),
                    hx_get=f"/api/shelf/{shelf.slug}/close-share-modal",
                    hx_target="#share-modal-container",
                    hx_swap="innerHTML",
                    cls="share-modal-close",
                    title="Close"
                ),
                Div(
                    H2(
                        I(cls="fas fa-share-alt"),
                        f"Share: {shelf.name}",
                        cls="share-modal-title"
                    ),
                    P(f"{privacy_icon} {shelf.privacy.replace('-', ' ').title()} shelf", cls="share-modal-privacy"),
                    cls="share-modal-title-section"
                ),
                cls="share-modal-header"
            ),
            
            # Main content with better organization
            Div(
                # Share options section
                Div(
                    H3("Choose how to share", cls="share-section-title"),
                    P("Select an option below to generate a sharing link", cls="share-section-subtitle"),
                    Div(*share_options, cls="share-options-grid"),
                    cls="share-options-section"
                ),
                
                # Preview section
                Div(
                    Div(
                        Div(
                            I(cls="fas fa-info-circle"),
                            "Select a sharing option above to see a preview",
                            cls="share-preview-placeholder"
                        ),
                        id="share-preview", 
                        cls="share-preview-container"
                    ),
                    cls="share-preview-section"
                ),
                
                cls="share-modal-body"
            ),
            cls="share-modal-dialog"
        ),
        cls="share-modal-overlay"
    )

def ShareLinkResult(link, message, share_type):
    """Display the generated sharing link with copy functionality - replaces entire modal content."""
    # Extract shelf slug from link for proper navigation
    shelf_slug = ""
    if "/shelf/" in link:
        parts = link.split("/shelf/")
        if len(parts) > 1:
            shelf_slug = parts[1].split("/")[0]
    elif "/join/" in link:
        # For invite links, we need to extract from the referrer or pass it differently
        # For now, we'll use a generic approach
        shelf_slug = link.split('/')[-2] if '/' in link else ''
    
    return Div(
        Div(
            # Modal header with improved spacing - matches ShareModal design
            Div(
                Button(
                    I(cls="fas fa-times"),
                    hx_get=f"/api/shelf/{shelf_slug}/close-share-modal",
                    hx_target="#share-modal-container",
                    hx_swap="innerHTML",
                    cls="share-modal-close",
                    title="Close"
                ),
                Div(
                    H2(
                        I(cls="fas fa-check-circle", style="color: #28a745; margin-right: 0.5rem;"),
                        "Ready to share!",
                        cls="share-modal-title"
                    ),
                    P("Your sharing link has been generated", cls="share-modal-privacy"),
                    cls="share-modal-title-section"
                ),
                cls="share-modal-header"
            ),
            
            # Main content with better organization - matches app design system
            Div(
                # Success message section
                Div(
                    H3("Share this message", cls="share-section-title"),
                    P("Copy and paste this message to share your bookshelf:", cls="share-section-subtitle"),
                    
                    # Message display with improved styling
                    Div(
                        Div(
                            Div(
                                Span("📋", cls="message-type-icon"),
                                Span("Ready to Share", cls="message-type-label"),
                                cls="message-type-header"
                            ),
                            Div(
                                message,
                                cls="share-preview-message-text",
                                onclick="this.select(); document.execCommand('selectAll');"
                            ),
                            Div(
                                I(cls="fas fa-copy", style="margin-right: 0.25rem; font-size: 0.8rem;"),
                                "Click message to select all text",
                                cls="message-copy-hint"
                            ),
                            cls="share-preview-message-content"
                        ),
                        cls="share-preview-message-card"
                    ),
                    
                    # Copy button with app styling
                    Button(
                        I(cls="fas fa-copy", style="margin-right: 0.5rem;"),
                        "Copy Message",
                        onclick="copyShareMessage(this)",
                        cls="generate-link-btn enhanced-primary",
                        id="copy-message-btn",
                        style="margin-top: 1rem;"
                    ),
                    
                    cls="share-options-section"
                ),
                
                cls="share-modal-body"
            ),
            
            # Footer with action buttons - matches modal design
            Div(
                Button(
                    "Share Another Way",
                    hx_get=f"/api/shelf/{shelf_slug}/share-modal",
                    hx_target="#share-modal-container",
                    hx_swap="innerHTML",
                    cls="secondary",
                    style="margin-right: 1rem;"
                ),
                Button(
                    "Done",
                    hx_get=f"/api/shelf/{shelf_slug}/close-share-modal",
                    hx_target="#share-modal-container",
                    hx_swap="innerHTML",
                    cls="primary"
                ),
                cls="share-result-actions",
                style="padding: 1.5rem 2rem; border-top: 1px solid var(--brand-border); display: flex; justify-content: flex-end; background: var(--brand-light);"
            ),
            
            cls="share-modal-dialog"
        ),
        # Enhanced copy functionality with better feedback
        Script("""
            function copyShareMessage(button) {
                const messageText = document.querySelector('.share-preview-message-text').textContent;
                
                navigator.clipboard.writeText(messageText).then(() => {
                    const original = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-check" style="margin-right: 0.5rem;"></i>Copied!';
                    button.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
                    button.style.borderColor = '#28a745';
                    button.style.transform = 'translateY(-2px)';
                    button.style.boxShadow = '0 6px 24px rgba(40, 167, 69, 0.4)';
                    
                    setTimeout(() => {
                        button.innerHTML = original;
                        button.style.background = '';
                        button.style.borderColor = '';
                        button.style.transform = '';
                        button.style.boxShadow = '';
                    }, 2500);
                }).catch((err) => {
                    console.error('Copy failed:', err);
                    const original = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-exclamation-triangle" style="margin-right: 0.5rem;"></i>Copy failed - please select text manually';
                    button.style.background = 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)';
                    button.style.borderColor = '#dc3545';
                    
                    setTimeout(() => {
                        button.innerHTML = original;
                        button.style.background = '';
                        button.style.borderColor = '';
                    }, 3000);
                });
            }
            
            // Auto-select message text when modal loads
            setTimeout(() => {
                const messageElement = document.querySelector('.share-preview-message-text');
                if (messageElement) {
                    messageElement.focus();
                }
            }, 300);
        """),
        cls="share-modal-overlay"
    )

def SharePreview(shelf, share_type, base_url):
    """Preview of what will be shared based on the selected share type."""
    # Handle case when no share type is selected
    if not share_type:
        return Div(
            Div(
                I(cls="fas fa-info-circle"),
                "Select a sharing option above to see a preview",
                cls="share-preview-placeholder"
            ),
            cls="share-preview-container"
        )
    
    privacy_descriptions = {
        'public': 'This public shelf can be viewed by anyone',
        'link-only': 'This shelf can be viewed by anyone with the link',
        'private': 'This private shelf requires an invitation to view'
    }
    
    if share_type == "public_link":
        preview_link = f"{base_url}/shelf/{shelf.slug}"
        preview_message = f"Check out this bookshelf: {shelf.name} - {preview_link}"
        description = privacy_descriptions.get(shelf.privacy, '')
        message_icon = "🔗"
        message_type = "Public Link"
    elif share_type == "invite_viewer":
        preview_link = f"{base_url}/shelf/join/[INVITE-CODE]"
        if shelf.privacy == 'private':
            preview_message = f"I've shared my private bookshelf with you: {shelf.name} - {preview_link}"
        else:
            preview_message = f"I've shared a bookshelf with you: {shelf.name} - {preview_link}"
        description = "Recipients will be able to view the shelf and see all books"
        message_icon = "👁️"
        message_type = "Viewer Invitation"
    else:  # invite_contributor
        preview_link = f"{base_url}/shelf/join/[INVITE-CODE]"
        preview_message = f"Join me in building this bookshelf: {shelf.name} - {preview_link}"
        description = "Recipients will be able to add books, vote, and view the shelf"
        message_icon = "🤝"
        message_type = "Contributor Invitation"
    
    return Div(
        # Enhanced header with icon and better typography
        Div(
            Div(
                I(cls="fas fa-eye", style="margin-right: 0.5rem; color: var(--brand-amber);"),
                H5("Preview", cls="share-preview-title"),
                cls="share-preview-title-container"
            ),
            P(description, cls="share-preview-description"),
            cls="share-preview-header"
        ),
        
        # Enhanced message section with card-like appearance
        Div(
            Div(
                I(cls="fas fa-comment-dots", style="margin-right: 0.5rem; color: var(--brand-amber);"),
                P("Ready to share:", cls="share-preview-label"),
                cls="share-preview-label-container"
            ),
            Div(
                Div(
                    Div(
                        Span(message_icon, cls="message-type-icon"),
                        Span(message_type, cls="message-type-label"),
                        cls="message-type-header"
                    ),
                    Div(preview_message, cls="share-preview-message-text"),
                    Div(
                        I(cls="fas fa-copy", style="margin-right: 0.25rem; font-size: 0.8rem;"),
                        "Click to select",
                        cls="message-copy-hint"
                    ),
                    cls="share-preview-message-content",
                    onclick="this.querySelector('.share-preview-message-text').select(); this.querySelector('.share-preview-message-text').setSelectionRange(0, 99999);"
                ),
                cls="share-preview-message-card"
            ),
            cls="share-preview-content"
        ),
        
        # Enhanced generate button with better styling
        Button(
            I(cls="fas fa-magic", style="margin-right: 0.5rem;"),
            "Generate Share Link",
            hx_post=f"/api/shelf/{shelf.slug}/generate-share-link",
            hx_vals=f'{{"share_type": "{share_type}"}}',
            hx_target="#share-modal-container",
            hx_swap="innerHTML",
            cls="generate-link-btn enhanced-primary"
        ),
        cls="share-preview-card enhanced"
    )
