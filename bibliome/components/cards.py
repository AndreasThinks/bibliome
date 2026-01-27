"""Card components for Bibliome."""

from fasthtml.common import *
from datetime import datetime
from typing import Dict, List, Any

from .utils import format_time_ago


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


def ActivityCard(activity: Dict):
    """Render a single activity card."""
    user_profile = activity['user_profile']
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
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


def CompactActivityCard(activity: Dict):
    """Render a compact activity card for the homepage preview."""
    user_profile = activity['user_profile']
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
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


def UserActivityCard(activity):
    """Render a single activity card for user profile (without user info)."""
    activity_type = activity['activity_type']
    created_at = activity['created_at']
    
    # Format timestamp
    if isinstance(created_at, str):
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

    # Format created date subtly
    created_text = None
    if hasattr(shelf, 'created_at') and shelf.created_at:
        try:
            if isinstance(shelf.created_at, str):
                created_dt = datetime.fromisoformat(shelf.created_at.replace('Z', '+00:00'))
            else:
                created_dt = shelf.created_at
            created_text = format_time_ago(created_dt)
        except:
            created_text = None

    # Build metadata items for footer right section
    metadata_items = []
    if created_text:
        metadata_items.append(Span(created_text, cls="shelf-created-date"))
    metadata_items.append(Span(f"{getattr(shelf, 'book_count', 0)} books", cls="book-count"))

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
                Div(*metadata_items, cls="shelf-footer-meta"),
                cls="shelf-card-footer"
            )
        )
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


def InviteCard(invite, bookshelf_slug, req=None):
    """Render an invite link card."""
    import os
    
    def get_base_url(req):
        """Get the base URL from the request."""
        if not req:
            return os.getenv('BASE_URL', 'http://localhost:5001').rstrip('/')
        scheme = 'https' if req.url.is_secure else 'http'
        return f"{scheme}://{req.url.netloc}"
    
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
