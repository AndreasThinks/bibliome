"""Entry point for the Bibliome application."""

import os
import sys
import time
import signal
import threading
import logging
from pathlib import Path
from app import app, serve
from service_manager import ServiceManager

# Set up logging
logger = logging.getLogger(__name__)

# Global service manager instance
service_manager = None

def start_background_services():
    """Start background services in a separate thread."""
    global service_manager
    
    try:
        logger.info("Starting background services...")
        service_manager = ServiceManager(setup_signals=False)
        
        # Start services
        service_manager.start_all_services()
        
        # Give services a moment to start
        time.sleep(3)
        
        # Print initial status
        service_manager.print_status()
        
        logger.info("Background services started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start background services: {e}")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        
        if service_manager:
            logger.info("Stopping background services...")
            service_manager.stop_all_services()
        
        logger.info("Bibliome application shutdown complete")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def main():
    """Start the Bibliome FastHTML application with background services."""
    print("=" * 60)
    print("Starting Bibliome Application Suite")
    print("=" * 60)
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Check if we should skip background services (useful for development)
    skip_services = os.getenv('BIBLIOME_SKIP_SERVICES', 'false').lower() == 'true'
    
    if not skip_services:
        print("🔄 Starting background services...")
        # Start background services in a separate thread
        services_thread = threading.Thread(target=start_background_services, daemon=True)
        services_thread.start()
        
        # Give services time to start
        time.sleep(5)
    else:
        print("⏭️ Skipping background services (BIBLIOME_SKIP_SERVICES=true)")
    
    print("🌐 Starting web application...")
    print("📊 Admin dashboard: http://localhost:5001/admin")
    print("🔍 Process monitoring: http://localhost:5001/admin/processes")
    print("=" * 60)
    
    try:
        serve()
    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
        if service_manager:
            print("🔄 Stopping background services...")
            service_manager.stop_all_services()
    except Exception as e:
        logger.error(f"Application error: {e}")
        if service_manager:
            service_manager.stop_all_services()
        raise

if __name__ == "__main__":
    main()
