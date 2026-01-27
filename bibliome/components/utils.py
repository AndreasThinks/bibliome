"""Utility components and helper functions for Bibliome UI."""

from fasthtml.common import *
from datetime import datetime


def format_time_ago(dt):
    """Format datetime as 'time ago' string."""
    now = datetime.now()
    if dt.tzinfo is not None:
        # Convert to naive datetime for comparison
        dt = dt.replace(tzinfo=None)
    
    diff = now - dt
    
    if diff.days > 7:
        return dt.strftime("%b %d, %Y")
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
