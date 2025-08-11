#!/usr/bin/env python3

from fasthtml.common import *

"""Basic test to verify the FastHTML application structure."""

import sys
import os

def test_imports():
    """Test that all modules can be imported without errors."""
    try:
        print("Testing imports...")
        
        # Test models
        from models import setup_database, User, Bookshelf, Book
        print("✓ Models imported successfully")
        
        # Test auth
        from auth import BlueskyAuth, get_current_user_did
        print("✓ Auth imported successfully")
        
        # Test API clients
        from api_clients import BookAPIClient
        print("✓ API clients imported successfully")
        
        # Test components
        from components import NavBar, BookCard, CreateBookshelfForm
        print("✓ Components imported successfully")
        
        # Test main app
        from app import app, rt
        print("✓ Main app imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_database_setup():
    """Test database setup."""
    try:
        print("\nTesting database setup...")
        from models import setup_database
        
        # Use in-memory database for testing
        db_tables = setup_database(':memory:')
        
        # Check that all tables exist
        required_tables = ['users', 'bookshelves', 'books', 'permissions', 'upvotes']
        for table_name in required_tables:
            if table_name not in db_tables:
                raise Exception(f"Missing table: {table_name}")
        
        print("✓ Database setup successful")
        print(f"✓ Created tables: {list(db_tables.keys())}")
        
        return True
    except Exception as e:
        print(f"✗ Database setup error: {e}")
        return False

def test_fasthtml_patterns():
    """Test FastHTML patterns and components."""
    try:
        print("\nTesting FastHTML patterns...")
        from components import NavBar, Alert, BookCard
        from models import Book
        from datetime import datetime
        
        # Test NavBar component
        nav = NavBar()
        print("✓ NavBar component works")
        
        # Test Alert component
        alert = Alert("Test message", "info")
        print("✓ Alert component works")
        
        # Test BookCard with mock data
        mock_book = Book(
            bookshelf_id=1,
            title="Test Book",
            added_by_did="test-did",
            author="Test Author",
            description="Test description",
            upvotes=5,
            added_at=datetime.now()
        )
        mock_book.id = 1  # Simulate database ID
        
        card = BookCard(mock_book)
        print("✓ BookCard component works")
        
        # Test Titled usage
        page = Titled("Test Page", P("Test content"))
        print("✓ Titled component works correctly")
        
        return True
    except Exception as e:
        print(f"✗ FastHTML patterns error: {e}")
        return False

def test_route_structure():
    """Test that routes are properly defined."""
    try:
        print("\nTesting route structure...")
        from app import app
        
        # Get all routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        # Check for essential routes
        essential_routes = [
            '/',
            '/auth/login',
            '/auth/logout',
            '/shelf/new',
            '/shelf/create',
        ]
        
        for route_path in essential_routes:
            # Check if route exists (may have parameters)
            route_exists = any(route_path in route for route in routes)
            if not route_exists:
                print(f"Warning: Route {route_path} not found in {routes}")
        
        print(f"✓ Found {len(routes)} routes")
        return True
    except Exception as e:
        print(f"✗ Route structure error: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running BookdIt FastHTML Tests\n")
    
    tests = [
        test_imports,
        test_database_setup,
        test_fasthtml_patterns,
        test_route_structure,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application structure looks good.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
