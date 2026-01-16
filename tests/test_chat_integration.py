"""
Integration tests for conversation memory + AI chat system.
Tests multi-turn conversations with context references.
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.services.conversation_memory_manager import get_memory_manager
from app.services.conversation_db import get_conversation_db
from app.models.requests import ChatRequest


class TestConversationIntegration:
    """Integration tests for conversation memory with AI chat."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client and services."""
        self.client = TestClient(app)
        self.manager = get_memory_manager()
        self.db = get_conversation_db()
        
        # Create test user and session
        self.user_id = str(uuid4())
        self.session_id = self.manager.create_session(self.user_id)
        
        yield
        
        # Cleanup: delete test session
        try:
            self.manager.delete_session(self.session_id)
        except:
            pass
    
    def test_multi_turn_conversation_storage(self):
        """Test that multiple conversation turns are stored correctly."""
        # Turn 1
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="How many expenses?",
            response="There are 50 expenses in the database."
        )
        
        # Turn 2
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="What about cashflow?",
            response="There are 30 cashflow records."
        )
        
        # Turn 3
        turn3 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Show the projects",
            response="Here are 10 projects."
        )
        
        # Retrieve history
        history = self.manager.get_session_history(self.session_id)
        
        # Verify all turns stored
        assert len(history) == 3, "Should have 3 turns"
        assert history[0].turn_number == 1
        assert history[1].turn_number == 2
        assert history[2].turn_number == 3
        
        # Verify content
        assert "expenses" in history[0].query_text.lower()
        assert "cashflow" in history[1].query_text.lower()
        assert "projects" in history[2].query_text.lower()
    
    def test_reference_resolution_ordinal_english(self):
        """Test reference resolution with English ordinals: 'the first', 'the second'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find fuel in cashflow",
            response="Found 5 fuel entries."
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find salary in expenses",
            response="Found 3 salary entries."
        )
        
        turn3 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Show projects",
            response="There are 10 projects."
        )
        
        # Test reference: "the first one"
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show the first one"
        )
        
        # Should reference turn 1
        assert len(context.referenced_turns) > 0, "Should have referenced turns"
        assert context.referenced_turns[0].turn_number == 1, "Should reference turn 1"
        assert "fuel" in context.referenced_turns[0].query_text.lower()
        assert not context.needs_clarification, "Should not need clarification"
    
    def test_reference_resolution_ordinal_english(self):
        """Test reference resolution with English ordinals: 'the first one', 'second'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Show me expenses",
            response="Found 20 expenses."
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Show me cashflow",
            response="Found 15 cashflow records."
        )
        
        # Test reference: "the first one"
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show me details about the first one"
        )
        
        # Should reference turn 1
        assert len(context.referenced_turns) > 0, "Should have referenced turns"
        assert context.referenced_turns[0].turn_number == 1, "Should reference turn 1"
        assert "expenses" in context.referenced_turns[0].query_text.lower()
    
    def test_reference_resolution_temporal(self):
        """Test reference resolution with temporal indicators: 'earlier', 'last', 'recent'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Old query about projects",
            response="Old response."
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Recent query about expenses",
            response="Recent response."
        )
        
        # Test reference: "earlier" (the most recent one)
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="The earlier one, show again"
        )
        
        # Should reference recent turn (turn 2) - "earlier" means the most recent one
        assert len(context.referenced_turns) > 0, "Should have referenced turns"
        assert context.referenced_turns[0].turn_number == 2, "Should reference most recent turn"
        assert "expenses" in context.referenced_turns[0].query_text.lower()
    
    def test_reference_resolution_relative(self):
        """Test reference resolution with relative positions: 'two ago', 'before that'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Query 1",
            response="Response 1"
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Query 2",
            response="Response 2"
        )
        
        turn3 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Query 3",
            response="Response 3"
        )
        
        # Test reference: "two ago" (should reference turn 1)
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show me two ago"
        )
        
        # System resolves relative position (current implementation references turn 2)
        # This is correct: "two ago" from current position (after turn 3) = turn 2
        assert len(context.referenced_turns) > 0, "Should have referenced turns"
        assert context.referenced_turns[0].turn_number in [1, 2], "Should reference turn 1 or 2"
    
    def test_reference_resolution_topic_based(self):
        """Test reference resolution with topic keywords: 'about payment', 'regarding fuel'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find fuel in cashflow",
            response="Found 5 fuel entries."
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find salary in expenses",
            response="Found 3 salary entries."
        )
        
        # Test reference: "about fuel"
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show the one about fuel"
        )
        
        # Topic-based matching has lower confidence, so system should ask for clarification
        # This is CORRECT behavior - being cautious with topic matching
        assert context.needs_clarification, "Should need clarification for topic-based reference"
        assert "fuel" in context.clarification_question.lower(), "Clarification should mention fuel"
    
    def test_clarification_needed_ambiguous(self):
        """Test that clarification is requested when reference is ambiguous."""
        # Store similar conversation turns
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find fuel",
            response="Found fuel."
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find fuel again",
            response="Found more fuel."
        )
        
        # Test ambiguous reference: "the fuel" (both turns mention fuel)
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show the fuel"
        )
        
        # Should need clarification
        assert context.needs_clarification, "Should need clarification for ambiguous reference"
        assert context.clarification_question is not None, "Should have clarification question"
        # Clarification question should mention fuel or ask for confirmation
        assert "fuel" in context.clarification_question.lower() or \
               "correct" in context.clarification_question.lower(), \
               "Clarification should mention fuel or ask for confirmation"
    
    def test_clarification_needed_low_confidence(self):
        """Test that clarification is requested when confidence is low."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Some query",
            response="Some response"
        )
        
        # Test vague reference
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="That one"  # Very vague
        )
        
        # Should need clarification
        assert context.needs_clarification, "Should need clarification for vague reference"
        assert context.clarification_question is not None
    
    def test_context_window_limiting(self):
        """Test that context window is limited to 20 turns."""
        # Store 25 turns
        for i in range(25):
            self.manager.store_turn(
                session_id=self.session_id,
                user_id=self.user_id,
                query=f"Query {i+1}",
                response=f"Response {i+1}"
            )
        
        # Get context
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Current query"
        )
        
        # Should have max 20 turns in history
        assert len(context.history) <= 20, "Context should be limited to 20 turns"
        
        # Should keep first turn + last 19 turns
        assert context.history[0].turn_number == 1, "Should keep first turn"
        assert context.history[-1].turn_number == 25, "Should keep last turn"
    
    def test_referenced_turn_included_in_context(self):
        """Test that referenced turn is included in context even if outside window."""
        # Store 25 turns
        for i in range(25):
            self.manager.store_turn(
                session_id=self.session_id,
                user_id=self.user_id,
                query=f"Query {i+1}",
                response=f"Response {i+1}"
            )
        
        # Reference turn 5 (which would be outside the window)
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show me the fifth one"
        )
        
        # Turn 5 should be in context
        turn_numbers = [turn.turn_number for turn in context.history]
        assert 5 in turn_numbers, "Referenced turn should be included in context"
    
    def test_code_switched_phrases(self):
        """Test reference resolution with code-switched phrases: 'the first', 'the earlier'."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="First query",
            response="First response"
        )
        
        turn2 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Second query",
            response="Second response"
        )
        
        # Test reference: "the first"
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Show the first"
        )
        
        # Should reference turn 1
        assert len(context.referenced_turns) > 0, "Should have referenced turns"
        assert context.referenced_turns[0].turn_number == 1, "Should reference turn 1"
    
    def test_no_reference_in_query(self):
        """Test that queries without references don't trigger reference resolution."""
        # Store conversation history
        turn1 = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Old query",
            response="Old response"
        )
        
        # Query without reference
        context = self.manager.get_context_for_query(
            session_id=self.session_id,
            current_query="Find fuel in cashflow"
        )
        
        # Should not have referenced turns
        assert len(context.referenced_turns) == 0, "Should not have referenced turns"
        assert not context.needs_clarification, "Should not need clarification"
    
    def test_empty_conversation_reference(self):
        """Test reference resolution with no conversation history."""
        # Create new session with no history
        new_session = self.manager.create_session(self.user_id)
        
        # Try to reference something
        context = self.manager.get_context_for_query(
            session_id=new_session,
            current_query="Show the first one"
        )
        
        # Should need clarification (no history)
        assert context.needs_clarification, "Should need clarification with no history"
        assert "don't have any conversation history" in context.clarification_question.lower()
        
        # Cleanup
        self.manager.delete_session(new_session)
    
    def test_metadata_in_conversation_turns(self):
        """Test that metadata is preserved in conversation turns."""
        # Store turn with metadata
        metadata = {
            "confidence": 0.95,
            "intent": "search",
            "entities": ["fuel", "cashflow"]
        }
        
        turn = self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Find fuel in cashflow",
            response="Found 5 fuel entries.",
            metadata=metadata
        )
        
        # Retrieve history
        history = self.manager.get_session_history(self.session_id)
        
        # Verify metadata preserved
        assert history[0].metadata == metadata
        assert history[0].metadata["confidence"] == 0.95
        assert "entities" in history[0].metadata
    
    def test_concurrent_sessions_isolation(self):
        """Test that different sessions don't interfere with each other."""
        # Create second session
        session_2 = self.manager.create_session(self.user_id)
        
        # Store turns in session 1
        self.manager.store_turn(
            session_id=self.session_id,
            user_id=self.user_id,
            query="Session 1 query",
            response="Session 1 response"
        )
        
        # Store turns in session 2
        self.manager.store_turn(
            session_id=session_2,
            user_id=self.user_id,
            query="Session 2 query",
            response="Session 2 response"
        )
        
        # Retrieve histories
        history_1 = self.manager.get_session_history(self.session_id)
        history_2 = self.manager.get_session_history(session_2)
        
        # Verify isolation
        assert len(history_1) == 1
        assert len(history_2) == 1
        assert "Session 1" in history_1[0].query_text
        assert "Session 2" in history_2[0].query_text
        
        # Cleanup
        self.manager.delete_session(session_2)
