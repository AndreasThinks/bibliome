"""
Rate limiter using the token bucket algorithm with exponential backoff support.
"""
import asyncio
import time
import random
import logging
from typing import Coroutine, Callable, Any
import httpx

logger = logging.getLogger(__name__)

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


class ExponentialBackoffRateLimiter:
    """
    Rate limiter with exponential backoff for handling API rate limits (429 errors).
    """
    
    def __init__(self, 
                 tokens_per_second: float = 1.0,
                 max_tokens: int = 10,
                 max_retries: int = 5,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 jitter: bool = True):
        """
        Initialize the rate limiter with exponential backoff.
        
        Args:
            tokens_per_second: Rate of token refill
            max_tokens: Maximum tokens in bucket
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between retries (seconds)
            jitter: Whether to add random jitter to delays
        """
        self.base_limiter = RateLimiter(tokens_per_second, max_tokens)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        
        # Track consecutive failures for adaptive rate limiting
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.adaptive_multiplier = 1.0
        
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff with optional jitter."""
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = self.base_delay * (2 ** attempt) * self.adaptive_multiplier
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add jitter: ±25% of the delay
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay)  # Ensure minimum delay
        
        return delay
    
    def _update_adaptive_rate(self, success: bool):
        """Update adaptive rate limiting based on success/failure patterns."""
        current_time = time.monotonic()
        
        if success:
            # Successful request - gradually reduce adaptive multiplier
            self.consecutive_failures = 0
            if self.adaptive_multiplier > 1.0:
                self.adaptive_multiplier = max(1.0, self.adaptive_multiplier * 0.9)
        else:
            # Failed request - increase adaptive multiplier
            self.consecutive_failures += 1
            self.last_failure_time = current_time
            
            # Increase backoff multiplier based on consecutive failures
            if self.consecutive_failures >= 3:
                self.adaptive_multiplier = min(4.0, self.adaptive_multiplier * 1.5)
    
    async def execute_with_backoff(self, 
                                   func: Callable,
                                   *args,
                                   **kwargs) -> Any:
        """
        Execute a function with exponential backoff on rate limit errors.
        
        Args:
            func: Async function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Acquire rate limit token before making request
                await self.base_limiter.acquire()
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Success - update adaptive rate and return
                self._update_adaptive_rate(success=True)
                if attempt > 0:
                    logger.info(f"Request succeeded after {attempt} retries")
                
                return result
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                
                if e.response.status_code == 429:
                    # Rate limited - apply exponential backoff
                    self._update_adaptive_rate(success=False)
                    
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(f"Rate limited (429), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limited (429), exhausted all {self.max_retries} retries")
                        raise
                        
                elif e.response.status_code >= 500:
                    # Server error - also retry with backoff
                    self._update_adaptive_rate(success=False)
                    
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(f"Server error ({e.response.status_code}), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Server error ({e.response.status_code}), exhausted all {self.max_retries} retries")
                        raise
                else:
                    # Other HTTP errors - don't retry
                    logger.error(f"HTTP error {e.response.status_code}, not retrying")
                    raise
                    
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                # Network errors - retry with backoff
                last_exception = e
                self._update_adaptive_rate(success=False)
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Network error ({type(e).__name__}), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Network error ({type(e).__name__}), exhausted all {self.max_retries} retries")
                    raise
                    
            except Exception as e:
                # Other exceptions - don't retry
                logger.error(f"Unexpected error: {e}, not retrying")
                raise
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Unexpected error in retry logic")
