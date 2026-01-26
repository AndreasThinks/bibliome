"""
Shared logging configuration for Bibliome services.

Provides consistent logging format with clear service identification
for Railway deployment and local development.

Usage:
    from logging_config import setup_logging
    logger = setup_logging("web_app")  # or "firehose_ingester", "service_manager", etc.
"""

import logging
import os
import sys
import json
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (Railway-friendly)."""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if any
        extra_data = getattr(record, 'extra_data', None)
        if extra_data is not None:
            log_entry["data"] = extra_data
        
        return json.dumps(log_entry)


class ServiceFormatter(logging.Formatter):
    """Standard formatter with clear service prefix."""
    
    def __init__(self, service_name: str):
        # Format: [service_name] 2026-01-26 19:45:00 - INFO - Message
        super().__init__(
            fmt=f'[{service_name}] %(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    service_name: str,
    log_file: Optional[str] = None,
    use_json: Optional[bool] = None
) -> logging.Logger:
    """
    Setup logging for a Bibliome service with consistent formatting.
    
    Args:
        service_name: Name of the service (e.g., "web_app", "firehose_ingester")
        log_file: Optional path to log file. If None, logs to console only.
        use_json: Whether to use JSON format. If None, auto-detects based on
                  RAILWAY_ENVIRONMENT or LOG_FORMAT environment variable.
    
    Returns:
        Configured logger instance.
    
    Example:
        from logging_config import setup_logging
        logger = setup_logging("web_app")
        logger.info("Application started")
        # Output: [web_app] 2026-01-26 19:45:00 - INFO - Application started
    """
    # Get log level from environment
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level_str, logging.INFO)
    
    # Auto-detect JSON format if not explicitly set
    if use_json is None:
        # Use JSON in Railway or if explicitly requested
        log_format = os.getenv('LOG_FORMAT', '').lower()
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None
        use_json = log_format == 'json' or (is_railway and log_format != 'text')
    
    # Get or create logger for the service
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    # Clear any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Choose formatter based on environment
    if use_json:
        formatter = JSONFormatter(service_name)
    else:
        formatter = ServiceFormatter(service_name)
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    return logger


def silence_noisy_loggers():
    """Silence commonly noisy third-party loggers."""
    noisy_loggers = [
        'watchfiles.main',
        'httpx',
        'httpcore',
        'urllib3',
        'asyncio',
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# Convenience function to get a child logger that inherits service prefix
def get_child_logger(parent_logger: logging.Logger, name: str) -> logging.Logger:
    """
    Get a child logger that inherits the parent's configuration.
    
    Useful for sub-modules that want their own logger but with consistent formatting.
    
    Example:
        logger = setup_logging("web_app")
        auth_logger = get_child_logger(logger, "auth")
        # auth_logger will have name "web_app.auth"
    """
    return parent_logger.getChild(name)
