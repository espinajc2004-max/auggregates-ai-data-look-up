# Implementation Plan: Database-Based Long-Term Conversation Memory

## Overview

This implementation plan breaks down the database-based conversation memory system into discrete coding tasks. The approach follows an incremental strategy: database schema → core storage → reference parsing → clarification → cleanup service → testing. Each task builds on previous work and includes validation through tests.

## Tasks

- [x] 1. Set up database schema and core data models
  - Create Supabase migration for `conversation_turns` table with all required fields (id, session_id, user_id, turn_number, query_text, response_text, created_at, metadata)
  - Add indexes for performance: idx_session_id, idx_created_at, idx_user_sessions, idx_cleanup
  - Create Python data models (Turn, ConversationContext, ReferenceIntent, ReferenceResolution, SemanticFeatures)
  - Set up database connection with connection pooling
  - _Requirements: 1.1, 1.4, 5.3_

- [x] 1.1 Write property test for turn storage completeness
  - **Property 1: Turn Storage Completeness**
  - **Validates: Requirements 1.1, 1.4**

- [x] 2. Implement Conversation Memory Manager core functionality
  - [x] 2.1 Implement store_turn() method
    - Store conversation turns with auto-incrementing turn_number
    - Generate UUIDs for turn IDs
    - Handle database errors with logging
    - _Requirements: 1.1, 1.4_
  
  - [x] 2.2 Implement get_session_history() method
    - Retrieve all turns for a session ordered by turn_number
    - Support pagination/limiting (max 50 turns)
    - Implement session isolation (only return turns for requested session)
    - _Requirements: 5.1, 5.5_
  
  - [x] 2.3 Implement create_session() method
    - Generate unique session_id using UUID
    - Return session_id for client use
    - _Requirements: 6.1_
  
  - [x] 2.4 Implement delete_session() method
    - Delete all turns for a given session_id
    - Return count of deleted turns
    - _Requirements: 6.4_

- [x] 2.5 Write property tests for Memory Manager
  - **Property 2: Persistence Across Restarts**
  - **Property 12: Session Isolation**
  - **Property 14: Chronological Ordering**
  - **Property 15: Session ID Uniqueness**
  - **Property 16: Session Continuity**
  - **Property 17: Turn-Session Association**
  - **Property 18: Cascading Session Deletion**
  - **Validates: Requirements 1.2, 5.1, 5.5, 6.1, 6.2, 6.3, 6.4**

- [x] 2.6 Write unit tests for Memory Manager edge cases
  - Test empty conversation history
  - Test single turn conversation
  - Test session with exactly 20 turns (boundary)
  - _Requirements: 1.1, 5.1_

- [x] 3. Implement Dynamic Reference Parser
  - [x] 3.1 Set up NLP model (spaCy or NLTK)
    - Install and configure spaCy with English and multilingual models
    - Create initialization logic for NLP pipeline
    - _Requirements: 3.1, 7.4_
  
  - [x] 3.2 Implement detect_reference() method
    - Detect if query contains context references
    - Return ReferenceIntent with intent_type and indicators
    - Support multiple languages (English, Tagalog, code-switched)
    - _Requirements: 3.1, 3.5_
  
  - [x] 3.3 Implement extract_semantic_features() method
    - Extract temporal indicators (first, last, earlier, recent, kanina, nauna)
    - Extract ordinal positions (1st, 2nd, una, pangalawa)
    - Extract relative positions (before that, two ago)
    - Extract topic keywords using TF-IDF or keyword extraction
    - _Requirements: 8.1, 8.3_
  
  - [x] 3.4 Implement resolve_reference() method
    - Match reference intent to specific turns using semantic features
    - Calculate confidence scores for each potential match
    - Handle ambiguous references (multiple high-confidence matches)
    - Select most contextually relevant turn
    - _Requirements: 3.1, 3.4, 8.4_

- [x] 3.5 Write property tests for Dynamic Reference Parser
  - **Property 8: Dynamic Reference Identification**
  - **Property 9: Contextual Disambiguation**
  - **Property 20: Confidence Scoring**
  - **Validates: Requirements 3.1, 3.4, 3.5, 8.1, 8.3, 8.4**

- [x] 3.6 Write unit tests for specific reference phrases
  - Test "yung una", "yung pangalawa", "yung pinakauna" (Tagalog ordinal)
  - Test "kanina", "nauna", "dati" (Tagalog temporal)
  - Test "the first one", "the last one" (English ordinal)
  - Test "the earlier one", "the previous" (English temporal)
  - Test "two queries ago", "the one before that" (relative)
  - Test code-switched phrases ("yung first", "the nauna")
  - _Requirements: 3.1, 3.5_

- [x] 4. Implement Clarification Engine
  - [x] 4.1 Implement needs_clarification() method
    - Check if confidence score < 0.7 (threshold)
    - Check if multiple matches with confidence > 0.6
    - Return boolean indicating if clarification needed
    - _Requirements: 4.1, 4.2, 8.5_
  
  - [x] 4.2 Implement generate_clarification_question() method
    - Generate specific question referencing possible turn matches
    - Include turn content snippets to help user identify
    - Format: "Did you mean your first question about 'X' or your second question about 'Y'?"
    - _Requirements: 4.1, 4.4_
  
  - [x] 4.3 Implement resolve_with_clarification() method
    - Parse user's clarification response
    - Select correct turn based on clarification
    - Return resolved turn for context
    - _Requirements: 4.5_

- [x] 4.4 Write property tests for Clarification Engine
  - **Property 10: Clarification Triggering**
  - **Property 11: Clarification Resolution**
  - **Validates: Requirements 4.1, 4.2, 4.4, 4.5, 8.5**

- [x] 4.5 Write unit tests for clarification flow
  - Test ambiguous reference triggers clarification
  - Test low confidence triggers clarification
  - Test clarification question includes turn references
  - Test clarification resolution selects correct turn
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 5. Implement context assembly in Memory Manager
  - [x] 5.1 Implement get_context_for_query() method
    - Retrieve session history
    - Detect context references using Dynamic Reference Parser
    - Resolve references to specific turns
    - Check if clarification needed using Clarification Engine
    - Assemble ConversationContext with history and referenced turns
    - Implement sliding window for sessions > 20 turns
    - _Requirements: 3.1, 4.1, 5.2_
  
  - [x] 5.2 Implement context window limiting logic
    - Keep first turn (context setting)
    - Keep last 19 turns (recent context)
    - Include referenced turns even if outside window
    - _Requirements: 5.2_

- [x] 5.3 Write property tests for context assembly
  - **Property 3: Long Conversation Performance**
  - **Property 13: Context Window Limiting**
  - **Property 19: Multi-Session Support**
  - **Validates: Requirements 1.3, 5.2, 6.5**

- [x] 6. Implement Auto-Cleanup Service
  - [x] 6.1 Implement run_cleanup() method
    - Query for sessions with created_at < NOW() - INTERVAL '24 hours'
    - Delete turns in batches of 1000 to avoid long locks
    - Count deleted sessions and turns
    - Log cleanup results
    - Handle errors gracefully with retry logic
    - _Requirements: 2.1, 2.4_
  
  - [x] 6.2 Implement schedule_hourly() method
    - Set up APScheduler for hourly execution
    - Configure job to run run_cleanup() every hour
    - Add error handling for scheduler failures
    - _Requirements: 2.3_
  
  - [x] 6.3 Implement get_cleanup_stats() method
    - Track cleanup statistics (total cleanups, sessions deleted, turns deleted)
    - Return CleanupStats data model
    - _Requirements: 2.4_

- [x] 6.4 Write property tests for Auto-Cleanup Service
  - **Property 4: 24-Hour Cleanup Deletion**
  - **Property 5: Recent Conversation Retention**
  - **Property 6: Cleanup Logging**
  - **Property 7: Cleanup Error Resilience**
  - **Validates: Requirements 2.1, 2.2, 2.4, 2.5**

- [x] 6.5 Write unit tests for cleanup edge cases
  - Test conversation exactly 24 hours old (boundary)
  - Test cleanup with no expired conversations
  - Test cleanup with database error (retry logic)
  - Test batch deletion with large dataset
  - _Requirements: 2.1, 2.5_

- [x] 7. Implement error handling and resilience
  - [x] 7.1 Add database connection retry logic
    - Implement exponential backoff (1s, 2s, 4s, 8s, max 5 attempts)
    - Log retry attempts with timestamps
    - Return graceful error after max retries
    - _Requirements: 9.2_
  
  - [x] 7.2 Add input validation
    - Validate session_id, user_id (valid UUIDs)
    - Validate query_text, response_text (non-empty, max length)
    - Validate turn_number (positive integer)
    - Return 400 Bad Request with field-specific errors
    - _Requirements: 9.3_
  
  - [x] 7.3 Add corruption handling
    - Detect corrupted turn data (missing fields, invalid JSON)
    - Skip corrupted turns and continue with valid data
    - Log corruption errors with turn IDs
    - _Requirements: 9.4_
  
  - [x] 7.4 Add comprehensive logging
    - Log all database operations (store, retrieve, delete)
    - Log reference resolution attempts with confidence scores
    - Log clarification triggers and resolutions
    - Log cleanup operations with statistics
    - Log all errors with stack traces
    - _Requirements: 9.1, 9.5_

- [x] 7.5 Write property tests for error handling
  - **Property 21: Error Logging and Graceful Degradation**
  - **Property 22: Retry with Exponential Backoff**
  - **Property 23: Input Validation**
  - **Property 24: Corruption Handling**
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**

- [x] 7.6 Write unit tests for error scenarios
  - Test database connection failure
  - Test invalid UUID format
  - Test null query text
  - Test empty response text
  - Test corrupted turn data in history
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 8. Integrate with existing chat API
  - [ ] 8.1 Update chat endpoint to use Conversation Memory Manager
    - Create or retrieve session_id
    - Call get_context_for_query() to assemble context
    - Handle clarification flow (return clarification question if needed)
    - Store turn after generating response
    - Return response with session_id
    - _Requirements: 1.1, 3.1, 4.1_
  
  - [ ] 8.2 Add session management endpoints
    - POST /chat/session - Create new session
    - GET /chat/session/{session_id}/history - Retrieve session history
    - DELETE /chat/session/{session_id} - Delete session
    - _Requirements: 6.1, 5.1, 6.4_

- [ ] 8.3 Write integration tests for chat API
  - Test full conversation flow with context references
  - Test clarification flow end-to-end
  - Test session creation and retrieval
  - Test multi-turn conversation (10+ turns)
  - Test concurrent sessions for same user
  - _Requirements: 1.1, 3.1, 4.1, 6.5_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Run all property tests (minimum 100 iterations each)
  - Run all unit tests
  - Run all integration tests
  - Verify database schema is correct
  - Verify cleanup service is scheduled
  - Ask the user if questions arise

- [ ] 10. Add monitoring and observability
  - [ ] 10.1 Add metrics collection
    - Track average turn storage time
    - Track average history retrieval time
    - Track reference resolution accuracy
    - Track clarification trigger rate
    - Track cleanup service execution time
    - Track database storage usage
    - Track error rates by category
    - _Requirements: 9.5_
  
  - [ ] 10.2 Set up alerts
    - Alert if storage exceeds 400MB (80% of free tier)
    - Alert if response time > 1 second
    - Alert if error rate > 5%
    - Alert if cleanup service fails
    - _Requirements: 7.3_

- [ ] 11. Documentation and deployment preparation
  - [ ] 11.1 Write API documentation
    - Document all endpoints with request/response examples
    - Document session management flow
    - Document clarification flow
    - Document error responses
  
  - [ ] 11.2 Write deployment guide
    - Document Supabase migration steps
    - Document environment variables needed
    - Document NLP model installation
    - Document cleanup service setup
  
  - [ ] 11.3 Write usage examples
    - Example: Basic conversation
    - Example: Conversation with context reference
    - Example: Clarification flow
    - Example: Multi-session usage

- [ ] 12. Final checkpoint - Production readiness
  - Verify all tests pass (unit, property, integration)
  - Verify cleanup service runs successfully
  - Verify database indexes are created
  - Verify error handling works correctly
  - Verify logging is comprehensive
  - Verify storage usage is within free tier limits
  - Ask the user if questions arise

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- The implementation uses Python with spaCy for NLP, Supabase for storage, and APScheduler for cleanup scheduling
