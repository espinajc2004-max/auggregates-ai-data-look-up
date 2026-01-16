# Implementation Tasks: Text-to-SQL Analytics

## Overview

This document outlines the implementation tasks for adding Text-to-SQL analytics capability to the AU-Ggregates AI system. The implementation follows a three-phase approach:

- **Phase 1**: Semantic search using embeddings + pgvector (3-4 days)
- **Phase 2**: Text-to-SQL model integration on remote GPU (1-2 weeks)
- **Phase 3**: Integration, testing, and optimization (3-4 days)

**Total Estimated Time**: 2.5-3 weeks

---

## Phase 1: Semantic Search with Embeddings (3-4 days)

### Task 1: Set up pgvector extension in Supabase

**Description**: Enable pgvector extension and add embedding column to ai_documents table

**Subtasks**:
- [ ] 1.1 Create migration file `supabase/migrations/YYYYMMDD_add_pgvector.sql`
- [ ] 1.2 Add `CREATE EXTENSION IF NOT EXISTS vector;` statement
- [ ] 1.3 Add `embedding vector(768)` column to ai_documents table
- [ ] 1.4 Create IVFFlat index on embedding column for fast similarity search
- [ ] 1.5 Apply migration to Supabase using MCP tool
- [ ] 1.6 Verify extension and column are created successfully

**Acceptance Criteria**:
- pgvector extension is enabled
- ai_documents table has embedding column (768 dimensions)
- Vector similarity index is created
- Migration applies without errors

**Estimated Time**: 1 hour

---

### Task 2: Create EmbeddingsService

**Description**: Implement service to generate semantic embeddings using multilingual-e5-base model

**Subtasks**:
- [ ] 2.1 Create `app/services/embedding_service.py`
- [ ] 2.2 Install required dependencies: `sentence-transformers`, `torch`
- [ ] 2.3 Implement `EmbeddingsService` class with model loading
- [ ] 2.4 Implement `encode_query()` method for query embeddings
- [ ] 2.5 Implement `encode_document()` method for document embeddings
- [ ] 2.6 Implement `batch_encode()` method for efficient batch processing
- [ ] 2.7 Add device detection (CUDA vs CPU)
- [ ] 2.8 Add error handling and logging
- [ ] 2.9 Create unit tests for EmbeddingsService

**Acceptance Criteria**:
- EmbeddingsService loads multilingual-e5-base model successfully
- encode_query() returns 768-dimensional vector
- encode_document() returns 768-dimensional vector
- batch_encode() processes multiple texts efficiently
- Service works on both CPU and GPU
- Unit tests pass

**Estimated Time**: 4 hours

---

### Task 3: Create hybrid search database function

**Description**: Create PostgreSQL function for hybrid semantic + keyword search

**Subtasks**:
- [ ] 3.1 Create migration file `supabase/migrations/YYYYMMDD_add_hybrid_search.sql`
- [ ] 3.2 Implement `ai_search_hybrid()` function with parameters:
  - p_query_embedding (vector)
  - p_search_term (text)
  - p_source_table (text, optional)
  - p_project_id (text, optional)
  - p_limit (integer, default 20)
  - p_semantic_weight (float, default 0.7)
- [ ] 3.3 Calculate semantic score using cosine similarity
- [ ] 3.4 Calculate keyword score using ts_rank
- [ ] 3.5 Combine scores with weighted average
- [ ] 3.6 Return results sorted by combined score
- [ ] 3.7 Apply migration to Supabase
- [ ] 3.8 Test function with sample queries

**Acceptance Criteria**:
- ai_search_hybrid() function is created
- Function accepts embedding vector and search term
- Function returns combined semantic + keyword scores
- Results are ranked by combined score
- Function respects source_table and project_id filters
- Migration applies without errors

**Estimated Time**: 3 hours

---

### Task 4: Generate embeddings for existing documents

**Description**: Create script to generate and store embeddings for all existing ai_documents rows

**Subtasks**:
- [ ] 4.1 Create `scripts/generate_embeddings.py` script
- [ ] 4.2 Fetch all ai_documents rows without embeddings
- [ ] 4.3 Process documents in batches of 100
- [ ] 4.4 Generate embeddings using EmbeddingsService
- [ ] 4.5 Update ai_documents rows with embeddings
- [ ] 4.6 Add progress logging (e.g., "Processed 500/2000 documents")
- [ ] 4.7 Add error handling for failed embeddings
- [ ] 4.8 Run script to index all existing documents
- [ ] 4.9 Verify embeddings are stored correctly

**Acceptance Criteria**:
- Script processes all ai_documents rows
- Embeddings are generated in batches
- Progress is logged during processing
- All documents have embeddings after script completes
- Script handles errors gracefully

**Estimated Time**: 3 hours

---

### Task 5: Update UniversalHandler to use hybrid search

**Description**: Enhance UniversalHandler to use semantic + keyword hybrid search

**Subtasks**:
- [ ] 5.1 Update `app/services/query_handlers/universal_handler.py`
- [ ] 5.2 Import EmbeddingsService
- [ ] 5.3 Modify `search()` method to generate query embedding
- [ ] 5.4 Call `ai_search_hybrid()` function with embedding + search term
- [ ] 5.5 Keep existing keyword-only search as fallback
- [ ] 5.6 Add semantic_score to result items
- [ ] 5.7 Update result formatting to show semantic relevance
- [ ] 5.8 Add configuration flag to enable/disable semantic search
- [ ] 5.9 Test hybrid search with sample queries

**Acceptance Criteria**:
- UniversalHandler uses hybrid search by default
- Query embeddings are generated for each search
- Results include both semantic and keyword scores
- Fallback to keyword-only search if embeddings fail
- Configuration flag controls semantic search feature
- Existing tests still pass

**Estimated Time**: 4 hours

---

### Task 6: Test Phase 1 implementation

**Description**: Create comprehensive tests for semantic search functionality

**Subtasks**:
- [ ] 6.1 Create `test_semantic_search.py`
- [ ] 6.2 Test EmbeddingsService with English queries
- [ ] 6.3 Test EmbeddingsService with Tagalog queries
- [ ] 6.4 Test hybrid search function directly
- [ ] 6.5 Test UniversalHandler with semantic search enabled
- [ ] 6.6 Test semantic search finds relevant results
- [ ] 6.7 Test semantic search handles typos better than keyword
- [ ] 6.8 Test semantic search respects role-based access control
- [ ] 6.9 Test fallback to keyword search when embeddings fail
- [ ] 6.10 Run all tests and verify they pass

**Acceptance Criteria**:
- All semantic search tests pass
- Semantic search improves relevance over keyword-only
- Semantic search works for both English and Tagalog
- RBAC is enforced in semantic search results
- Fallback mechanism works correctly

**Estimated Time**: 3 hours

---

## Phase 2: Text-to-SQL Model Integration (1-2 weeks)

### Task 7: Set up Modal.com deployment

**Description**: Create Modal.com deployment for Text-to-SQL model

**Subtasks**:
- [ ] 7.1 Install Modal CLI: `pip install modal`
- [ ] 7.2 Create Modal account and get API token
- [ ] 7.3 Create `modal_text_to_sql.py` deployment script
- [ ] 7.4 Configure GPU instance (T4 or A10G)
- [ ] 7.5 Add model dependencies: transformers, torch, accelerate, bitsandbytes
- [ ] 7.6 Implement `generate_sql()` function with 8-bit quantization
- [ ] 7.7 Add prompt template with schema and role information
- [ ] 7.8 Deploy to Modal: `modal deploy modal_text_to_sql.py`
- [ ] 7.9 Test deployment with sample query
- [ ] 7.10 Get API endpoint URL and save to .env

**Acceptance Criteria**:
- Modal.com deployment is successful
- Text-to-SQL model loads with 8-bit quantization
- API endpoint is accessible
- Sample query returns valid SQL
- Deployment uses T4 or A10G GPU

**Estimated Time**: 4 hours

---

### Task 8: Create TextToSQLService

**Description**: Implement service to communicate with Modal.com Text-to-SQL API

**Subtasks**:
- [ ] 8.1 Create `app/services/text_to_sql_service.py`
- [ ] 8.2 Implement `TextToSQLService` class
- [ ] 8.3 Add configuration for Modal API URL and key
- [ ] 8.4 Implement `generate_sql()` method with HTTP requests
- [ ] 8.5 Add retry logic (max 3 retries)
- [ ] 8.6 Add timeout handling (10 seconds)
- [ ] 8.7 Implement `health_check()` method
- [ ] 8.8 Add error handling and logging
- [ ] 8.9 Create unit tests for TextToSQLService

**Acceptance Criteria**:
- TextToSQLService communicates with Modal API
- generate_sql() returns SQL query
- Retry logic handles transient failures
- Timeout prevents hanging requests
- health_check() verifies service availability
- Unit tests pass

**Estimated Time**: 3 hours

---

### Task 9: Create SchemaProvider

**Description**: Implement service to provide database schema information to Text-to-SQL model

**Subtasks**:
- [ ] 9.1 Create `app/services/schema_provider.py`
- [ ] 9.2 Define TableSchema, ColumnInfo, ForeignKeyInfo dataclasses
- [ ] 9.3 Implement `SchemaProvider` class
- [ ] 9.4 Add schema definitions for Expenses, CashFlow, Project, Quotation
- [ ] 9.5 Implement `get_schema()` method with role filtering
- [ ] 9.6 Implement `format_for_prompt()` method
- [ ] 9.7 Add schema descriptions and column descriptions
- [ ] 9.8 Add foreign key relationship information
- [ ] 9.9 Create unit tests for SchemaProvider

**Acceptance Criteria**:
- SchemaProvider returns complete schema information
- Schema is filtered by user role (ENCODER excludes CashFlow)
- format_for_prompt() generates Text-to-SQL compatible format
- Schema includes table/column descriptions
- Foreign key relationships are included
- Unit tests pass

**Estimated Time**: 3 hours

---

### Task 10: Create SQLValidator

**Description**: Implement SQL validation service for safety and correctness

**Subtasks**:
- [ ] 10.1 Create `app/services/sql_validator.py`
- [ ] 10.2 Install sqlparse library: `pip install sqlparse`
- [ ] 10.3 Implement `SQLValidator` class
- [ ] 10.4 Implement `validate()` method with all checks
- [ ] 10.5 Implement `_check_injection()` for SQL injection patterns
- [ ] 10.6 Implement `_check_write_operations()` for INSERT/UPDATE/DELETE
- [ ] 10.7 Implement `_check_role_access()` for RBAC
- [ ] 10.8 Implement `_parse_sql()` using sqlparse
- [ ] 10.9 Add validation for multiple statements
- [ ] 10.10 Create comprehensive unit tests for SQLValidator

**Acceptance Criteria**:
- SQLValidator rejects SQL injection attempts
- SQLValidator rejects write operations (INSERT, UPDATE, DELETE)
- SQLValidator enforces role-based table access
- SQLValidator rejects multiple statements
- SQLValidator parses SQL correctly
- All validation tests pass

**Estimated Time**: 4 hours

---

### Task 11: Create AnalyticsHandler

**Description**: Implement handler for analytics queries using Text-to-SQL pipeline

**Subtasks**:
- [ ] 11.1 Create `app/services/analytics_handler.py`
- [ ] 11.2 Implement `AnalyticsHandler` class
- [ ] 11.3 Inject dependencies: TextToSQLService, SQLValidator, SupabaseClient
- [ ] 11.4 Implement `handle_query()` method with full pipeline
- [ ] 11.5 Implement `_generate_sql()` with retry logic
- [ ] 11.6 Implement `_execute_sql()` with timeout
- [ ] 11.7 Implement `_format_results()` for user-friendly responses
- [ ] 11.8 Implement `_fallback_to_universal()` for error cases
- [ ] 11.9 Add logging for all pipeline steps
- [ ] 11.10 Create unit tests for AnalyticsHandler

**Acceptance Criteria**:
- AnalyticsHandler executes full Text-to-SQL pipeline
- Pipeline includes: generation → validation → execution → formatting
- Fallback to UniversalHandler on any failure
- Retry logic handles transient failures
- Query timeout prevents long-running queries
- Unit tests pass

**Estimated Time**: 5 hours

---

### Task 12: Create ResultsFormatter

**Description**: Implement service to format SQL results into natural language responses

**Subtasks**:
- [ ] 12.1 Create `app/services/results_formatter.py`
- [ ] 12.2 Implement `ResultsFormatter` class
- [ ] 12.3 Implement `format_analytics_results()` method
- [ ] 12.4 Implement `_detect_aggregation_type()` to identify SUM/COUNT/AVG
- [ ] 12.5 Implement `_format_number()` with locale support (PHP currency)
- [ ] 12.6 Implement `_translate_response()` for Tagalog responses
- [ ] 12.7 Add templates for different aggregation types
- [ ] 12.8 Add support for grouped results (GROUP BY)
- [ ] 12.9 Create unit tests for ResultsFormatter

**Acceptance Criteria**:
- ResultsFormatter generates natural language responses
- Numbers are formatted with proper locale (₱ for PHP)
- Responses match query language (English/Tagalog)
- Different aggregation types have appropriate templates
- Grouped results are formatted clearly
- Unit tests pass

**Estimated Time**: 3 hours

---

### Task 13: Enhance Router for analytics intent

**Description**: Add ANALYTICS intent classification to existing DistilBERT router

**Subtasks**:
- [ ] 13.1 Update `app/services/router_service.py`
- [ ] 13.2 Add "ANALYTICS" to INTENT_LABELS list
- [ ] 13.3 Update fallback logic to detect analytics patterns
- [ ] 13.4 Add analytics keywords: total, sum, average, count, compare
- [ ] 13.5 Add Tagalog analytics keywords: kabuuan, average, bilang
- [ ] 13.6 Update RouterOutput to handle ANALYTICS intent
- [ ] 13.7 Test router with analytics queries
- [ ] 13.8* Optionally retrain router with analytics examples (500-1000 examples)

**Acceptance Criteria**:
- Router can classify ANALYTICS intent
- Fallback logic detects analytics patterns
- Both English and Tagalog analytics queries are detected
- Router tests pass with analytics queries
- Optional: Retrained model improves analytics detection accuracy

**Estimated Time**: 2 hours (+ 4 hours if retraining)

---

### Task 14: Update chat endpoint to route analytics queries

**Description**: Integrate AnalyticsHandler into chat endpoint routing logic

**Subtasks**:
- [ ] 14.1 Update `app/api/routes/chat.py`
- [ ] 14.2 Import AnalyticsHandler
- [ ] 14.3 Add analytics routing logic after router classification
- [ ] 14.4 Route ANALYTICS intent to AnalyticsHandler
- [ ] 14.5 Keep existing routing for other intents
- [ ] 14.6 Add fallback from AnalyticsHandler to UniversalHandler
- [ ] 14.7 Update response formatting for analytics results
- [ ] 14.8 Add logging for analytics routing
- [ ] 14.9 Test chat endpoint with analytics queries

**Acceptance Criteria**:
- Chat endpoint routes ANALYTICS intent to AnalyticsHandler
- Other intents still route to existing handlers
- Fallback mechanism works correctly
- Analytics responses are formatted properly
- Existing chat functionality is not broken

**Estimated Time**: 2 hours

---

### Task 15: Update configuration for Text-to-SQL

**Description**: Add configuration settings for Text-to-SQL services

**Subtasks**:
- [ ] 15.1 Update `app/config.py`
- [ ] 15.2 Add MODAL_API_URL configuration
- [ ] 15.3 Add MODAL_API_KEY configuration
- [ ] 15.4 Add TEXT_TO_SQL_ENABLED feature flag
- [ ] 15.5 Add TEXT_TO_SQL_TIMEOUT setting (default 10s)
- [ ] 15.6 Add TEXT_TO_SQL_MAX_RETRIES setting (default 3)
- [ ] 15.7 Add SEMANTIC_SEARCH_WEIGHT setting (default 0.7)
- [ ] 15.8 Update .env.example with new variables
- [ ] 15.9 Document configuration in README

**Acceptance Criteria**:
- Config includes all Text-to-SQL settings
- Feature flag allows enabling/disabling Text-to-SQL
- Timeout and retry settings are configurable
- .env.example is updated
- Configuration is documented

**Estimated Time**: 1 hour

---

## Phase 3: Integration, Testing, and Optimization (3-4 days)

### Task 16: Create comprehensive integration tests

**Description**: Test full Text-to-SQL pipeline end-to-end

**Subtasks**:
- [ ] 16.1 Create `test_text_to_sql_integration.py`
- [ ] 16.2 Test simple aggregation query (SUM)
- [ ] 16.3 Test COUNT query
- [ ] 16.4 Test AVG query
- [ ] 16.5 Test GROUP BY query
- [ ] 16.6 Test date range filtering
- [ ] 16.7 Test multi-condition WHERE clauses
- [ ] 16.8 Test Tagalog analytics queries
- [ ] 16.9 Test role-based access control (ENCODER vs ADMIN)
- [ ] 16.10 Test fallback to UniversalHandler
- [ ] 16.11 Test SQL injection prevention
- [ ] 16.12 Test write operation rejection
- [ ] 16.13 Run all integration tests

**Acceptance Criteria**:
- All integration tests pass
- Text-to-SQL pipeline works end-to-end
- RBAC is enforced correctly
- Security validations work
- Fallback mechanism works
- Both English and Tagalog queries work

**Estimated Time**: 6 hours

---

### Task 17: Performance optimization

**Description**: Optimize Text-to-SQL pipeline for response time

**Subtasks**:
- [ ] 17.1 Profile Text-to-SQL generation time
- [ ] 17.2 Profile SQL execution time
- [ ] 17.3 Add caching for frequently used SQL patterns
- [ ] 17.4 Optimize database queries with indexes
- [ ] 17.5 Implement connection pooling for Supabase
- [ ] 17.6 Add request batching for Modal API
- [ ] 17.7 Measure end-to-end response time
- [ ] 17.8 Verify 80% of queries complete within 1 second
- [ ] 17.9 Document performance metrics

**Acceptance Criteria**:
- 80% of analytics queries complete within 1 second
- SQL generation completes within 500ms for 90% of queries
- Caching reduces repeated query time
- Database queries are optimized
- Performance metrics are documented

**Estimated Time**: 4 hours

---

### Task 18: Create monitoring and logging

**Description**: Implement comprehensive logging and monitoring for Text-to-SQL

**Subtasks**:
- [ ] 18.1 Add structured logging for all Text-to-SQL operations
- [ ] 18.2 Log SQL generation requests and responses
- [ ] 18.3 Log validation failures with specific rules violated
- [ ] 18.4 Log SQL execution errors with stack traces
- [ ] 18.5 Track metrics: success rate, response time, fallback rate
- [ ] 18.6 Create dashboard or API endpoint for metrics
- [ ] 18.7 Add alerting for high failure rates
- [ ] 18.8 Document logging format and metrics

**Acceptance Criteria**:
- All Text-to-SQL operations are logged
- Validation failures include specific error details
- Metrics are tracked and accessible
- Dashboard or API shows Text-to-SQL analytics
- Alerting is configured for failures

**Estimated Time**: 3 hours

---

### Task 19: Create user documentation

**Description**: Document Text-to-SQL feature for users and developers

**Subtasks**:
- [ ] 19.1 Create `docs/TEXT_TO_SQL_USER_GUIDE.md`
- [ ] 19.2 Document supported analytics query types
- [ ] 19.3 Provide example queries (English and Tagalog)
- [ ] 19.4 Document limitations and edge cases
- [ ] 19.5 Create `docs/TEXT_TO_SQL_DEVELOPER_GUIDE.md`
- [ ] 19.6 Document architecture and components
- [ ] 19.7 Document deployment process (Modal.com)
- [ ] 19.8 Document configuration options
- [ ] 19.9 Document troubleshooting steps
- [ ] 19.10 Update main README with Text-to-SQL section

**Acceptance Criteria**:
- User guide explains how to use analytics queries
- Example queries are provided
- Developer guide explains architecture
- Deployment process is documented
- Troubleshooting guide is available
- README is updated

**Estimated Time**: 3 hours

---

### Task 20: Fine-tune Text-to-SQL model (Optional)

**Description**: Fine-tune SQLCoder model on construction domain data

**Subtasks**:
- [ ] 20.1* Create training dataset (500-1000 query-SQL pairs)
- [ ] 20.2* Include construction-specific terminology
- [ ] 20.3* Include Tagalog query examples
- [ ] 20.4* Set up fine-tuning environment
- [ ] 20.5* Fine-tune SQLCoder-7B-2 model
- [ ] 20.6* Evaluate fine-tuned model accuracy
- [ ] 20.7* Deploy fine-tuned model to Modal.com
- [ ] 20.8* Test fine-tuned model with real queries
- [ ] 20.9* Compare accuracy vs base model
- [ ] 20.10* Document fine-tuning process

**Acceptance Criteria**:
- Training dataset includes construction domain queries
- Fine-tuned model improves accuracy over base model
- Model handles Tagalog queries better
- Fine-tuned model is deployed to Modal.com
- Accuracy improvement is measured and documented

**Estimated Time**: 8-12 hours (optional)

---

## Task Summary

### Phase 1: Semantic Search (3-4 days)
- Task 1: Set up pgvector (1 hour)
- Task 2: Create EmbeddingsService (4 hours)
- Task 3: Create hybrid search function (3 hours)
- Task 4: Generate embeddings for existing documents (3 hours)
- Task 5: Update UniversalHandler (4 hours)
- Task 6: Test Phase 1 (3 hours)

**Phase 1 Total**: 18 hours (~3 days)

### Phase 2: Text-to-SQL Integration (1-2 weeks)
- Task 7: Set up Modal.com (4 hours)
- Task 8: Create TextToSQLService (3 hours)
- Task 9: Create SchemaProvider (3 hours)
- Task 10: Create SQLValidator (4 hours)
- Task 11: Create AnalyticsHandler (5 hours)
- Task 12: Create ResultsFormatter (3 hours)
- Task 13: Enhance Router (2 hours + optional 4 hours)
- Task 14: Update chat endpoint (2 hours)
- Task 15: Update configuration (1 hour)

**Phase 2 Total**: 27 hours (~1 week) + optional 4 hours for router retraining

### Phase 3: Integration and Testing (3-4 days)
- Task 16: Integration tests (6 hours)
- Task 17: Performance optimization (4 hours)
- Task 18: Monitoring and logging (3 hours)
- Task 19: User documentation (3 hours)
- Task 20: Fine-tune model (8-12 hours, optional)

**Phase 3 Total**: 16 hours (~2 days) + optional 8-12 hours for fine-tuning

### Grand Total
- **Minimum**: 61 hours (~2 weeks)
- **With Optional Tasks**: 77-81 hours (~2.5-3 weeks)

---

## Dependencies

### Python Packages
```
sentence-transformers>=2.2.0
torch>=2.0.0
transformers>=4.30.0
accelerate>=0.20.0
bitsandbytes>=0.41.0
sqlparse>=0.4.4
modal>=0.55.0
```

### External Services
- Modal.com account and API token
- Supabase with pgvector extension support

### Database
- PostgreSQL 14+ with pgvector extension
- Existing ai_documents table

---

## Notes

- Tasks marked with `*` are optional but recommended
- Estimated times are for a single developer
- Some tasks can be parallelized (e.g., Task 8-12 in Phase 2)
- Fine-tuning (Task 20) can be done after initial deployment
- Router retraining (Task 13) can be done incrementally

---

## Success Criteria

The Text-to-SQL Analytics feature is considered complete when:

1. ✅ Semantic search improves relevance over keyword-only search
2. ✅ Text-to-SQL generates valid SQL for analytics queries
3. ✅ SQL validation prevents injection and write operations
4. ✅ RBAC is enforced (ENCODER cannot access CashFlow)
5. ✅ 80% of queries complete within 1 second
6. ✅ Fallback to keyword search works correctly
7. ✅ Both English and Tagalog queries are supported
8. ✅ All integration tests pass
9. ✅ Monitoring and logging are in place
10. ✅ Documentation is complete
