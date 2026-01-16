# Design Document: Database-Based Long-Term Conversation Memory

## Overview

The Database-Based Long-Term Conversation Memory system provides persistent, intelligent conversation history management using Supabase PostgreSQL storage. The system enables natural multi-turn conversations (10+ turns) with dynamic context understanding, automatic cleanup, and zero additional cost.

**Core Design Principles:**
- **Zero Hardcoding**: All context reference understanding uses semantic analysis, not pattern matching
- **Free Tier Optimization**: Designed to stay within Supabase free tier limits (500MB storage, 2GB bandwidth)
- **Semantic Intelligence**: NLP-based understanding of ANY phrasing for context references
- **Production Ready**: Comprehensive error handling, logging, and graceful degradation
- **Scalable**: Stateless design supporting 1000+ concurrent sessions

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Chat API Layer                          │
│  (Receives user queries, returns responses)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Conversation Memory Manager                      │
│  - Session management                                       │
│  - Turn storage/retrieval                                   │
│  - Context assembly                                         │
└─────┬──────────────────────────────┬────────────────────────┘
      │                              │
      ▼                              ▼
┌──────────────────────┐   ┌─────────────────────────────────┐
│ Dynamic Reference    │   │  Clarification Engine           │
│ Parser               │   │  - Ambiguity detection          │
│ - Semantic analysis  │   │  - Question generation          │
│ - Intent extraction  │   │  - Confidence scoring           │
│ - Turn matching      │   └─────────────────────────────────┘
└──────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│              Supabase Storage Layer                         │
│  - conversation_turns table                                 │
│  - Indexed queries (session_id, created_at)                 │
│  - Connection pooling                                       │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│           Auto-Cleanup Service (Background)                 │
│  - Hourly execution                                         │
│  - Deletes conversations > 24 hours                         │
│  - Logging and monitoring                                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

**1. New Query Flow:**
```
User Query → Memory Manager → Check for context references
                            ↓
                    Dynamic Reference Parser
                            ↓
                    (If ambiguous) → Clarification Engine
                            ↓
                    Assemble full context
                            ↓
                    Process query with context
                            ↓
                    Store turn in Supabase
                            ↓
                    Return response
```

**2. Context Reference Flow:**
```
User says "yung una" → Dynamic Reference Parser
                            ↓
                    Extract semantic intent: "first"
                            ↓
                    Query conversation history
                            ↓
                    Find turn_number = 1
                            ↓
                    Return referenced content
```

**3. Auto-Cleanup Flow:**
```
Hourly Trigger → Auto-Cleanup Service
                            ↓
                    Query: created_at < NOW() - INTERVAL '24 hours'
                            ↓
                    Delete matching sessions
                            ↓
                    Log deletion count
```

## Components and Interfaces

### 1. Conversation Memory Manager

**Responsibilities:**
- Store and retrieve conversation turns
- Manage session lifecycle
- Assemble context for query processing
- Coordinate with Dynamic Reference Parser and Clarification Engine

**Interface:**
```python
class ConversationMemoryManager:
    def store_turn(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str
    ) -> Turn:
        """Store a conversation turn in Supabase."""
        pass
    
    def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Turn]:
        """Retrieve conversation history for a session."""
        pass
    
    def create_session(self, user_id: str) -> str:
        """Create a new conversation session."""
        pass
    
    def get_context_for_query(
        self,
        session_id: str,
        current_query: str
    ) -> ConversationContext:
        """
        Assemble full context including:
        - Previous turns
        - Referenced turns (if any)
        - Clarification state
        """
        pass
    
    def delete_session(self, session_id: str) -> int:
        """Delete a session and all its turns."""
        pass
```

**Data Models:**
```python
@dataclass
class Turn:
    id: str
    session_id: str
    user_id: str
    turn_number: int
    query_text: str
    response_text: str
    created_at: datetime
    metadata: Dict[str, Any]  # For extensibility

@dataclass
class ConversationContext:
    session_id: str
    current_query: str
    history: List[Turn]
    referenced_turns: List[Turn]  # Turns explicitly referenced
    needs_clarification: bool
    clarification_question: Optional[str]
```

### 2. Dynamic Reference Parser

**Responsibilities:**
- Detect context references in user queries
- Extract semantic intent without pattern matching
- Match references to specific turns
- Calculate confidence scores

**Interface:**
```python
class DynamicReferenceParser:
    def __init__(self, nlp_model):
        """Initialize with spaCy or similar NLP model."""
        self.nlp = nlp_model
    
    def detect_reference(self, query: str) -> Optional[ReferenceIntent]:
        """
        Detect if query contains a context reference.
        Returns None if no reference detected.
        """
        pass
    
    def resolve_reference(
        self,
        intent: ReferenceIntent,
        history: List[Turn]
    ) -> ReferenceResolution:
        """
        Match reference intent to specific turn(s).
        Returns confidence scores for matches.
        """
        pass
    
    def extract_semantic_features(self, query: str) -> SemanticFeatures:
        """
        Extract features like:
        - Temporal indicators (first, last, earlier, recent)
        - Ordinal positions (1st, 2nd, previous)
        - Topic keywords
        - Relative positions (before that, two ago)
        """
        pass
```

**Data Models:**
```python
@dataclass
class ReferenceIntent:
    query: str
    intent_type: str  # "ordinal", "temporal", "topic", "relative"
    indicators: List[str]  # Extracted semantic indicators
    confidence: float

@dataclass
class ReferenceResolution:
    matched_turns: List[Tuple[Turn, float]]  # (turn, confidence_score)
    best_match: Optional[Turn]
    is_ambiguous: bool  # True if multiple high-confidence matches
    confidence: float

@dataclass
class SemanticFeatures:
    temporal_indicators: List[str]  # ["first", "earlier", "recent"]
    ordinal_positions: List[int]  # [1, 2] for "first", "second"
    topic_keywords: List[str]
    relative_positions: List[int]  # [-1] for "previous", [-2] for "two ago"
```

**Semantic Analysis Strategy:**

The parser uses multi-layered semantic analysis:

1. **Temporal Analysis**: Detect time-related references
   - "kanina" (earlier), "nauna" (before), "last", "recent"
   - Map to recent turns (last 3-5 turns)

2. **Ordinal Analysis**: Detect position-based references
   - "una" (first), "pangalawa" (second), "pinakauna" (very first)
   - Map to turn_number directly

3. **Topic Similarity**: Detect content-based references
   - "yung tungkol sa X" (the one about X)
   - Use TF-IDF or semantic similarity to match topics

4. **Relative Position**: Detect relative references
   - "yung before that", "two queries ago"
   - Calculate relative to current turn

5. **Language Detection**: Support code-switching
   - Detect Tagalog, English, or mixed phrases
   - Use language-agnostic semantic features

### 3. Clarification Engine

**Responsibilities:**
- Detect ambiguous or unclear queries
- Generate specific clarification questions
- Track clarification state
- Resolve queries after clarification

**Interface:**
```python
class ClarificationEngine:
    def needs_clarification(
        self,
        query: str,
        resolution: ReferenceResolution
    ) -> bool:
        """
        Determine if clarification is needed based on:
        - Low confidence scores (< 0.7)
        - Multiple high-confidence matches
        - Missing context
        """
        pass
    
    def generate_clarification_question(
        self,
        query: str,
        resolution: ReferenceResolution,
        history: List[Turn]
    ) -> str:
        """
        Generate a specific question referencing possible matches.
        Example: "Did you mean your first question about 'X' or 
                  your second question about 'Y'?"
        """
        pass
    
    def resolve_with_clarification(
        self,
        original_query: str,
        clarification_response: str,
        resolution: ReferenceResolution
    ) -> Turn:
        """
        Use clarification response to select the correct turn.
        """
        pass
```

**Clarification Strategy:**

1. **Confidence Threshold**: If best match confidence < 0.7, ask for clarification
2. **Multiple Matches**: If 2+ matches with confidence > 0.6, present options
3. **Context-Aware Questions**: Reference specific turn content in questions
4. **Progressive Clarification**: Start broad, narrow down based on responses

### 4. Auto-Cleanup Service

**Responsibilities:**
- Run hourly background job
- Delete conversations older than 24 hours
- Log cleanup operations
- Handle errors gracefully

**Interface:**
```python
class AutoCleanupService:
    def __init__(self, supabase_client, logger):
        self.supabase = supabase_client
        self.logger = logger
    
    def run_cleanup(self) -> CleanupResult:
        """
        Execute cleanup:
        1. Find sessions with created_at < NOW() - 24 hours
        2. Delete all turns for those sessions
        3. Log results
        """
        pass
    
    def schedule_hourly(self):
        """Set up hourly execution using APScheduler or similar."""
        pass
    
    def get_cleanup_stats(self) -> CleanupStats:
        """Return statistics about cleanup operations."""
        pass
```

**Data Models:**
```python
@dataclass
class CleanupResult:
    sessions_deleted: int
    turns_deleted: int
    execution_time: float
    errors: List[str]
    timestamp: datetime

@dataclass
class CleanupStats:
    total_cleanups: int
    total_sessions_deleted: int
    total_turns_deleted: int
    average_execution_time: float
    last_cleanup: datetime
```

**Implementation Strategy:**
- Use APScheduler for scheduling
- Query: `DELETE FROM conversation_turns WHERE created_at < NOW() - INTERVAL '24 hours'`
- Batch delete in chunks of 1000 to avoid long locks
- Retry on failure with exponential backoff

## Data Models

### Database Schema

**conversation_turns table:**
```sql
CREATE TABLE conversation_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id UUID NOT NULL,
    turn_number INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT unique_session_turn UNIQUE (session_id, turn_number),
    
    -- Indexes for performance
    INDEX idx_session_id ON conversation_turns(session_id),
    INDEX idx_created_at ON conversation_turns(created_at),
    INDEX idx_user_sessions ON conversation_turns(user_id, session_id)
);

-- Index for cleanup queries
CREATE INDEX idx_cleanup ON conversation_turns(created_at) 
WHERE created_at < NOW() - INTERVAL '24 hours';
```

**Storage Estimates:**
- Average turn size: ~500 bytes (query + response)
- 10 turns per session: ~5KB
- 24-hour retention: Assuming 100 active users, 10 sessions each = 1000 sessions = 5MB
- Well within Supabase free tier (500MB)

### Context Window Management

For sessions with many turns, implement sliding window:

```python
def get_relevant_context(
    history: List[Turn],
    max_turns: int = 20
) -> List[Turn]:
    """
    Return most relevant turns:
    - Always include first turn (context setting)
    - Include last N-1 turns (recent context)
    - If referenced turn is outside window, include it
    """
    if len(history) <= max_turns:
        return history
    
    # Keep first turn + last (max_turns - 1) turns
    return [history[0]] + history[-(max_turns - 1):]
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Turn Storage Completeness
*For any* user query and response, when stored in the database, the resulting turn record must contain all required fields (user_id, session_id, turn_number, query_text, response_text, created_at) with non-null values.

**Validates: Requirements 1.1, 1.4**

### Property 2: Persistence Across Restarts
*For any* set of stored conversations, after simulating a server restart (database reconnection), all conversation data must be retrievable with identical content.

**Validates: Requirements 1.2**

### Property 3: Long Conversation Performance
*For any* conversation with 10 to 50 turns, retrieving the full history must complete within a reasonable time threshold (< 500ms) without data loss.

**Validates: Requirements 1.3**

### Property 4: 24-Hour Cleanup Deletion
*For any* conversation with created_at timestamp older than 24 hours, running the cleanup service must result in all turns for that session being deleted from the database.

**Validates: Requirements 2.1**

### Property 5: Recent Conversation Retention
*For any* conversation with created_at timestamp less than 24 hours old, running the cleanup service must NOT delete any turns from that session.

**Validates: Requirements 2.2**

### Property 6: Cleanup Logging
*For any* cleanup operation, the service must log the number of sessions deleted and turns deleted, and these logged values must match the actual deletions performed.

**Validates: Requirements 2.4**

### Property 7: Cleanup Error Resilience
*For any* simulated database failure during cleanup, the service must retry the operation and log errors, while all active (non-expired) conversations remain intact and accessible.

**Validates: Requirements 2.5**

### Property 8: Dynamic Reference Identification
*For any* reference phrase (including ordinal references like "yung una", temporal references like "kanina", relative references like "two ago", and topic-based references) in any supported language (English, Tagalog, code-switched), the Dynamic Reference Parser must correctly identify the referenced turn from the conversation history.

**Validates: Requirements 3.1, 3.5, 8.1, 8.3**

### Property 9: Contextual Disambiguation
*For any* ambiguous reference where multiple turns could match, the Dynamic Reference Parser must select the most contextually relevant turn based on semantic similarity and positional analysis.

**Validates: Requirements 3.4**

### Property 10: Clarification Triggering
*For any* query with ambiguous context references or insufficient context (confidence < 70%), the Clarification Engine must generate a clarification question that references specific conversation turns.

**Validates: Requirements 4.1, 4.2, 4.4, 8.5**

### Property 11: Clarification Resolution
*For any* clarification interaction, after the user provides clarification, the system must continue processing the original query using the correctly identified context from the clarified turn.

**Validates: Requirements 4.5**

### Property 12: Session Isolation
*For any* session_id, retrieving conversation history must return only turns belonging to that session, with no turns from other sessions included.

**Validates: Requirements 5.1**

### Property 13: Context Window Limiting
*For any* session with more than 20 turns, retrieving context must return at most 20 turns (using a sliding window strategy), preventing unbounded context growth.

**Validates: Requirements 5.2**

### Property 14: Chronological Ordering
*For any* retrieved conversation history, the turns must be ordered in ascending order by turn_number, maintaining chronological sequence.

**Validates: Requirements 5.5**

### Property 15: Session ID Uniqueness
*For any* set of newly created sessions, all generated session_ids must be unique with no duplicates.

**Validates: Requirements 6.1**

### Property 16: Session Continuity
*For any* session, all turns added to that session must share the same session_id, maintaining conversation continuity.

**Validates: Requirements 6.2**

### Property 17: Turn-Session Association
*For any* stored turn, it must be associated with exactly one non-null session_id, ensuring proper data integrity.

**Validates: Requirements 6.3**

### Property 18: Cascading Session Deletion
*For any* session, when deleted, all associated turns must be removed from the database, leaving no orphaned turn records.

**Validates: Requirements 6.4**

### Property 19: Multi-Session Support
*For any* user, creating and maintaining multiple concurrent sessions must result in all sessions being independently accessible and isolated from each other.

**Validates: Requirements 6.5**

### Property 20: Confidence Scoring
*For any* ambiguous reference, the Dynamic Reference Parser must calculate confidence scores for all possible matches, with scores between 0.0 and 1.0, and the sum of top matches reflecting the degree of ambiguity.

**Validates: Requirements 8.4**

### Property 21: Error Logging and Graceful Degradation
*For any* database operation failure, the system must log the error with relevant context and return a user-friendly error message without exposing internal details or crashing.

**Validates: Requirements 9.1**

### Property 22: Retry with Exponential Backoff
*For any* temporary database unavailability, the system must retry the operation with exponentially increasing delays (e.g., 1s, 2s, 4s) up to a maximum number of attempts.

**Validates: Requirements 9.2**

### Property 23: Input Validation
*For any* input data (query, session_id, user_id), the system must validate the data before storage, rejecting invalid inputs (null, empty, malformed) with appropriate error messages.

**Validates: Requirements 9.3**

### Property 24: Corruption Handling
*For any* conversation history containing corrupted turn data, the system must skip corrupted records and return all valid turns, allowing continued operation despite partial data corruption.

**Validates: Requirements 9.4**

## Error Handling

### Error Categories and Strategies

**1. Database Connection Errors**
- **Detection**: Connection timeout, connection refused, network errors
- **Strategy**: Retry with exponential backoff (1s, 2s, 4s, 8s, max 5 attempts)
- **Fallback**: Return error to user with "Service temporarily unavailable" message
- **Logging**: Log connection errors with timestamp and retry count

**2. Data Validation Errors**
- **Detection**: Null values, empty strings, malformed UUIDs, invalid timestamps
- **Strategy**: Reject immediately with specific validation error
- **Fallback**: Return 400 Bad Request with field-specific error messages
- **Logging**: Log validation failures with input data (sanitized)

**3. Query Execution Errors**
- **Detection**: SQL syntax errors, constraint violations, deadlocks
- **Strategy**: Log error, rollback transaction if applicable
- **Fallback**: Return generic error message to user
- **Logging**: Log full error with SQL query (parameterized) and stack trace

**4. Reference Resolution Errors**
- **Detection**: No matching turns, ambiguous references, low confidence
- **Strategy**: Trigger clarification flow
- **Fallback**: If clarification fails, process query without context
- **Logging**: Log reference resolution attempts and confidence scores

**5. Cleanup Service Errors**
- **Detection**: Deletion failures, transaction errors
- **Strategy**: Retry cleanup on next scheduled run
- **Fallback**: Continue with partial cleanup, log failures
- **Logging**: Log cleanup errors with affected session_ids

### Error Response Format

```python
@dataclass
class ErrorResponse:
    error_code: str  # "DB_CONNECTION_ERROR", "VALIDATION_ERROR", etc.
    message: str  # User-friendly message
    details: Optional[Dict[str, Any]]  # Additional context (dev mode only)
    timestamp: datetime
    request_id: str  # For tracing
```

### Graceful Degradation Strategy

**Priority Levels:**
1. **Critical**: Store new turns (core functionality)
2. **High**: Retrieve recent history (last 5 turns)
3. **Medium**: Reference resolution
4. **Low**: Full history retrieval, clarification

**Degradation Flow:**
- If database is slow (> 1s response): Reduce context window to last 5 turns
- If reference resolution fails: Process query without context, notify user
- If storage fails: Return response but warn user about persistence failure

## Testing Strategy

### Dual Testing Approach

This feature requires both **unit tests** and **property-based tests** for comprehensive coverage:

**Unit Tests** focus on:
- Specific examples of reference phrases ("yung una", "kanina", "the first one")
- Edge cases (empty history, single turn, exactly 24 hours old)
- Error conditions (database unavailable, corrupted data, invalid input)
- Integration points (API endpoints, database connections)
- Clarification flow examples

**Property-Based Tests** focus on:
- Universal properties across all inputs (any query, any reference phrase, any session)
- Comprehensive input coverage through randomization
- Invariants that must hold (session isolation, chronological ordering, data completeness)
- Stress testing (long conversations, many concurrent sessions)

### Property-Based Testing Configuration

**Framework**: Use `hypothesis` (Python) for property-based testing

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number
- Tag format: `# Feature: database-long-term-memory, Property {N}: {property_text}`

**Example Property Test Structure**:
```python
from hypothesis import given, strategies as st
import pytest

@given(
    query=st.text(min_size=1, max_size=500),
    response=st.text(min_size=1, max_size=2000),
    user_id=st.uuids(),
    session_id=st.uuids()
)
@pytest.mark.property_test
def test_turn_storage_completeness(query, response, user_id, session_id):
    """
    Feature: database-long-term-memory, Property 1: Turn Storage Completeness
    
    For any user query and response, when stored in the database,
    the resulting turn record must contain all required fields with non-null values.
    """
    # Store turn
    turn = memory_manager.store_turn(
        session_id=str(session_id),
        user_id=str(user_id),
        query=query,
        response=response
    )
    
    # Verify all required fields are present and non-null
    assert turn.id is not None
    assert turn.session_id == str(session_id)
    assert turn.user_id == str(user_id)
    assert turn.turn_number > 0
    assert turn.query_text == query
    assert turn.response_text == response
    assert turn.created_at is not None
```

### Test Data Generators

**For Reference Phrases**:
```python
# Generate diverse reference phrases
reference_phrases = st.sampled_from([
    # Tagalog ordinal
    "yung una", "yung pangalawa", "yung pangatlo", "yung pinakauna",
    # Tagalog temporal
    "yung kanina", "yung nauna", "yung dati",
    # English ordinal
    "the first one", "the second", "the last one",
    # English temporal
    "the earlier one", "the recent one", "the previous",
    # Relative
    "the one before that", "two queries ago", "three back",
    # Topic-based
    "yung tungkol sa payment", "the one about users",
    # Code-switched
    "yung first", "the nauna", "yung last query"
])
```

**For Conversation History**:
```python
# Generate realistic conversation histories
@st.composite
def conversation_history(draw):
    num_turns = draw(st.integers(min_value=1, max_value=50))
    turns = []
    session_id = draw(st.uuids())
    
    for i in range(num_turns):
        turn = Turn(
            id=str(draw(st.uuids())),
            session_id=str(session_id),
            user_id=str(draw(st.uuids())),
            turn_number=i + 1,
            query_text=draw(st.text(min_size=10, max_size=200)),
            response_text=draw(st.text(min_size=20, max_size=500)),
            created_at=datetime.now() - timedelta(hours=draw(st.integers(0, 23))),
            metadata={}
        )
        turns.append(turn)
    
    return turns
```

### Unit Test Coverage

**Critical Unit Tests**:
1. **Reference phrase examples**: Test specific phrases like "yung una", "kanina", "the first"
2. **Edge cases**:
   - Empty conversation history
   - Single turn conversation
   - Exactly 24 hours old (boundary condition)
   - Reference to non-existent turn
3. **Error scenarios**:
   - Database connection failure
   - Invalid UUID format
   - Null query text
   - Corrupted turn data
4. **Clarification flow**:
   - Ambiguous reference triggers clarification
   - Clarification response resolves correctly
   - Multiple clarification rounds
5. **Cleanup service**:
   - Deletes old conversations
   - Preserves recent conversations
   - Handles partial failures

### Integration Tests

**API Integration**:
```python
def test_full_conversation_flow():
    """Test complete conversation with context references."""
    # Create session
    session_id = client.post("/chat/session").json()["session_id"]
    
    # Turn 1
    response1 = client.post("/chat", json={
        "session_id": session_id,
        "query": "What is the capital of France?"
    })
    assert "Paris" in response1.json()["response"]
    
    # Turn 2
    response2 = client.post("/chat", json={
        "session_id": session_id,
        "query": "What about Germany?"
    })
    assert "Berlin" in response2.json()["response"]
    
    # Turn 3 with reference
    response3 = client.post("/chat", json={
        "session_id": session_id,
        "query": "Tell me more about yung una"  # Reference to Turn 1
    })
    assert "France" in response3.json()["response"] or "Paris" in response3.json()["response"]
```

### Performance Tests

**Load Testing**:
- Test 1000 concurrent sessions
- Test sessions with 50+ turns
- Measure cleanup service execution time
- Verify sub-second response times

**Stress Testing**:
- Test database connection pool under load
- Test with 10,000+ stored turns
- Verify memory usage remains stable
- Test cleanup with large datasets

### Test Execution Strategy

1. **Unit tests**: Run on every commit (fast, < 1 minute)
2. **Property tests**: Run on every commit (moderate, 2-5 minutes with 100 iterations)
3. **Integration tests**: Run on PR merge (moderate, 5-10 minutes)
4. **Performance tests**: Run nightly or weekly (slow, 30+ minutes)

### Continuous Monitoring

**Metrics to Track**:
- Average turn storage time
- Average history retrieval time
- Reference resolution accuracy (manual validation)
- Clarification trigger rate
- Cleanup service execution time
- Database storage usage
- Error rates by category

**Alerts**:
- Storage exceeds 400MB (80% of free tier)
- Response time > 1 second
- Error rate > 5%
- Cleanup service failures
