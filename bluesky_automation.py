"""Core module for Bluesky automation, including posting, rate limiting, and message generation."""

import os
import random
import time
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from atproto import Client as AtprotoClient
import logging
from dotenv import load_dotenv
from process_monitor import (
    log_process_event, record_process_metric, process_heartbeat, 
    update_process_status, get_process_monitor
)
from circuit_breaker import CircuitBreaker

load_dotenv()

# Configure logging with service name prefix
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, log_level_str, logging.INFO)
# Create a custom formatter
formatter = logging.Formatter('[bluesky_automation] %(asctime)s - %(levelname)s - %(message)s')
# Get the root logger
logger = logging.getLogger()
logger.setLevel(level)
# Remove existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Create a new handler with the custom formatter
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Process name for monitoring
PROCESS_NAME = "bluesky_automation"

class BlueskyAutomator:
    """Handles automated posting to a dedicated Bluesky account."""

    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.is_enabled = os.getenv('BLUESKY_AUTOMATION_ENABLED', 'false').lower() == 'true'
        self.handle = os.getenv('BLUESKY_AUTOMATION_HANDLE')
        self.password = os.getenv('BLUESKY_AUTOMATION_PASSWORD')
        self.post_threshold = int(os.getenv('BLUESKY_POST_THRESHOLD', 3))
        self.max_posts_per_hour = int(os.getenv('BLUESKY_MAX_POSTS_PER_HOUR', 3))
        
        if self.is_enabled and not (self.handle and self.password):
            logger.warning("Bluesky automation is enabled but handle or password are not set.")
            self.is_enabled = False
        
        self.client = None
        self._post_timestamps = []
        
        # Apply circuit breaker to methods
        self._login = self.circuit_breaker(self._login)
        self.post_to_bluesky = self.circuit_breaker(self.post_to_bluesky)

    def _login(self):
        """Logs into the dedicated Bluesky account."""
        if not self.is_enabled:
            return False
        
        try:
            self.client = AtprotoClient()
            self.client.login(self.handle, self.password)
            logger.info(f"Successfully logged into Bluesky as {self.handle}")
            return True
        except Exception as e:
            logger.error(f"Failed to log into Bluesky as {self.handle}: {e}", exc_info=True)
            self.is_enabled = False
            return False

    def _is_rate_limited(self):
        """Checks if the bot is currently rate-limited."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Filter out timestamps older than one hour
        self._post_timestamps = [ts for ts in self._post_timestamps if ts > one_hour_ago]
        
        if len(self._post_timestamps) >= self.max_posts_per_hour:
            logger.warning(f"Rate limit reached: {len(self._post_timestamps)} posts in the last hour.")
            return True
        
        return False

    def get_message_variety(self, event_type: str, context: dict) -> str:
        """Generates a cheeky and fun message based on the event type."""
        
        shelf_name = context.get('shelf_name', 'a new shelf')
        book_count = context.get('book_count', 0)
        shelf_url = context.get('shelf_url', '')

        # Message templates for when a shelf reaches the post threshold
        threshold_messages = [
            f"A new literary collection is born! '{shelf_name}' just hit {book_count} books. The library is growing! {shelf_url}",
            f"Watch out, world! The '{shelf_name}' bookshelf now has {book_count} books and is officially a thing. {shelf_url}",
            f"Someone's been busy! '{shelf_name}' just blossomed with {book_count} new books. What's inside? {shelf_url}",
            f"It's alive! The '{shelf_name}' bookshelf has sparked into existence with {book_count} books. {shelf_url}",
            f"And so it begins... '{shelf_name}' has been created with {book_count} books, ready for discovery. {shelf_url}",
            f"Behold! A new challenger appears: '{shelf_name}', armed with {book_count} books. {shelf_url}",
            f"New shelf alert! '{shelf_name}' just dropped with {book_count} books. Let the reading commence! {shelf_url}",
            f"The ink is still wet on this one! '{shelf_name}' is here with {book_count} books. {shelf_url}",
            f"From zero to hero! '{shelf_name}' just went from an idea to a {book_count}-book reality. {shelf_url}",
            f"Is it a bird? Is it a plane? No, it's '{shelf_name}' with {book_count} books! {shelf_url}",
            f"The community is buzzing about '{shelf_name}', which just hit {book_count} books. {shelf_url}",
            f"We've got a reader on our hands! '{shelf_name}' is now showcasing {book_count} books. {shelf_url}",
            f"This is not a drill! '{shelf_name}' has been spotted with {book_count} books. {shelf_url}",
            f"Prepare for literary greatness. '{shelf_name}' has arrived with {book_count} books. {shelf_url}",
            f"The shelves are stocked! '{shelf_name}' is now home to {book_count} books. {shelf_url}",
            f"Just in: '{shelf_name}' has been curated with {book_count} initial books. {shelf_url}",
            f"A new star is born in the Bibliome universe: '{shelf_name}' with {book_count} books. {shelf_url}",
            f"The reading list to end all reading lists? '{shelf_name}' makes its debut with {book_count} books. {shelf_url}",
            f"Get ready to expand your TBR pile. '{shelf_name}' is here with {book_count} books. {shelf_url}",
            f"What's better than a new book? A new bookshelf! '{shelf_name}' has {book_count} of them. {shelf_url}",
            f"The community that reads together, stays together. Check out '{shelf_name}' with {book_count} books. {shelf_url}",
            f"Warning: '{shelf_name}' may cause spontaneous reading. It already has {book_count} books. {shelf_url}",
            f"The seeds of a great library have been sown. '{shelf_name}' starts with {book_count} books. {shelf_url}",
            f"A new bookshelf has entered the chat: '{shelf_name}' with {book_count} books. {shelf_url}",
            f"Let the great book hunt begin! '{shelf_name}' is your new treasure map with {book_count} books. {shelf_url}",
            f"Curiosity piqued! '{shelf_name}' just appeared with {book_count} books. {shelf_url}",
            f"Bibliome is getting bigger! Say hello to '{shelf_name}' and its {book_count} books. {shelf_url}",
            f"The latest and greatest reading list? You decide. '{shelf_name}' has {book_count} books. {shelf_url}",
            f"Ready for your next reading adventure? '{shelf_name}' might be it, with {book_count} books. {shelf_url}",
            f"The digital ink is barely dry on '{shelf_name}', a new bookshelf with {book_count} books. {shelf_url}"
        ]

        # Placeholder for other event types
        event_messages = {
            "shelf_threshold_reached": threshold_messages,
        }

        messages = event_messages.get(event_type, ["A new event happened on Bibliome!"])
        return random.choice(messages)

    def post_to_bluesky(self, event_type: str, context: dict):
        """Posts a message to Bluesky if not rate-limited."""
        if not self.is_enabled:
            log_process_event(PROCESS_NAME, "Automation disabled - skipping post", "INFO", "activity")
            return

        if not self.client:
            if not self._login():
                log_process_event(PROCESS_NAME, "Failed to login - cannot post", "ERROR", "error")
                return

        if self._is_rate_limited():
            log_process_event(PROCESS_NAME, f"Rate limited - {len(self._post_timestamps)} posts in last hour", "WARNING", "activity")
            return

        try:
            message = self.get_message_variety(event_type, context)
            
            # Basic link parsing for rich text
            # This is a simplified implementation. A more robust solution would parse all links.
            from atproto import RichText
            rt = RichText(message)
            rt.detect_facets() # Automatically detects links

            self.client.send_post(text=rt.text, facets=rt.facets)
            
            self._post_timestamps.append(datetime.now())
            logger.info(f"Successfully posted to Bluesky: {message}")
            
            # Log successful post and metrics
            log_process_event(PROCESS_NAME, f"Posted to Bluesky: {event_type}", "INFO", "activity", {
                "event_type": event_type,
                "message_length": len(message),
                "shelf_name": context.get('shelf_name', ''),
                "book_count": context.get('book_count', 0)
            })
            record_process_metric(PROCESS_NAME, "posts_sent", 1)
            
            # Send heartbeat with activity info
            process_heartbeat(PROCESS_NAME, {"posts_sent": len(self._post_timestamps)})
            
        except Exception as e:
            logger.error(f"Failed to post to Bluesky: {e}", exc_info=True)
            log_process_event(PROCESS_NAME, f"Failed to post to Bluesky: {e}", "ERROR", "error")
            record_process_metric(PROCESS_NAME, "post_failures", 1)

class BlueskyService:
    """Background service for Bluesky automation monitoring."""
    
    def __init__(self):
        self.automator = BlueskyAutomator()
        self.running = False
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down Bluesky service...")
            update_process_status(PROCESS_NAME, "stopped")
            log_process_event(PROCESS_NAME, "Service shutdown via signal", "INFO", "stop")
            self.running = False
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def run_service(self):
        """Run the background service."""
        self.setup_signal_handlers()
        
        # Update process status to starting
        update_process_status(PROCESS_NAME, "starting", pid=os.getpid())
        log_process_event(PROCESS_NAME, "Bluesky automation service starting", "INFO", "start")
        
        # Update status to running
        update_process_status(PROCESS_NAME, "running", pid=os.getpid())
        self.running = True
        
        heartbeat_interval = 300  # 5 minutes
        last_heartbeat = datetime.now()
        
        try:
            while self.running:
                current_time = datetime.now()
                
                # Send periodic heartbeat
                if (current_time - last_heartbeat).total_seconds() >= heartbeat_interval:
                    activity_info = {
                        "posts_sent_last_hour": len([ts for ts in self.automator._post_timestamps 
                                                   if (current_time - ts).total_seconds() < 3600]),
                        "total_posts_session": len(self.automator._post_timestamps),
                        "automation_enabled": self.automator.is_enabled,
                        "rate_limited": self.automator._is_rate_limited()
                    }
                    process_heartbeat(PROCESS_NAME, activity_info)
                    log_process_event(PROCESS_NAME, "Periodic heartbeat", "DEBUG", "heartbeat")
                    last_heartbeat = current_time
                
                # Sleep for 30 seconds before next check
                await asyncio.sleep(30)
                
        except Exception as e:
            logger.error(f"Error in Bluesky service loop: {e}", exc_info=True)
            log_process_event(PROCESS_NAME, f"Service error: {e}", "ERROR", "error")
            update_process_status(PROCESS_NAME, "failed", error_message=str(e))
        finally:
            update_process_status(PROCESS_NAME, "stopped")
            log_process_event(PROCESS_NAME, "Bluesky service stopped", "INFO", "stop")

# Singleton instances
automator = BlueskyAutomator()
service = BlueskyService()

def trigger_automation(event_type: str, context: dict):
    """Entry point for triggering an automation event."""
    if automator.is_enabled:
        # In a more complex system, this could be a background task
        automator.post_to_bluesky(event_type, context)

async def run_background_service():
    """Run the Bluesky automation as a background service."""
    await service.run_service()

if __name__ == "__main__":
    """Run as background service when executed directly."""
    try:
        asyncio.run(run_background_service())
    except KeyboardInterrupt:
        logger.info("Bluesky automation service terminated")
        update_process_status(PROCESS_NAME, "stopped")
        log_process_event(PROCESS_NAME, "Service terminated by interrupt", "INFO", "stop")
