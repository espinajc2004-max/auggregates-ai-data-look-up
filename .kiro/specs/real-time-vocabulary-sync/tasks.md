# Implementation Plan: Real-Time Vocabulary Sync

## Overview

This implementation plan breaks down the Real-Time Vocabulary Sync feature into discrete coding tasks. The approach follows this sequence:

1. Create database triggers and migration
2. Implement Redis listener bridge service
3. Add manual refresh API endpoint
4. Update application startup to initialize listener
5. Add configuration for PostgreSQL connection
6. Write property-based tests for correctness properties
7. Write unit tests for edge cases and error handling

Each task builds incrementally, with checkpoints to ensure functionality works before proceeding.

## Tasks

- [ ] 1. Create database migration for vocabulary sync triggers
  - Create migration file `supabase/migrations/YYYYMMDD_vocabulary_sync_triggers.sql`
  - Implement `notify_vocabulary_change()` trigger function with error handling
  - Create AFTER INSERT OR UPDATE OR DELETE triggers on all five vocabulary tables: Project, Expenses, CashFlow, ExpensesColumn, CashFlowColumn
  - Use `pg_notify('vocabulary_changed', TG_TABLE_NAME)` to publish notifications
  - Include exception handling to prevent blocking database operations
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 1.1 Write property test for database trigger notifications
  - **Property 1: Database triggers publish notifications for all operations**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.5**

- [ ] 2. Implement Redis listener bridge service
  - [ ] 2.1 Create `app/services/vocabulary_sync_bridge.py`
    - Implement `VocabularySyncBridge` class with PostgreSQL LISTEN/NOTIFY support
    - Use `psycopg2` for PostgreSQL connection with `LISTEN vocabulary_changed`
    - Use `select.select()` for non-blocking notification polling
    - Forward notifications to Redis Pub/Sub channel 'vocabulary_updated'
    - Include connection error handling and logging
    - _Requirements: 1.5, 2.1_
  
  - [ ] 2.2 Add bridge service entry point
    - Implement `run_bridge()` function as main entry point
    - Add graceful shutdown handling (KeyboardInterrupt)
    - Include automatic reconnection logic with exponential backoff
    - _Requirements: 1.5_
  
  - [ ]* 2.3 Write unit tests for bridge service error handling
    - Test PostgreSQL connection failure handling
    - Test Redis connection failure handling
    - Test graceful shutdown
    - _Requirements: 1.5_

- [ ] 3. Add manual refresh API endpoint
  - [ ] 3.1 Create `app/api/routes/vocabulary.py`
    - Implement POST /api/vocabulary/refresh endpoint
    - Call `redis_vocabulary_cache.refresh_cache()` on request
    - Return HTTP 200 with vocabulary counts on success
    - Return HTTP 500 with error message on failure
    - Log all manual refresh operations
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ] 3.2 Register vocabulary router in main.py
    - Import vocabulary router
    - Add `app.include_router(vocabulary.router)` to main.py
    - _Requirements: 4.1_
  
  - [ ]* 3.3 Write property test for manual refresh endpoint
    - **Property 6: Manual refresh endpoint triggers cache update**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

- [ ] 4. Checkpoint - Test database triggers and API endpoint
  - Apply database migration to test environment
  - Start bridge service
  - Insert test vocabulary data
  - Verify notifications are published
  - Call POST /api/vocabulary/refresh
  - Verify cache is updated
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Update application startup initialization
  - [ ] 5.1 Modify `app/main.py` startup_event
    - Ensure `redis_vocabulary_cache.start_listener()` is called
    - Ensure `redis_vocabulary_cache.refresh_cache()` is called for initial population
    - Add error handling for Redis initialization failures
    - Log all initialization steps
    - _Requirements: 5.1, 5.2, 5.3, 5.5_
  
  - [ ]* 5.2 Write unit tests for startup initialization
    - Test RedisVocabularyCache initializes on startup
    - Test listener thread starts
    - Test initial cache refresh occurs
    - Test graceful handling when Redis unavailable
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [ ] 6. Add PostgreSQL configuration for bridge service
  - [ ] 6.1 Update `app/config.py`
    - Add SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD config variables
    - Load from environment variables with defaults
    - _Requirements: 6.1_
  
  - [ ] 6.2 Update `.env.example` with PostgreSQL connection variables
    - Document required environment variables for bridge service
    - Include example values
    - _Requirements: 6.1_

- [ ] 7. Implement cache refresh completeness verification
  - [ ] 7.1 Update `RedisVocabularyCache.refresh_cache()` method
    - Ensure all six vocabulary fields are included: projects, project_locations, expense_files, cashflow_files, expense_categories, cashflow_categories
    - Verify JSON serialization includes all fields
    - Add logging with vocabulary counts for each field
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 7.2 Write property test for cache refresh completeness
    - **Property 3: Cache refresh updates all vocabulary data**
    - **Validates: Requirements 2.2, 2.3, 2.4, 7.1, 7.2, 7.3, 7.4, 7.5**

- [ ] 8. Implement and test fallback behavior
  - [ ] 8.1 Verify fallback logic in `RedisVocabularyCache.get_vocabulary()`
    - Ensure fallback to VocabularyLoader when Redis unavailable
    - Ensure fallback on Redis connection errors during operation
    - Add logging for fallback mode usage
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ]* 8.2 Write property test for fallback mode accuracy
    - **Property 4: Fallback mode provides accurate vocabulary data**
    - **Validates: Requirements 3.2, 3.3, 3.4**
  
  - [ ]* 8.3 Write property test for Redis reconnection
    - **Property 5: Redis reconnection after failure**
    - **Validates: Requirements 3.5**
  
  - [ ]* 8.4 Write unit test for Redis unavailable at startup
    - Test warning logged when Redis unavailable
    - Test application continues initialization
    - _Requirements: 3.1_

- [ ] 9. Checkpoint - Test end-to-end vocabulary sync
  - Start application with Redis and bridge service
  - Insert new project into database
  - Wait 2 seconds
  - Query vocabulary via AI system
  - Verify new project is detected
  - Verify cache refresh logged
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Write property tests for listener and trigger behavior
  - [ ]* 10.1 Write property test for listener initialization
    - **Property 7: Listener initialization and subscription**
    - **Validates: Requirements 5.2, 5.3**
  
  - [ ]* 10.2 Write property test for trigger payload
    - **Property 8: Trigger function includes table name in payload**
    - **Validates: Requirements 6.4**
  
  - [ ]* 10.3 Write property test for trigger error handling
    - **Property 9: Trigger function handles errors gracefully**
    - **Validates: Requirements 6.5**

- [ ] 11. Write property tests for performance and reliability
  - [ ]* 11.1 Write property test for cache refresh timing
    - **Property 2: Cache refresh completes within time bound**
    - **Validates: Requirements 2.1, 8.1**
  
  - [ ]* 11.2 Write property test for listener crash fallback
    - **Property 10: Listener crash fallback behavior**
    - **Validates: Requirements 8.3**
  
  - [ ]* 11.3 Write unit test for cache TTL configuration
    - Test cache TTL is set to 3600 seconds
    - _Requirements: 8.4_

- [ ] 12. Create deployment documentation
  - [ ] 12.1 Create `docs/vocabulary_sync_deployment.md`
    - Document bridge service deployment options (systemd, Docker Compose, supervisor)
    - Document database migration deployment steps
    - Document Redis deployment recommendations
    - Document monitoring and alerting setup
    - Document rollback plan
    - _Requirements: All_
  
  - [ ] 12.2 Create bridge service startup scripts
    - Create systemd service file example
    - Create Docker Compose configuration example
    - Create supervisor configuration example
    - _Requirements: All_

- [ ] 13. Final checkpoint - Complete system verification
  - Run all unit tests and property tests
  - Verify all 10 correctness properties pass
  - Test manual refresh endpoint
  - Test fallback mode when Redis unavailable
  - Test bridge service restart recovery
  - Verify deployment documentation is complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation at key milestones
- Bridge service must run as separate process alongside FastAPI application
- System gracefully degrades to fallback mode if Redis or bridge service unavailable
