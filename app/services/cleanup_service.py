"""
Auto-Cleanup Service - Deletes conversations older than 24 hours.
Runs hourly to prevent database growth beyond free tier limits.
"""

import time
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.conversation_db import get_conversation_db
from app.models.conversation import CleanupResult, CleanupStats
from app.utils.logger import logger


class AutoCleanupService:
    """
    Background service that automatically cleans up old conversations.
    Runs every hour to delete conversations older than 24 hours.
    """
    
    def __init__(self):
        """Initialize the cleanup service."""
        self.db = get_conversation_db()
        self.scheduler: Optional[BackgroundScheduler] = None
        self.stats = CleanupStats(
            total_cleanups=0,
            total_sessions_deleted=0,
            total_turns_deleted=0,
            average_execution_time=0.0,
            last_cleanup=datetime.now()
        )
        self._execution_times = []
    
    def run_cleanup(self) -> CleanupResult:
        """
        Execute cleanup operation.
        
        Deletes all conversations with created_at > 24 hours ago.
        
        Returns:
            CleanupResult with deletion statistics
        """
        start_time = time.time()
        
        logger.info("Starting cleanup of old conversations...")
        
        try:
            # Call database cleanup function
            result = self.db.cleanup_old_conversations()
            
            execution_time = time.time() - start_time
            
            # Update statistics
            self._update_stats(result, execution_time)
            
            logger.info(
                f"Cleanup completed: {result.sessions_deleted} sessions, "
                f"{result.turns_deleted} turns deleted in {execution_time:.2f}s",
                extra={
                    "sessions_deleted": result.sessions_deleted,
                    "turns_deleted": result.turns_deleted,
                    "execution_time": execution_time
                }
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(
                f"Cleanup failed: {error_msg}",
                extra={
                    "error": error_msg,
                    "execution_time": execution_time
                },
                exc_info=True
            )
            
            # Return failed result
            return CleanupResult(
                sessions_deleted=0,
                turns_deleted=0,
                execution_time=execution_time,
                errors=[error_msg]
            )
    
    def schedule_hourly(self):
        """
        Set up hourly execution using APScheduler.
        
        The cleanup will run every hour to check for expired conversations.
        """
        if self.scheduler is not None:
            logger.warning("Cleanup service already scheduled")
            return
        
        # Create scheduler
        self.scheduler = BackgroundScheduler()
        
        # Add job to run every hour
        self.scheduler.add_job(
            func=self.run_cleanup,
            trigger=IntervalTrigger(hours=1),
            id='cleanup_old_conversations',
            name='Cleanup old conversations (24h+)',
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info(
            "Cleanup service scheduled: running every hour",
            extra={"interval": "1 hour"}
        )
    
    def stop_scheduler(self):
        """Stop the cleanup scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
            logger.info("Cleanup service stopped")
    
    def get_cleanup_stats(self) -> CleanupStats:
        """
        Get statistics about cleanup operations.
        
        Returns:
            CleanupStats with aggregated statistics
        """
        return self.stats
    
    def _update_stats(self, result: CleanupResult, execution_time: float):
        """Update cleanup statistics."""
        self.stats.total_cleanups += 1
        self.stats.total_sessions_deleted += result.sessions_deleted
        self.stats.total_turns_deleted += result.turns_deleted
        self.stats.last_cleanup = datetime.now()
        
        # Track execution times for average
        self._execution_times.append(execution_time)
        if len(self._execution_times) > 100:  # Keep last 100
            self._execution_times.pop(0)
        
        # Calculate average
        if self._execution_times:
            self.stats.average_execution_time = sum(self._execution_times) / len(self._execution_times)


# Singleton instance
_cleanup_service = None


def get_cleanup_service() -> AutoCleanupService:
    """Get the cleanup service instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = AutoCleanupService()
    return _cleanup_service


def start_cleanup_service():
    """Start the cleanup service (call on app startup)."""
    service = get_cleanup_service()
    service.schedule_hourly()
    logger.info("Auto-cleanup service started")


def stop_cleanup_service():
    """Stop the cleanup service (call on app shutdown)."""
    service = get_cleanup_service()
    service.stop_scheduler()
    logger.info("Auto-cleanup service stopped")
