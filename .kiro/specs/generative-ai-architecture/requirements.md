# Requirements Document

## Introduction

This document specifies requirements for implementing a hybrid 3-stage architecture combining Mistral 7B and T5 models. The new system uses:
- **Stage 1 (Mistral)**: Intent understanding and ambiguity detection
- **Stage 2 (T5)**: Fast SQL generation from structured intent
- **Stage 3 (Mistral)**: Natural language response formatting in Taglish

This hybrid approach combines Mistral's intelligence for understanding and formatting with T5's speed and proven SQL generation capabilities, addressing critical bugs in the current system while maintaining performance.

The new architecture will be deployed on the user's own server with GPU (14GB available for Mistral) and CPU (for T5).

## Glossary

- **Mistral_Model**: The Mistral 7B language model used for intent understanding (Stage 1) and response formatting (Stage 3)
- **T5_Model**: The T5 text-to-SQL model used for SQL generation (Stage 2)
- **Stage_1_Intent**: Mistral extracts structured intent from natural language
- **Stage_2_SQL**: T5 generates SQL from structured intent
- **Stage_3_Response**: Mistral formats results into conversational Taglish
- **Hybrid_Architecture**: 3-stage pipeline combining Mistral and T5
- **Intent_Extraction**: Process of converting natural language to structured JSON intent
- **Construction_Domain**: The specific business domain including expenses, cashflow, projects, and documents
- **Conversation_Context**: The history of previous queries and responses in a conversation session
- **Clarification_Detection**: Mistral's ability to detect ambiguous queries and request clarification

## Requirements

### Requirement 1: Core Model Integration

**User Story:** As a system administrator, I want to integrate Mistral 7B from Hugging Face, so that I can replace the complex 3-stage architecture with a single generative model.

#### Acceptance Criteria

1. THE System SHALL load the Mistral 7B model from Hugging Face transformers library
2. THE System SHALL initialize the model with GPU acceleration using the available 14GB GPU memory
3. THE System SHALL configure the model for text generation with appropriate parameters (temperature, max_tokens, top_p)
4. WHEN the model fails to load, THE System SHALL return a descriptive error message indicating the failure reason
5. THE System SHALL validate that GPU memory is sufficient before loading the model
6. THE System SHALL support model quantization (4-bit or 8-bit) to optimize memory usage if needed

### Requirement 2: System Prompt Construction

**User Story:** As a developer, I want comprehensive system prompts that guide the model, so that it can generate accurate SQL queries without heavy training.

#### Acceptance Criteria

1. THE System_Prompt SHALL include the complete database schema with table names, column names, and data types
2. THE System_Prompt SHALL include example queries demonstrating common patterns (date ranges, comparisons, categories, aggregations)
3. THE System_Prompt SHALL include construction domain terminology and entity definitions (expenses, cashflow, projects, documents)
4. THE System_Prompt SHALL include instructions for handling conversation context and references to previous queries
5. THE System_Prompt SHALL include guidelines for when to request clarification from users
6. THE System_Prompt SHALL include SQL generation rules and best practices specific to the database schema
7. THE System_Prompt SHALL be configurable and updatable without code changes
8. THE System_Prompt SHALL include instructions for handling multi-table joins and complex relationships

### Requirement 3: Natural Language Query Processing

**User Story:** As a user, I want to ask questions in natural English, so that I can retrieve construction management data without knowing SQL.

#### Acceptance Criteria

1. WHEN a user submits a natural language query, THE Query_Processor SHALL pass it to the Mistral_Model with the System_Prompt
2. THE Query_Processor SHALL extract the generated SQL query from the model's response
3. THE Query_Processor SHALL handle queries about expenses, cashflow, projects, and documents
4. THE Query_Processor SHALL support date range queries (e.g., "expenses last month", "projects in Q1 2024")
5. THE Query_Processor SHALL support category queries (e.g., "labor expenses", "material costs")
6. THE Query_Processor SHALL support comparison queries (e.g., "projects over budget", "expenses greater than 5000")
7. THE Query_Processor SHALL support aggregation queries (e.g., "total expenses", "average project cost")
8. WHEN the model generates invalid output, THE Query_Processor SHALL retry with additional clarification in the prompt

### Requirement 4: Conversation Context Management

**User Story:** As a user, I want the system to remember previous queries in a conversation, so that I can ask follow-up questions naturally.

#### Acceptance Criteria

1. THE Context_Manager SHALL maintain a conversation history for each user session
2. WHEN a user submits a query, THE Context_Manager SHALL include relevant previous queries and results in the System_Prompt
3. THE Context_Manager SHALL resolve references to previous queries (e.g., "show me more", "what about last year")
4. THE Context_Manager SHALL limit conversation history to the most recent N exchanges to fit within token limits
5. THE Context_Manager SHALL clear conversation context when a user starts a new conversation
6. THE Context_Manager SHALL preserve entity references across queries (e.g., project names, date ranges)
7. FOR ALL conversation sessions, maintaining context SHALL NOT cause the combined prompt to exceed the model's token limit

### Requirement 5: SQL Query Validation

**User Story:** As a system administrator, I want generated SQL queries to be validated, so that invalid or dangerous queries are not executed.

#### Acceptance Criteria

1. WHEN a SQL query is generated, THE SQL_Validator SHALL verify the query syntax is valid
2. THE SQL_Validator SHALL verify that all referenced tables exist in the database schema
3. THE SQL_Validator SHALL verify that all referenced columns exist in their respective tables
4. THE SQL_Validator SHALL reject queries containing destructive operations (DROP, DELETE, UPDATE, INSERT, TRUNCATE)
5. THE SQL_Validator SHALL reject queries attempting to access tables outside the allowed schema
6. IF a query fails validation, THEN THE System SHALL log the validation error and request the model to regenerate the query
7. THE SQL_Validator SHALL allow SELECT queries with JOINs, WHERE clauses, GROUP BY, ORDER BY, and LIMIT clauses

### Requirement 6: Smart Clarification

**User Story:** As a user, I want the system to ask for clarification when my query is ambiguous, so that I get accurate results.

#### Acceptance Criteria

1. WHEN a query references ambiguous entities, THE Clarification_Engine SHALL detect the ambiguity
2. WHEN ambiguity is detected, THE Clarification_Engine SHALL generate specific clarification questions
3. THE Clarification_Engine SHALL detect ambiguous date references (e.g., "last month" when current date is unclear)
4. THE Clarification_Engine SHALL detect ambiguous project references when multiple projects match
5. THE Clarification_Engine SHALL detect missing required parameters for specific query types
6. WHEN clarification is needed, THE System SHALL return a clarification request instead of executing a potentially incorrect query
7. WHEN a user provides clarification, THE Context_Manager SHALL incorporate it into the conversation context

### Requirement 7: Construction Domain Support

**User Story:** As a construction manager, I want the system to understand construction-specific terminology, so that I can use natural domain language.

#### Acceptance Criteria

1. THE System_Prompt SHALL include definitions for construction domain entities (expenses, cashflow, projects, documents, vendors, materials, labor)
2. THE Query_Processor SHALL recognize construction-specific categories (labor, materials, equipment, subcontractors, permits)
3. THE Query_Processor SHALL recognize construction-specific metrics (budget, actual cost, variance, completion percentage)
4. THE Query_Processor SHALL recognize construction-specific time periods (project phases, milestones, billing periods)
5. THE Query_Processor SHALL handle construction-specific relationships (project-to-expense, project-to-document, vendor-to-expense)
6. THE System_Prompt SHALL include example queries using construction domain terminology

### Requirement 8: Database Schema Integration

**User Story:** As a developer, I want the system to automatically load database schema information, so that the model has accurate context about available tables and columns.

#### Acceptance Criteria

1. THE Schema_Provider SHALL query the database to retrieve all table names in the allowed schema
2. THE Schema_Provider SHALL query the database to retrieve all column names and data types for each table
3. THE Schema_Provider SHALL retrieve foreign key relationships between tables
4. THE Schema_Provider SHALL format schema information in a clear, structured format for the System_Prompt
5. WHEN the database schema changes, THE Schema_Provider SHALL refresh the schema information
6. THE Schema_Provider SHALL cache schema information to avoid repeated database queries
7. THE Schema_Provider SHALL include sample values for enum columns and lookup tables

### Requirement 9: Error Handling and Recovery

**User Story:** As a user, I want helpful error messages when something goes wrong, so that I can understand what happened and try again.

#### Acceptance Criteria

1. WHEN the Mistral_Model fails to generate a response, THE System SHALL return a user-friendly error message
2. WHEN SQL validation fails, THE System SHALL explain why the query was invalid
3. WHEN SQL execution fails, THE System SHALL return the database error in user-friendly language
4. WHEN the model generates non-SQL output, THE System SHALL detect this and retry with additional instructions
5. IF retries fail after N attempts, THEN THE System SHALL return a failure message and log the issue for debugging
6. THE System SHALL log all errors with sufficient context for troubleshooting
7. WHEN GPU memory is insufficient, THE System SHALL suggest using quantization or reducing batch size

### Requirement 10: Performance and Resource Management

**User Story:** As a system administrator, I want the system to use GPU resources efficiently, so that it can handle multiple concurrent queries within the 14GB memory limit.

#### Acceptance Criteria

1. THE System SHALL monitor GPU memory usage during model inference
2. THE System SHALL support batching multiple queries when possible to improve throughput
3. THE System SHALL complete query processing within 5 seconds for simple queries
4. THE System SHALL complete query processing within 15 seconds for complex queries requiring clarification
5. WHEN GPU memory usage exceeds 90%, THE System SHALL queue additional requests
6. THE System SHALL release GPU memory after processing each query
7. THE System SHALL support concurrent query processing up to the GPU memory limit

### Requirement 11: Optional Fine-Tuning Support

**User Story:** As a developer, I want to optionally fine-tune the model on construction-specific examples, so that I can improve accuracy over time.

#### Acceptance Criteria

1. WHERE fine-tuning is enabled, THE System SHALL support loading a fine-tuned version of Mistral 7B
2. WHERE fine-tuning is enabled, THE System SHALL provide utilities to prepare training data in the required format
3. WHERE fine-tuning is enabled, THE System SHALL support LoRA (Low-Rank Adaptation) for efficient fine-tuning
4. WHERE fine-tuning is enabled, THE System SHALL validate that the fine-tuned model is compatible with the base model
5. THE System SHALL support switching between base model and fine-tuned model without code changes
6. THE System SHALL document the fine-tuning process including data format, hyperparameters, and evaluation metrics

### Requirement 12: Query Result Formatting

**User Story:** As a user, I want query results presented in a clear, readable format, so that I can easily understand the data.

#### Acceptance Criteria

1. WHEN a SQL query executes successfully, THE System SHALL format the results as structured JSON
2. THE System SHALL include column names and data types in the result format
3. THE System SHALL format dates in a consistent, readable format (ISO 8601)
4. THE System SHALL format currency amounts with appropriate precision and currency symbols
5. THE System SHALL limit result sets to a maximum number of rows to prevent overwhelming responses
6. WHEN results are truncated, THE System SHALL indicate how many total rows match the query
7. THE System SHALL handle NULL values appropriately in the result formatting

### Requirement 13: Logging and Observability

**User Story:** As a developer, I want comprehensive logging of queries and model behavior, so that I can debug issues and improve the system.

#### Acceptance Criteria

1. THE System SHALL log all incoming natural language queries with timestamps and user identifiers
2. THE System SHALL log all generated SQL queries with the corresponding natural language input
3. THE System SHALL log model inference time and token usage for each query
4. THE System SHALL log validation failures with the specific validation rule that failed
5. THE System SHALL log SQL execution time and result row counts
6. THE System SHALL log all errors with full stack traces and context
7. THE System SHALL support configurable log levels (DEBUG, INFO, WARNING, ERROR)
8. THE System SHALL provide metrics for monitoring (queries per second, average latency, error rate)

### Requirement 14: Configuration Management

**User Story:** As a system administrator, I want to configure system behavior without code changes, so that I can tune the system for different use cases.

#### Acceptance Criteria

1. THE System SHALL load configuration from environment variables or configuration files
2. THE System SHALL support configuring model parameters (temperature, max_tokens, top_p, top_k)
3. THE System SHALL support configuring validation rules (allowed tables, maximum result rows)
4. THE System SHALL support configuring retry behavior (max retries, retry delay)
5. THE System SHALL support configuring conversation context limits (max history length, max tokens)
6. THE System SHALL support enabling/disabling optional features (fine-tuning, clarification, fuzzy matching)
7. THE System SHALL validate configuration values on startup and report errors for invalid configurations

### Requirement 15: Migration from 3-Stage Architecture

**User Story:** As a developer, I want a clear migration path from the old architecture, so that I can transition smoothly without data loss.

#### Acceptance Criteria

1. THE System SHALL provide a compatibility layer that accepts requests in the old API format
2. THE System SHALL support running in parallel with the old system for A/B testing
3. THE System SHALL provide migration scripts to convert old conversation data to the new format
4. THE System SHALL document API changes and breaking changes from the old system
5. THE System SHALL provide performance comparison metrics between old and new systems
6. THE System SHALL maintain backward compatibility for stored conversation history
7. THE System SHALL provide rollback procedures in case migration issues occur

## Notes

### Current System Problems Addressed

This new architecture addresses the following problems in the current 3-stage system:

- Date range queries not working → Handled by comprehensive system prompts with date handling examples
- Category queries don't work → Handled by construction domain knowledge in system prompts
- Comparison queries not supported → Handled by example queries in system prompts
- Fuzzy matching missing → Can be added to system prompts or fine-tuning data
- Conversation context broken → Handled by dedicated Context_Manager component
- Too many hardcoded rules → Eliminated by using generative model with flexible prompts
- File-level vs row-level confusion → Clarified in system prompts with schema context
- Smart clarification not working → Handled by dedicated Clarification_Engine component

### Technical Approach

The system will use a zero-shot approach initially, relying on comprehensive system prompts to guide the Mistral 7B model. This eliminates the need for:
- Multiple model training pipelines (DistilBERT, T5, LoRA)
- Complex orchestration between models
- Separate intent detection and SQL generation stages
- Extensive training data preparation

Optional fine-tuning can be added later using LoRA for efficient adaptation to construction-specific patterns.

### Deployment Considerations

- Model will run on user's server with 14GB GPU
- Quantization (4-bit or 8-bit) may be needed to fit within memory constraints
- System should support graceful degradation if GPU memory is insufficient
- Consider using vLLM or similar inference optimization frameworks for production deployment
