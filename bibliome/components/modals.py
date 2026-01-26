"""Modal components for Bibliome."""

from fasthtml.common import *
from datetime import datetime
from typing import List

from .forms import ContactForm


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


def CommentModal(book, comments, can_comment=False, user_auth_status="anonymous"):
    """Modal content for viewing and adding comments to a book."""
    # Book header with cover and title
    cover = Img(
        src=book.cover_url,
        alt=f"Cover of {book.title}",
        cls="comment-modal-book-cover"
    ) if book.cover_url else Div("📖", cls="comment-modal-book-cover-placeholder")
    
    # Comments list
    comment_items = []
    for comment in comments:
        comment_items.append(
            Div(
                Div(
                    Img(
                        src=comment.user_avatar_url,
                        alt=comment.user_display_name or comment.user_handle,
                        cls="comment-avatar"
                    ) if comment.user_avatar_url else Div("👤", cls="comment-avatar-placeholder"),
                    Div(
                        Strong(comment.user_display_name or comment.user_handle),
                        Span(f"@{comment.user_handle}", cls="comment-handle"),
                        cls="comment-user-info"
                    ),
                    cls="comment-header"
                ),
                P(comment.content, cls="comment-content"),
                Div(
                    Span(
                        comment.created_at.strftime("%B %d, %Y at %I:%M %p") if comment.created_at and hasattr(comment.created_at, 'strftime') else 
                        (datetime.fromisoformat(comment.created_at.replace('Z', '+00:00')).strftime("%B %d, %Y at %I:%M %p") if isinstance(comment.created_at, str) and comment.created_at else "Unknown time")
                    ),
                    comment.is_edited and Span("(edited)", cls="edited-indicator") or None,
                    cls="comment-meta"
                ),
                cls="comment-item",
                id=f"comment-{comment.id}"
            )
        )
    
    # Comment form (if user can comment)
    comment_form = None
    if can_comment:
        comment_form = Form(
            Textarea(
                name="content",
                placeholder="Share your thoughts about this book...",
                required=True,
                rows=3,
                cls="comment-modal-textarea"
            ),
            Button("Post Comment", type="submit", cls="comment-modal-submit-btn primary"),
            hx_post=f"/api/book/{book.id}/comment",
            hx_target="#modal-comments-list",
            hx_swap="afterbegin",
            hx_on_after_request="this.reset()",  # Clear form after successful submission
            cls="comment-modal-form"
        )
    elif user_auth_status == "anonymous":
        comment_form = Div(
            P("Sign in to comment on this book", cls="comment-auth-message"),
            A("Sign In", href="/auth/login", cls="primary comment-auth-btn"),
            cls="comment-auth-section"
        )
    else:
        comment_form = Div(
            P("Only contributors can comment on books in this shelf", cls="comment-permission-message"),
            cls="comment-permission-section"
        )
    
    return Div(
        Div(
            # Modal header
            Div(
                Button(
                    I(cls="fas fa-times"),
                    hx_get="/api/close-comment-modal",
                    hx_target="#comment-modal-container",
                    hx_swap="innerHTML",
                    cls="comment-modal-close",
                    title="Close"
                ),
                Div(
                    cover,
                    Div(
                        H2(book.title, cls="comment-modal-book-title"),
                        P(f"by {book.author}", cls="comment-modal-book-author") if book.author else None,
                        cls="comment-modal-book-info"
                    ),
                    cls="comment-modal-book-header"
                ),
                cls="comment-modal-header"
            ),
            
            # Modal body with comments
            Div(
                Div(
                    H3(f"Comments ({len(comments)})", cls="comments-section-title"),
                    Div(
                        *comment_items if comment_items else [P("No comments yet. Be the first to share your thoughts!", cls="no-comments-message")],
                        cls="comments-list",
                        id="modal-comments-list"
                    ),
                    cls="comments-section"
                ),
                cls="comment-modal-body"
            ),
            
            # Modal footer with comment form
            Div(
                comment_form,
                cls="comment-modal-footer"
            ),
            
            cls="comment-modal-dialog"
        ),
        cls="comment-modal-overlay"
    )
