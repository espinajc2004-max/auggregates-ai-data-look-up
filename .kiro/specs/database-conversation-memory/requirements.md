# Requirements Document

## Introduction

This document specifies the requirements for a Database-Based Long-Term Conversation Memory system that enables production-level multi-turn conversations with automatic 24-hour history reset, dynamic turn reference understanding, and zero-cost database storage using Supabase.

## Glossary

- **Conversation_Memory_System**: The system responsible for storing, retrieving, and managing conversation history
- **Turn**: A single user query and AI response pair in a conversation
- **Turn_Reference**: User utterances that refer to previous conversation turns (e.g., "yung una", "the first one", "kanina")
- **Session**: A conversation context that persists for up to 24 hours
- **Database_Store**: Supabase PostgreSQL database used for persistent storage
- **TTL**: Time-to-live, the duration (24 hours) before conversation history expires
- **Dynamic_Reference_Detector**: Component that identifies and resolves turn references without hardcoded patterns
- **User_ID**: Unique identifier for tracking individual user conversations

## Requirements

### Requirement 1: Persistent Conversation Storage

**User Story:** As a user, I want my conversation history to persist across server restarts, so that I can continue conversations without losing context.

#### Acceptance Criteria

1. WHEN a user sends a message THEN the Conversation_Memory_System SHALL store the turn in the Database_Store immediately
2. WHEN the server restarts THEN the Conversation_Memory_System SHALL retrieve existing conversation history from the Database_Store
3. WHEN storing a turn THEN the Conversation_Memory_System SHALL include timestamp, user message, AI response, and user_id
4. THE Conversation_Memory_System SHALL use JSONB format for storing conversation turns in PostgreSQL
5. WHEN a turn is stored THEN the Database_Store SHALL confirm successful write before responding to the user

### Requirement 2: Automatic 24-Hour History Reset

**User Story:** As a user, I want my conversation history to automatically reset after 24 hours, so that old irrelevant context doesn't affect current conversations.

#### Acceptance Criteria

1. WHEN a conversation turn is older than 24 hours THEN the Conversation_Memory_System SHALL automatically delete it from the Database_Store
2. WHEN a user sends a message THEN the Conversation_Memory_System SHALL only retrieve turns from the last 24 hours
3. THE Conversation_Memory_System SHALL use database triggers or scheduled jobs for automatic cleanup
4. WHEN cleanup occurs THEN the Conversation_Memory_System SHALL maintain data integrity and not affect active conversations
5. WHEN a user references a turn older than 24 hours THEN the Conversation_Memory_System SHALL indicate that history is not available

### Requirement 3: Recent Turn Storage Limit

**User Story:** As a system administrator, I want to limit conversation history to the last 10 turns per user, so that performance remains optimal.

#### Acceptance Criteria

1. WHEN retrieving conversation history THEN the Conversation_Memory_System SHALL return a maximum of 10 most recent turns
2. WHEN storing a new turn and the user has 10 existing turns THEN the Conversation_Memory_System SHALL remove the oldest turn
3. THE Conversation_Memory_System SHALL maintain chronological order of turns
4. WHEN counting turns THEN the Conversation_Memory_System SHALL only count turns within the 24-hour TTL window
5. WHEN a user has fewer than 10 turns THEN the Conversation_Memory_System SHALL return all available turns

### Requirement 4: Dynamic Turn Reference Detection

**User Story:** As a user, I want to reference previous conversation turns using natural language (e.g., "yung una", "the first one", "kanina"), so that I can interact naturally without memorizing specific commands.

#### Acceptance Criteria

1. WHEN a user message contains a turn reference THEN the Dynamic_Reference_Detector SHALL identify it using pattern matching and NLP techniques without hardcoded dictionaries
2. WHEN a turn reference is detected THEN the Dynamic_Reference_Detector SHALL resolve it to the specific turn index dynamically
3. THE Dynamic_Reference_Detector SHALL support multiple languages including English and Filipino through regex patterns and semantic analysis
4. WHEN resolving references like "yung una", "the first one", "una", "first" THEN the Dynamic_Reference_Detector SHALL map to the earliest turn in history
5. WHEN resolving references like "kanina", "previous", "last", "yung last" THEN the Dynamic_Reference_Detector SHALL map to the most recent turn
6. WHEN resolving references like "second", "pangalawa", "ikalawa" THEN the Dynamic_Reference_Detector SHALL map to the appropriate ordinal position
7. IF a turn reference is ambiguous THEN the Dynamic_Reference_Detector SHALL request clarification from the user
8. THE Dynamic_Reference_Detector SHALL use regex patterns for ordinal numbers (1st, 2nd, una, dalawa) and temporal references (kanina, previous) rather than hardcoded lookup tables
9. WHEN new reference patterns emerge THEN the Dynamic_Reference_Detector SHALL be extensible through pattern configuration without code changes

### Requirement 5: Conversation Context Retrieval

**User Story:** As an AI system, I want to retrieve relevant conversation context efficiently, so that I can provide contextually aware responses.

#### Acceptance Criteria

1. WHEN processing a user message THEN the Conversation_Memory_System SHALL retrieve the user's conversation history within 100ms
2. WHEN a turn reference is detected THEN the Conversation_Memory_System SHALL retrieve the referenced turn content
3. THE Conversation_Memory_System SHALL return turns in chronological order (oldest to newest)
4. WHEN no conversation history exists THEN the Conversation_Memory_System SHALL return an empty result without errors
5. WHEN retrieving history THEN the Conversation_Memory_System SHALL include turn index, timestamp, user message, and AI response

### Requirement 6: User Isolation and Privacy

**User Story:** As a user, I want my conversation history to be private and isolated from other users, so that my data remains secure.

#### Acceptance Criteria

1. WHEN storing a turn THEN the Conversation_Memory_System SHALL associate it with a unique user_id
2. WHEN retrieving conversation history THEN the Conversation_Memory_System SHALL only return turns belonging to the requesting user
3. THE Conversation_Memory_System SHALL prevent cross-user data leakage through database constraints
4. WHEN a user_id is not provided THEN the Conversation_Memory_System SHALL reject the request with an error
5. THE Database_Store SHALL enforce row-level security policies for conversation data

### Requirement 7: Zero-Cost Database Implementation

**User Story:** As a system administrator on a student budget, I want to use existing free database resources, so that there are no additional infrastructure costs.

#### Acceptance Criteria

1. THE Conversation_Memory_System SHALL use the existing Supabase PostgreSQL database
2. THE Conversation_Memory_System SHALL NOT require Redis, Vector databases, or paid services
3. WHEN implementing storage THEN the Conversation_Memory_System SHALL use efficient JSONB indexing for performance
4. THE Conversation_Memory_System SHALL stay within Supabase free tier limits (500MB database, 2GB bandwidth)
5. WHEN querying conversation history THEN the Conversation_Memory_System SHALL use optimized queries to minimize database load

### Requirement 8: Performance and Scalability

**User Story:** As a user, I want the system to respond quickly even with long conversation histories, so that my experience remains smooth.

#### Acceptance Criteria

1. WHEN retrieving conversation history THEN the Conversation_Memory_System SHALL complete the operation within 100ms for 10 turns
2. WHEN storing a new turn THEN the Conversation_Memory_System SHALL complete the operation within 50ms
3. THE Conversation_Memory_System SHALL use database indexes on user_id and timestamp columns
4. WHEN handling concurrent requests THEN the Conversation_Memory_System SHALL maintain data consistency
5. THE Conversation_Memory_System SHALL handle at least 100 concurrent users without performance degradation

### Requirement 9: Error Handling and Resilience

**User Story:** As a user, I want the system to handle errors gracefully, so that temporary issues don't break my conversation flow.

#### Acceptance Criteria

1. IF the Database_Store is unavailable THEN the Conversation_Memory_System SHALL return a graceful error message
2. WHEN a database write fails THEN the Conversation_Memory_System SHALL retry up to 3 times with exponential backoff
3. IF conversation history cannot be retrieved THEN the Conversation_Memory_System SHALL continue processing the current message without history
4. WHEN a turn reference cannot be resolved THEN the Conversation_Memory_System SHALL ask the user for clarification
5. THE Conversation_Memory_System SHALL log all errors for debugging without exposing sensitive data to users

### Requirement 10: Fragmented Message Handling

**User Story:** As a user, I want to send incomplete or fragmented messages across multiple turns (e.g., "hello", then "find cement"), so that I can interact naturally without typing everything at once.

#### Acceptance Criteria

1. WHEN a user sends an incomplete message THEN the Conversation_Memory_System SHALL store it as a valid turn
2. WHEN processing a follow-up message THEN the Conversation_Memory_System SHALL provide previous turn context to understand the complete intent
3. WHEN a user sends "find cement" after "hello" THEN the AI SHALL understand this as a search query using conversation context
4. THE Conversation_Memory_System SHALL support multi-turn intent building without requiring complete sentences
5. WHEN context from previous turns is needed THEN the Conversation_Memory_System SHALL provide the last N relevant turns to the AI

### Requirement 11: Integration with Existing Chat System

**User Story:** As a developer, I want the conversation memory system to integrate seamlessly with the existing chat API, so that implementation is straightforward.

#### Acceptance Criteria

1. WHEN a chat message is received THEN the Conversation_Memory_System SHALL be invoked before query processing
2. THE Conversation_Memory_System SHALL provide conversation context to the query handler
3. WHEN a response is generated THEN the Conversation_Memory_System SHALL store the turn asynchronously
4. THE Conversation_Memory_System SHALL expose a clean API interface for storage and retrieval operations
5. WHEN integrated THEN the Conversation_Memory_System SHALL not break existing chat functionality
