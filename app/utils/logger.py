"""
Logging Configuration using loguru
===================================
Centralized logging setup for the entire application.
"""

from loguru import logger
import sys
from pathlib import Path

# Remove default handler
logger.remove()

# Console handler (colored output for development)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# File handler (rotating logs for production)
log_path = Path("logs")
log_path.mkdir(exist_ok=True)

logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",      # New file every day
    retention="7 days",    # Keep logs for 7 days
    compression="zip",     # Compress old logs
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# Error file handler (separate file for errors)
logger.add(
    "logs/errors_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",   # Keep error logs longer
    compression="zip",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
)

# Export logger
__all__ = ["logger", "get_logger"]


def get_logger(name: str = None):
    """
    Get a logger instance.
    
    Args:
        name: Optional logger name (for context)
        
    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger

