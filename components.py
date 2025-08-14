"""Reusable UI components for BookdIt."""

from fasthtml.common import *
from fasthtml.components import Img
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

def NavBar(auth=None):
    """Main navigation bar with mobile hamburger menu."""
    # Define menu links based on auth status
    if auth:
        links = [
            A("My Shelves", href="/"),
            A("Search", href="/search"),
            A("Create Shelf", href="/shelf/new"),
            A("Logout", href="/auth/logout"),
        ]
        user_greeting = Span(f"👋 {auth.get('display_name', auth.get('handle', 'User'))}", cls="user-greeting")
    else:
        links = [
            A("Explore", href="/explore"),
            A("Search", href="/search"),
            A("Login", href="/auth/login", cls="login-btn"),
        ]
        user_greeting = None

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
                user_greeting,
                *links,
                cls="user-menu desktop-menu"
            ),
            # Mobile menu button
            Button(
                "☰",
                cls="mobile-menu-toggle",
                onclick="toggleMobileMenu()"
            ),
            cls="nav-container"
        ),
        # Mobile menu (hidden by default)
        Div(
            *links,
            cls="mobile-menu",
            id="mobile-menu"
        ),
        Script("""
            function toggleMobileMenu() {
                const menu = document.getElementById('mobile-menu');
                menu.classList.toggle('active');
            }
        """),
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
                Div(
                    *[InviteCard(invite, bookshelf.slug) for invite in active_invites] if active_invites 
                    else [P("No active invites.", cls="empty-message")],
                    id="active-invites"
                ),
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

def LandingPageFooter():
    """Footer for the landing page."""
    return Footer(
        Container(
            Div(
                P("A project by ", A("AndreasThinks", href="https://andreasthinks.me/", target="_blank", rel="noopener"), ", built with ❤️ using FastHTML, AT-Proto, and some ✨vibes✨", cls="footer-text"),
                Div(
                    A(I(cls="fab fa-github"), href="https://github.com/AndreasThinks/bibliome", target="_blank", rel="noopener", cls="social-icon"),
                    cls="footer-social"
                ),
                P("© 2024 Bibliome. Open source and decentralized.", cls="footer-copyright"),
                cls="footer-content"
            ),
        ),
        cls="landing-footer"
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
            Strong(user_profile['display_name']),
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
    cover_previews = Div(cls="shelf-preview-covers")
    if hasattr(shelf, 'recent_covers') and shelf.recent_covers:
        for cover_url in shelf.recent_covers:
            cover_previews.append(Img(src=cover_url, alt="Book cover", loading="lazy"))
    else:
        cover_previews.append(Div("📚", cls="shelf-preview-placeholder"))

    # Owner info
    owner_info = Div(cls="shelf-owner-info")
    if hasattr(shelf, 'owner') and shelf.owner:
        owner_info.append(Img(src=shelf.owner.avatar_url, alt=shelf.owner.display_name, cls="owner-avatar") if shelf.owner.avatar_url else Div("👤", cls="owner-avatar-placeholder"))
        owner_info.append(Span(shelf.owner.display_name or shelf.owner.handle))

    return A(
        href=f"/shelf/{shelf.slug}",
        cls="shelf-preview-card"
    )(
        Card(
            cover_previews,
            H3(shelf.name),
            P(shelf.description, cls="shelf-description") if shelf.description else None,
            footer=Div(
                owner_info,
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

def SearchShelvesForm(query: str = "", book_title: str = "", book_author: str = "", book_isbn: str = "", privacy: str = "public", sort_by: str = "updated_at"):
    """Form for searching bookshelves with advanced options."""
    return Form(
        Div(
            Input(name="query", type="search", placeholder="Search shelves and books...", value=query),
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
                name="sort_by"
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
        cls="search-shelves-form"
    )

def SearchResultsGrid(shelves, page: int = 1, query: str = "", privacy: str = "public", sort_by: str = "updated_at"):
    """Grid of search results with simple pagination."""
    if not shelves:
        return EmptyState(
            "No Shelves Found",
            "No bookshelves matched your search criteria. Try a different search."
        )
    
    grid = Div(*[ShelfPreviewCard(shelf) for shelf in shelves], cls="public-shelves-grid")
    
    # Simple next/prev pagination
    pagination_links = []
    if page > 1:
        pagination_links.append(A("← Previous", href=f"/search?query={query}&privacy={privacy}&sort_by={sort_by}&page={page - 1}"))
    if len(shelves) == 12: # If we got a full page, there might be a next page
        pagination_links.append(A("Next →", href=f"/search?query={query}&privacy={privacy}&sort_by={sort_by}&page={page + 1}"))
    
    pagination = Nav(*pagination_links, cls="pagination") if pagination_links else None
    
    return Div(grid, pagination, id="search-results-grid")

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
