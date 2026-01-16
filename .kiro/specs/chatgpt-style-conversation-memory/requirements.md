# Requirements Document: ChatGPT-Style Conversation Memory

## Introduction

This feature implements ChatGPT-style conversation memory with 24-hour persistence, allowing users to continue conversations across multiple turns within the same session. The system maintains a hybrid memory architecture: short-term (5-minute) memory for clarification flows and long-term (24-hour) memory for persistent conversation history. All conversation data is stored in Supabase with automatic cleanup after 24 hours.

## Glossary

- **Conversation_Turn**: A single query-response pair in a conversation session
- **Session_ID**: Unique identifier for a conversation session
- **Short_Term_Memory**: 5-minute in-memory storage for clarification flows (existing Phase 3 system)
- **Long_Term_Memory**: 24-hour persistent storage in Supabase for conversation history
- **TTL**: Time-to-live, the duration before automatic data deletion (24 hours)
- **Hybrid_Memory_System**: Combined architecture using both short-term and long-term memory
- **Conversation_Memory_Manager**: Service managing conversation turn storage and retrieval
- **Conversation_DB**: Database service handling Supabase operations for conversation data
- **Graceful_Degradation**: System behavior when database is unavailable (fallback to in-memory)
- **Chat_Endpoint**: The `/api/chat` endpoint that processes user queries

## Requirements

### Requirement 1: Persistent Conversation Storage

**User Story:** As a user, I want my conversation history stored persistently, so that I can continue conversations across multiple sessions within 24 hours.

#### Acceptance Criteria

1. WHEN a user sends a query and receives a response, THE Conversation_Memory_Manager SHALL store the turn in the conversation_turns table
2. WHEN storing a conversation turn, THE System SHALL include session_id, user_query, assistant_response, and timestamp
3. WHEN a conversation turn is stored, THE System SHALL persist it to Supabase within 1 second of response generation
4. WHEN the database write succeeds, THE System SHALL log the successful storage operation
5. WHEN the database write fails, THE System SHALL log the error and continue operation without blocking the user response

### Requirement 2: Session Management

**User Story:** As a user, I want each conversation to have a unique session identifier, so that my conversations remain organized and retrievable.

#### Acceptance Criteria

1. WHEN a new conversation starts, THE System SHALL generate a unique session_id using UUID format
2. WHEN a user continues an existing session, THE System SHALL use the provided session_id
3. WHEN retrieving conversation history, THE System SHALL filter by session_id to return only relevant turns
4. WHEN a session_id is invalid or not found, THE System SHALL treat it as a new conversation session
5. THE System SHALL include session_id in all API responses for client-side session tracking

### Requirement 3: 24-Hour Time-to-Live

**User Story:** As a system administrator, I want conversations automatically deleted after 24 hours, so that storage costs remain manageable and user privacy is maintained.

#### Acceptance Criteria

1. WHEN the cleanup service runs, THE System SHALL delete all conversation turns older than 24 hours
2. WHEN calculating conversation age, THE System SHALL use the created_at timestamp from the database
3. THE Cleanup_Service SHALL run automatically on a scheduled interval
4. WHEN conversations are deleted, THE System SHALL log the number of deleted records
5. WHEN the cleanup operation fails, THE System SHALL log the error and retry on the next scheduled run

### Requirement 4: Hybrid Memory Architecture

**User Story:** As a developer, I want separate short-term and long-term memory systems, so that clarification flows remain fast while conversation history persists.

#### Acceptance Criteria

1. THE System SHALL maintain the existing 5-minute Short_Term_Memory for clarification flows unchanged
2. THE System SHALL implement 24-hour Long_Term_Memory for conversation history storage
3. WHEN a clarification flow occurs, THE System SHALL use Short_Term_Memory without accessing Long_Term_Memory
4. WHEN retrieving conversation context, THE System SHALL load from Long_Term_Memory
5. THE Short_Term_Memory and Long_Term_Memory SHALL operate independently without interference

### Requirement 5: Context Retrieval

**User Story:** As a user, I want the system to remember previous conversation turns, so that I can ask follow-up questions without repeating context.

#### Acceptance Criteria

1. WHEN a user continues a session, THE System SHALL retrieve all conversation turns for that session_id
2. WHEN loading conversation history, THE System SHALL order turns chronologically by created_at timestamp
3. WHEN conversation history is retrieved, THE System SHALL include it in the LLM context for response generation
4. WHEN no conversation history exists for a session_id, THE System SHALL proceed with an empty history
5. WHEN retrieving conversation history, THE System SHALL limit results to turns within the 24-hour TTL window

### Requirement 6: Graceful Degradation

**User Story:** As a user, I want the system to continue working even when the database is unavailable, so that I can still get responses to my queries.

#### Acceptance Criteria

1. WHEN the database connection fails, THE System SHALL fall back to in-memory storage for the current session
2. WHEN operating in fallback mode, THE System SHALL log a warning about degraded functionality
3. WHEN the database becomes available again, THE System SHALL resume normal persistent storage
4. WHEN in fallback mode, THE System SHALL still provide conversation responses without errors
5. WHEN database operations timeout, THE System SHALL treat it as a connection failure and activate fallback mode

### Requirement 7: Integration with Chat Endpoint

**User Story:** As a developer, I want conversation memory integrated into the existing chat endpoint, so that all chat interactions automatically benefit from conversation history.

#### Acceptance Criteria

1. WHEN the Chat_Endpoint receives a request, THE System SHALL extract or generate a session_id
2. WHEN processing a query, THE Chat_Endpoint SHALL retrieve conversation history before generating a response
3. WHEN a response is generated, THE Chat_Endpoint SHALL store the conversation turn
4. THE Chat_Endpoint SHALL maintain backward compatibility with existing API contracts
5. WHEN conversation memory operations fail, THE Chat_Endpoint SHALL still return a valid response

### Requirement 8: Backward Compatibility

**User Story:** As a developer, I want all existing Phase 3 tests to continue passing, so that no functionality is broken by the new feature.

#### Acceptance Criteria

1. WHEN Phase 3 tests are executed, THE System SHALL pass all existing test cases
2. THE Clarification_Engine SHALL continue operating with Short_Term_Memory unchanged
3. THE Conversation_Handler SHALL maintain existing behavior for clarification flows
4. WHEN new conversation memory features are disabled, THE System SHALL function identically to the previous version
5. THE System SHALL not introduce breaking changes to existing API endpoints or service interfaces

### Requirement 9: Database Schema Utilization

**User Story:** As a developer, I want to use the existing conversation_turns table and cleanup function, so that implementation is simplified and consistent with existing infrastructure.

#### Acceptance Criteria

1. THE System SHALL use the existing conversation_turns table schema without modifications
2. THE System SHALL utilize the cleanup_old_conversations() database function for TTL enforcement
3. WHEN storing conversation turns, THE System SHALL comply with the existing table constraints
4. THE System SHALL leverage existing database indexes for efficient query performance
5. THE System SHALL use the Conversation_DB service for all database operations

### Requirement 10: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive error handling and logging, so that I can monitor system health and troubleshoot issues.

#### Acceptance Criteria

1. WHEN any database operation fails, THE System SHALL log the error with context information
2. WHEN conversation storage succeeds, THE System SHALL log the operation at debug level
3. WHEN the cleanup service runs, THE System SHALL log the start time, end time, and number of deleted records
4. WHEN graceful degradation activates, THE System SHALL log a warning with the reason for fallback
5. THE System SHALL include session_id in all log messages related to conversation operations
