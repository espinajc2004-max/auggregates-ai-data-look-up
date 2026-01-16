# Requirements Document: ChatGPT-Style 3-Stage AI Query System (English-Only)

## Introduction

This specification defines the requirements for upgrading the AI query system to a ChatGPT-style 3-stage architecture with English-only support. The current system uses pattern-based extraction with Ollama, but fails on complex natural language queries, lacks proper conversation memory, and cannot handle multi-request queries or clarification flows. The upgraded system uses a 3-stage pipeline inspired by ChatGPT's architecture: (1) DistilBERT Orchestrator for intent/entity detection, (1.5) DB-driven clarification for truth-based options, (2) Fine-tuned T5 for SQL generation with server-side guardrails, (3A) LoRA for clarification responses, and (3B) LoRA for final answer composition. This approach maintains thesis compliance by demonstrating custom AI training and integration of multiple specialized models.

## Glossary

- **Stage 1 - Orchestrator**: Enhanced DistilBERT that detects intent, extracts entities, decides if clarification is needed, and splits multi-request queries (does NOT generate SQL or invent clarification options)
- **Stage 1.5 - DB Clarification**: Database-driven component that fetches real clarification options from the database (prevents hallucination)
- **Stage 2 - Retriever**: Fine-tuned T5 model that generates SQL from natural language and executes queries with server-side security guardrails
- **Stage 3A - Clarification Composer**: LoRA-based component that generates clarification questions when needs_clarification=true (before Stage 2)
- **Stage 3B - Answer Composer**: LoRA-based component that turns raw SQL results into human-friendly final answers with conversation context (after Stage 2)
- **DistilBERT**: Existing intent detection model, enhanced for orchestration role (intent detection, entity extraction, clarification detection)
- **T5_Model**: Text-to-Text Transfer Transformer (60M parameters) fine-tuned for SQL generation on English construction management queries
- **LoRA_Model**: Existing Low-Rank Adaptation model, enhanced for answer composition and conversation state management
- **Server_SQL_Guardrails**: Security enforcement layer that always injects org_id, blocks DDL operations, and parameterizes queries
- **Conversation_Memory**: System that maintains conversation context across multiple turns (e.g., "SJDM" stays active)
- **Entity_Extractor**: Component that extracts structured entities (project=SJDM, method=GCASH, ref=123) from English queries
- **Clarification_Engine**: Component that detects ambiguous queries and fetches real options from database
- **Multi_Query_Detector**: Component that splits multi-request queries into sub-queries
- **Authorization_Filter**: Component that attaches user_id/org_id filters to SQL for security
- **Typo_Corrector**: Existing preprocessing component for typo correction (English-only)
- **Training_Dataset**: Collection of 1000+ English query-SQL pairs from construction management domain

## Requirements

### Requirement 1: General Questions with Clarification (English-Only)

**User Story:** As a user, I want to ask general questions in English like "how many do we have project?", so that the system can ask for clarification when my query is ambiguous.

#### Acceptance Criteria

1. WHEN a user submits an ambiguous English query (e.g., "how many do we have project?"), THE Stage 1 Orchestrator SHALL detect the ambiguity and identify missing information
2. WHEN ambiguity is detected, THE Stage 1.5 DB Clarification SHALL fetch real project options from the database (e.g., query: SELECT id, code, name FROM projects WHERE org_id = $1 LIMIT 10)
3. WHEN real options are fetched, THE Stage 3A Clarification Composer SHALL generate a clarification question with the real options (e.g., "Which project? 1. SJDM, 2. Francis Gays, 3. All projects")
4. WHEN the user provides clarification, THE Stage 1 Orchestrator SHALL extract the entity and update conversation context
5. WHEN clarification is complete, THE Stage 2 Retriever SHALL generate and execute SQL with the clarified entity
6. WHEN the query is unambiguous, THE System SHALL proceed directly to Stage 2 SQL generation without clarification
7. THE System SHALL NEVER invent or hallucinate clarification options - all options MUST come from the database

### Requirement 2: Multiple Requests Returning Multiple Answers (English-Only)

**User Story:** As a user, I want to ask multiple questions in one English message (e.g., "how many expenses and how many cashflow?"), so that I can get multiple answers efficiently.

#### Acceptance Criteria

1. WHEN a user submits an English query with multiple requests, THE Stage 1 Orchestrator SHALL detect and split it into sub-queries
2. WHEN sub-queries are identified, THE Stage 2 Retriever SHALL process each sub-query independently
3. WHEN all sub-queries are processed, THE Stage 3B Answer Composer SHALL combine results into a single coherent response
4. WHEN one sub-query fails, THE System SHALL return partial results for successful sub-queries
5. WHEN sub-queries reference the same entity, THE Stage 1 Orchestrator SHALL maintain entity context across sub-queries

### Requirement 3: Specific Data Search (English-Only)

**User Story:** As a user, I want to search for specific data in English like "how much gcash payment in francis gays", so that I can find targeted information with multiple filters.

#### Acceptance Criteria

1. WHEN a user submits an English query with multiple entities (e.g., "gcash payment in francis gays"), THE Stage 1 Orchestrator SHALL extract all entities (method=GCASH, project=francis gays)
2. WHEN entities are extracted, THE Stage 2 Retriever SHALL generate SQL with all entity filters in WHERE clauses and Server SQL Guardrails SHALL inject org_id filter
3. WHEN entity names are fuzzy (e.g., "francis gays" vs "Francis Gays"), THE Stage 1 Orchestrator SHALL normalize and match entities
4. WHEN the query includes aggregation (e.g., "how much"), THE Stage 2 Retriever SHALL generate SQL with SUM aggregation
5. WHEN results are returned, THE Stage 3B Answer Composer SHALL format the answer with entity context (e.g., "GCASH payments in Francis Gays: ₱15,000")

### Requirement 4: Complex Queries Handled by Text-to-SQL (English-Only)

**User Story:** As a user, I want to ask complex English queries that pattern-based systems cannot handle, so that I can get answers to sophisticated questions.

#### Acceptance Criteria

1. WHEN a user submits a complex English query (e.g., "find all expenses over 10000 in SJDM last month"), THE Stage 2 Retriever SHALL generate SQL with multiple conditions
2. WHEN the query includes date ranges, THE Stage 2 Retriever SHALL generate SQL with date filtering
3. WHEN the query includes numeric comparisons (e.g., "over 10000"), THE Stage 2 Retriever SHALL generate SQL with comparison operators
4. WHEN the query includes sorting (e.g., "highest expenses"), THE Stage 2 Retriever SHALL generate SQL with ORDER BY clauses
5. WHEN complex SQL is generated, THE Server SQL Guardrails SHALL validate it and inject org_id before execution

### Requirement 5: Real-Time Data Updates

**User Story:** As a user, I want to see real-time data updates (e.g., 16 → add 1 → returns 17), so that I always get current information.

#### Acceptance Criteria

1. WHEN a user queries data, THE Stage 2 Retriever SHALL execute SQL against the live database (no caching)
2. WHEN data changes between queries, THE System SHALL return updated results
3. WHEN a user adds data and immediately queries, THE System SHALL include the new data in results
4. WHEN the database is updated, THE System SHALL reflect changes within 1 second
5. WHEN real-time queries fail, THE System SHALL return an error message indicating the issue

### Requirement 6: Continuous Conversation with Context Memory (English-Only)

**User Story:** As a user, I want the system to remember context from previous English messages (e.g., "SJDM" stays active), so that I can have natural follow-up conversations.

#### Acceptance Criteria

1. WHEN a user mentions an entity in English (e.g., "SJDM"), THE Conversation_Memory SHALL store it as active context
2. WHEN a user asks a follow-up question without mentioning the entity, THE Stage 1 Orchestrator SHALL use the active context
3. WHEN a user switches to a new entity, THE Conversation_Memory SHALL update the active context
4. WHEN a user asks "how much total?" after "find gcash", THE Stage 1 Orchestrator SHALL understand "total" refers to GCASH
5. WHEN conversation context is used, THE Stage 3B Answer Composer SHALL acknowledge it in the response (e.g., "For SJDM: ...")

### Requirement 7: Clarification When Ambiguous (English-Only with DB-Driven Options)

**User Story:** As a user, I want the system to ask for clarification when my English query is unclear, so that I get accurate results instead of guesses.

#### Acceptance Criteria

1. WHEN an English query references multiple possible entities, THE Stage 1 Orchestrator SHALL detect the ambiguity
2. WHEN ambiguity is detected, THE Stage 1.5 DB Clarification SHALL fetch real options from the database (e.g., SELECT id, code, name FROM projects WHERE org_id = $1 AND name ILIKE '%search_term%')
3. WHEN options are fetched, THE Stage 3A Clarification Composer SHALL format them clearly (e.g., "Which project? 1. SJDM, 2. SJDM2, 3. SJDM3, 4. All projects")
4. WHEN the user selects an option, THE Stage 1 Orchestrator SHALL extract the choice and proceed to Stage 2
5. WHEN the user provides additional context instead of selecting, THE Stage 1 Orchestrator SHALL re-evaluate the query
6. THE System SHALL NEVER invent clarification options - all options MUST come from database queries

### Requirement 8: Follow-Up Understanding (English-Only)

**User Story:** As a user, I want the system to understand follow-up English questions like "how much total?" after "find gcash", so that I can have natural conversations.

#### Acceptance Criteria

1. WHEN a user asks a follow-up question in English, THE Conversation_Memory SHALL provide previous query context
2. WHEN the follow-up references previous results (e.g., "total" after "find gcash"), THE Stage 1 Orchestrator SHALL understand the reference
3. WHEN the follow-up changes the operation (e.g., "find" → "how much"), THE Stage 1 Orchestrator SHALL detect the new intent
4. WHEN the follow-up adds filters (e.g., "in SJDM" after "find gcash"), THE Stage 1 Orchestrator SHALL combine filters
5. WHEN the follow-up is unrelated, THE Stage 1 Orchestrator SHALL treat it as a new query

### Requirement 9: File Location Display

**User Story:** As a user, I want to see file locations when requested (e.g., "where is this file?"), so that I can access the original documents.

#### Acceptance Criteria

1. WHEN a user asks for file location, THE Stage 1 Orchestrator SHALL detect the intent
2. WHEN file location is requested, THE Stage 2 Retriever SHALL query for file paths in metadata
3. WHEN file paths are found, THE Stage 3B Answer Composer SHALL format them as clickable links or paths
4. WHEN multiple files match, THE Stage 3B Answer Composer SHALL list all file locations
5. WHEN no file location is available, THE Stage 3B Answer Composer SHALL indicate the data is not file-based

### Requirement 10: Multiple Match Selection with User Choice

**User Story:** As a user, I want to see multiple matches and choose which one I mean, so that I can disambiguate when there are similar entities.

#### Acceptance Criteria

1. WHEN a query matches multiple entities (e.g., "SJDM" matches "SJDM", "SJDM2", "SJDM3"), THE Stage 1 Orchestrator SHALL detect multiple matches
2. WHEN multiple matches are found, THE Stage 3A Clarification Composer SHALL present them as numbered options
3. WHEN the user selects a number, THE Stage 1 Orchestrator SHALL extract the corresponding entity
4. WHEN the user provides more context, THE Stage 1 Orchestrator SHALL re-filter the matches
5. WHEN only one match is found, THE System SHALL proceed to Stage 2 without asking for selection

### Requirement 11: Stage 1 - Orchestrator (DistilBERT Enhancement for English)

**User Story:** As a system architect, I want to enhance DistilBERT for orchestration of English queries, so that it can detect intent, extract entities, and decide on clarification.

#### Acceptance Criteria

1. THE Stage 1 Orchestrator SHALL detect intent from English queries (count / lookup / list / location / analytics)
2. THE Stage 1 Orchestrator SHALL extract entities (project=SJDM, method=GCASH, ref=123) from English queries
3. THE Stage 1 Orchestrator SHALL decide if clarification is needed based on ambiguity detection
4. THE Stage 1 Orchestrator SHALL split multi-request queries into sub-queries
5. THE Stage 1 Orchestrator SHALL attach authorization filters (user_id/org_id) to all queries
6. THE Stage 1 Orchestrator SHALL NOT generate SQL, execute queries, or invent clarification options

### Requirement 11.5: Stage 1.5 - DB-Driven Clarification (Truth Lookup)

**User Story:** As a system architect, I want to fetch clarification options from the database, so that the system never invents or hallucinates options.

#### Acceptance Criteria

1. WHEN Stage 1 Orchestrator detects needs_clarification=true, THE Stage 1.5 DB Clarification SHALL query the database for real options
2. THE Stage 1.5 DB Clarification SHALL use parameterized queries with org_id filter (e.g., SELECT id, code, name FROM projects WHERE org_id = $1 ORDER BY updated_at DESC LIMIT 10)
3. THE Stage 1.5 DB Clarification SHALL return structured options with id, code, and name fields
4. THE Stage 1.5 DB Clarification SHALL include an "All" option when appropriate (e.g., "All projects" for count queries)
5. THE Stage 1.5 DB Clarification SHALL handle empty results gracefully (e.g., "No projects found for your organization")
6. THE Stage 1.5 DB Clarification SHALL NOT use AI models to generate options - all options MUST come from database queries

### Requirement 12: Stage 2 - Retriever (Fine-Tuned T5 with Server SQL Guardrails)

**User Story:** As a system architect, I want to train a T5 model for SQL generation with server-side security guardrails, so that it can handle complex English natural language queries safely.

#### Acceptance Criteria

1. THE Stage 2 Retriever SHALL generate parameterized SQL from English natural language queries
2. THE Server SQL Guardrails SHALL ALWAYS inject org_id filter into WHERE clauses (e.g., WHERE org_id = $1 AND ...)
3. THE Server SQL Guardrails SHALL block DDL operations (CREATE, DROP, ALTER, TRUNCATE, DELETE, UPDATE)
4. THE Server SQL Guardrails SHALL parameterize all user inputs to prevent SQL injection
5. THE Server SQL Guardrails SHALL validate generated SQL against the database schema before execution
6. THE Stage 2 Retriever SHALL execute SQL queries against the live database after guardrail validation
7. THE Stage 2 Retriever SHALL return raw query results to Stage 3B Answer Composer
8. THE Stage 2 Retriever SHALL handle errors gracefully and return error information
9. THE Stage 2 Retriever SHALL NOT decide clarification, maintain conversation state, or format user responses

### Requirement 13: Stage 3A - Clarification Composer (LoRA for Clarification Questions)

**User Story:** As a system architect, I want to use LoRA to generate clarification questions, so that users receive natural language clarification prompts when ambiguity is detected.

#### Acceptance Criteria

1. WHEN Stage 1 Orchestrator detects needs_clarification=true, THE Stage 3A Clarification Composer SHALL generate a clarification question
2. THE Stage 3A Clarification Composer SHALL format options from Stage 1.5 DB Clarification into natural language (e.g., "Which project do you mean? 1. SJDM, 2. Francis Gays, 3. All projects")
3. THE Stage 3A Clarification Composer SHALL maintain conversation context when generating clarification questions
4. THE Stage 3A Clarification Composer SHALL NOT generate SQL, execute queries, or invent options
5. THE Stage 3A Clarification Composer SHALL run BEFORE Stage 2 (no SQL execution yet)

### Requirement 13.5: Stage 3B - Answer Composer (LoRA for Final Answers)

**User Story:** As a system architect, I want to use LoRA to compose final answers, so that raw SQL results are turned into human-friendly responses.

#### Acceptance Criteria

1. THE Stage 3B Answer Composer SHALL turn raw SQL results from Stage 2 into natural language answers
2. THE Stage 3B Answer Composer SHALL show choices when multiple matches are found
3. THE Stage 3B Answer Composer SHALL maintain conversation state (e.g., "SJDM" stays active)
4. THE Stage 3B Answer Composer SHALL offer file location/path when available
5. THE Stage 3B Answer Composer SHALL format numbers with appropriate units (e.g., ₱15,000)
6. THE Stage 3B Answer Composer SHALL run AFTER Stage 2 (SQL execution complete)

### Requirement 14: Existing AI Models Integration

**User Story:** As a system architect, I want to keep and enhance existing AI models, so that we build on proven components.

#### Acceptance Criteria

1. THE System SHALL keep DistilBERT at `ml/model/router_model/` and enhance it for Stage 1 orchestration
2. THE System SHALL keep LoRA at `ml/model/lora_modifier/` and enhance it for Stage 3A clarification and Stage 3B composition
3. THE System SHALL keep the Typo_Corrector for English preprocessing
4. THE System SHALL keep Conversation_Memory for context tracking
5. THE System SHALL add Fine-Tuned T5 as a new component for Stage 2 SQL generation

### Requirement 15: Training Dataset for T5 (English-Only)

**User Story:** As a developer, I want to create an English-only training dataset for T5, so that it can learn construction management domain queries.

#### Acceptance Criteria

1. THE Training_Dataset SHALL contain at least 1000 English query-SQL pairs
2. THE Training_Dataset SHALL include examples from all user test cases (clarification, multi-request, specific search, etc.)
3. THE Training_Dataset SHALL be English-only (no Tagalog or Taglish)
4. THE Training_Dataset SHALL be validated to ensure all SQL is executable
5. THE Training_Dataset SHALL be split into training (80%), validation (10%), and test (10%) sets

### Requirement 16: Performance Requirements

**User Story:** As a user, I want fast responses, so that I can interact naturally with the system.

#### Acceptance Criteria

1. WHEN a query is processed, THE Stage 1 Orchestrator SHALL complete in less than 50ms
2. WHEN SQL is generated, THE Stage 2 Retriever SHALL complete in less than 200ms
3. WHEN answers are composed, THE Stage 3A/3B Composer SHALL complete in less than 100ms
4. WHEN the total pipeline runs, THE System SHALL respond in less than 500ms (excluding database query time)
5. WHEN concurrent queries are received, THE System SHALL handle them without performance degradation

### Requirement 17: Error Handling and Fallback

**User Story:** As a user, I want the system to handle errors gracefully, so that I always get some response even when things fail.

#### Acceptance Criteria

1. WHEN SQL generation fails, THE System SHALL fallback to keyword search
2. WHEN SQL validation fails, THE System SHALL fallback to keyword search
3. WHEN SQL execution fails, THE System SHALL return a descriptive error message
4. WHEN the Orchestrator fails, THE System SHALL use basic intent detection
5. WHEN the Composer fails, THE System SHALL return raw results with minimal formatting

### Requirement 18: Conversation Memory Persistence

**User Story:** As a user, I want my conversation context to persist across sessions, so that I can continue conversations later.

#### Acceptance Criteria

1. WHEN a conversation starts, THE System SHALL create a conversation record in the database
2. WHEN entities are mentioned, THE Conversation_Memory SHALL store them with timestamps
3. WHEN a user returns to a conversation, THE System SHALL load previous context
4. WHEN context is older than 24 hours, THE System SHALL expire it
5. WHEN a user explicitly resets context (e.g., "start over"), THE System SHALL clear conversation memory

### Requirement 19: Authorization and Security (Server SQL Guardrails)

**User Story:** As a system administrator, I want all queries to be filtered by user permissions with server-side guardrails, so that users only see data they're authorized to access and cannot perform dangerous operations.

#### Acceptance Criteria

1. WHEN SQL is generated, THE Server SQL Guardrails SHALL ALWAYS add org_id filter (WHERE org_id = $1 AND ...)
2. WHEN a user queries data, THE System SHALL only return data they own or have access to
3. WHEN SQL contains dangerous operations (DELETE, DROP, ALTER, TRUNCATE, UPDATE, CREATE), THE Server SQL Guardrails SHALL reject it
4. WHEN SQL attempts to access unauthorized tables, THE Server SQL Guardrails SHALL reject it
5. WHEN authorization fails, THE System SHALL return an error message without exposing schema details
6. THE Server SQL Guardrails SHALL parameterize all user inputs to prevent SQL injection

### Requirement 20: Thesis Compliance

**User Story:** As a researcher, I want the system to demonstrate custom AI training, so that it meets thesis requirements.

#### Acceptance Criteria

1. THE System SHALL use fine-tuned T5 (not pre-trained only) for Stage 2 SQL generation on English construction management queries
2. THE System SHALL use enhanced DistilBERT (already trained) for Stage 1 orchestration
3. THE System SHALL use enhanced LoRA (already trained) for Stage 3A clarification and Stage 3B composition
4. THE System SHALL document the training process for all models
5. THE System SHALL demonstrate measurable improvement over pattern-based approach (85%+ accuracy on English queries)
