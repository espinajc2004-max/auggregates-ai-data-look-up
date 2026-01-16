"""
Database service for conversation memory operations.
Handles all database interactions for storing and retrieving conversation turns.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import time

from app.services.supabase_client import get_supabase, SupabaseError
from app.models.conversation import Turn, CleanupResult
from app.utils.logger import logger


class ConversationDatabaseService:
    """Service for conversation memory database operations."""
    
    def __init__(self):
        self.supabase = get_supabase()
    
    def store_turn(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Turn:
        """
        Store a conversation turn in the database.
        
        Args:
            session_id: UUID of the conversation session
            user_id: UUID of the user
            query: User's query text
            response: AI's response text
            metadata: Optional metadata dictionary
            
        Returns:
            Turn object with stored data
            
        Raises:
            ValueError: If input validation fails
            SupabaseError: If database operation fails
        """
        # Input validation
        self._validate_turn_input(session_id, user_id, query, response)
        
        try:
            # Get next turn number for this session
            turn_number = self._get_next_turn_number(session_id)
            
            # Prepare turn data with prefixed parameter names
            turn_data = {
                "p_session_id": session_id,
                "p_user_id": user_id,
                "p_turn_number": turn_number,
                "p_query_text": query.strip(),
                "p_response_text": response.strip(),
                "p_metadata": metadata or {}
            }
            
            # Insert into database
            result = self.supabase.rpc("insert_conversation_turn", turn_data)
            
            if not result or len(result) == 0:
                raise SupabaseError("Failed to insert conversation turn")
            
            # Convert to Turn object
            turn = Turn.from_dict(result[0])
            
            logger.info(
                f"Stored turn {turn_number} for session {session_id[:8]}...",
                extra={
                    "session_id": session_id,
                    "turn_number": turn_number,
                    "query_length": len(query),
                    "response_length": len(response)
                }
            )
            
            return turn
            
        except SupabaseError as e:
            logger.error(
                f"Failed to store turn for session {session_id[:8]}...: {str(e)}",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error storing turn: {str(e)}",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise SupabaseError(f"Failed to store turn: {str(e)}")
    
    def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Turn]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: UUID of the conversation session
            limit: Maximum number of turns to retrieve (default 50)
            
        Returns:
            List of Turn objects ordered by turn_number
        """
        try:
            # Query conversation turns
            params = {
                "session_id": f"eq.{session_id}",
                "order": "turn_number.asc",
                "limit": limit
            }
            
            result = self.supabase.get("conversation_turns", params)
            
            if not result:
                logger.info(f"No history found for session {session_id[:8]}...")
                return []
            
            # Convert to Turn objects
            turns = [Turn.from_dict(turn_data) for turn_data in result]
            
            logger.info(
                f"Retrieved {len(turns)} turns for session {session_id[:8]}...",
                extra={"session_id": session_id, "turn_count": len(turns)}
            )
            
            return turns
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve session history: {str(e)}",
                extra={"session_id": session_id, "error": str(e)}
            )
            # Return empty list on error (graceful degradation)
            return []
    
    def create_session(self, user_id: str) -> str:
        """
        Create a new conversation session.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            New session_id (UUID string)
        """
        session_id = str(uuid4())
        
        logger.info(
            f"Created new session {session_id[:8]}... for user {user_id[:8]}...",
            extra={"session_id": session_id, "user_id": user_id}
        )
        
        return session_id
    
    def delete_session(self, session_id: str) -> int:
        """
        Delete a session and all its turns.
        
        Args:
            session_id: UUID of the session to delete
            
        Returns:
            Number of turns deleted
        """
        try:
            # Get turn count before deletion
            turns = self.get_session_history(session_id)
            turn_count = len(turns)
            
            # Delete all turns for this session
            params = {"session_id": f"eq.{session_id}"}
            self.supabase._session.delete(
                f"{self.supabase.base_url}/conversation_turns",
                params=params,
                timeout=self.supabase.DEFAULT_TIMEOUT
            )
            
            logger.info(
                f"Deleted session {session_id[:8]}... ({turn_count} turns)",
                extra={"session_id": session_id, "turns_deleted": turn_count}
            )
            
            return turn_count
            
        except Exception as e:
            logger.error(
                f"Failed to delete session: {str(e)}",
                extra={"session_id": session_id, "error": str(e)}
            )
            raise SupabaseError(f"Failed to delete session: {str(e)}")
    
    def cleanup_old_conversations(self) -> CleanupResult:
        """
        Delete conversations older than 24 hours.
        
        Returns:
            CleanupResult with deletion statistics
        """
        start_time = time.time()
        errors = []
        
        try:
            # Call cleanup function
            result = self.supabase.rpc("cleanup_old_conversations", {})
            
            if not result or len(result) == 0:
                raise SupabaseError("Cleanup function returned no results")
            
            sessions_deleted = result[0].get("sessions_deleted", 0)
            turns_deleted = result[0].get("turns_deleted", 0)
            execution_time = time.time() - start_time
            
            cleanup_result = CleanupResult(
                sessions_deleted=sessions_deleted,
                turns_deleted=turns_deleted,
                execution_time=execution_time,
                errors=errors
            )
            
            logger.info(
                f"Cleanup completed: {sessions_deleted} sessions, {turns_deleted} turns deleted",
                extra={
                    "sessions_deleted": sessions_deleted,
                    "turns_deleted": turns_deleted,
                    "execution_time": execution_time
                }
            )
            
            return cleanup_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            errors.append(error_msg)
            
            logger.error(
                f"Cleanup failed: {error_msg}",
                extra={"error": error_msg, "execution_time": execution_time}
            )
            
            return CleanupResult(
                sessions_deleted=0,
                turns_deleted=0,
                execution_time=execution_time,
                errors=errors
            )
    
    def _get_next_turn_number(self, session_id: str) -> int:
        """
        Get the next turn number for a session.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            Next turn number (1 for new session, N+1 for existing)
        """
        try:
            result = self.supabase.rpc("get_next_turn_number", {"p_session_id": session_id})
            
            # RPC function returns an integer directly, not an array
            if result is not None and isinstance(result, int):
                return result
            
            # Fallback: query manually
            turns = self.get_session_history(session_id, limit=1000)
            if turns:
                return max(t.turn_number for t in turns) + 1
            return 1
            
        except Exception as e:
            logger.warning(
                f"Failed to get next turn number, using fallback: {str(e)}",
                extra={"session_id": session_id}
            )
            # Fallback: query manually
            turns = self.get_session_history(session_id, limit=1000)
            if turns:
                return max(t.turn_number for t in turns) + 1
            return 1
    
    def _validate_turn_input(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str
    ):
        """
        Validate input data for storing a turn.
        
        Raises:
            ValueError: If validation fails
        """
        if not session_id or not session_id.strip():
            raise ValueError("session_id cannot be empty")
        
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if not query or not query.strip():
            raise ValueError("query_text cannot be empty")
        
        if not response or not response.strip():
            raise ValueError("response_text cannot be empty")
        
        # Validate UUID format (basic check)
        try:
            from uuid import UUID
            UUID(session_id)
            UUID(user_id)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {str(e)}")


# Singleton instance
_conversation_db = None


def get_conversation_db() -> ConversationDatabaseService:
    """Get the conversation database service instance."""
    global _conversation_db
    if _conversation_db is None:
        _conversation_db = ConversationDatabaseService()
    return _conversation_db
