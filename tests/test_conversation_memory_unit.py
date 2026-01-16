"""
Unit tests for conversation memory system edge cases.
Tests specific scenarios and boundary conditions.
"""

import pytest
from uuid import uuid4

from app.services.conversation_memory_manager import get_memory_manager
from app.services.conversation_db import get_conversation_db


class TestConversationMemoryEdgeCases:
    """Unit tests for edge cases in conversation memory."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test services."""
        self.manager = get_memory_manager()
        self.db = get_conversation_db()
        yield
    
    def test_empty_conversation_history(self):
        """Test retrieving history for a session with no turns."""
        session_id = str(uuid4())
        
        # Retrieve history for non-existent session
        history = self.manager.get_session_history(session_id)
        
        # Should return empty list, not error
        assert history == [], "Empty session should return empty list"
        assert isinstance(history, list), "Should return a list"
    
    def test_single_turn_conversation(self):
        """Test conversation with exactly one turn."""
        user_id = str(uuid4())
        session_id = self.manager.create_session(user_id)
        
        # Store single turn
        turn = self.manager.store_turn(
            session_id=session_id,
            user_id=user_id,
            query="Single query",
            response="Single response"
        )
        
        # Verify turn number is 1
        assert turn.turn_number == 1, "First turn should be number 1"
        
        # Retrieve history
        history = self.manager.get_session_history(session_id)
        
        # Verify single turn
        assert len(history) == 1, "Should have exactly one turn"
        assert history[0].turn_number == 1, "Turn number should be 1"
        assert history[0].query_text == "Single query"
    
    def test_session_with_exactly_20_turns(self):
        """Test boundary condition: session with exactly 20 turns."""
        user_id = str(uuid4())
        session_id = self.manager.create_session(user_id)
        
        # Store exactly 20 turns
        for i in range(20):
            self.manager.store_turn(
                session_id=session_id,
                user_id=user_id,
                query=f"Query {i}",
                response=f"Response {i}"
            )
        
        # Retrieve history
        history = self.manager.get_session_history(session_id)
        
        # Verify all 20 turns
        assert len(history) == 20, "Should have exactly 20 turns"
        assert history[0].turn_number == 1, "First turn should be 1"
        assert history[-1].turn_number == 20, "Last turn should be 20"
    
    def test_empty_query_validation(self):
        """Test that empty queries are rejected."""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        # Try to store turn with empty query
        with pytest.raises(ValueError, match="query_text cannot be empty"):
            self.manager.store_turn(
                session_id=session_id,
                user_id=user_id,
                query="",
                response="Valid response"
            )
    
    def test_empty_response_validation(self):
        """Test that empty responses are rejected."""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        # Try to store turn with empty response
        with pytest.raises(ValueError, match="response_text cannot be empty"):
            self.manager.store_turn(
                session_id=session_id,
                user_id=user_id,
                query="Valid query",
                response=""
            )
    
    def test_whitespace_only_query_validation(self):
        """Test that whitespace-only queries are rejected."""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        # Try to store turn with whitespace-only query
        with pytest.raises(ValueError, match="query_text cannot be empty"):
            self.manager.store_turn(
                session_id=session_id,
                user_id=user_id,
                query="   ",
                response="Valid response"
            )
    
    def test_invalid_session_id_format(self):
        """Test that invalid UUID format is rejected."""
        user_id = str(uuid4())
        
        # Try to store turn with invalid session_id
        with pytest.raises(ValueError, match="Invalid UUID format"):
            self.manager.store_turn(
                session_id="not-a-valid-uuid",
                user_id=user_id,
                query="Valid query",
                response="Valid response"
            )
    
    def test_invalid_user_id_format(self):
        """Test that invalid user_id format is rejected."""
        session_id = str(uuid4())
        
        # Try to store turn with invalid user_id
        with pytest.raises(ValueError, match="Invalid UUID format"):
            self.manager.store_turn(
                session_id=session_id,
                user_id="invalid-user-id",
                query="Valid query",
                response="Valid response"
            )
    
    def test_delete_non_existent_session(self):
        """Test deleting a session that doesn't exist."""
        session_id = str(uuid4())
        
        # Delete non-existent session (should not error)
        deleted_count = self.manager.delete_session(session_id)
        
        # Should return 0 (no turns deleted)
        assert deleted_count == 0, "Deleting non-existent session should return 0"
    
    def test_turn_text_trimming(self):
        """Test that query and response text are trimmed."""
        user_id = str(uuid4())
        session_id = self.manager.create_session(user_id)
        
        # Store turn with leading/trailing whitespace
        turn = self.manager.store_turn(
            session_id=session_id,
            user_id=user_id,
            query="  Query with spaces  ",
            response="  Response with spaces  "
        )
        
        # Verify text is trimmed
        assert turn.query_text == "Query with spaces", "Query should be trimmed"
        assert turn.response_text == "Response with spaces", "Response should be trimmed"
    
    def test_metadata_storage(self):
        """Test that metadata is stored and retrieved correctly."""
        user_id = str(uuid4())
        session_id = self.manager.create_session(user_id)
        
        # Store turn with metadata
        metadata = {
            "confidence": 0.95,
            "intent": "search",
            "entities": ["project", "expense"]
        }
        
        turn = self.manager.store_turn(
            session_id=session_id,
            user_id=user_id,
            query="Test query",
            response="Test response",
            metadata=metadata
        )
        
        # Verify metadata
        assert turn.metadata == metadata, "Metadata should be stored correctly"
        assert turn.metadata["confidence"] == 0.95
        assert "entities" in turn.metadata
    
    def test_concurrent_sessions_same_user(self):
        """Test that a user can have multiple concurrent sessions."""
        user_id = str(uuid4())
        
        # Create multiple sessions for same user
        session_1 = self.manager.create_session(user_id)
        session_2 = self.manager.create_session(user_id)
        session_3 = self.manager.create_session(user_id)
        
        # Store turns in each session
        self.manager.store_turn(session_1, user_id, "Query 1", "Response 1")
        self.manager.store_turn(session_2, user_id, "Query 2", "Response 2")
        self.manager.store_turn(session_3, user_id, "Query 3", "Response 3")
        
        # Verify each session has its own history
        history_1 = self.manager.get_session_history(session_1)
        history_2 = self.manager.get_session_history(session_2)
        history_3 = self.manager.get_session_history(session_3)
        
        assert len(history_1) == 1 and "Query 1" in history_1[0].query_text
        assert len(history_2) == 1 and "Query 2" in history_2[0].query_text
        assert len(history_3) == 1 and "Query 3" in history_3[0].query_text
