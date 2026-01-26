"""Circuit breaker implementation for protecting services from cascading failures."""
import time
from functools import wraps
from threading import RLock


class CircuitBreaker:
    """
    A circuit breaker implementation that can be used to protect services from cascading failures.
    """
    def __init__(self, failure_threshold, recovery_timeout):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._lock = RLock()
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = 0

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                else:
                    raise Exception("Circuit is open")
            
            try:
                result = func(*args, **kwargs)
                self.reset()
                return result
            except Exception as e:
                self.trip()
                raise e
        return wrapper

    def trip(self):
        with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                self.last_failure_time = time.time()

    def reset(self):
        with self._lock:
            self.failures = 0
            self.state = "CLOSED"
            self.last_failure_time = 0
