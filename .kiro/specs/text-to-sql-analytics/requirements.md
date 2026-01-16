# Requirements Document: Text-to-SQL Analytics

## Introduction

This feature adds Text-to-SQL capability to enable complex analytics queries that go beyond simple keyword search. The system will translate natural language questions (in English and Tagalog) into SQL queries, execute them safely, and return formatted results. This addresses the current limitation where keyword search cannot handle aggregations, date ranges, cross-table comparisons, and complex filtering.

## Glossary

- **Text-to-SQL Model**: A machine learning model that translates natural language queries into SQL statements
- **Router**: The DistilBERT-based model that classifies user intent and routes queries to appropriate handlers
- **Analytics Handler**: The new query handler that processes analytics-intent queries using Text-to-SQL
- **Universal Handler**: The existing keyword search handler using ai_documents index
- **SQL Injection**: A security vulnerability where malicious SQL code is inserted into queries
- **Read-Only Enforcement**: Restriction that prevents any data modification operations (INSERT, UPDATE, DELETE)
- **Role-Based Access Control (RBAC)**: Permission system where different user roles have access to different tables
- **Query Validation**: Process of checking generated SQL for safety, correctness, and permission compliance

## Requirements

### Requirement 1: Text-to-SQL Model Integration

**User Story:** As a system architect, I want to integrate a Text-to-SQL model into the query processing pipeline, so that the system can translate natural language analytics questions into executable SQL queries.

#### Acceptance Criteria

1. THE System SHALL load a fine-tunable Text-to-SQL model (T5-based or CodeT5) with maximum size of 14GB
2. WHEN the Analytics Handler receives a natural language query, THE System SHALL generate a SQL query using the Text-to-SQL model
3. THE System SHALL support both English and Tagalog input queries
4. WHEN SQL generation fails, THE System SHALL log the error and return a fallback response
5. THE System SHALL complete SQL generation within 500ms for 90% of queries

### Requirement 2: Analytics Intent Detection and Routing

**User Story:** As a user, I want the system to automatically detect when my query requires analytics, so that it routes to the appropriate handler without manual intervention.

#### Acceptance Criteria

1. WHEN the Router receives a query, THE Router SHALL classify whether it requires analytics processing
2. WHEN a query is classified as analytics intent, THE Router SHALL route it to the Analytics Handler
3. WHEN a query is classified as non-analytics intent, THE Router SHALL route it to the Universal Handler
4. THE Router SHALL maintain classification accuracy of 90% or higher for analytics vs non-analytics queries
5. THE Router SHALL complete intent classification within 100ms

### Requirement 3: SQL Query Validation and Safety

**User Story:** As a security engineer, I want all generated SQL queries to be validated for safety, so that the system prevents SQL injection and unauthorized operations.

#### Acceptance Criteria

1. WHEN a SQL query is generated, THE System SHALL validate it against SQL injection patterns
2. THE System SHALL reject any SQL query containing write operations (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE)
3. THE System SHALL reject any SQL query containing multiple statements or command chaining
4. WHEN a SQL query fails validation, THE System SHALL log the violation and return an error message
5. THE System SHALL only execute SQL queries that pass all validation checks

### Requirement 4: Role-Based Access Control for SQL Queries

**User Story:** As a system administrator, I want SQL queries to respect role-based permissions, so that users can only access tables they are authorized to view.

#### Acceptance Criteria

1. WHEN generating SQL for an ENCODER role user, THE System SHALL exclude CashFlow table from the query
2. WHEN generating SQL for an ADMIN role user, THE System SHALL allow access to all tables (Expenses, CashFlow, Project, Quotation)
3. WHEN a generated SQL query attempts to access unauthorized tables, THE System SHALL reject the query
4. THE System SHALL inject role-based WHERE clauses into generated SQL to enforce row-level permissions
5. WHEN role validation fails, THE System SHALL return an access denied error message

### Requirement 5: Complex Analytics Query Support

**User Story:** As a user, I want to ask complex analytics questions involving aggregations, grouping, and date ranges, so that I can get insights from the data without writing SQL manually.

#### Acceptance Criteria

1. WHEN a query requests aggregation (SUM, AVG, COUNT, MIN, MAX), THE System SHALL generate SQL with appropriate aggregate functions
2. WHEN a query requests grouped results, THE System SHALL generate SQL with GROUP BY clauses
3. WHEN a query specifies date ranges, THE System SHALL generate SQL with date filtering (last month, last 3 months, this year)
4. WHEN a query requests comparisons, THE System SHALL generate SQL with multiple aggregations or subqueries
5. WHEN a query has multiple conditions, THE System SHALL generate SQL with appropriate WHERE clauses and logical operators

### Requirement 6: Database Schema Awareness

**User Story:** As a developer, I want the Text-to-SQL model to understand the database schema, so that it generates queries with correct table names, column names, and relationships.

#### Acceptance Criteria

1. THE System SHALL provide the Text-to-SQL model with schema information for tables: Expenses, CashFlow, Project, Quotation
2. THE System SHALL include column names, data types, and foreign key relationships in the schema context
3. WHEN generating SQL, THE System SHALL use correct table and column names from the schema
4. WHEN a query references ambiguous terms, THE System SHALL map them to the correct schema elements
5. THE System SHALL handle table joins correctly based on foreign key relationships

### Requirement 7: SQL Execution and Result Formatting

**User Story:** As a user, I want to receive formatted, readable results from my analytics queries, so that I can understand the data without interpreting raw SQL output.

#### Acceptance Criteria

1. WHEN a validated SQL query is ready, THE System SHALL execute it against the Supabase PostgreSQL database
2. THE System SHALL set a query timeout of 10 seconds to prevent long-running queries
3. WHEN query execution succeeds, THE System SHALL format results into a human-readable response
4. WHEN query execution fails, THE System SHALL return a user-friendly error message
5. THE System SHALL include relevant metadata (row count, execution time) in the response

### Requirement 8: Fallback to Keyword Search

**User Story:** As a user, I want the system to gracefully handle cases where Text-to-SQL fails, so that I still get results using the existing keyword search.

#### Acceptance Criteria

1. WHEN SQL generation fails after 3 retry attempts, THE System SHALL fall back to the Universal Handler
2. WHEN SQL validation fails due to safety concerns, THE System SHALL fall back to the Universal Handler
3. WHEN SQL execution returns an error, THE System SHALL fall back to the Universal Handler
4. THE System SHALL log all fallback events for monitoring and improvement
5. THE System SHALL inform the user when a fallback occurs with a message indicating keyword search was used

### Requirement 9: Performance and Response Time

**User Story:** As a user, I want analytics queries to return results quickly, so that I can have a responsive conversational experience.

#### Acceptance Criteria

1. THE System SHALL complete the full analytics pipeline (generation + validation + execution + formatting) within 1 second for 80% of queries
2. THE System SHALL complete SQL generation within 500ms for 90% of queries
3. THE System SHALL complete SQL validation within 50ms
4. WHEN a query exceeds the 10-second timeout, THE System SHALL cancel execution and return a timeout error
5. THE System SHALL cache frequently used SQL patterns to improve response time

### Requirement 10: Multilingual Query Support

**User Story:** As a Filipino user, I want to ask analytics questions in Tagalog, so that I can use my native language for data analysis.

#### Acceptance Criteria

1. WHEN a query is in Tagalog, THE System SHALL translate it to SQL with the same accuracy as English queries
2. THE System SHALL recognize Tagalog terms for aggregations (kabuuan=SUM, average=AVG, bilang=COUNT)
3. THE System SHALL recognize Tagalog date expressions (nakaraang buwan=last month, ngayong taon=this year)
4. THE System SHALL recognize Tagalog table/column references (gastos=expenses, proyekto=project)
5. THE System SHALL format responses in the same language as the input query

### Requirement 11: Query Logging and Monitoring

**User Story:** As a system administrator, I want to monitor Text-to-SQL performance and errors, so that I can identify issues and improve the system.

#### Acceptance Criteria

1. THE System SHALL log all generated SQL queries with timestamps and user context
2. THE System SHALL log validation failures with the specific rule violated
3. THE System SHALL log execution errors with error messages and stack traces
4. THE System SHALL track metrics: success rate, average response time, fallback rate
5. THE System SHALL provide a dashboard or API endpoint to view Text-to-SQL analytics

### Requirement 12: Model Fine-Tuning Support

**User Story:** As a machine learning engineer, I want to fine-tune the Text-to-SQL model on domain-specific data, so that it improves accuracy for construction project management queries.

#### Acceptance Criteria

1. THE System SHALL support loading custom fine-tuned Text-to-SQL model weights
2. THE System SHALL provide a training data format specification for fine-tuning
3. THE System SHALL include example queries and SQL pairs for the construction domain
4. THE System SHALL allow model updates without system downtime (hot-swapping)
5. THE System SHALL validate model compatibility before loading new weights
