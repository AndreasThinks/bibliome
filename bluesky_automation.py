"""Core module for Bluesky automation, including posting, rate limiting, and message generation."""

import os
import random
import time
from datetime import datetime, timedelta
from atproto import Client as AtprotoClient
import logging
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class BlueskyAutomator:
    """Handles automated posting to a dedicated Bluesky account."""

    def __init__(self):
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
            return

        if not self.client:
            if not self._login():
                return

        if self._is_rate_limited():
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
        except Exception as e:
            logger.error(f"Failed to post to Bluesky: {e}", exc_info=True)

# Singleton instance
automator = BlueskyAutomator()

def trigger_automation(event_type: str, context: dict):
    """Entry point for triggering an automation event."""
    if automator.is_enabled:
        # In a more complex system, this could be a background task
        automator.post_to_bluesky(event_type, context)
