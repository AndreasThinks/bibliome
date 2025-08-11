# Collaborative Bookshelf Project Plan

## 1. Overview

A decentralized, collaborative bookshelf platform with Bluesky (AT-Proto) authentication. Users can create and manage lists of books, set privacy levels, and assign roles for collaboration. The platform will be built with **FastHTML** for both frontend and backend, integrating external book APIs for metadata.

## 2. Core Features

### 2.1 List Creation and Management

* Users can create named bookshelves with a unique URL.
* Each list can contain books added manually or through a book search API.
* Books can be **added** or **upvoted** by permitted users.
* No drag-and-drop reordering.

### 2.2 Privacy Levels

* **Public**: Fully open and indexed by search engines.
* **Link-only**: Accessible only to users with the URL, not indexed.
* **Private**: Only accessible by Bluesky accounts explicitly added to the list.

### 2.3 User Roles

* **Admin**: Full control over the list, users, and settings.
* **Editor**: Can add and upvote books but not manage users.
* **Viewer**: Can only view the list.

### 2.4 Authentication

* Login with Bluesky via AT-Proto authentication.
* Potential for portable user identity across instances.

## 3. API Integrations

* **Google Books API** (free) for book metadata.
* **Open Library API** as an alternative or fallback.
* Possible ISBNdb integration for premium, more detailed metadata.

## 4. Monetization Approach

* Core platform is **open source**.
* Managed hosting service for those who prefer not to self-host.
* Premium plugins, e.g., advanced analytics.
* WordPress-style model: free base, paid premium enhancements.

## 5. Tech Stack

* **Backend & Frontend**: FastHTML
* **Auth**: AT-Proto (Bluesky login)
* **Database**: SQLite for MVP (later migration to Postgres if scaling)
* **APIs**: Google Books, Open Library

## 6. Implementation Roadmap

### Phase 1 – MVP

1. Setup FastHTML project structure.
2. Implement Bluesky authentication.
3. Create database models for Users, Bookshelves, Books, and Permissions using FastLite dataclass style.
4. Implement list creation and book addition/upvoting.
5. Integrate Google Books API.
6. Basic frontend UI using PicoCSS components.

### Phase 2 – Privacy & Roles

1. Add privacy settings for lists.
2. Implement role-based permissions.
3. Test Bluesky private list access.

### Phase 3 – Monetization & Scaling

1. Add Open Library API fallback.
2. Implement managed hosting infrastructure.
3. Develop premium analytics plugin.
4. Marketing and community outreach.

## 7. Example Code Snippets (Updated for FastHTML best practices)

> Notes: Use FastHTML's `fast_app()` and `@rt` routing (HTML-first). Prefer `Titled`, `.to()` for path building, and session-based auth with Beforeware.

### 7.1 List Creation Handler (HTML-first)

```python
from fasthtml.common import *

app, rt = fast_app()

# Assume user auth has populated sess['auth'] via Beforeware
@rt
def create_list(sess, name: str, privacy: str):
    user = sess.get('auth')
    if not user: return RedirectResponse('/login', status_code=303)

    bs = Bookshelf(name=name, privacy=privacy, owner_id=user.id)
    bookshelves.insert(**asdict(bs))  # fastlite/sqlalchemy – implement as per your DB layer

    # Return HTML with a link using .to() for the show route
    return Titled(
        'Bookshelf Created',
        P('Your bookshelf is ready.'),
        A('Open shelf', href=show_list.to(id=bs.id))
    )
```

### 7.2 Adding a Book (with redirect/toast)

```python
@rt
def add_book(sess, list_id: int, query: str):
    user = sess.get('auth')
    if not user: return RedirectResponse('/login', status_code=303)
    require_role(sess, list_id, {'admin','editor'})

    data = search_book(query)  # wrap Google Books / Open Library lookup
    if data:
        bk = Book(title=data['title'], author=data['author'], list_id=list_id)
        books.insert(**asdict(bk))
        add_toast(sess, 'Book added', 'success')  # optional: setup_toasts(app)

    # HTMX-friendly redirect back to the list page
    return HtmxResponseHeaders(location=show_list.to(id=list_id))
```

### 7.3 Role Checking (helper + Beforeware pattern)

```python
# Simple helper used inside handlers
def require_role(sess, list_id: int, allowed: set[str]):
    role = get_role(sess['auth'].id, list_id)  # implement per your schema
    if role not in allowed:
        raise HTTPException(status_code=403, detail='Forbidden')

# Example global Beforeware for login requirement

def login_before(req, sess):
    if req.url.path not in {'/login','/'} and not sess.get('auth'):
        return RedirectResponse('/login', status_code=303)

before = Beforeware(login_before, skip=[r'/static/.*', r'.*\.css', r'.*\.js'])
app, rt = fast_app(before=before)
```

### 7.4 Generating Paths Safely with `.to()`

```python
@rt
def show_list(id: int):
    # render the bookshelf
    ...

# Build a path with query params, e.g. in an anchor or hx_ attribute
path = add_book.to(list_id=42, query='dune')  # '/add_book?list_id=42&query=dune'
```

## 8. Next Steps

* Finalize API choices and schema.

* Draft UI wireframes.

* Begin Phase 1 MVP development.

* Finalize API choices and schema.

* Draft UI wireframes using PicoCSS.

* Begin Phase 1 MVP development.
