"""Meta tag utilities for social media sharing and SEO."""

from fasthtml.common import *
import os
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

def get_base_url():
    """Get the base URL from environment or default."""
    return os.getenv('BASE_URL', 'http://localhost:5001')

def create_meta_tags(
    title: str,
    description: str,
    image_url: str = None,
    url: str = None,
    type: str = "website",
    site_name: str = "Bibliome",
    twitter_card: str = "summary_large_image"
):
    """
    Create Open Graph and Twitter Card meta tags for social media sharing.
    
    Args:
        title: Page title
        description: Page description
        image_url: Full URL to the image (optional)
        url: Canonical URL of the page (optional)
        type: Open Graph type (website, article, profile)
        site_name: Site name for Open Graph
        twitter_card: Twitter card type (summary, summary_large_image)
    
    Returns:
        List of meta tag elements
    """
    base_url = get_base_url()
    
    # Default image if none provided
    if not image_url:
        image_url = urljoin(base_url, '/static/bibliome_transparent.png')
    
    # Ensure image URL is absolute
    if image_url and not image_url.startswith(('http://', 'https://')):
        image_url = urljoin(base_url, image_url)
    
    # Ensure URL is absolute
    if url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    meta_tags = [
        # Open Graph tags
        Meta(property="og:title", content=title),
        Meta(property="og:description", content=description),
        Meta(property="og:type", content=type),
        Meta(property="og:site_name", content=site_name),
        
        # Twitter Card tags
        Meta(name="twitter:card", content=twitter_card),
        Meta(name="twitter:title", content=title),
        Meta(name="twitter:description", content=description),
        
        # Standard meta tags
        Meta(name="description", content=description),
    ]
    
    # Add image tags if image is provided
    if image_url:
        meta_tags.extend([
            Meta(property="og:image", content=image_url),
            Meta(property="og:image:width", content="1200"),
            Meta(property="og:image:height", content="630"),
            Meta(property="og:image:alt", content=f"{title} - {site_name}"),
            Meta(name="twitter:image", content=image_url),
            Meta(name="twitter:image:alt", content=f"{title} - {site_name}"),
        ])
    
    # Add URL if provided
    if url:
        meta_tags.extend([
            Meta(property="og:url", content=url),
            Link(rel="canonical", href=url),
        ])
    
    return meta_tags

def create_bookshelf_meta_tags(shelf, req=None, book_count=0, sample_books=None):
    """
    Create meta tags specifically for bookshelf pages.
    
    Args:
        shelf: Bookshelf object from database
        req: Request object to get current URL
        book_count: Number of books in the shelf
        sample_books: List of sample book titles for description
    
    Returns:
        List of meta tag elements
    """
    base_url = get_base_url()
    
    # Build title
    title = f"{shelf.name} - Bibliome"
    
    # Build description
    if shelf.description and shelf.description.strip():
        description = shelf.description.strip()
    else:
        # Generate description based on content
        if book_count > 0:
            if sample_books and len(sample_books) > 0:
                if book_count == 1:
                    description = f"A curated bookshelf featuring {sample_books[0]}"
                elif book_count <= 3:
                    book_list = " and ".join(sample_books[:book_count])
                    description = f"A curated collection of {book_count} books including {book_list}"
                else:
                    book_list = ", ".join(sample_books[:2])
                    description = f"A curated collection of {book_count} books including {book_list} and {book_count - 2} more"
            else:
                description = f"A curated collection of {book_count} books on Bibliome"
        else:
            description = f"A collaborative bookshelf on Bibliome - join the reading community!"
    
    # Get current URL
    current_url = None
    if req:
        current_url = str(req.url)
    else:
        current_url = urljoin(base_url, f'/shelf/{shelf.slug}')
    
    # For now, use the default logo - we'll enhance this later with book cover collages
    image_url = urljoin(base_url, '/static/bibliome_transparent.png')
    
    return create_meta_tags(
        title=title,
        description=description,
        image_url=image_url,
        url=current_url,
        type="article"
    )

def create_user_profile_meta_tags(user, req=None, shelf_count=0):
    """
    Create meta tags specifically for user profile pages.
    
    Args:
        user: User object from database
        req: Request object to get current URL
        shelf_count: Number of public shelves the user has
    
    Returns:
        List of meta tag elements
    """
    base_url = get_base_url()
    
    # Build title
    title = f"@{user.handle}'s Profile - Bibliome"
    
    # Build description
    display_name = user.display_name or user.handle
    if shelf_count > 0:
        if shelf_count == 1:
            description = f"{display_name}'s reading collection with 1 public bookshelf on Bibliome"
        else:
            description = f"{display_name}'s reading collection with {shelf_count} public bookshelves on Bibliome"
    else:
        description = f"{display_name}'s profile on Bibliome - discover their reading interests"
    
    # Get current URL
    current_url = None
    if req:
        current_url = str(req.url)
    else:
        current_url = urljoin(base_url, f'/user/{user.handle}')
    
    # Use user's avatar if available, otherwise fallback to logo
    image_url = user.avatar_url if user.avatar_url else urljoin(base_url, '/static/bibliome_transparent.png')
    
    return create_meta_tags(
        title=title,
        description=description,
        image_url=image_url,
        url=current_url,
        type="profile"
    )

def create_homepage_meta_tags(req=None):
    """
    Create meta tags for the homepage.
    
    Args:
        req: Request object to get current URL
    
    Returns:
        List of meta tag elements
    """
    base_url = get_base_url()
    
    title = "Bibliome - Building the very best reading lists, together"
    description = "Create collaborative bookshelves, discover new books, and build reading communities with friends. Join the decentralized reading revolution powered by Bluesky."
    
    # Get current URL
    current_url = None
    if req:
        current_url = str(req.url)
    else:
        current_url = base_url
    
    image_url = urljoin(base_url, '/static/bibliome_transparent.png')
    
    return create_meta_tags(
        title=title,
        description=description,
        image_url=image_url,
        url=current_url,
        type="website"
    )

def create_explore_meta_tags(req=None):
    """
    Create meta tags for the explore page.
    
    Args:
        req: Request object to get current URL
    
    Returns:
        List of meta tag elements
    """
    base_url = get_base_url()
    
    title = "Explore Bookshelves - Bibliome"
    description = "Discover amazing reading lists from the Bibliome community. Find your next great book through curated collections and collaborative recommendations."
    
    # Get current URL
    current_url = None
    if req:
        current_url = str(req.url)
    else:
        current_url = urljoin(base_url, '/explore')
    
    image_url = urljoin(base_url, '/static/bibliome_transparent.png')
    
    return create_meta_tags(
        title=title,
        description=description,
        image_url=image_url,
        url=current_url,
        type="website"
    )

def truncate_description(text, max_length=160):
    """
    Truncate description to optimal length for social media.
    
    Args:
        text: Text to truncate
        max_length: Maximum length (default 160 for optimal social media)
    
    Returns:
        Truncated text with ellipsis if needed
    """
    if not text:
        return ""
    
    text = text.strip()
    if len(text) <= max_length:
        return text
    
    # Find the last space before the limit to avoid cutting words
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # Only use space if it's not too far back
        truncated = truncated[:last_space]
    
    return truncated + "..."

def get_sample_book_titles(books, max_titles=3):
    """
    Get a sample of book titles for description generation.
    
    Args:
        books: List of book objects
        max_titles: Maximum number of titles to return
    
    Returns:
        List of book titles
    """
    if not books:
        return []
    
    # Sort by upvote count (if available) to get the most popular books
    try:
        sorted_books = sorted(books, key=lambda b: getattr(b, 'upvote_count', 0), reverse=True)
    except:
        sorted_books = books
    
    return [book.title for book in sorted_books[:max_titles]]
