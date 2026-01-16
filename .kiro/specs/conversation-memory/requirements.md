# Requirements Document: Database-Based Long-Term Conversation Memory

## Introduction

This feature enables long-term conversation memory for AI interactions using Supabase database storage. The system stores conversation history to allow users to reference previous queries and maintain context across multiple turns. To prevent performance degradation from accumulated irrelevant data, conversations automatically reset after 24 hours, ensuring the system remains fast and responsive while maintaining relevant context.

## Glossary

- **Conversation_Store**: The database-backed service that manages conversation history storage and retrieval
- **Turn**: A single user query and AI response pair in a conversation
- **Turn_Reference**: A user's reference to a previous turn using phrases like "yung una" (the first one), "yung pangalawa" (the second one), "yung kanina" (earlier)
- **Conversation_Context**: The collection of recent turns stored for a specific user
- **Auto_Reset**: The automatic deletion of conversation history after 24 hours
- **Supabase_Client**: The database client used to interact with the Supabase PostgreSQL database

## Requirements

### Requirement 1: Conversation History Storage

**User Story:** As a user, I want my conversation history stored in a database, so that I can have long conversations with context that survives server restarts.

#### Acceptance Criteria

1. WHEN a user sends a query THEN THE Conversation_Store SHALL persist the query and response to the Supabase database
2. WHEN the server restarts THEN THE Conversation_Store SHALL retrieve existing conversation history from the database
3. THE Conversation_Store SHALL store conversations using only the existing Supabase database infrastructure without requiring additional services
4. WHEN storing a conversation turn THEN THE Conversation_Store SHALL include a timestamp for auto-cleanup purposes
5. THE Conversation_Store SHALL associate each conversation turn with a unique user identifier

### Requirement 2: Turn Limit Management

**User Story:** As a system administrator, I want to limit stored conversation turns per user, so that the system remains performant and storage costs stay minimal.

#### Acceptance Criteria

1. THE Conversation_Store SHALL maintain a maximum of 10 conversation turns per user
2. WHEN a new turn is added and the limit is reached THEN THE Conversation_Store SHALL remove the oldest turn before adding the new one
3. WHEN retrieving conversation history THEN THE Conversation_Store SHALL return turns in chronological order
4. THE Conversation_Store SHALL count only complete turns (query-response pairs) toward the 10-turn limit

### Requirement 3: Turn Reference Resolution

**User Story:** As a user, I want to reference previous queries using natural language phrases, so that I can easily refer back to earlier parts of the conversation.

#### Acceptance Criteria

1. WHEN a user uses "yung una" or "the first one" THEN THE Conversation_Store SHALL resolve this to the first turn in the conversation history
2. WHEN a user uses "yung pangalawa" or "the second one" THEN THE Conversation_Store SHALL resolve this to the second turn in the conversation history
3. WHEN a user uses "yung kanina" or "earlier" THEN THE Conversation_Store SHALL resolve this to the most recent turn in the conversation history
4. WHEN a turn reference cannot be resolved THEN THE Conversation_Store SHALL return an empty result without causing errors
5. THE Conversation_Store SHALL support ordinal references from first through tenth turn

### Requirement 4: 24-Hour Auto-Reset

**User Story:** As a user, I want my conversation history to automatically reset after 24 hours, so that the system stays fast and only remembers relevant recent context.

#### Acceptance Criteria

1. WHEN a conversation turn is older than 24 hours THEN THE Conversation_Store SHALL automatically delete it from the database
2. WHEN retrieving conversation history THEN THE Conversation_Store SHALL exclude turns older than 24 hours
3. THE Conversation_Store SHALL perform auto-cleanup checks before retrieving conversation history
4. WHEN all turns are older than 24 hours THEN THE Conversation_Store SHALL return an empty conversation history
5. THE Conversation_Store SHALL use the turn timestamp to determine if a turn exceeds the 24-hour threshold

### Requirement 5: Database Schema

**User Story:** As a developer, I want a well-designed database schema for conversation storage, so that the system is maintainable and scalable.

#### Acceptance Criteria

1. THE Conversation_Store SHALL use a table with columns for user_id, turn_number, user_query, ai_response, and created_at timestamp
2. THE Conversation_Store SHALL create appropriate indexes on user_id and created_at columns for query performance
3. WHEN querying conversation history THEN THE Conversation_Store SHALL use efficient queries that leverage database indexes
4. THE Conversation_Store SHALL use the existing Supabase database connection without creating new connections

### Requirement 6: Context Retrieval

**User Story:** As a user, I want the AI to remember my recent conversation history, so that I can have natural multi-turn conversations without repeating context.

#### Acceptance Criteria

1. WHEN a user sends a new query THEN THE Conversation_Store SHALL retrieve the user's recent conversation history
2. THE Conversation_Store SHALL format conversation history in a way that can be included in AI prompts
3. WHEN no conversation history exists for a user THEN THE Conversation_Store SHALL return an empty context without errors
4. THE Conversation_Store SHALL include both user queries and AI responses in the retrieved context

### Requirement 7: Error Handling

**User Story:** As a system administrator, I want robust error handling for database operations, so that conversation storage failures don't break the main application.

#### Acceptance Criteria

1. WHEN a database write operation fails THEN THE Conversation_Store SHALL log the error and continue without crashing the application
2. WHEN a database read operation fails THEN THE Conversation_Store SHALL return an empty conversation history and log the error
3. WHEN the database connection is unavailable THEN THE Conversation_Store SHALL gracefully degrade to stateless operation
4. THE Conversation_Store SHALL validate user input before storing to prevent SQL injection or data corruption

### Requirement 8: Performance Optimization

**User Story:** As a user, I want fast response times even with conversation history enabled, so that the system remains responsive.

#### Acceptance Criteria

1. WHEN retrieving conversation history THEN THE Conversation_Store SHALL complete the operation within 100 milliseconds
2. WHEN storing a new turn THEN THE Conversation_Store SHALL complete the operation within 100 milliseconds
3. THE Conversation_Store SHALL use database connection pooling to minimize connection overhead
4. THE Conversation_Store SHALL limit the amount of data retrieved per query to only necessary fields
