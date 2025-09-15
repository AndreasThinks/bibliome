"""Utilities for static file serving with cache busting."""

import os
import hashlib
from pathlib import Path

def get_file_hash(file_path: str, length: int = 8) -> str:
    """Generate a hash of a file's content for cache busting.
    
    Args:
        file_path: Path to the file
        length: Length of the hash to return (default 8 characters)
    
    Returns:
        Hash string of the specified length
    """
    try:
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash[:length]
    except (FileNotFoundError, IOError):
        # Fallback to a timestamp-based approach if file can't be read
        try:
            stat = os.stat(file_path)
            return str(int(stat.st_mtime))[:length]
        except:
            # Ultimate fallback
            return "00000000"[:length]

def get_static_url(file_path: str, use_cache_busting: bool = True) -> str:
    """Generate a URL for a static file with optional cache busting.
    
    Args:
        file_path: Path to the static file (e.g., "css/styles.css")
        use_cache_busting: Whether to append a cache-busting parameter
    
    Returns:
        URL string with or without cache busting parameter
    """
    base_url = f"/static/{file_path}"
    
    if not use_cache_busting:
        return base_url
    
    # Check if we have an environment variable override
    css_version = os.getenv('CSS_VERSION')
    if css_version:
        return f"{base_url}?v={css_version}"
    
    # Generate hash-based version
    full_path = os.path.join("static", file_path)
    file_hash = get_file_hash(full_path)
    return f"{base_url}?v={file_hash}"

def get_css_url() -> str:
    """Get the CSS URL with cache busting."""
    return get_static_url("css/styles.css")

def get_js_url(js_file: str) -> str:
    """Get a JavaScript file URL with cache busting."""
    return get_static_url(f"js/{js_file}")

# Cache the CSS hash to avoid recalculating on every request
_css_hash_cache = None
_css_file_mtime = None

def get_cached_css_url() -> str:
    """Get the CSS URL with cache busting, using in-memory caching for performance."""
    global _css_hash_cache, _css_file_mtime
    
    css_file_path = "static/css/styles.css"
    
    try:
        # Check if file has been modified
        current_mtime = os.path.getmtime(css_file_path)
        
        if _css_hash_cache is None or _css_file_mtime != current_mtime:
            # File has changed or cache is empty, regenerate
            _css_hash_cache = get_css_url()
            _css_file_mtime = current_mtime
        
        return _css_hash_cache
    except:
        # Fallback if file operations fail
        return get_css_url()
