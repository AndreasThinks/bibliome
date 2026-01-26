"""
Bibliome UI Components Package.

This package contains all reusable UI components for the Bibliome application,
organized by category for better maintainability.

All components are re-exported here for easy importing:
    from bibliome.components import NavBar, BookshelfCard, ShareModal
"""

# Navigation components
from .navigation import AlphaBadge, NavBar

# Utility components and helpers
from .utils import (
    format_time_ago,
    Alert,
    Modal,
    EmptyState,
    LoadingSpinner,
    Pagination,
)

# Form components
from .forms import (
    AddBooksToggle,
    BookSearchForm,
    SearchResultCard,
    CreateBookshelfForm,
    ContactForm,
    ContactFormSuccess,
    ContactFormError,
    ExploreSearchForm,
    SearchForm,
    SelfJoinButton,
    SelfJoinSuccess,
)

# Card components
from .cards import (
    BookshelfCard,
    BookCard,
    MemberCard,
    MemberRoleEditor,
    RoleChangePreview,
    ActivityCard,
    ActivityBookshelfCreated,
    ActivityBookAdded,
    CompactActivityCard,
    CompactActivityBookshelfCreated,
    CompactActivityBookAdded,
    UserActivityCard,
    UserActivityBookshelfCreated,
    UserActivityBookAdded,
    ShelfPreviewCard,
    UserSearchResultCard,
    BookScrollCard,
    InviteCard,
)

# Modal components
from .modals import (
    ContactModal,
    ShareModal,
    ShareLinkResult,
    SharePreview,
    CommentModal,
)

# Page section components
from .pages import (
    get_base_url,
    EnhancedEmptyState,
    ShelfHeader,
    ShareInterface,
    LandingPageHero,
    FeaturesSection,
    HowItWorksSection,
    PublicShelvesPreview,
    UniversalFooter,
    NetworkActivityFeed,
    NetworkActivityPreview,
    NetworkActivityPreviewLoading,
    NetworkActivityPreviewError,
    EmptyNetworkState,
    UnifiedExploreHero,
    ExplorePageHero,
    PublicShelvesGrid,
    SearchPageHero,
    CommunityReadingSection,
    SearchResultsGrid,
    BookListView,
    UserProfileHeader,
    UserPublicShelves,
    UserActivityFeed,
    NetworkPageHero,
    NetworkActivityFilters,
    FullNetworkActivityFeed,
    EmptyNetworkStateFullPage,
)

# Admin components
from .admin import (
    AdminDashboard,
    AdminStatsCard,
    AdminActivitySection,
    AdminActivityCard,
    AdminDatabaseSection,
    DatabaseUploadForm,
    BackupHistoryCard,
)

__all__ = [
    # Navigation
    "AlphaBadge",
    "NavBar",
    # Utils
    "format_time_ago",
    "Alert",
    "Modal",
    "EmptyState",
    "LoadingSpinner",
    "Pagination",
    # Forms
    "AddBooksToggle",
    "BookSearchForm",
    "SearchResultCard",
    "CreateBookshelfForm",
    "ContactForm",
    "ContactFormSuccess",
    "ContactFormError",
    "ExploreSearchForm",
    "SearchForm",
    "SelfJoinButton",
    "SelfJoinSuccess",
    # Cards
    "BookshelfCard",
    "BookCard",
    "MemberCard",
    "MemberRoleEditor",
    "RoleChangePreview",
    "ActivityCard",
    "ActivityBookshelfCreated",
    "ActivityBookAdded",
    "CompactActivityCard",
    "CompactActivityBookshelfCreated",
    "CompactActivityBookAdded",
    "UserActivityCard",
    "UserActivityBookshelfCreated",
    "UserActivityBookAdded",
    "ShelfPreviewCard",
    "UserSearchResultCard",
    "BookScrollCard",
    "InviteCard",
    # Modals
    "ContactModal",
    "ShareModal",
    "ShareLinkResult",
    "SharePreview",
    "CommentModal",
    # Pages
    "get_base_url",
    "EnhancedEmptyState",
    "ShelfHeader",
    "ShareInterface",
    "LandingPageHero",
    "FeaturesSection",
    "HowItWorksSection",
    "PublicShelvesPreview",
    "UniversalFooter",
    "NetworkActivityFeed",
    "NetworkActivityPreview",
    "NetworkActivityPreviewLoading",
    "NetworkActivityPreviewError",
    "EmptyNetworkState",
    "UnifiedExploreHero",
    "ExplorePageHero",
    "PublicShelvesGrid",
    "SearchPageHero",
    "CommunityReadingSection",
    "SearchResultsGrid",
    "BookListView",
    "UserProfileHeader",
    "UserPublicShelves",
    "UserActivityFeed",
    "NetworkPageHero",
    "NetworkActivityFilters",
    "FullNetworkActivityFeed",
    "EmptyNetworkStateFullPage",
    # Admin
    "AdminDashboard",
    "AdminStatsCard",
    "AdminActivitySection",
    "AdminActivityCard",
    "AdminDatabaseSection",
    "DatabaseUploadForm",
    "BackupHistoryCard",
]
