"""
Unit tests for Dynamic Reference Parser.
Tests specific reference phrases and edge cases.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.reference_parser import get_reference_parser
from app.models.conversation import Turn


class TestReferenceParserSpecificPhrases:
    """Unit tests for specific reference phrases."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test parser."""
        self.parser = get_reference_parser()
        self.sample_history = self._create_sample_history()
        yield
    
    def _create_sample_history(self) -> list[Turn]:
        """Create sample conversation history for testing."""
        session_id = str(uuid4())
        user_id = str(uuid4())
        
        turns = [
            Turn(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                turn_number=1,
                query_text="What is the capital of France?",
                response_text="The capital of France is Paris.",
                created_at=datetime.now(),
                metadata={}
            ),
            Turn(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                turn_number=2,
                query_text="What about Germany?",
                response_text="The capital of Germany is Berlin.",
                created_at=datetime.now(),
                metadata={}
            ),
            Turn(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                turn_number=3,
                query_text="Tell me about payment methods",
                response_text="We accept credit cards, debit cards, and PayPal.",
                created_at=datetime.now(),
                metadata={}
            ),
        ]
        
        return turns
    
    # English Ordinal Tests
    def test_english_ordinal_first(self):
        """Test 'the first one'."""
        intent = self.parser.detect_reference("Tell me about the first one")
        assert intent is not None
        assert intent.intent_type == "ordinal"
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        assert resolution.best_match.turn_number == 1
    
    def test_english_ordinal_second(self):
        """Test 'the second'."""
        intent = self.parser.detect_reference("What about the second?")
        assert intent is not None
        assert intent.intent_type == "ordinal"
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        assert resolution.best_match.turn_number == 2
    
    def test_english_ordinal_last(self):
        """Test 'the last one'."""
        intent = self.parser.detect_reference("Explain the last one")
        assert intent is not None
        assert intent.intent_type == "temporal"
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        # Should match last turn
        assert resolution.best_match.turn_number == 3
    
    # English Temporal Tests
    def test_english_temporal_earlier(self):
        """Test 'the earlier one'."""
        intent = self.parser.detect_reference("What was the earlier one?")
        assert intent is not None
        assert intent.intent_type == "temporal"
    
    def test_english_temporal_previous(self):
        """Test 'the previous'."""
        intent = self.parser.detect_reference("Go back to the previous")
        assert intent is not None
        assert intent.intent_type == "temporal"
    
    # Relative Position Tests
    def test_relative_two_ago(self):
        """Test 'two queries ago'."""
        intent = self.parser.detect_reference("What did I ask two ago?")
        assert intent is not None
        assert intent.intent_type == "relative"
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        # Two ago from end (turn 3) = turn 1
        assert resolution.best_match.turn_number == 1
    
    def test_relative_before_that(self):
        """Test 'the one before that'."""
        intent = self.parser.detect_reference("Tell me about the one before that")
        assert intent is not None
        assert intent.intent_type == "relative"
    
    # Topic-Based Tests
    def test_topic_based_payment(self):
        """Test topic-based reference 'about payment'."""
        intent = self.parser.detect_reference("Tell me more about payment")
        assert intent is not None
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        # Should match turn 3 (payment methods)
        assert resolution.best_match.turn_number == 3
    
    def test_topic_based_france(self):
        """Test topic-based reference 'about France'."""
        intent = self.parser.detect_reference("More details about France")
        assert intent is not None
        
        resolution = self.parser.resolve_reference(intent, self.sample_history)
        # Should match turn 1 (France capital)
        assert resolution.best_match.turn_number == 1
    
    # Edge Cases
    def test_no_reference_detected(self):
        """Test query with no reference."""
        intent = self.parser.detect_reference("What is the weather today?")
        # Should return None or very low confidence
        assert intent is None or intent.confidence < 0.5
    
    def test_empty_history(self):
        """Test reference resolution with empty history."""
        intent = self.parser.detect_reference("Tell me about the first one")
        resolution = self.parser.resolve_reference(intent, [])
        
        assert resolution.best_match is None
        assert resolution.confidence == 0.0
    
    def test_ambiguous_reference(self):
        """Test ambiguous reference detection."""
        # Create history with similar topics
        similar_history = [
            Turn(
                id=str(uuid4()),
                session_id=str(uuid4()),
                user_id=str(uuid4()),
                turn_number=1,
                query_text="Tell me about payment options",
                response_text="We have credit cards and PayPal",
                created_at=datetime.now(),
                metadata={}
            ),
            Turn(
                id=str(uuid4()),
                session_id=str(uuid4()),
                user_id=str(uuid4()),
                turn_number=2,
                query_text="What payment methods do you accept?",
                response_text="We accept all major payment methods",
                created_at=datetime.now(),
                metadata={}
            ),
        ]
        
        intent = self.parser.detect_reference("Tell me more about payment")
        resolution = self.parser.resolve_reference(intent, similar_history)
        
        # Should detect ambiguity
        assert len(resolution.matched_turns) >= 2
