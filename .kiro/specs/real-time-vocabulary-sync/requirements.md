# Requirements Document

## Introduction

The Real-Time Vocabulary Sync feature enables the AI system to automatically detect and reflect new data added to the database within 1-2 seconds. Currently, the vocabulary cache is loaded at application startup and does not refresh when new projects, categories, or files are added to Supabase. This feature implements automatic cache invalidation using database triggers and Redis Pub/Sub to ensure the AI always has access to the latest vocabulary data.

## Glossary

- **Vocabulary**: The collection of known entities (projects, categories, files) that the AI uses for entity matching and query understanding
- **VocabularyLoader**: Python service that loads vocabulary data from Supabase database tables
- **RedisVocabularyCache**: Python service that caches vocabulary in Redis and listens for update events via Pub/Sub
- **Database_Trigger**: PostgreSQL trigger that automatically executes when INSERT/UPDATE/DELETE operations occur on vocabulary tables
- **Redis_Pub_Sub**: Redis publish/subscribe messaging system for real-time event notifications
- **Vocabulary_Tables**: The five database tables containing vocabulary data: Project, Expenses, CashFlow, ExpensesColumn, CashFlowColumn
- **Cache_Refresh**: The process of reloading vocabulary data from the database into Redis cache
- **Manual_Refresh_Endpoint**: HTTP API endpoint that allows manual triggering of cache refresh
- **Startup_Listener**: Background thread that starts automatically when the application launches to listen for vocabulary update events

## Requirements

### Requirement 1: Automatic Database Change Detection

**User Story:** As a system administrator, I want the database to automatically detect when vocabulary data changes, so that the AI cache can be updated without manual intervention.

#### Acceptance Criteria

1. WHEN a new row is inserted into any Vocabulary_Table, THEN THE Database_Trigger SHALL publish a cache refresh event
2. WHEN an existing row is updated in any Vocabulary_Table, THEN THE Database_Trigger SHALL publish a cache refresh event
3. WHEN a row is deleted from any Vocabulary_Table, THEN THE Database_Trigger SHALL publish a cache refresh event
4. THE Database_Trigger SHALL execute on all five Vocabulary_Tables: Project, Expenses, CashFlow, ExpensesColumn, CashFlowColumn
5. WHEN a Database_Trigger executes, THEN THE System SHALL publish to the Redis_Pub_Sub channel 'vocabulary_updated'

### Requirement 2: Real-Time Cache Synchronization

**User Story:** As an AI system, I want to receive vocabulary updates within 1-2 seconds of database changes, so that I can accurately match user queries against the latest data.

#### Acceptance Criteria

1. WHEN a vocabulary update event is published, THEN THE RedisVocabularyCache SHALL detect it within 2 seconds
2. WHEN the RedisVocabularyCache detects an update event, THEN THE System SHALL reload vocabulary from the database
3. WHEN vocabulary is reloaded, THEN THE System SHALL update the Redis cache with the new data
4. WHEN the cache is updated, THEN THE System SHALL log the refresh operation with vocabulary counts
5. THE System SHALL maintain cache updates even when multiple servers are running (distributed cache)

### Requirement 3: Graceful Fallback Handling

**User Story:** As a system operator, I want the application to continue functioning when Redis is unavailable, so that vocabulary lookups still work even if the cache layer fails.

#### Acceptance Criteria

1. WHEN Redis is not available at startup, THEN THE System SHALL log a warning and continue initialization
2. WHEN Redis is not available, THEN THE RedisVocabularyCache SHALL fallback to VocabularyLoader for direct database queries
3. WHEN Redis connection fails during operation, THEN THE System SHALL catch the error and fallback to VocabularyLoader
4. WHEN operating in fallback mode, THEN THE System SHALL still provide accurate vocabulary data from the database
5. WHEN Redis becomes available again, THEN THE System SHALL automatically reconnect on the next cache operation

### Requirement 4: Manual Refresh API Endpoint

**User Story:** As a system administrator, I want a manual refresh endpoint, so that I can force a cache update for testing or troubleshooting purposes.

#### Acceptance Criteria

1. THE System SHALL provide an HTTP POST endpoint at /api/vocabulary/refresh
2. WHEN the refresh endpoint is called, THEN THE System SHALL trigger an immediate cache refresh
3. WHEN the refresh completes successfully, THEN THE System SHALL return HTTP 200 with a success message
4. WHEN the refresh fails, THEN THE System SHALL return HTTP 500 with an error message
5. WHEN the refresh endpoint is called, THEN THE System SHALL log the manual refresh operation

### Requirement 5: Automatic Listener Initialization

**User Story:** As a developer, I want the Redis listener to start automatically on application startup, so that real-time updates work immediately without manual configuration.

#### Acceptance Criteria

1. WHEN the FastAPI application starts, THEN THE System SHALL initialize the RedisVocabularyCache
2. WHEN RedisVocabularyCache is initialized, THEN THE System SHALL start the Startup_Listener thread
3. WHEN the Startup_Listener starts, THEN THE System SHALL subscribe to the 'vocabulary_updated' Redis channel
4. WHEN the Startup_Listener is running, THEN THE System SHALL continuously listen for update events in the background
5. WHEN the application starts, THEN THE System SHALL perform an initial Cache_Refresh to populate the cache

### Requirement 6: Database Trigger Implementation

**User Story:** As a database administrator, I want PostgreSQL triggers installed on vocabulary tables, so that cache refresh events are published automatically when data changes.

#### Acceptance Criteria

1. THE System SHALL provide a database migration script that creates the trigger function
2. THE Trigger_Function SHALL use PostgreSQL NOTIFY to publish events to Redis
3. THE System SHALL install triggers on all five Vocabulary_Tables using AFTER INSERT OR UPDATE OR DELETE
4. WHEN a trigger executes, THEN THE System SHALL include the table name in the notification payload
5. THE Trigger_Function SHALL handle errors gracefully without blocking the original database operation

### Requirement 7: Vocabulary Data Completeness

**User Story:** As an AI system, I want the cache to include all vocabulary fields, so that entity matching works correctly for all query types.

#### Acceptance Criteria

1. WHEN vocabulary is cached, THEN THE System SHALL include project names from the Project table
2. WHEN vocabulary is cached, THEN THE System SHALL include project locations from the Project table
3. WHEN vocabulary is cached, THEN THE System SHALL include file names from both Expenses and CashFlow tables
4. WHEN vocabulary is cached, THEN THE System SHALL include category names from both ExpensesColumn and CashFlowColumn tables
5. WHEN vocabulary is serialized to Redis, THEN THE System SHALL use JSON format with all six vocabulary fields

### Requirement 8: Performance and Reliability

**User Story:** As a system operator, I want the cache refresh to be fast and reliable, so that it doesn't impact application performance or user experience.

#### Acceptance Criteria

1. WHEN a cache refresh is triggered, THEN THE System SHALL complete the refresh within 5 seconds under normal load
2. WHEN multiple refresh events occur simultaneously, THEN THE System SHALL handle them without race conditions
3. WHEN the Redis listener thread crashes, THEN THE System SHALL log the error and continue serving requests using fallback mode
4. THE System SHALL set a cache TTL of 1 hour as a backup expiration policy
5. WHEN vocabulary data is large, THEN THE System SHALL still cache it efficiently without memory issues
