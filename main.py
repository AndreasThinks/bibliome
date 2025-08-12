"""Entry point for the Bibliome application."""

from app import app, serve

def main():
    """Start the Bibliome FastHTML application."""
    print("Starting Bibliome application...")
    serve()

if __name__ == "__main__":
    main()
