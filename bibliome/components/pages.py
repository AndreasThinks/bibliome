"""Page section components for Bibliome."""

from fasthtml.common import *
from datetime import datetime
from typing import Dict, List, Any
import os

from .utils import format_time_ago, EmptyState, Pagination
from .cards import (
    MemberCard, InviteCard, ActivityCard, CompactActivityCard,
    ShelfPreviewCard, UserSearchResultCard, BookScrollCard, UserActivityCard
)


def get_base_url(req):
    """Get the base URL from the request."""
    if not req:
        return os.getenv('BASE_URL', 'http://localhost:5001').rstrip('/')
    scheme = 'https' if req.url.is_secure else 'http'
    return f"{scheme}://{req.url.netloc}"


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


def ShelfHeader(shelf, action_buttons, current_view="grid", can_share=False, user_is_logged_in=False, creator=None):
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
    
    # Creator information section
    creator_info = None
    if creator:
        creator_avatar = Img(
            src=creator.avatar_url,
            alt=creator.display_name or creator.handle,
            cls="owner-avatar"
        ) if creator.avatar_url else Div("👤", cls="owner-avatar-placeholder")
        
        creator_info = Div(
            creator_avatar,
            A(
                creator.display_name or creator.handle,
                href=f"/user/{creator.handle}",
                cls="shelf-owner-link",
                title="View creator's profile"
            ),
            cls="shelf-owner-info"
        )
    
    # Format creation date as "Created X ago"
    created_date_text = None
    if shelf.created_at:
        try:
            # Handle both string and datetime objects
            if isinstance(shelf.created_at, str):
                try:
                    # Try ISO format first
                    created_dt = datetime.fromisoformat(shelf.created_at.replace('Z', '+00:00'))
                except ValueError:
                    # Fallback for other formats
                    from dateutil.parser import parse
                    created_dt = parse(shelf.created_at)
            else:
                created_dt = shelf.created_at
            
            time_ago = format_time_ago(created_dt)
            created_date_text = f"📅 Created {time_ago}"
        except Exception:
            created_date_text = "📅 Creation date unknown"
    else:
        created_date_text = "📅 Creation date unknown"
    
    return Card(
        H1(shelf.name, cls="shelf-title"),
        P(shelf.description, cls="shelf-description") if shelf.description else None,
        creator_info,
        Div(
            Div(
                Span(f"🌍 {shelf.privacy.replace('-', ' ').title()}", cls="privacy-badge"),
                Span("🤝 Open to contributions", cls="contribution-badge") if getattr(shelf, 'self_join', False) else None,
                Span(created_date_text, cls="shelf-created-date") if created_date_text else None,
                cls="shelf-badges"
            ),
            Div(*all_actions, cls="shelf-actions"),
            cls="shelf-meta"
        ),
        cls="shelf-header-card"
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
            Div(*[ShelfPreviewCard(shelf) for shelf in public_shelves[:6]], cls="bookshelf-grid"),
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
                # Left side: Text content with alpha badge
                Div(
                    P("A project by ", A("AndreasThinks", href="https://andreasthinks.me/", target="_blank", rel="noopener"), ", built with ❤️ using FastHTML, AT-Proto, and some ✨vibes✨", cls="footer-text"),
                    P("© 2025 Bibliome. Open source and decentralized.", cls="footer-copyright"),
                    Div(
                        Span(
                            "⚠️ Alpha",
                            cls="footer-alpha-badge",
                            title="Bibliome is in very early active development. Data may be reset and features may change as we improve the platform.",
                            onclick="showFooterAlphaMessage(this)"
                        ),
                        Div(
                            "Bibliome is in very early, active development. Data may be reset and features may change as we improve the platform.",
                            cls="footer-alpha-message",
                            id="footer-alpha-message"
                        ),
                        Script("""
                            function showFooterAlphaMessage(badge) {
                                const message = document.getElementById('footer-alpha-message');
                                if (message) {
                                    // Show the message
                                    message.classList.add('show');
                                    
                                    // Hide after 2 seconds with fade
                                    setTimeout(() => {
                                        message.classList.remove('show');
                                    }, 2000);
                                }
                            }
                        """),
                        cls="footer-alpha-badge-container"
                    ),
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


def PublicShelvesGrid(shelves, page=1, total_pages=1, total_count=None):
    """Grid of public bookshelves with pagination.
    
    Args:
        shelves: List of shelf objects to display
        page: Current page number
        total_pages: Total number of pages
        total_count: Total number of shelves (for header display). If None, uses len(shelves).
    """
    if not shelves:
        return EmptyState(
            "No Public Shelves Found",
            "There are no public bookshelves to display at the moment. Why not create one?"
        )
    
    # Use total_count if provided, otherwise fall back to len(shelves)
    display_count = total_count if total_count is not None else len(shelves)
    
    header = H3(f"Bookshelves ({display_count})", cls="search-section-title")
    grid = Div(*[ShelfPreviewCard(shelf) for shelf in shelves], cls="public-shelves-grid")
    
    pagination = Pagination(current_page=page, total_pages=total_pages, base_url="/explore")
    
    return Div(header, grid, pagination, id="public-shelves-grid")


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


def SearchResultsGrid(shelves, users=None, search_type="all", page: int = 1, query: str = "", privacy: str = "public", sort_by: str = "updated_at", open_to_contributions: str = "", total_shelf_count: int = None):
    """Grid of search results with tabs for different content types.
    
    Args:
        shelves: List of shelf objects to display
        users: List of user objects to display
        search_type: Type of search ("all", "shelves", "users")
        page: Current page number
        query: Search query string
        privacy: Privacy filter
        sort_by: Sort order
        open_to_contributions: Open to contributions filter
        total_shelf_count: Total number of shelves (for header display). If None, uses len(shelves).
    """
    # Use total_shelf_count if provided, otherwise fall back to len(shelves)
    shelf_count = total_shelf_count if total_shelf_count is not None else (len(shelves) if shelves else 0)
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


def BookListView(books, can_upvote=True, can_remove=False, user_auth_status="anonymous", db_tables=None):
    """Render books in a table/list view format."""
    if not books:
        return Div("No books to display", cls="empty-list-message")
    
    # Create table rows
    book_rows = [book.as_table_row(
        can_upvote=can_upvote,
        user_has_upvoted=book.user_has_upvoted,
        upvote_count=book.upvote_count,
        can_remove=can_remove,
        user_auth_status=user_auth_status,
        db_tables=db_tables
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
