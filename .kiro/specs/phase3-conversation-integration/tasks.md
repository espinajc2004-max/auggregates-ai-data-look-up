# Implementation Plan: Phase 3 Conversation Integration

## Overview

This implementation plan breaks down Phase 3 into discrete coding tasks that build incrementally on the existing Phase 1 and Phase 2 implementation. The focus is on integrating selection detection and conversation state management with the Chat V2 endpoint while maintaining data-agnostic principles.

## Tasks

- [x] 1. Create SelectionDetector component with strategy pattern
  - Create `app/services/selection_detector.py` with SelectionDetector class
  - Implement `detect()` method that orchestrates strategy execution
  - Implement `_detect_number()` strategy for digit string detection (1, 2, 3)
  - Implement `_detect_english_ordinal()` strategy (first, second, third)
  - Implement `_detect_tagalog_ordinal()` strategy (una, pangalawa, pangatlo)
  - Implement `_detect_natural_language()` strategy (yung una, yung pangalawa)
  - Implement `_detect_name_match()` strategy for fuzzy name matching
  - Apply strategies in priority order (number → English → Tagalog → natural → name)
  - Return None for no match (fail-safe behavior)
  - _Requirements: 1.1, 1.2, 1.3, 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.5, 10.1-10.5_

- [ ]* 1.1 Write property test for number selection mapping
  - **Property 1: Number Selection Mapping**
  - **Validates: Requirements 1.1, 1.2**

- [ ]* 1.2 Write property test for out-of-range rejection
  - **Property 2: Out-of-Range Rejection**
  - **Validates: Requirements 1.3, 2.4, 3.4**

- [ ]* 1.3 Write property test for English ordinal mapping
  - **Property 3: English Ordinal Mapping**
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ]* 1.4 Write property test for Tagalog ordinal mapping
  - **Property 4: Tagalog Ordinal Mapping**
  - **Validates: Requirements 3.1, 3.2, 3.3**

- [ ]* 1.5 Write property test for case insensitivity
  - **Property 5: Case Insensitivity**
  - **Validates: Requirements 2.5, 3.5, 5.5**

- [ ]* 1.6 Write property test for natural language ordinal extraction
  - **Property 6: Natural Language Ordinal Extraction**
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ]* 1.7 Write property test for unique name matching
  - **Property 7: Unique Name Matching**
  - **Validates: Requirements 5.1, 5.2**

- [ ]* 1.8 Write property test for ambiguous name rejection
  - **Property 8: Ambiguous Name Rejection**
  - **Validates: Requirements 5.3**

- [ ]* 1.9 Write property test for strategy priority order
  - **Property 9: Strategy Priority Order**
  - **Validates: Requirements 10.1-10.5**

- [ ]* 1.10 Write unit tests for edge cases
  - Test zero input (should reject)
  - Test empty options list
  - Test empty string input
  - Test special characters in names
  - _Requirements: 1.4, 5.4_

- [x] 2. Create ConversationHandler component
  - Create `app/services/conversation_handler.py` with ConversationHandler class
  - Implement `save_clarification()` method to save conversation state
  - Implement `get_clarification()` method to retrieve state with expiration check
  - Implement `clear_clarification()` method to delete state
  - Implement `is_expired()` method to check 5-minute TTL
  - Use existing ConversationStore for storage (no schema changes)
  - Store state structure: {type, original_query, search_term, options, last_results, timestamp, step}
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ]* 2.1 Write property test for state persistence round-trip
  - **Property 10: State Persistence Round-Trip**
  - **Validates: Requirements 6.1, 6.2, 6.5**

- [ ]* 2.2 Write property test for session isolation
  - **Property 11: Session Isolation**
  - **Validates: Requirements 6.4**

- [ ]* 2.3 Write property test for state expiration
  - **Property 12: State Expiration**
  - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**

- [ ]* 2.4 Write property test for state cleanup after success
  - **Property 13: State Cleanup After Success**
  - **Validates: Requirements 7.5, 8.3, 11.5**

- [ ]* 2.5 Write unit tests for ConversationHandler
  - Test save with missing user_id
  - Test retrieve with missing user_id
  - Test clear with non-existent state
  - _Requirements: 6.1-6.5, 11.1-11.5_

- [ ] 3. Checkpoint - Ensure all tests pass
  - Run all property tests and unit tests for SelectionDetector and ConversationHandler
  - Verify no regressions in existing Phase 1 & 2 tests
  - Ask the user if questions arise

- [x] 4. Integrate SelectionDetector with Chat V2 endpoint
  - Modify `app/api/routes/chat_v2.py` to import SelectionDetector
  - Update `handle_clarification_response()` to use SelectionDetector.detect()
  - Replace existing `detect_selection()` function with SelectionDetector call
  - Ensure selection detection is attempted when conversation state exists
  - Extract selected option from conversation state after successful detection
  - _Requirements: 7.1, 7.2_

- [ ]* 4.1 Write property test for selection detection trigger
  - **Property 14: Selection Detection Trigger**
  - **Validates: Requirements 7.1**

- [ ]* 4.2 Write property test for successful selection refinement
  - **Property 15: Successful Selection Refinement**
  - **Validates: Requirements 7.2**

- [x] 5. Integrate ConversationHandler with Chat V2 endpoint
  - Modify `app/api/routes/chat_v2.py` to import ConversationHandler
  - Update `handle_new_query()` to use ConversationHandler.save_clarification()
  - Update `chat_v2()` to use ConversationHandler.get_clarification()
  - Update `handle_clarification_response()` to use ConversationHandler.clear_clarification()
  - Replace direct ConversationStore calls with ConversationHandler methods
  - _Requirements: 6.1, 6.5, 7.5, 8.3, 11.5_

- [x] 6. Implement error handling and graceful degradation
  - Add try-except blocks around SelectionDetector.detect() calls
  - Add try-except blocks around ConversationHandler operations
  - Implement fallback to new query on selection detection failure
  - Implement fallback to new query on state retrieval failure
  - Ensure clarification options are still returned even if state save fails
  - Log detailed error information for all exceptions
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ]* 6.1 Write property test for failed selection fallback
  - **Property 16: Failed Selection Fallback**
  - **Validates: Requirements 7.4, 8.5, 12.1, 12.2**

- [ ]* 6.2 Write property test for graceful degradation
  - **Property 18: Graceful Degradation**
  - **Validates: Requirements 12.3, 12.4**

- [ ]* 6.3 Write unit tests for error scenarios
  - Test selection detection exception handling
  - Test state retrieval failure
  - Test state save failure
  - Test conversation store unavailable
  - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 7. Implement multi-turn conversation flow
  - Ensure `handle_new_query()` saves state when multiple results found
  - Ensure `chat_v2()` checks for pending clarification before processing
  - Ensure `handle_clarification_response()` refines search with selection
  - Ensure state is cleared after successful selection
  - Implement retry clarification for unclear selections
  - Implement timeout handling for expired states
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ]* 7.1 Write property test for multi-result clarification trigger
  - **Property 17: Multi-Result Clarification Trigger**
  - **Validates: Requirements 8.1**

- [ ]* 7.2 Write integration test for complete multi-turn flow
  - Test full conversation: query → clarification → selection → results
  - Test with sample data (francis, TEST)
  - _Requirements: 8.2, 14.4_

- [ ] 8. Checkpoint - Ensure all integration tests pass
  - Run all integration tests for Chat V2 with conversation flow
  - Verify existing Chat V2 features still work (no breaking changes)
  - Verify Phase 1 & 2 tests still pass (regression check)
  - Ask the user if questions arise

- [ ] 9. Create comprehensive random data tests
  - Create `tests/test_random_data_conversation.py`
  - Generate random person names NOT in original sample (john santos, maria reyes, pedro cruz)
  - Generate random project names NOT in original sample (Manila Building, Cebu Tower)
  - Add random test data to test database
  - Test selection detection with random names
  - Test multi-turn conversation with random data
  - Document that NO code changes were needed for new data
  - _Requirements: 9.1, 9.2, 9.4, 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ]* 9.1 Write property test for data-agnostic selection detection
  - **Property 19: Data-Agnostic Selection Detection**
  - **Validates: Requirements 9.1, 9.2, 9.4, 13.2, 13.3**

- [ ]* 9.2 Write property test for no hardcoded identifiers
  - **Property 20: No Hardcoded Identifiers**
  - **Validates: Requirements 9.5**

- [ ]* 9.3 Write integration test for random data multi-turn conversation
  - Test complete flow with completely novel data
  - Verify system works without code changes
  - _Requirements: 13.4_

- [x] 10. Create data models and type definitions
  - Create `app/models/selection.py` with SelectionStrategy enum
  - Create SelectionResult dataclass
  - Create ClarificationState dataclass
  - Add type hints to all new functions
  - _Requirements: Design - Data Models section_

- [x] 11. Update existing components for integration
  - Verify `semantic_extractor_v2.py` requires no changes
  - Verify `conversation_store.py` schema requires no changes
  - Verify existing clarification logic in Chat V2 is reused
  - Update imports in `chat_v2.py` as needed
  - _Requirements: 14.1, 14.2, 14.3, 14.5_

- [ ]* 11.1 Write integration tests for existing component compatibility
  - Test that Semantic_Extractor_V2 still works
  - Test that Conversation_Store schema is unchanged
  - Test that existing Chat V2 features work
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 12. Final checkpoint - Comprehensive testing
  - Run ALL tests (unit, property, integration)
  - Verify all 20 correctness properties pass
  - Verify all requirements are covered
  - Verify no regressions in Phase 1 & 2
  - Verify system works with random data
  - Ask the user if questions arise

- [x] 13. Create documentation
  - Create `PHASE3_INTEGRATION_COMPLETE.md` documenting:
    - What was implemented
    - How to use the new features
    - Examples of multi-turn conversations
    - Proof of data-agnostic operation with random data
    - Test results summary
  - Update existing documentation if needed

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Random data tests prove data-agnostic operation
- All existing Phase 1 & 2 functionality must continue working (no breaking changes)
