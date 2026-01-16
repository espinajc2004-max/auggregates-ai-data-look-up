"""
Data models for conversation memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID


@dataclass
class Turn:
    """Represents a single conversation turn (user query + AI response)."""
    id: str
    session_id: str
    user_id: str
    turn_number: int
    query_text: str
    response_text: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "turn_number": self.turn_number,
            "query_text": self.query_text,
            "response_text": self.response_text,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turn":
        """Create Turn from dictionary."""
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            user_id=data["user_id"],
            turn_number=data["turn_number"],
            query_text=data["query_text"],
            response_text=data["response_text"],
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationContext:
    """Full context for processing a query with conversation history."""
    session_id: str
    current_query: str
    history: List[Turn]
    referenced_turns: List[Turn] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "current_query": self.current_query,
            "history": [turn.to_dict() for turn in self.history],
            "referenced_turns": [turn.to_dict() for turn in self.referenced_turns],
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question
        }


@dataclass
class ReferenceIntent:
    """Detected intent for a context reference in a query."""
    query: str
    intent_type: str  # "ordinal", "temporal", "topic", "relative"
    indicators: List[str]  # Extracted semantic indicators
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "intent_type": self.intent_type,
            "indicators": self.indicators,
            "confidence": self.confidence
        }


@dataclass
class ReferenceResolution:
    """Result of resolving a reference to specific turn(s)."""
    matched_turns: List[tuple[Turn, float]]  # (turn, confidence_score)
    best_match: Optional[Turn]
    is_ambiguous: bool  # True if multiple high-confidence matches
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "matched_turns": [(turn.to_dict(), score) for turn, score in self.matched_turns],
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "is_ambiguous": self.is_ambiguous,
            "confidence": self.confidence
        }


@dataclass
class SemanticFeatures:
    """Semantic features extracted from a query for reference resolution."""
    temporal_indicators: List[str] = field(default_factory=list)  # ["first", "earlier", "recent"]
    ordinal_positions: List[int] = field(default_factory=list)  # [1, 2] for "first", "second"
    topic_keywords: List[str] = field(default_factory=list)
    relative_positions: List[int] = field(default_factory=list)  # [-1] for "previous", [-2] for "two ago"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "temporal_indicators": self.temporal_indicators,
            "ordinal_positions": self.ordinal_positions,
            "topic_keywords": self.topic_keywords,
            "relative_positions": self.relative_positions
        }


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    sessions_deleted: int
    turns_deleted: int
    execution_time: float
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sessions_deleted": self.sessions_deleted,
            "turns_deleted": self.turns_deleted,
            "execution_time": self.execution_time,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CleanupStats:
    """Statistics about cleanup operations."""
    total_cleanups: int
    total_sessions_deleted: int
    total_turns_deleted: int
    average_execution_time: float
    last_cleanup: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_cleanups": self.total_cleanups,
            "total_sessions_deleted": self.total_sessions_deleted,
            "total_turns_deleted": self.total_turns_deleted,
            "average_execution_time": self.average_execution_time,
            "last_cleanup": self.last_cleanup.isoformat()
        }
