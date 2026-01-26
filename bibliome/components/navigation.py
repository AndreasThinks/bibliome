"""Navigation components for Bibliome."""

from fasthtml.common import *


def AlphaBadge():
    """Alpha status badge component with mobile-friendly click functionality."""
    return Div(
        Span(
            "⚠️ Alpha",
            cls="alpha-badge",
            title="Bibliome is in very early, active development. Data may be reset and features may change as we improve the platform.",
            onclick="showAlphaMessage(this)"
        ),
        Div(
            "Bibliome is in very early, active development. Data may be reset and features may change as we improve the platform.",
            cls="alpha-message",
            id="alpha-message"
        ),
        Script("""
            function showAlphaMessage(badge) {
                const message = document.getElementById('alpha-message');
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
        cls="alpha-badge-container"
    )


def NavBar(auth=None):
    """Main navigation bar with HTMX-powered mobile hamburger menu."""
    from auth import is_admin
    # Define menu links based on auth status
    if auth:
        links = [
            A("My Shelves", href="/"),
            A("Your Network", href="/network"),
            A("Explore", href="/explore"),
            A("Create Shelf", href="/shelf/new"),
        ]
        if is_admin(auth):
            links.append(A("Admin", href="/admin"))
        
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
            A("Login", href="/auth/login", cls="login-btn"),
        ]
        user_profile_card = None

    return Nav(
        Div(
            # Logo and alpha badge grouped together
            Div(
                A(
                    Img(src="/static/bibliome_transparent_no_text.png", alt="Bibliome", cls="logo-img"),
                    "Bibliome",
                    href="/", 
                    cls="logo"
                ),
                AlphaBadge(),
                cls="logo-with-badge"
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
