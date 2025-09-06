"""
Rate limiter using the token bucket algorithm.
"""
import asyncio
import time
from typing import Coroutine

class RateLimiter:
    """
    A rate limiter using the token bucket algorithm for async operations.
    """
    def __init__(self, tokens_per_second: float, max_tokens: int):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_refill_time = time.monotonic()
        self.lock = asyncio.Lock()

    async def _refill_tokens(self):
        now = time.monotonic()
        time_passed = now - self.last_refill_time
        new_tokens = time_passed * self.tokens_per_second
        
        if new_tokens > 0:
            self.tokens = min(self.max_tokens, self.tokens + new_tokens)
            self.last_refill_time = now

    async def acquire(self, weight: int = 1):
        """
        Acquire a token before making a rate-limited call.
        Waits if necessary.
        """
        if weight > self.max_tokens:
            raise ValueError("Request weight exceeds max tokens.")

        async with self.lock:
            await self._refill_tokens()
            
            while self.tokens < weight:
                # Calculate time to wait for enough tokens
                required = weight - self.tokens
                wait_time = required / self.tokens_per_second
                
                # Release lock while waiting
                self.lock.release()
                await asyncio.sleep(wait_time)
                await self.lock.acquire()
                
                # Refill and re-check
                await self._refill_tokens()

            self.tokens -= weight

    async def __call__(self, coro: Coroutine):
        """
        Wrap a coroutine to be rate-limited.
        """
        await self.acquire()
        return await coro
