# Requirements Document: System Simplification

## Introduction

The AU-Aggregates AI system has accumulated complexity through incremental feature additions, including Redis caching, multilingual support, and various Supabase resources. This simplification effort aims to reduce system complexity by 30-40% while maintaining all core English-language functionality. The focus is on removing Redis vocabulary caching, eliminating Tagalog language support, auditing Supabase resources, and consolidating duplicate services.

## Glossary

- **System**: The AU-Aggregates AI query processing system
- **Redis_Cache**: The Redis-based vocabulary caching layer
- **Vocabulary_Loader**: The service responsible for loading vocabulary data from Supabase
- **Intent_Detector**: The service that identifies user query intent using keyword matching
- **Semantic_Extractor**: The service that extracts semantic meaning from queries
- **Router_Service**: The service that routes queries to appropriate handlers
- **Supabase**: The backend database and API platform
- **Migration**: A database schema change script
- **RPC_Function**: A remote procedure call function stored in Supabase
- **Trigger**: A database trigger that executes automatically on data changes
- **English_Query**: A user query written in English language
- **Tagalog_Query**: A user query written in Tagalog language (to be removed)

## Requirements

### Requirement 1: Redis Cache Removal

**User Story:** As a system administrator, I want to remove the Redis vocabulary cache, so that the system has fewer dependencies and reduced operational complexity.

#### Acceptance Criteria

1. THE System SHALL load vocabulary data directly from Supabase without Redis caching
2. WHEN the System starts, THE Vocabulary_Loader SHALL fetch vocabulary data from Supabase
3. THE System SHALL NOT initialize or connect to Redis services
4. THE System SHALL NOT include Redis configuration in environment variables
5. THE System SHALL NOT include Redis dependencies in package requirements
6. WHEN vocabulary data is requested, THE System SHALL return fresh data from Supabase
7. THE System SHALL maintain or improve query response times compared to the Redis-cached version

### Requirement 2: Tagalog Language Support Removal

**User Story:** As a developer, I want to remove all Tagalog language support, so that the codebase is simpler and focuses on English-only queries.

#### Acceptance Criteria

1. THE Intent_Detector SHALL recognize only English keywords for intent classification
2. THE Semantic_Extractor SHALL process only English temporal expressions
3. THE Router_Service SHALL handle only English query patterns
4. THE System SHALL return error messages only in English
5. THE System SHALL NOT contain Tagalog keywords in any service module
6. THE System SHALL NOT contain Tagalog error messages or user-facing text
7. WHEN a query is processed, THE System SHALL use only English language rules and patterns
8. THE System SHALL remove Tagalog test cases from test suites

### Requirement 3: Supabase Resource Audit and Cleanup

**User Story:** As a database administrator, I want to identify and remove unused Supabase resources, so that the database schema is clean and maintainable.

#### Acceptance Criteria

1. THE System SHALL identify all unused database migrations
2. THE System SHALL identify all unused RPC functions
3. THE System SHALL identify all unused database triggers
4. THE System SHALL document which Supabase resources are actively used
5. THE System SHALL remove unused migrations that do not affect production data
6. THE System SHALL remove unused RPC functions that are not called by the application
7. THE System SHALL remove unused triggers that do not serve active functionality
8. WHEN database resources are removed, THE System SHALL maintain all production functionality

### Requirement 4: Service Consolidation

**User Story:** As a developer, I want to consolidate duplicate and similar services, so that the codebase is more maintainable and has less redundancy.

#### Acceptance Criteria

1. THE System SHALL use only one semantic extraction service (semantic_extractor_v2.py)
2. THE System SHALL remove the deprecated semantic_extractor.py service
3. THE System SHALL update all references to use the consolidated service
4. THE System SHALL identify other duplicate or similar services
5. THE System SHALL consolidate identified duplicate services into single implementations
6. WHEN services are consolidated, THE System SHALL maintain all existing functionality
7. THE System SHALL remove unused configuration variables from config files

### Requirement 5: Backward Compatibility

**User Story:** As a system operator, I want all existing English queries to continue working, so that production functionality is not disrupted.

#### Acceptance Criteria

1. THE System SHALL process all existing English query patterns correctly
2. THE System SHALL maintain all security and permission checks
3. THE System SHALL maintain all API endpoint functionality
4. THE System SHALL return correct results for all supported English query types
5. WHEN an English query is processed, THE System SHALL produce results equivalent to the pre-simplification version
6. THE System SHALL maintain response time performance for English queries

### Requirement 6: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive tests to validate the simplified system, so that I can verify all functionality works correctly.

#### Acceptance Criteria

1. THE System SHALL pass all existing English query tests
2. THE System SHALL pass all API endpoint tests
3. THE System SHALL pass all permission and security tests
4. THE System SHALL NOT include tests for removed Tagalog functionality
5. THE System SHALL NOT include tests for removed Redis functionality
6. WHEN vocabulary loading is tested, THE System SHALL successfully load data without Redis
7. WHEN intent detection is tested, THE System SHALL correctly identify intents using English keywords only
8. THE System SHALL demonstrate no performance degradation in test results

### Requirement 7: Code Complexity Reduction

**User Story:** As a developer, I want the codebase to be 30-40% less complex, so that it is easier to understand, maintain, and onboard new developers.

#### Acceptance Criteria

1. THE System SHALL reduce total lines of code by at least 30%
2. THE System SHALL reduce the number of service files by removing unused services
3. THE System SHALL reduce the number of configuration variables
4. THE System SHALL reduce the number of external dependencies
5. THE System SHALL reduce the number of language-specific code paths
6. THE System SHALL maintain clear separation of concerns in remaining services
7. WHEN code complexity is measured, THE System SHALL show measurable improvement in maintainability metrics

### Requirement 8: Documentation and Migration

**User Story:** As a system administrator, I want clear documentation of all changes, so that I can safely deploy the simplified system.

#### Acceptance Criteria

1. THE System SHALL document all removed Redis configuration variables
2. THE System SHALL document all removed Tagalog keywords and patterns
3. THE System SHALL document all removed Supabase resources
4. THE System SHALL document all consolidated services
5. THE System SHALL provide a migration guide for deployment
6. THE System SHALL document any required environment variable changes
7. WHEN deploying the simplified system, THE System SHALL provide rollback procedures for each phase
