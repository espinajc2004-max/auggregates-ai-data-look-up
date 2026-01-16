# Design Document: Database-Based Long-Term Conversation Memory

## Overview

This feature implements a database-backed conversation memory system that enables multi-turn conversations with context retention. The system stores conversation history in Supabase PostgreSQL, allowing users to reference previous queries naturally while maintaining fast performance through automatic 24-hour cleanup of old conversations.

The design prioritizes zero-cost operation by leveraging existing Supabase infrastructure, ensures production-readiness through proper error handling and performance optimization, and maintains simplicity by storing only the last 10 turns per user with automatic cleanup of conversations older than 24 hours.

## Architecture

### System Components

```
┌─────────────────┐
│   Chat API      │
│   (main.py)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Conversation Store     │
│  (conversation_store.py)│
│  - store_turn()         │
│  - get_history()        │
│  - resolve_reference()  │
│  - cleanup_old_turns()  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Supabase Database     │
│   (conversations table) │
│   - user_id             │
│   - turn_number         │
│   - user_query          │
│   - ai_response         │
│   - created_at          │
└─────────────────────────┘
```

### Data Flow

1. **Incoming Query Flow**:
   - User sends query → Chat API receives request
   - Chat API calls `get_history(user_id)` → Retrieves last 10 turns (within 24 hours)
   - Chat API includes history in AI prompt → AI generates response with context
   - Chat API calls `store_turn(user_id, query, response)` → Persists new turn

2. **Turn Reference Flow**:
   - User query contains reference ("yung una") → Chat API detects reference
   - Chat API calls `resolve_reference(user_id, reference)` → Returns specific turn
   - Chat API includes referenced turn in context → AI understands what user means

3. **Auto-Cleanup Flow**:
   - `get_history()` called → Triggers `cleanup_old_turns(user_id)` first
   - Cleanup deletes turns older than 24 hours → Database stays lean
   - Returns only recent, relevant turns → Fast query performance

## Components and Interfaces

### 1. Conversation Store Service

**File**: `app/services/conversation_store.py`

**Purpose**: Manages all conversation history operations with the database.

**Interface**:

```python
class ConversationStore:
    def __init__(self, supabase_client):
        """Initialize with existing Supabase client"""
        
    def store_turn(self, user_id: str, user_query: str, ai_response: str) -> bool:
        """
        Store a conversation turn in the database.
        
        Args:
            user_id: Unique identifier for the user
            user_query: The user's query text
            ai_response: The AI's response text
            
        Returns:
            True if successful, False otherwise
            
        Behavior:
            - Gets current turn count for user
            - If count >= 10, deletes oldest turn
            - Inserts new turn with incremented turn_number
            - Handles errors gracefully
        """
        
    def get_history(self, user_id: str, max_turns: int = 10) -> List[Dict]:
        """
        Retrieve conversation history for a user.
        
        Args:
            user_id: Unique identifier for the user
            max_turns: Maximum number of turns to retrieve (default 10)
            
        Returns:
            List of conversation turns in chronological order
            Each turn: {
                "turn_number": int,
                "user_query": str,
                "ai_response": str,
                "created_at": datetime
            }
            
        Behavior:
            - First calls cleanup_old_turns() to remove stale data
            - Queries database for user's turns within 24 hours
            - Orders by turn_number ascending
            - Returns empty list if no history or on error
        """
        
    def resolve_reference(self, user_id: str, reference: str) -> Optional[Dict]:
        """
        Resolve a turn reference to a specific conversation turn.
        
        Args:
            user_id: Unique identifier for the user
            reference: Reference phrase ("yung una", "the first one", etc.)
            
        Returns:
            The referenced turn dict or None if not found
            
        Behavior:
            - Maps reference phrases to turn numbers
            - Retrieves specific turn from history
            - Returns None if reference invalid or turn not found
        """
        
    def cleanup_old_turns(self, user_id: str) -> int:
        """
        Delete conversation turns older than 24 hours.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Number of turns deleted
            
        Behavior:
            - Calculates 24-hour threshold timestamp
            - Deletes all turns older than threshold
            - Logs deletion count
        """
        
    def format_history_for_prompt(self, history: List[Dict]) -> str:
        """
        Format conversation history for inclusion in AI prompt.
        
        Args:
            history: List of conversation turns
            
        Returns:
            Formatted string suitable for AI context
            
        Format:
            "Previous conversation:
             Turn 1:
             User: [query]
             AI: [response]
             
             Turn 2:
             User: [query]
             AI: [response]"
        """
```

### 2. Database Schema

**Migration File**: `supabase/migrations/YYYYMMDD_conversation_memory.sql`

**Table**: `conversations`

```sql
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    user_query TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Composite unique constraint: one turn number per user
    UNIQUE(user_id, turn_number)
);

-- Index for fast user history retrieval
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- Index for efficient time-based cleanup
CREATE INDEX idx_conversations_created_at ON conversations(created_at);

-- Composite index for user + time queries (most common operation)
CREATE INDEX idx_conversations_user_time ON conversations(user_id, created_at DESC);
```

### 3. Chat API Integration

**File**: `app/api/routes/chat.py`

**Integration Points**:

```python
from app.services.conversation_store import ConversationStore

# Initialize conversation store
conversation_store = ConversationStore(supabase_client)

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_id = request.user_id
    query = request.query
    
    # 1. Retrieve conversation history
    history = conversation_store.get_history(user_id)
    
    # 2. Check for turn references
    if contains_reference(query):
        referenced_turn = conversation_store.resolve_reference(user_id, query)
        if referenced_turn:
            # Add referenced turn to context
            context = f"User is referring to: {referenced_turn['user_query']}"
    
    # 3. Format history for AI prompt
    history_context = conversation_store.format_history_for_prompt(history)
    
    # 4. Generate AI response with context
    ai_response = await generate_response(query, history_context)
    
    # 5. Store the new turn
    conversation_store.store_turn(user_id, query, ai_response)
    
    return {"response": ai_response}
```

## Data Models

### Conversation Turn

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConversationTurn:
    """Represents a single conversation turn"""
    user_id: str
    turn_number: int
    user_query: str
    ai_response: str
    created_at: datetime
    
    def is_expired(self, hours: int = 24) -> bool:
        """Check if turn is older than specified hours"""
        age = datetime.now(timezone.utc) - self.created_at
        return age.total_seconds() > (hours * 3600)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "turn_number": self.turn_number,
            "user_query": self.user_query,
            "ai_response": self.ai_response,
            "created_at": self.created_at.isoformat()
        }
```

### Turn Reference Mapping

```python
TURN_REFERENCES = {
    # Filipino references
    "yung una": 1,
    "una": 1,
    "yung pangalawa": 2,
    "pangalawa": 2,
    "yung pangatlo": 3,
    "pangatlo": 3,
    "yung pang-apat": 4,
    "yung kanina": -1,  # Most recent
    "kanina": -1,
    
    # English references
    "the first one": 1,
    "first": 1,
    "the second one": 2,
    "second": 2,
    "the third one": 3,
    "third": 3,
    "earlier": -1,
    "previous": -1,
    "last one": -1
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

