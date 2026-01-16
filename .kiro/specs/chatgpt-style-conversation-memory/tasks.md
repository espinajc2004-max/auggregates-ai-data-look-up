# Implementation Plan: ChatGPT-Style Conversation Memory

## Overview

This implementation integrates existing conversation memory infrastructure into the chat endpoint to provide ChatGPT-style conversation memory with 24-hour persistence. The approach leverages complete, ready-to-use services (`conversation_memory_manager.py`, `conversation_db.py`) and requires minimal new code (~50 lines in chat endpoint, ~10 lines in models).

## Tasks

- [x] 1. Update request and response models
  - Add `session_id` field to `ChatRequest` model (optional)
  - Add `session_id` field to `ChatResponse` model (optional)
  - Ensure backward compatibility with existing API contracts
  - _Requirements: 2.5, 7.1_

- [x] 2. Integrate conversation memory into chat endpoint
  - [x] 2.1 Add session ID handling
    - Extract `session_id` from request or generate new one using `ConversationMemoryManager.create_session()`
    - Import and initialize `ConversationMemoryManager` at module level
    - _Requirements: 2.1, 2.2, 2.4, 7.1_
  
  - [ ]* 2.2 Write property test for session ID handling
    - **Property 2: Session ID Uniqueness and Format**
    - **Validates: Requirements 2.1, 2.5, 7.1**
  
  - [x] 2.3 Add conversation history retrieval
    - Call `memory_manager.get_session_history(session_id, limit=20)` before query processing
    - Wrap in try-except for graceful degradation
    - Log warnings on retrieval failures
    - _Requirements: 5.1, 5.2, 5.4, 7.2_
  
  - [ ]* 2.4 Write property test for session isolation
    - **Property 3: Session Isolation**
    - **Validates: Requirements 2.3, 5.1**
  
  - [ ]* 2.5 Write property test for chronological ordering
    - **Property 7: Chronological Ordering**
    - **Validates: Requirements 5.2**
  
  - [x] 2.6 Add conversation turn storage
    - Call `memory_manager.store_turn()` after response generation
    - Include metadata (intent, confidence, result_count)
    - Wrap in try-except for graceful degradation (fire-and-forget pattern)
    - Log errors on storage failures
    - _Requirements: 1.1, 1.2, 1.5, 7.3_
  
  - [ ]* 2.7 Write property test for turn storage completeness
    - **Property 1: Turn Storage Completeness**
    - **Validates: Requirements 1.1, 1.2, 7.3**
  
  - [x] 2.8 Add session_id to response
    - Set `response.session_id = session_id` before returning
    - Ensure all response paths include session_id
    - _Requirements: 2.5_

- [x] 3. Implement graceful degradation
  - [x] 3.1 Add error handling for database failures
    - Catch `ConnectionError`, `TimeoutError`, `SupabaseError` in history retrieval
    - Catch same exceptions in turn storage
    - Continue operation with empty history or without storage on failures
    - _Requirements: 1.5, 6.1, 6.4, 6.5, 7.5_
  
  - [ ]* 3.2 Write property test for graceful degradation
    - **Property 8: Graceful Degradation on Database Failure**
    - **Validates: Requirements 1.5, 6.1, 6.4, 6.5, 7.5**
  
  - [ ]* 3.3 Write unit tests for error scenarios
    - Test database connection failures
    - Test timeout handling
    - Test continued operation during failures
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 4. Verify backward compatibility
  - [x] 4.1 Run existing Phase 3 test suite
    - Execute `pytest test_phase3_*.py -v`
    - Verify all tests pass without modifications
    - _Requirements: 8.1, 8.2, 8.3, 8.5_
  
  - [ ]* 4.2 Write property test for memory layer independence
    - **Property 9: Memory Layer Independence**
    - **Validates: Requirements 4.3, 4.4, 4.5**
  
  - [ ]* 4.3 Write unit tests for clarification flow compatibility
    - Test that short-term clarification memory still works
    - Test that clarification flows don't access long-term memory
    - Test mixed usage of both memory layers
    - _Requirements: 4.1, 4.3, 8.2, 8.3_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement property-based tests for core properties
  - [ ] 6.1 Write property test for session continuity
    - **Property 4: Session Continuity**
    - **Validates: Requirements 2.2**
  
  - [ ]* 6.2 Write property test for invalid session handling
    - **Property 5: Invalid Session Handling**
    - **Validates: Requirements 2.4, 5.4**
  
  - [ ]* 6.3 Write property test for TTL enforcement
    - **Property 6: TTL Enforcement**
    - **Validates: Requirements 3.1, 5.5**
  
  - [ ]* 6.4 Write property test for long-term memory persistence
    - **Property 10: Long-Term Memory Persistence**
    - **Validates: Requirements 4.2**
  
  - [ ]* 6.5 Write property test for database constraint compliance
    - **Property 11: Database Constraint Compliance**
    - **Validates: Requirements 9.3**
  
  - [ ]* 6.6 Write property test for error logging with context
    - **Property 12: Error Logging with Context**
    - **Validates: Requirements 10.1, 10.5**

- [ ] 7. Write integration tests
  - [ ]* 7.1 Write end-to-end conversation flow test
    - Test multiple turns in a single session
    - Verify history accumulates correctly
    - Verify session continuity across requests
    - _Requirements: 1.1, 2.2, 5.1, 7.3_
  
  - [ ]* 7.2 Write cleanup verification test
    - Create turns with backdated timestamps
    - Run cleanup service
    - Verify old turns deleted, recent turns remain
    - _Requirements: 3.1, 3.4_
  
  - [ ]* 7.3 Write database failure recovery test
    - Simulate database failure
    - Verify graceful degradation
    - Restore database connection
    - Verify normal operation resumes
    - _Requirements: 6.1, 6.3, 6.4_

- [x] 8. Add logging and monitoring
  - [x] 8.1 Add debug logging for successful operations
    - Log turn storage success with session_id
    - Log history retrieval with turn count
    - _Requirements: 10.2_
  
  - [x] 8.2 Add error logging with context
    - Include session_id in all error logs
    - Include operation type and error details
    - Log warnings for graceful degradation
    - _Requirements: 10.1, 10.4, 10.5_
  
  - [ ]* 8.3 Write unit tests for logging behavior
    - Test success logging at debug level
    - Test error logging with context
    - Test warning logging for fallback mode
    - _Requirements: 1.4, 6.2, 10.2, 10.3, 10.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- All existing Phase 3 tests must pass without modifications
- Existing services (`conversation_memory_manager.py`, `conversation_db.py`) are complete and ready to use
- Database schema and cleanup function already exist
- Total new code: ~560 lines (50 endpoint, 10 models, 500 tests)
