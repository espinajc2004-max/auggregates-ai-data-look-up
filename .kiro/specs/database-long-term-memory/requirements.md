# Requirements Document: Database-Based Long-Term Conversation Memory

## Introduction

This feature enables long-term conversation memory (10+ turns) using Supabase database storage with automatic cleanup and intelligent context understanding. The system must dynamically understand ANY reference to past conversations without hardcoded patterns, provide smart clarification when confused, and automatically clean up conversations older than 24 hours to prevent performance degradation.

## Glossary

- **Conversation_Memory_System**: The system that stores, retrieves, and manages conversation history
- **Turn**: A single user query and AI response pair in a conversation
- **Context_Reference**: Any user phrase that refers to previous conversation turns
- **Clarification_Engine**: The component that detects confusion and asks relevant questions
- **Auto_Cleanup_Service**: The background service that deletes conversations older than 24 hours
- **Supabase_Store**: The PostgreSQL database storage layer for conversation history
- **Session**: A continuous conversation thread identified by a unique session_id
- **Dynamic_Reference_Parser**: The NLP-based component that understands context references without pattern matching

## Requirements

### Requirement 1: Persistent Conversation Storage

**User Story:** As a user, I want my conversation history stored in a database, so that my conversations survive server restarts and I can have long multi-turn discussions.

#### Acceptance Criteria

1. WHEN a user sends a query THEN the Conversation_Memory_System SHALL store the query and response in Supabase_Store with timestamp and session_id
2. WHEN the server restarts THEN the Conversation_Memory_System SHALL retrieve all active conversations from Supabase_Store
3. WHEN a conversation exceeds 10 turns THEN the Conversation_Memory_System SHALL maintain full history without performance degradation
4. WHEN storing conversation data THEN the Conversation_Memory_System SHALL include user_id, session_id, turn_number, query_text, response_text, and created_at timestamp
5. THE Conversation_Memory_System SHALL use the existing Supabase database without requiring additional paid services

### Requirement 2: 24-Hour Auto-Cleanup

**User Story:** As a system administrator, I want conversations older than 24 hours automatically deleted, so that the database remains performant and doesn't accumulate stale data.

#### Acceptance Criteria

1. WHEN a conversation's created_at timestamp exceeds 24 hours THEN the Auto_Cleanup_Service SHALL delete all turns for that session
2. WHILE a conversation is less than 24 hours old THEN the Conversation_Memory_System SHALL retain ALL conversation history
3. THE Auto_Cleanup_Service SHALL run automatically every hour to check for expired conversations
4. WHEN cleanup occurs THEN the Auto_Cleanup_Service SHALL log the number of deleted sessions and turns
5. IF cleanup fails THEN the Auto_Cleanup_Service SHALL retry and log errors without affecting active conversations

### Requirement 3: Dynamic Context Reference Understanding

**User Story:** As a user, I want to reference past conversations using ANY natural phrasing, so that I don't have to remember specific keywords and can communicate naturally.

#### Acceptance Criteria

1. WHEN a user references a past turn using ANY phrase (e.g., "yung una", "yung nauna", "yung sinabi ko kanina", "yung last", "yung pinakauna") THEN the Dynamic_Reference_Parser SHALL identify the referenced turn
2. THE Dynamic_Reference_Parser SHALL NOT use hardcoded word patterns or keyword matching
3. WHEN analyzing context references THEN the Dynamic_Reference_Parser SHALL use semantic understanding and positional analysis
4. WHEN multiple interpretations are possible THEN the Dynamic_Reference_Parser SHALL select the most contextually relevant turn
5. THE Dynamic_Reference_Parser SHALL support references in multiple languages (English, Tagalog, mixed code-switching)

### Requirement 4: Smart Clarification System

**User Story:** As a user, I want the AI to ask for clarification when it doesn't understand my query, so that I get accurate responses instead of guesses.

#### Acceptance Criteria

1. WHEN the Clarification_Engine detects ambiguous context references THEN the Conversation_Memory_System SHALL ask a specific clarification question
2. WHEN the Clarification_Engine detects insufficient context THEN the Conversation_Memory_System SHALL request additional information
3. THE Clarification_Engine SHALL NOT use pattern-based detection
4. WHEN generating clarification questions THEN the Clarification_Engine SHALL reference specific conversation turns to help the user
5. WHEN clarification is provided THEN the Conversation_Memory_System SHALL continue with the original query using the clarified context

### Requirement 5: Efficient Context Retrieval

**User Story:** As a user, I want fast responses even with long conversation history, so that the system remains responsive throughout extended conversations.

#### Acceptance Criteria

1. WHEN retrieving conversation history THEN the Conversation_Memory_System SHALL fetch only the current session's turns
2. WHEN a session has more than 20 turns THEN the Conversation_Memory_System SHALL use pagination or windowing to limit context size
3. THE Conversation_Memory_System SHALL create database indexes on session_id and created_at for fast queries
4. WHEN loading context THEN the Conversation_Memory_System SHALL complete retrieval within 200ms for sessions up to 50 turns
5. THE Conversation_Memory_System SHALL order turns chronologically by turn_number

### Requirement 6: Session Management

**User Story:** As a user, I want each conversation to have a unique session, so that my different conversations don't get mixed together.

#### Acceptance Criteria

1. WHEN a new conversation starts THEN the Conversation_Memory_System SHALL generate a unique session_id
2. WHEN a user continues an existing conversation THEN the Conversation_Memory_System SHALL use the same session_id
3. THE Conversation_Memory_System SHALL associate each turn with exactly one session_id
4. WHEN a session is deleted THEN the Conversation_Memory_System SHALL remove all associated turns
5. THE Conversation_Memory_System SHALL support multiple concurrent sessions per user

### Requirement 7: Zero-Cost Implementation

**User Story:** As a student developer, I want the solution to be 100% free, so that I can deploy it without ongoing costs.

#### Acceptance Criteria

1. THE Conversation_Memory_System SHALL use only the existing Supabase free tier database
2. THE Conversation_Memory_System SHALL NOT require Redis, Vector DB, or any paid services
3. THE Conversation_Memory_System SHALL NOT exceed Supabase free tier limits (500MB storage, 2GB bandwidth)
4. WHEN implementing NLP features THEN the Conversation_Memory_System SHALL use free libraries (spaCy, NLTK, or similar)
5. THE Auto_Cleanup_Service SHALL prevent database growth beyond free tier limits

### Requirement 8: Semantic Context Analysis

**User Story:** As a user, I want the system to understand the meaning of my references, so that it correctly identifies what I'm referring to regardless of how I phrase it.

#### Acceptance Criteria

1. WHEN analyzing a context reference THEN the Dynamic_Reference_Parser SHALL extract semantic intent (first, last, previous, specific topic)
2. WHEN determining which turn is referenced THEN the Dynamic_Reference_Parser SHALL consider temporal indicators, ordinal positions, and topic similarity
3. THE Dynamic_Reference_Parser SHALL handle relative references (e.g., "the one before that", "two queries ago")
4. WHEN a reference is ambiguous THEN the Dynamic_Reference_Parser SHALL calculate confidence scores for possible matches
5. IF confidence is below 70% THEN the Clarification_Engine SHALL request clarification

### Requirement 9: Production-Ready Reliability

**User Story:** As a system administrator, I want the conversation memory system to be reliable and handle errors gracefully, so that it works consistently in production.

#### Acceptance Criteria

1. WHEN database operations fail THEN the Conversation_Memory_System SHALL log errors and return graceful error messages
2. WHEN Supabase is temporarily unavailable THEN the Conversation_Memory_System SHALL retry with exponential backoff
3. THE Conversation_Memory_System SHALL validate all input data before storage
4. WHEN data corruption is detected THEN the Conversation_Memory_System SHALL skip corrupted turns and continue with valid data
5. THE Conversation_Memory_System SHALL include comprehensive logging for debugging and monitoring

### Requirement 10: Scalable Architecture

**User Story:** As a developer, I want the system to scale efficiently, so that it can handle growing user base and conversation volume.

#### Acceptance Criteria

1. THE Conversation_Memory_System SHALL support at least 1000 concurrent sessions
2. WHEN the database grows THEN the Auto_Cleanup_Service SHALL maintain consistent performance through proper indexing
3. THE Conversation_Memory_System SHALL use connection pooling for database access
4. WHEN query load increases THEN the Conversation_Memory_System SHALL maintain sub-second response times
5. THE Conversation_Memory_System SHALL be stateless to support horizontal scaling
