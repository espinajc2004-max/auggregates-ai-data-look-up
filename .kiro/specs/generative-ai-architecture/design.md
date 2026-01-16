# Design Document: Generative AI Architecture Migration

## Overview

This design document specifies the migration from the current 3-stage architecture (DistilBERT + T5 + LoRA) to a simplified generative AI approach using Mistral 7B. The new system eliminates the complexity of multiple models and training pipelines while addressing critical bugs in the current system.

### Current Architecture Problems

The existing 3-stage system has several critical issues:
- Date range queries not working correctly
- Category queries failing to match construction domain terms
- Comparison queries not supported
- Conversation context broken across queries
- Too many hardcoded rules making maintenance difficult
- Complex orchestration between three separate models
- Extensive training data preparation required for each model

### New Architecture Benefits

- Single model handles all query processing
- Flexible system prompts replace hardcoded rules
- Better conversation context management
- Easier to maintain and extend
- Optional fine-tuning for domain adaptation
- Reduced infrastructure complexity

### Migration Strategy

Clean slate approach with 5 phases:
1. **Backup & Cleanup**: Remove old 3-stage code
2. **Install Dependencies**: Set up Mistral 7B and libraries
3. **Implement Core Service**: Build Mistral query processor
4. **Integration**: Update chat route, reuse existing utilities
5. **Testing & Validation**: Comprehensive testing and rollout


## Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    User[User Query] --> API[FastAPI Chat Endpoint]
    API --> MistralService[Mistral Service]
    
    MistralService --> PromptBuilder[System Prompt Builder]
    MistralService --> ContextMgr[Context Manager]
    MistralService --> Model[Mistral 7B Model]
    
    PromptBuilder --> SchemaProvider[Schema Provider]
    PromptBuilder --> Examples[Example Queries]
    
    ContextMgr --> ConvDB[(Conversation DB)]
    
    Model --> SQLValidator[SQL Validator]
    SQLValidator --> Supabase[(Supabase DB)]
    
    Supabase --> ResultsFormatter[Results Formatter]
    ResultsFormatter --> API
    
    style Model fill:#f9f,stroke:#333,stroke-width:4px
    style MistralService fill:#bbf,stroke:#333,stroke-width:2px

```

### Architecture Comparison

**OLD (3-Stage Architecture)**:
```
User Query → Stage 1 (DistilBERT Orchestrator) → Stage 2 (T5 SQL Generator) → Stage 3 (LoRA Answer Composer) → Database
```

**NEW (Mistral 7B Architecture)**:
```
User Query → Mistral 7B (with System Prompt) → SQL Validator → Database
```

### Component Overview

| Component | Purpose | Status |
|-----------|---------|--------|
| **Mistral Service** | Main service coordinating query processing | NEW |
| **System Prompt Builder** | Constructs prompts with schema + examples | NEW |
| **Context Manager** | Manages conversation history | NEW |
| **Mistral 7B Model** | Core generative AI model | NEW |
| **SQL Validator** | Validates generated SQL | KEEP (existing) |
| **Schema Provider** | Provides database schema info | KEEP (existing) |
| **Conversation DB** | Stores conversation history | KEEP (existing) |
| **Results Formatter** | Formats query results | KEEP (existing) |
| **Supabase Client** | Database connection | KEEP (existing) |


## Migration Plan

### Phase 1: Backup & Cleanup

**Objective**: Remove old 3-stage architecture code while preserving reusable components.

**Files to DELETE**:

```
app/services/stage1/
├── __init__.py
├── orchestrator.py
└── db_clarification.py

app/services/stage2/
├── __init__.py
└── t5_sql_generator.py

app/services/stage3/
├── __init__.py
├── answer_composer.py
└── clarification_composer.py

app/services/
├── intent_router.py
├── context_aware_intent_detector.py
├── query_parser.py (old version)
├── semantic_extractor.py (old version)
├── semantic_extractor_v2.py
├── text_to_sql_service.py (old version)
├── router_service.py
├── embedding_service.py (if only used for old system)

ml/training/
├── adapt_massive_to_stage1.py
├── finetune_t5_construction.py
├── generate_orchestrator_dataset.py
├── generate_stage3_dataset.py
├── generate_t5_expanded_dataset.py
├── generate_t5_training_data.py
├── lora_training.py
├── lora_training_colab.ipynb
├── modifier_training_colab.ipynb
├── Orchestrator_Training_Colab.ipynb
├── Router_Training_v3.ipynb
├── Stage3_LoRA_Training_Colab.ipynb
├── Stage3_LoRA_Training_Colab_v2.ipynb
├── T5_Training_Colab.ipynb
├── train_router.py
├── train_t5_local.py
├── MODIFIER_TRAINING_GUIDE.md
├── ORCHESTRATOR_TRAINING_GUIDE.md
├── STAGE3_LORA_TRAINING_GUIDE.md
├── T5_DATASET_GENERATION_PROMPT.md
└── data/ (all training datasets)
```

**Files to KEEP**:

```
app/services/
├── conversation_db.py
├── conversation_handler.py
├── conversation_memory_manager.py
├── conversation_store.py
├── schema_provider.py
├── schema_introspection.py
├── sql_validator.py
├── supabase_client.py
├── results_formatter.py
├── clarification_engine.py
├── clarification_service.py
├── ambiguity_detector.py
├── vocabulary_service.py
├── vocabulary_loader.py
├── reference_parser.py
├── multi_query_detector.py
├── normalizers/ (date_normalizer, amount_normalizer)
└── query_handlers/ (may need updates)

app/utils/
├── logger.py
└── permissions.py

app/api/routes/
└── chat.py (will be modified)
```

**Backup Strategy**:
```bash
# Create backup branch
git checkout -b backup-3stage-architecture
git add .
git commit -m "Backup: 3-stage architecture before migration"
git push origin backup-3stage-architecture

# Return to main branch
git checkout main
```


### Phase 2: Install Dependencies

**Objective**: Install Mistral 7B and required libraries.

**Dependencies to Add** (requirements.txt):

```txt
# Core ML Libraries
torch>=2.1.0
transformers>=4.36.0
accelerate>=0.25.0
bitsandbytes>=0.41.0  # For quantization

# Optional: Inference Optimization
# vllm>=0.2.0  # For production deployment

# Optional: Fine-tuning (if needed later)
# peft>=0.7.0  # For LoRA fine-tuning
# datasets>=2.15.0
```

**Installation Steps**:

```bash
# 1. Update requirements.txt
pip install torch>=2.1.0 transformers>=4.36.0 accelerate>=0.25.0 bitsandbytes>=0.41.0

# 2. Verify GPU availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"

# 3. Download Mistral 7B model (will be done programmatically in code)
# Model will be cached in ~/.cache/huggingface/
```

**GPU Memory Requirements**:
- Full precision (FP32): ~28GB (won't fit)
- Half precision (FP16): ~14GB (exact fit)
- 8-bit quantization: ~7GB (recommended)
- 4-bit quantization: ~3.5GB (fallback option)

**Recommended Configuration**: 8-bit quantization for optimal balance of quality and memory usage.


### Phase 3: Implement Core Service

**Objective**: Build the Mistral query processor with supporting components.

**New Files to Create**:

1. `app/services/mistral_service.py` - Main service
2. `app/services/system_prompt_builder.py` - Prompt construction
3. `app/services/context_manager.py` - Conversation context
4. `app/config/mistral_config.py` - Configuration
5. `app/config/prompt_templates.py` - Prompt templates

**Directory Structure After Phase 3**:

```
app/
├── services/
│   ├── mistral_service.py          # NEW
│   ├── system_prompt_builder.py    # NEW
│   ├── context_manager.py          # NEW
│   ├── conversation_db.py          # KEEP
│   ├── schema_provider.py          # KEEP
│   ├── sql_validator.py            # KEEP
│   ├── results_formatter.py        # KEEP
│   └── ...
├── config/
│   ├── mistral_config.py           # NEW
│   └── prompt_templates.py         # NEW
└── api/
    └── routes/
        └── chat.py                 # MODIFY
```


### Phase 4: Integration

**Objective**: Update chat route and integrate with existing utilities.

**Integration Points**:

1. **Chat API Route** (`app/api/routes/chat.py`):
   - Replace 3-stage orchestrator call with Mistral service
   - Keep conversation management
   - Keep result formatting

2. **Conversation Management**:
   - Reuse `conversation_db.py`
   - Reuse `conversation_handler.py`
   - Update `context_manager.py` to work with new format

3. **Security & Validation**:
   - Reuse `sql_validator.py`
   - Reuse `permissions.py`
   - Keep all security guardrails

4. **Utilities**:
   - Reuse `schema_provider.py`
   - Reuse `results_formatter.py`
   - Reuse `logger.py`

**Modified Chat Route Flow**:

```python
# OLD FLOW
query → orchestrator → t5_generator → lora_composer → database

# NEW FLOW
query → mistral_service → sql_validator → database
```


### Phase 5: Testing & Validation

**Objective**: Comprehensive testing and gradual rollout.

**Testing Strategy**:

1. **Unit Tests**:
   - Test Mistral service initialization
   - Test prompt builder with various schemas
   - Test context manager with conversation history
   - Test SQL extraction from model output

2. **Integration Tests**:
   - Test end-to-end query processing
   - Test conversation context across multiple queries
   - Test error handling and recovery
   - Test with real construction domain queries

3. **Performance Tests**:
   - Measure query latency
   - Monitor GPU memory usage
   - Test concurrent query handling
   - Validate 5-second target for simple queries

4. **Comparison Tests**:
   - Compare results with old system
   - Measure accuracy improvements
   - Document breaking changes

**Rollout Strategy**:

1. Deploy to staging environment
2. Run parallel testing (old vs new)
3. Gradual rollout: 10% → 50% → 100%
4. Monitor error rates and performance
5. Keep rollback plan ready


## Components and Interfaces

### 1. Mistral Service

**Purpose**: Main service that coordinates query processing using Mistral 7B.

**Responsibilities**:
- Load and manage Mistral 7B model
- Process natural language queries
- Extract SQL from model output
- Handle retries and error recovery
- Manage GPU memory

**Interface**:

```python
class MistralService:
    """Main service for processing queries with Mistral 7B."""
    
    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.1",
        quantization: str = "8bit",
        device: str = "cuda"
    ):
        """Initialize Mistral service with model configuration."""
        pass
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> QueryResult:
        """
        Process a natural language query and return results.
        
        Args:
            query: Natural language query from user
            user_id: User identifier for conversation tracking
            conversation_id: Optional conversation ID for context
            
        Returns:
            QueryResult with SQL, data, and metadata
            
        Raises:
            ModelLoadError: If model fails to load
            GenerationError: If model fails to generate valid output
            ValidationError: If generated SQL is invalid
        """
        pass
    
    def _load_model(self) -> None:
        """Load Mistral model with quantization."""
        pass
    
    def _generate_sql(
        self,
        query: str,
        system_prompt: str,
        max_retries: int = 3
    ) -> str:
        """Generate SQL from natural language query."""
        pass
    
    def _extract_sql(self, model_output: str) -> str:
        """Extract SQL query from model output."""
        pass
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current GPU memory usage."""
        pass
```

**Key Design Decisions**:
- Use 8-bit quantization by default for memory efficiency
- Support async operations for better concurrency
- Implement retry logic for transient failures
- Extract SQL using regex patterns and validation


### 2. System Prompt Builder

**Purpose**: Constructs comprehensive system prompts with schema, examples, and instructions.

**Responsibilities**:
- Load database schema from Schema Provider
- Format schema for model consumption
- Include example queries
- Add construction domain terminology
- Build conversation-aware prompts

**Interface**:

```python
class SystemPromptBuilder:
    """Builds system prompts for Mistral model."""
    
    def __init__(
        self,
        schema_provider: SchemaProvider,
        examples_path: str = "app/config/prompt_templates.py"
    ):
        """Initialize prompt builder with schema and examples."""
        pass
    
    def build_prompt(
        self,
        query: str,
        conversation_context: Optional[List[Dict]] = None,
        include_examples: bool = True
    ) -> str:
        """
        Build complete system prompt for query.
        
        Args:
            query: User's natural language query
            conversation_context: Previous queries and results
            include_examples: Whether to include example queries
            
        Returns:
            Complete system prompt string
        """
        pass
    
    def _format_schema(self, schema: Dict) -> str:
        """Format database schema for prompt."""
        pass
    
    def _get_relevant_examples(self, query: str) -> List[str]:
        """Get examples relevant to query type."""
        pass
    
    def _format_conversation_context(
        self,
        context: List[Dict]
    ) -> str:
        """Format conversation history for prompt."""
        pass
```

**Prompt Structure**:

```
[SYSTEM INSTRUCTIONS]
You are a SQL query generator for a construction management system.
Generate ONLY valid PostgreSQL SELECT queries. Do not include explanations.

[DATABASE SCHEMA]
<formatted schema with tables, columns, types, relationships>

[CONSTRUCTION DOMAIN TERMINOLOGY]
<entity definitions and category mappings>

[EXAMPLE QUERIES]
<5-10 example query patterns>

[CONVERSATION CONTEXT]
<previous queries and results if applicable>

[USER QUERY]
<current user query>

[OUTPUT FORMAT]
Return only the SQL query, starting with SELECT.
```


### 3. Context Manager

**Purpose**: Manages conversation history and context across queries.

**Responsibilities**:
- Store conversation history
- Retrieve relevant context for queries
- Resolve references to previous queries
- Manage token limits
- Clear expired conversations

**Interface**:

```python
class ContextManager:
    """Manages conversation context for Mistral queries."""
    
    def __init__(
        self,
        conversation_db: ConversationDB,
        max_history_length: int = 5,
        max_tokens: int = 2000
    ):
        """Initialize context manager."""
        pass
    
    async def get_context(
        self,
        conversation_id: str,
        current_query: str
    ) -> List[Dict]:
        """
        Get relevant conversation context.
        
        Args:
            conversation_id: Conversation identifier
            current_query: Current user query
            
        Returns:
            List of previous exchanges with queries and results
        """
        pass
    
    async def add_exchange(
        self,
        conversation_id: str,
        query: str,
        sql: str,
        results: Any
    ) -> None:
        """Add query exchange to conversation history."""
        pass
    
    def _resolve_references(
        self,
        query: str,
        context: List[Dict]
    ) -> str:
        """Resolve references like 'show me more', 'last month'."""
        pass
    
    def _truncate_context(
        self,
        context: List[Dict],
        max_tokens: int
    ) -> List[Dict]:
        """Truncate context to fit within token limit."""
        pass
    
    async def clear_conversation(
        self,
        conversation_id: str
    ) -> None:
        """Clear conversation history."""
        pass
```

**Context Format**:

```python
{
    "conversation_id": "uuid",
    "exchanges": [
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "query": "Show me expenses last month",
            "sql": "SELECT * FROM expenses WHERE date >= '2023-12-01'...",
            "result_summary": "Found 45 expenses totaling $12,500"
        },
        {
            "timestamp": "2024-01-15T10:31:00Z",
            "query": "What about labor costs?",
            "sql": "SELECT * FROM expenses WHERE category = 'labor'...",
            "result_summary": "Found 12 labor expenses totaling $8,200"
        }
    ]
}
```


### 4. Configuration Module

**Purpose**: Centralized configuration for Mistral service.

**Interface**:

```python
# app/config/mistral_config.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class MistralConfig:
    """Configuration for Mistral service."""
    
    # Model Configuration
    model_name: str = "mistralai/Mistral-7B-v0.1"
    quantization: str = "8bit"  # Options: "none", "8bit", "4bit"
    device: str = "cuda"
    device_map: str = "auto"
    
    # Generation Parameters
    temperature: float = 0.1  # Low for deterministic SQL
    max_new_tokens: int = 512
    top_p: float = 0.95
    top_k: int = 50
    do_sample: bool = True
    
    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Context Configuration
    max_conversation_history: int = 5
    max_context_tokens: int = 2000
    
    # Performance Configuration
    batch_size: int = 1
    max_concurrent_requests: int = 3
    
    # Timeout Configuration
    generation_timeout: int = 30  # seconds
    
    @classmethod
    def from_env(cls) -> "MistralConfig":
        """Load configuration from environment variables."""
        import os
        return cls(
            model_name=os.getenv("MISTRAL_MODEL", cls.model_name),
            quantization=os.getenv("MISTRAL_QUANTIZATION", cls.quantization),
            temperature=float(os.getenv("MISTRAL_TEMPERATURE", cls.temperature)),
            max_new_tokens=int(os.getenv("MISTRAL_MAX_TOKENS", cls.max_new_tokens)),
        )
```


## Data Models

### Query Result Model

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass
class QueryResult:
    """Result of processing a natural language query."""
    
    # Query Information
    query: str
    conversation_id: Optional[str]
    user_id: str
    timestamp: datetime
    
    # Generated SQL
    sql: str
    sql_valid: bool
    
    # Execution Results
    data: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    
    # Metadata
    model_generation_time_ms: float
    total_time_ms: float
    tokens_used: int
    
    # Error Information
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    # Context
    context_used: bool = False
    context_length: int = 0
```

### Conversation Context Model

```python
@dataclass
class ConversationExchange:
    """Single exchange in a conversation."""
    
    timestamp: datetime
    query: str
    sql: str
    result_summary: str
    row_count: int

@dataclass
class ConversationContext:
    """Conversation context for a user session."""
    
    conversation_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    exchanges: List[ConversationExchange]
    
    def get_recent_exchanges(self, n: int = 5) -> List[ConversationExchange]:
        """Get n most recent exchanges."""
        return self.exchanges[-n:]
    
    def to_prompt_format(self) -> str:
        """Format context for inclusion in system prompt."""
        if not self.exchanges:
            return ""
        
        lines = ["Previous conversation:"]
        for ex in self.exchanges[-5:]:
            lines.append(f"User: {ex.query}")
            lines.append(f"SQL: {ex.sql}")
            lines.append(f"Result: {ex.result_summary}")
        
        return "\n".join(lines)
```


### Model Loading Configuration

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelLoadConfig:
    """Configuration for loading Mistral model."""
    
    model_name: str
    quantization: str
    device: str
    device_map: str
    torch_dtype: str = "auto"
    trust_remote_code: bool = False
    
    def to_transformers_kwargs(self) -> dict:
        """Convert to kwargs for transformers.AutoModelForCausalLM.from_pretrained()."""
        kwargs = {
            "device_map": self.device_map,
            "torch_dtype": self.torch_dtype,
            "trust_remote_code": self.trust_remote_code,
        }
        
        if self.quantization == "8bit":
            kwargs["load_in_8bit"] = True
        elif self.quantization == "4bit":
            kwargs["load_in_4bit"] = True
        
        return kwargs
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, I identified several areas of redundancy:

1. **SQL Validation Properties (5.1-5.3, 5.5, 5.7)**: These can be combined into a comprehensive validation property
2. **Query Type Support (3.4-3.7, 7.2-7.5)**: Multiple properties about query type support can be consolidated
3. **Logging Properties (13.1-13.6)**: All logging requirements follow the same pattern and can be combined
4. **Configuration Properties (14.2-14.6)**: All configuration requirements can be unified
5. **Context Management (4.1, 4.2, 4.4, 4.7)**: Context properties can be consolidated into fewer comprehensive properties
6. **Schema Provider (8.1-8.4)**: Schema retrieval properties can be combined

The following properties represent the unique, non-redundant correctness requirements:


### Property 1: Schema Completeness in Prompts

*For any* database schema, the generated system prompt should contain all table names, column names, data types, and foreign key relationships from that schema.

**Validates: Requirements 2.1, 8.1, 8.2, 8.3, 8.4**

### Property 2: Query Processing with System Prompt

*For any* natural language query, the Query Processor should pass both the query and the complete system prompt to the Mistral model.

**Validates: Requirements 3.1**

### Property 3: SQL Extraction from Model Output

*For any* model response containing valid SQL, the Query Processor should successfully extract the SQL query.

**Validates: Requirements 3.2**

### Property 4: Query Type Support

*For any* valid query of supported types (date range, category, comparison, aggregation, construction-specific), the system should generate appropriate SQL that correctly represents the query intent.

**Validates: Requirements 3.4, 3.5, 3.6, 3.7, 7.2, 7.3, 7.4, 7.5**

### Property 5: Comprehensive SQL Validation

*For any* generated SQL query, the SQL Validator should verify that: (1) syntax is valid, (2) all referenced tables exist in the schema, (3) all referenced columns exist in their tables, (4) no destructive operations are present, (5) only allowed schema tables are accessed, and (6) only SELECT queries with standard clauses are allowed.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7**

### Property 6: Conversation Context Inclusion

*For any* query with existing conversation history, the Context Manager should include relevant previous exchanges in the system prompt, limited to the most recent N exchanges.

**Validates: Requirements 4.1, 4.2, 4.4**

### Property 7: Reference Resolution

*For any* query containing references to previous queries (e.g., "show me more", "what about last year"), the Context Manager should resolve these references using conversation history.

**Validates: Requirements 4.3, 4.6**

### Property 8: Token Limit Enforcement

*For any* conversation context, the combined system prompt (schema + examples + context + query) should not exceed the model's token limit.

**Validates: Requirements 4.7**

### Property 9: Ambiguity Detection

*For any* query with ambiguous entities, dates, project references, or missing required parameters, the Clarification Engine should detect the ambiguity.

**Validates: Requirements 6.1, 6.3, 6.4, 6.5**

### Property 10: Clarification Question Generation

*For any* detected ambiguity, the Clarification Engine should generate a specific clarification question rather than executing a potentially incorrect query.

**Validates: Requirements 6.2**

### Property 11: Clarification Context Integration

*For any* user-provided clarification, the Context Manager should incorporate it into the conversation context for subsequent queries.

**Validates: Requirements 6.7**


### Property 12: Schema Caching

*For any* repeated schema request within the cache validity period, the Schema Provider should return cached schema information without querying the database.

**Validates: Requirements 8.6**

### Property 13: Enum Sample Values

*For any* enum column or lookup table in the schema, the Schema Provider should include sample values in the formatted schema output.

**Validates: Requirements 8.7**

### Property 14: Error Message User-Friendliness

*For any* validation failure or execution failure, the system should provide a user-friendly error message explaining what went wrong.

**Validates: Requirements 9.2, 9.3**

### Property 15: Error Logging with Context

*For any* error that occurs in the system, it should be logged with sufficient context including stack trace, user ID, query, and timestamp.

**Validates: Requirements 9.6, 13.6**

### Property 16: GPU Memory Monitoring

*For any* model inference operation, the system should monitor and record GPU memory usage.

**Validates: Requirements 10.1**

### Property 17: Query Performance Targets

*For any* simple query, processing time should be under 5 seconds; for any complex query requiring clarification, processing time should be under 15 seconds.

**Validates: Requirements 10.3, 10.4**

### Property 18: Memory Release After Processing

*For any* completed query, the system should release GPU memory allocated for that query.

**Validates: Requirements 10.6**

### Property 19: Concurrent Query Support

*For any* set of concurrent queries that fit within GPU memory limits, the system should process them concurrently without failures.

**Validates: Requirements 10.7**

### Property 20: Result Formatting Consistency

*For any* successful SQL query execution, the results should be formatted as structured JSON with column names, data types, ISO 8601 dates, properly formatted currency, and appropriate NULL handling.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.7**

### Property 21: Result Set Limiting

*For any* query result exceeding the maximum row limit, the system should truncate the results and indicate the total number of matching rows.

**Validates: Requirements 12.5, 12.6**

### Property 22: Comprehensive Query Logging

*For any* processed query, the system should log: the natural language query, generated SQL, model inference time, token usage, validation results, execution time, and result row count.

**Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5**

### Property 23: Metrics Availability

*For any* monitoring request, the system should provide metrics including queries per second, average latency, and error rate.

**Validates: Requirements 13.8**

### Property 24: Configuration Flexibility

*For any* configurable parameter (model parameters, validation rules, retry behavior, context limits, feature flags), it should be settable via environment variables or configuration files.

**Validates: Requirements 14.2, 14.3, 14.4, 14.5, 14.6**

### Property 25: Configuration Validation

*For any* invalid configuration value, the system should detect it at startup and report a descriptive error before processing any queries.

**Validates: Requirements 14.7**

### Property 26: API Backward Compatibility

*For any* request in the old API format, the compatibility layer should accept and process it correctly.

**Validates: Requirements 15.1**

### Property 27: Conversation Data Migration

*For any* conversation stored in the old format, the migration script should convert it to the new format without data loss.

**Validates: Requirements 15.3, 15.6**


## Error Handling

### Error Categories

1. **Model Loading Errors**
   - GPU not available
   - Insufficient GPU memory
   - Model download failures
   - Invalid model configuration

2. **Generation Errors**
   - Model timeout
   - Non-SQL output generated
   - Empty or malformed output
   - Token limit exceeded

3. **Validation Errors**
   - Invalid SQL syntax
   - Non-existent tables or columns
   - Destructive operations detected
   - Unauthorized schema access

4. **Execution Errors**
   - Database connection failures
   - SQL execution errors
   - Permission denied
   - Query timeout

5. **Context Errors**
   - Conversation not found
   - Context too large for token limit
   - Invalid conversation format

### Error Handling Strategy

```python
class ErrorHandler:
    """Centralized error handling for Mistral service."""
    
    @staticmethod
    def handle_model_error(error: Exception) -> Dict[str, Any]:
        """Handle model loading and inference errors."""
        if isinstance(error, torch.cuda.OutOfMemoryError):
            return {
                "error": "Insufficient GPU memory",
                "suggestion": "Try using 8-bit or 4-bit quantization",
                "user_message": "The system is experiencing high load. Please try again in a moment."
            }
        elif isinstance(error, TimeoutError):
            return {
                "error": "Model generation timeout",
                "suggestion": "Reduce max_tokens or simplify query",
                "user_message": "Your query is taking too long to process. Please try a simpler question."
            }
        else:
            return {
                "error": str(error),
                "suggestion": "Check model configuration and GPU availability",
                "user_message": "We encountered an error processing your query. Please try again."
            }
    
    @staticmethod
    def handle_validation_error(
        sql: str,
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """Handle SQL validation errors."""
        return {
            "error": f"Invalid SQL: {validation_result.error}",
            "sql": sql,
            "rule_violated": validation_result.rule,
            "user_message": f"I couldn't generate a valid query: {validation_result.user_friendly_message}"
        }
    
    @staticmethod
    def handle_execution_error(
        sql: str,
        db_error: Exception
    ) -> Dict[str, Any]:
        """Handle database execution errors."""
        user_message = ErrorHandler._make_user_friendly(str(db_error))
        return {
            "error": str(db_error),
            "sql": sql,
            "user_message": user_message
        }
    
    @staticmethod
    def _make_user_friendly(db_error: str) -> str:
        """Convert database errors to user-friendly messages."""
        if "does not exist" in db_error:
            return "The requested data could not be found in the database."
        elif "permission denied" in db_error:
            return "You don't have permission to access this data."
        elif "timeout" in db_error:
            return "The query took too long to execute. Try narrowing your search."
        else:
            return "There was an error retrieving your data. Please try again."
```

### Retry Logic

```python
async def process_with_retry(
    query: str,
    max_retries: int = 3
) -> QueryResult:
    """Process query with retry logic."""
    
    for attempt in range(max_retries):
        try:
            # Generate SQL
            sql = await mistral_service.generate_sql(query)
            
            # Validate SQL
            validation = sql_validator.validate(sql)
            if not validation.is_valid:
                if attempt < max_retries - 1:
                    # Retry with additional instructions
                    query = f"{query}\n\nPrevious attempt failed: {validation.error}. Please fix."
                    continue
                else:
                    raise ValidationError(validation.error)
            
            # Execute SQL
            results = await database.execute(sql)
            return QueryResult(sql=sql, data=results)
            
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise
```


## Testing Strategy

### Dual Testing Approach

The system requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Both are complementary and necessary. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across a wide range of inputs.

### Property-Based Testing Configuration

We will use **Hypothesis** (Python's property-based testing library) for implementing correctness properties.

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: generative-ai-architecture, Property {number}: {property_text}`

**Example Property Test**:

```python
from hypothesis import given, strategies as st
import pytest

# Feature: generative-ai-architecture, Property 1: Schema Completeness in Prompts
@given(
    tables=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=20),  # table name
            st.lists(
                st.tuples(
                    st.text(min_size=1, max_size=20),  # column name
                    st.sampled_from(['TEXT', 'INTEGER', 'BOOLEAN', 'TIMESTAMP'])  # type
                ),
                min_size=1,
                max_size=10
            )
        ),
        min_size=1,
        max_size=5
    )
)
@pytest.mark.property_test
def test_schema_completeness_in_prompts(tables):
    """Property 1: For any database schema, the generated system prompt 
    should contain all table names, column names, and data types."""
    
    # Arrange: Create schema from generated tables
    schema = {table_name: columns for table_name, columns in tables}
    schema_provider = SchemaProvider(schema)
    prompt_builder = SystemPromptBuilder(schema_provider)
    
    # Act: Build prompt
    prompt = prompt_builder.build_prompt("test query")
    
    # Assert: All tables, columns, and types are in prompt
    for table_name, columns in tables:
        assert table_name in prompt, f"Table {table_name} missing from prompt"
        for col_name, col_type in columns:
            assert col_name in prompt, f"Column {col_name} missing from prompt"
            assert col_type in prompt, f"Type {col_type} missing from prompt"
```


### Unit Testing Strategy

Unit tests focus on specific examples, edge cases, and integration points:

**1. Model Loading Tests**:
```python
def test_model_loads_with_8bit_quantization():
    """Test that Mistral model loads successfully with 8-bit quantization."""
    service = MistralService(quantization="8bit")
    assert service.model is not None
    assert service.model.device.type == "cuda"

def test_model_load_failure_returns_error():
    """Test that model load failures return descriptive errors."""
    with pytest.raises(ModelLoadError) as exc_info:
        service = MistralService(model_name="invalid/model")
    assert "failed to load" in str(exc_info.value).lower()
```

**2. Prompt Building Tests**:
```python
def test_prompt_includes_schema():
    """Test that system prompt includes database schema."""
    schema = {"expenses": [("id", "INTEGER"), ("amount", "DECIMAL")]}
    prompt = prompt_builder.build_prompt("show expenses", schema)
    assert "expenses" in prompt
    assert "amount" in prompt
    assert "DECIMAL" in prompt

def test_prompt_includes_conversation_context():
    """Test that prompt includes previous conversation exchanges."""
    context = [
        {"query": "show expenses", "sql": "SELECT * FROM expenses", "result": "10 rows"}
    ]
    prompt = prompt_builder.build_prompt("show more", context=context)
    assert "show expenses" in prompt
    assert "10 rows" in prompt
```

**3. SQL Extraction Tests**:
```python
def test_extract_sql_from_model_output():
    """Test SQL extraction from various model output formats."""
    outputs = [
        "SELECT * FROM expenses WHERE date > '2024-01-01'",
        "Here's the query:\nSELECT * FROM expenses\nThis will show all expenses.",
        "```sql\nSELECT * FROM expenses\n```"
    ]
    for output in outputs:
        sql = mistral_service._extract_sql(output)
        assert sql.strip().startswith("SELECT")
        assert "expenses" in sql
```

**4. Validation Tests**:
```python
def test_validator_rejects_destructive_operations():
    """Test that validator rejects DROP, DELETE, UPDATE, INSERT."""
    destructive_queries = [
        "DROP TABLE expenses",
        "DELETE FROM expenses WHERE id = 1",
        "UPDATE expenses SET amount = 0",
        "INSERT INTO expenses VALUES (1, 100)"
    ]
    for query in destructive_queries:
        result = sql_validator.validate(query)
        assert not result.is_valid
        assert "destructive" in result.error.lower()

def test_validator_allows_valid_select():
    """Test that validator allows valid SELECT queries."""
    valid_queries = [
        "SELECT * FROM expenses",
        "SELECT * FROM expenses WHERE date > '2024-01-01'",
        "SELECT category, SUM(amount) FROM expenses GROUP BY category",
        "SELECT e.*, p.name FROM expenses e JOIN projects p ON e.project_id = p.id"
    ]
    for query in valid_queries:
        result = sql_validator.validate(query)
        assert result.is_valid
```

**5. Context Management Tests**:
```python
def test_context_manager_stores_exchanges():
    """Test that context manager stores conversation exchanges."""
    context_mgr = ContextManager()
    context_mgr.add_exchange(
        conversation_id="conv1",
        query="show expenses",
        sql="SELECT * FROM expenses",
        results={"rows": 10}
    )
    context = context_mgr.get_context("conv1")
    assert len(context) == 1
    assert context[0]["query"] == "show expenses"

def test_context_truncation_respects_token_limit():
    """Test that context is truncated to fit token limits."""
    context_mgr = ContextManager(max_tokens=100)
    # Add many exchanges
    for i in range(20):
        context_mgr.add_exchange(
            conversation_id="conv1",
            query=f"query {i}",
            sql=f"SELECT * FROM table{i}",
            results={"rows": i}
        )
    context = context_mgr.get_context("conv1")
    # Should be truncated
    assert len(context) < 20
```

**6. Error Handling Tests**:
```python
def test_retry_on_invalid_sql():
    """Test that system retries when model generates invalid SQL."""
    with patch.object(mistral_service, '_generate_sql') as mock_gen:
        mock_gen.side_effect = [
            "INVALID SQL",  # First attempt
            "SELECT * FROM expenses"  # Second attempt
        ]
        result = mistral_service.process_query("show expenses")
        assert result.sql == "SELECT * FROM expenses"
        assert mock_gen.call_count == 2

def test_user_friendly_error_messages():
    """Test that database errors are converted to user-friendly messages."""
    db_errors = [
        ('relation "invalid_table" does not exist', "could not be found"),
        ('permission denied for table expenses', "don't have permission"),
        ('canceling statement due to statement timeout', "took too long")
    ]
    for db_error, expected_phrase in db_errors:
        user_msg = ErrorHandler._make_user_friendly(db_error)
        assert expected_phrase in user_msg.lower()
```

**7. Integration Tests**:
```python
@pytest.mark.integration
async def test_end_to_end_query_processing():
    """Test complete query processing from input to results."""
    query = "Show me expenses from last month over $1000"
    result = await mistral_service.process_query(
        query=query,
        user_id="test_user"
    )
    assert result.sql is not None
    assert "expenses" in result.sql.lower()
    assert result.data is not None
    assert result.execution_time_ms > 0

@pytest.mark.integration
async def test_conversation_context_across_queries():
    """Test that conversation context works across multiple queries."""
    conv_id = "test_conv"
    
    # First query
    result1 = await mistral_service.process_query(
        query="Show me projects",
        user_id="test_user",
        conversation_id=conv_id
    )
    assert "projects" in result1.sql.lower()
    
    # Follow-up query with reference
    result2 = await mistral_service.process_query(
        query="Show me their expenses",
        user_id="test_user",
        conversation_id=conv_id
    )
    # Should reference projects from previous query
    assert "project" in result2.sql.lower() or "join" in result2.sql.lower()
```


### Performance Testing

```python
@pytest.mark.performance
async def test_simple_query_under_5_seconds():
    """Test that simple queries complete within 5 seconds."""
    start = time.time()
    result = await mistral_service.process_query(
        query="Show me all expenses",
        user_id="test_user"
    )
    elapsed = time.time() - start
    assert elapsed < 5.0, f"Query took {elapsed}s, expected < 5s"

@pytest.mark.performance
async def test_complex_query_under_15_seconds():
    """Test that complex queries complete within 15 seconds."""
    start = time.time()
    result = await mistral_service.process_query(
        query="Show me total expenses by category for each project in Q1 2024, "
              "comparing to budget and showing variance percentage",
        user_id="test_user"
    )
    elapsed = time.time() - start
    assert elapsed < 15.0, f"Query took {elapsed}s, expected < 15s"

@pytest.mark.performance
async def test_concurrent_query_handling():
    """Test that system handles concurrent queries within memory limits."""
    queries = [
        "Show me expenses",
        "Show me projects",
        "Show me documents"
    ]
    
    # Process concurrently
    results = await asyncio.gather(*[
        mistral_service.process_query(query, user_id=f"user_{i}")
        for i, query in enumerate(queries)
    ])
    
    assert len(results) == 3
    assert all(r.sql is not None for r in results)
```

### Test Coverage Goals

- **Unit Test Coverage**: Minimum 80% code coverage
- **Property Test Coverage**: All 27 correctness properties implemented
- **Integration Test Coverage**: All major user scenarios covered
- **Performance Test Coverage**: All performance requirements validated

### Continuous Testing

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov hypothesis pytest-asyncio
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=app --cov-report=xml
      
      - name: Run property tests
        run: pytest tests/property/ -v --hypothesis-show-statistics
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```


## Code Examples

### 1. Loading Mistral 7B with Quantization

```python
# app/services/mistral_service.py

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class MistralService:
    """Service for processing queries with Mistral 7B."""
    
    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.1",
        quantization: str = "8bit",
        device: str = "cuda"
    ):
        self.model_name = model_name
        self.quantization = quantization
        self.device = device
        self.model = None
        self.tokenizer = None
        
        self._load_model()
    
    def _load_model(self) -> None:
        """Load Mistral model with quantization."""
        try:
            logger.info(f"Loading {self.model_name} with {self.quantization} quantization")
            
            # Check GPU availability
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available. GPU is required.")
            
            # Check GPU memory
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"Available GPU memory: {gpu_memory:.2f} GB")
            
            if gpu_memory < 6:
                raise RuntimeError(
                    f"Insufficient GPU memory: {gpu_memory:.2f} GB. "
                    "At least 6 GB required for 8-bit quantization."
                )
            
            # Configure quantization
            quantization_config = None
            if self.quantization == "8bit":
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_threshold=6.0
                )
            elif self.quantization == "4bit":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=torch.float16 if quantization_config is None else None,
                trust_remote_code=False
            )
            
            logger.info("Model loaded successfully")
            self._log_memory_usage()
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Failed to load {self.model_name}: {str(e)}")
    
    def _log_memory_usage(self) -> None:
        """Log current GPU memory usage."""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            logger.info(f"GPU Memory - Allocated: {allocated:.2f} GB, Reserved: {reserved:.2f} GB")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current GPU memory usage."""
        if not torch.cuda.is_available():
            return {"allocated_gb": 0, "reserved_gb": 0, "free_gb": 0}
        
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        free = total - allocated
        
        return {
            "allocated_gb": allocated,
            "reserved_gb": reserved,
            "free_gb": free,
            "total_gb": total
        }


class ModelLoadError(Exception):
    """Exception raised when model fails to load."""
    pass
```


### 2. Building System Prompts

```python
# app/services/system_prompt_builder.py

from typing import List, Dict, Optional
from app.services.schema_provider import SchemaProvider

class SystemPromptBuilder:
    """Builds comprehensive system prompts for Mistral model."""
    
    def __init__(self, schema_provider: SchemaProvider):
        self.schema_provider = schema_provider
    
    def build_prompt(
        self,
        query: str,
        conversation_context: Optional[List[Dict]] = None,
        include_examples: bool = True
    ) -> str:
        """Build complete system prompt for query."""
        
        sections = []
        
        # 1. System Instructions
        sections.append(self._get_system_instructions())
        
        # 2. Database Schema
        schema = self.schema_provider.get_schema()
        sections.append(self._format_schema(schema))
        
        # 3. Construction Domain Terminology
        sections.append(self._get_domain_terminology())
        
        # 4. Example Queries (if requested)
        if include_examples:
            sections.append(self._get_example_queries())
        
        # 5. Conversation Context (if available)
        if conversation_context:
            sections.append(self._format_conversation_context(conversation_context))
        
        # 6. User Query
        sections.append(f"\n[USER QUERY]\n{query}\n")
        
        # 7. Output Format Instructions
        sections.append(self._get_output_format())
        
        return "\n\n".join(sections)
    
    def _get_system_instructions(self) -> str:
        """Get system instructions."""
        return """[SYSTEM INSTRUCTIONS]
You are a SQL query generator for a construction management system.
Your task is to convert natural language queries into valid PostgreSQL SELECT queries.

IMPORTANT RULES:
- Generate ONLY valid PostgreSQL SELECT queries
- Do NOT include explanations, comments, or markdown formatting
- Do NOT use destructive operations (DROP, DELETE, UPDATE, INSERT, TRUNCATE)
- Use proper JOIN syntax when querying multiple tables
- Use appropriate WHERE clauses for filtering
- Use GROUP BY for aggregations
- Always include LIMIT clause to prevent overwhelming results (default: LIMIT 100)
- Return only the SQL query, nothing else"""
    
    def _format_schema(self, schema: Dict) -> str:
        """Format database schema for prompt."""
        lines = ["[DATABASE SCHEMA]"]
        
        for table_name, table_info in schema.items():
            lines.append(f"\nTable: {table_name}")
            lines.append("Columns:")
            
            for column in table_info["columns"]:
                col_line = f"  - {column['name']} ({column['type']})"
                if column.get("nullable") is False:
                    col_line += " NOT NULL"
                if column.get("primary_key"):
                    col_line += " PRIMARY KEY"
                lines.append(col_line)
            
            # Foreign keys
            if table_info.get("foreign_keys"):
                lines.append("Foreign Keys:")
                for fk in table_info["foreign_keys"]:
                    lines.append(
                        f"  - {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                    )
        
        return "\n".join(lines)
    
    def _get_domain_terminology(self) -> str:
        """Get construction domain terminology."""
        return """[CONSTRUCTION DOMAIN TERMINOLOGY]

Entity Definitions:
- Expenses: Financial transactions for construction costs (labor, materials, equipment, etc.)
- Projects: Construction projects with budgets, timelines, and deliverables
- Documents: Project-related files (contracts, invoices, permits, drawings)
- Cashflow: Money movement in and out of projects
- Vendors: Suppliers and subcontractors
- Materials: Construction materials and supplies
- Labor: Worker time and costs

Category Mappings:
- "labor costs" -> category = 'labor'
- "material costs" -> category = 'materials'
- "equipment" -> category = 'equipment'
- "subcontractors" -> category = 'subcontractor'
- "permits" -> category = 'permits'

Common Metrics:
- Budget: Planned spending for a project
- Actual Cost: Real spending to date
- Variance: Difference between budget and actual (budget - actual)
- Completion Percentage: Progress toward project completion

Time Periods:
- "last month" -> date >= (current_date - interval '1 month')
- "this year" -> date >= date_trunc('year', current_date)
- "Q1 2024" -> date >= '2024-01-01' AND date < '2024-04-01'"""
    
    def _get_example_queries(self) -> str:
        """Get example queries."""
        return """[EXAMPLE QUERIES]

Example 1 - Simple filtering:
User: "Show me expenses from last month"
SQL: SELECT * FROM expenses WHERE date >= (CURRENT_DATE - INTERVAL '1 month') LIMIT 100;

Example 2 - Category filtering:
User: "Show me labor expenses"
SQL: SELECT * FROM expenses WHERE category = 'labor' LIMIT 100;

Example 3 - Comparison:
User: "Show me expenses over $5000"
SQL: SELECT * FROM expenses WHERE amount > 5000 ORDER BY amount DESC LIMIT 100;

Example 4 - Aggregation:
User: "What's the total expenses by category?"
SQL: SELECT category, SUM(amount) as total FROM expenses GROUP BY category ORDER BY total DESC;

Example 5 - Join with projects:
User: "Show me expenses for the Downtown Office project"
SQL: SELECT e.* FROM expenses e JOIN projects p ON e.project_id = p.id WHERE p.name ILIKE '%Downtown Office%' LIMIT 100;

Example 6 - Date range with aggregation:
User: "Total expenses per month in 2024"
SQL: SELECT DATE_TRUNC('month', date) as month, SUM(amount) as total FROM expenses WHERE date >= '2024-01-01' AND date < '2025-01-01' GROUP BY month ORDER BY month;"""
    
    def _format_conversation_context(self, context: List[Dict]) -> str:
        """Format conversation history for prompt."""
        if not context:
            return ""
        
        lines = ["[CONVERSATION CONTEXT]", "Previous exchanges:"]
        
        for exchange in context[-5:]:  # Last 5 exchanges
            lines.append(f"\nUser: {exchange['query']}")
            lines.append(f"SQL: {exchange['sql']}")
            if exchange.get('result_summary'):
                lines.append(f"Result: {exchange['result_summary']}")
        
        lines.append("\nUse this context to resolve references in the current query.")
        return "\n".join(lines)
    
    def _get_output_format(self) -> str:
        """Get output format instructions."""
        return """[OUTPUT FORMAT]
Return ONLY the SQL query. Start with SELECT. Do not include:
- Explanations
- Markdown code blocks (no ```sql)
- Comments
- Multiple queries

Example correct output:
SELECT * FROM expenses WHERE date > '2024-01-01' LIMIT 100;"""
```


### 3. Generating SQL with Mistral

```python
# app/services/mistral_service.py (continued)

import re
import asyncio
from typing import Optional
from app.models.query_result import QueryResult
from app.services.system_prompt_builder import SystemPromptBuilder
from app.services.context_manager import ContextManager
from app.services.sql_validator import SQLValidator
from app.services.supabase_client import SupabaseClient

class MistralService:
    # ... (previous code)
    
    def __init__(self, config: MistralConfig):
        self.config = config
        self.prompt_builder = SystemPromptBuilder(schema_provider)
        self.context_manager = ContextManager()
        self.sql_validator = SQLValidator()
        self.db_client = SupabaseClient()
        
        self._load_model()
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> QueryResult:
        """Process a natural language query and return results."""
        
        start_time = time.time()
        
        try:
            # Get conversation context
            context = None
            if conversation_id:
                context = await self.context_manager.get_context(conversation_id, query)
            
            # Build system prompt
            system_prompt = self.prompt_builder.build_prompt(query, context)
            
            # Generate SQL with retries
            sql = await self._generate_sql_with_retry(
                query=query,
                system_prompt=system_prompt,
                max_retries=self.config.max_retries
            )
            
            # Validate SQL
            validation = self.sql_validator.validate(sql)
            if not validation.is_valid:
                raise ValidationError(f"Invalid SQL: {validation.error}")
            
            # Execute SQL
            results = await self.db_client.execute(sql)
            
            # Format results
            formatted_results = self._format_results(results)
            
            # Store in conversation context
            if conversation_id:
                await self.context_manager.add_exchange(
                    conversation_id=conversation_id,
                    query=query,
                    sql=sql,
                    results=formatted_results
                )
            
            # Build result
            total_time = (time.time() - start_time) * 1000
            
            return QueryResult(
                query=query,
                conversation_id=conversation_id,
                user_id=user_id,
                timestamp=datetime.now(),
                sql=sql,
                sql_valid=True,
                data=formatted_results["rows"],
                row_count=formatted_results["count"],
                execution_time_ms=formatted_results["execution_time_ms"],
                total_time_ms=total_time,
                tokens_used=formatted_results.get("tokens_used", 0),
                context_used=context is not None,
                context_length=len(context) if context else 0
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return QueryResult(
                query=query,
                user_id=user_id,
                timestamp=datetime.now(),
                sql="",
                sql_valid=False,
                data=[],
                row_count=0,
                execution_time_ms=0,
                total_time_ms=(time.time() - start_time) * 1000,
                tokens_used=0,
                error=str(e),
                error_type=type(e).__name__
            )
    
    async def _generate_sql_with_retry(
        self,
        query: str,
        system_prompt: str,
        max_retries: int = 3
    ) -> str:
        """Generate SQL with retry logic."""
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Add retry context to prompt if not first attempt
                if attempt > 0:
                    system_prompt += f"\n\nPrevious attempt failed: {last_error}. Please generate a valid SQL query."
                
                # Generate SQL
                sql = await self._generate_sql(system_prompt, query)
                
                # Extract SQL from output
                sql = self._extract_sql(sql)
                
                if sql:
                    return sql
                else:
                    last_error = "No SQL found in output"
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        
        raise GenerationError(f"Failed to generate SQL after {max_retries} attempts: {last_error}")
    
    async def _generate_sql(self, system_prompt: str, query: str) -> str:
        """Generate SQL using Mistral model."""
        
        # Combine system prompt and query
        full_prompt = f"{system_prompt}\n\nGenerate SQL for: {query}"
        
        # Tokenize
        inputs = self.tokenizer(
            full_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=4096
        ).to(self.device)
        
        # Generate
        gen_start = time.time()
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                do_sample=self.config.do_sample,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        gen_time = (time.time() - gen_start) * 1000
        logger.info(f"Generation took {gen_time:.2f}ms")
        
        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the new generated part (after the prompt)
        generated_text = generated_text[len(full_prompt):].strip()
        
        return generated_text
    
    def _extract_sql(self, text: str) -> Optional[str]:
        """Extract SQL query from model output."""
        
        # Remove markdown code blocks
        text = re.sub(r'```sql\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find SELECT statement
        patterns = [
            r'(SELECT\s+.+?;)',  # With semicolon
            r'(SELECT\s+.+?)(?:\n\n|\Z)',  # Until double newline or end
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1).strip()
                # Clean up
                sql = sql.rstrip(';').strip() + ';'
                return sql
        
        # If no pattern matches, check if entire text is SQL
        if text.strip().upper().startswith('SELECT'):
            return text.strip().rstrip(';') + ';'
        
        return None
    
    def _format_results(self, results: Dict) -> Dict:
        """Format query results."""
        return {
            "rows": results.get("data", []),
            "count": len(results.get("data", [])),
            "execution_time_ms": results.get("execution_time_ms", 0),
            "tokens_used": results.get("tokens_used", 0)
        }


class GenerationError(Exception):
    """Exception raised when SQL generation fails."""
    pass


class ValidationError(Exception):
    """Exception raised when SQL validation fails."""
    pass
```


### 4. Context Manager Implementation

```python
# app/services/context_manager.py

from typing import List, Dict, Optional
from datetime import datetime
from app.services.conversation_db import ConversationDB
from app.models.conversation import ConversationExchange

class ContextManager:
    """Manages conversation context for Mistral queries."""
    
    def __init__(
        self,
        conversation_db: ConversationDB,
        max_history_length: int = 5,
        max_tokens: int = 2000
    ):
        self.conversation_db = conversation_db
        self.max_history_length = max_history_length
        self.max_tokens = max_tokens
    
    async def get_context(
        self,
        conversation_id: str,
        current_query: str
    ) -> List[Dict]:
        """Get relevant conversation context."""
        
        # Retrieve conversation history
        conversation = await self.conversation_db.get_conversation(conversation_id)
        
        if not conversation or not conversation.exchanges:
            return []
        
        # Get recent exchanges
        recent_exchanges = conversation.get_recent_exchanges(self.max_history_length)
        
        # Resolve references in current query
        resolved_query = self._resolve_references(current_query, recent_exchanges)
        
        # Truncate to fit token limit
        context = self._truncate_context(recent_exchanges, self.max_tokens)
        
        return [
            {
                "query": ex.query,
                "sql": ex.sql,
                "result_summary": ex.result_summary,
                "timestamp": ex.timestamp.isoformat()
            }
            for ex in context
        ]
    
    async def add_exchange(
        self,
        conversation_id: str,
        query: str,
        sql: str,
        results: Dict
    ) -> None:
        """Add query exchange to conversation history."""
        
        # Create result summary
        result_summary = self._create_result_summary(results)
        
        # Create exchange
        exchange = ConversationExchange(
            timestamp=datetime.now(),
            query=query,
            sql=sql,
            result_summary=result_summary,
            row_count=results.get("count", 0)
        )
        
        # Store in database
        await self.conversation_db.add_exchange(conversation_id, exchange)
    
    def _resolve_references(
        self,
        query: str,
        context: List[ConversationExchange]
    ) -> str:
        """Resolve references like 'show me more', 'last month'."""
        
        if not context:
            return query
        
        query_lower = query.lower()
        
        # Reference patterns
        reference_patterns = {
            "show me more": "previous query",
            "show more": "previous query",
            "what about": "related to previous",
            "their": "from previous query",
            "those": "from previous query",
            "them": "from previous query"
        }
        
        # Check for references
        for pattern, meaning in reference_patterns.items():
            if pattern in query_lower:
                # Add context hint
                last_exchange = context[-1]
                query += f" (referring to: {last_exchange.query})"
                break
        
        return query
    
    def _truncate_context(
        self,
        context: List[ConversationExchange],
        max_tokens: int
    ) -> List[ConversationExchange]:
        """Truncate context to fit within token limit."""
        
        # Rough estimate: 1 token ≈ 4 characters
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token
        
        truncated = []
        total_chars = 0
        
        # Add exchanges from most recent, working backwards
        for exchange in reversed(context):
            exchange_chars = len(exchange.query) + len(exchange.sql) + len(exchange.result_summary)
            
            if total_chars + exchange_chars > max_chars:
                break
            
            truncated.insert(0, exchange)
            total_chars += exchange_chars
        
        return truncated
    
    def _create_result_summary(self, results: Dict) -> str:
        """Create a summary of query results."""
        
        row_count = results.get("count", 0)
        
        if row_count == 0:
            return "No results found"
        elif row_count == 1:
            return "Found 1 result"
        else:
            return f"Found {row_count} results"
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation history."""
        await self.conversation_db.delete_conversation(conversation_id)
```


### 5. Integration with Chat API

```python
# app/api/routes/chat.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from app.services.mistral_service import MistralService
from app.services.sql_validator import SQLValidator
from app.services.results_formatter import ResultsFormatter
from app.utils.logger import get_logger
from app.utils.permissions import check_user_permissions

router = APIRouter()
logger = get_logger(__name__)

# Initialize services (singleton pattern)
mistral_service = None

def get_mistral_service() -> MistralService:
    """Get or create Mistral service instance."""
    global mistral_service
    if mistral_service is None:
        from app.config.mistral_config import MistralConfig
        config = MistralConfig.from_env()
        mistral_service = MistralService(config)
    return mistral_service


class ChatRequest(BaseModel):
    """Chat request model."""
    query: str
    user_id: str
    conversation_id: Optional[str] = None
    organization_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    sql: Optional[str] = None
    execution_time_ms: float
    conversation_id: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: MistralService = Depends(get_mistral_service)
):
    """
    Process a natural language query and return results.
    
    This endpoint replaces the old 3-stage architecture with a single
    Mistral 7B model that handles query understanding and SQL generation.
    """
    
    try:
        logger.info(f"Processing query for user {request.user_id}: {request.query}")
        
        # Check permissions
        if request.organization_id:
            has_permission = await check_user_permissions(
                request.user_id,
                request.organization_id
            )
            if not has_permission:
                raise HTTPException(status_code=403, detail="Permission denied")
        
        # Process query with Mistral
        result = await service.process_query(
            query=request.query,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        )
        
        # Check for errors
        if result.error:
            logger.error(f"Query processing failed: {result.error}")
            return ChatResponse(
                success=False,
                error=result.error,
                execution_time_ms=result.total_time_ms
            )
        
        # Format response
        return ChatResponse(
            success=True,
            data={
                "rows": result.data,
                "row_count": result.row_count,
                "columns": _extract_columns(result.data)
            },
            sql=result.sql,
            execution_time_ms=result.total_time_ms,
            conversation_id=result.conversation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _extract_columns(data: list) -> list:
    """Extract column names from result data."""
    if not data:
        return []
    return list(data[0].keys()) if data else []


@router.post("/chat/clear")
async def clear_conversation(
    conversation_id: str,
    user_id: str,
    service: MistralService = Depends(get_mistral_service)
):
    """Clear conversation history."""
    
    try:
        await service.context_manager.clear_conversation(conversation_id)
        return {"success": True, "message": "Conversation cleared"}
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/health")
async def health_check(service: MistralService = Depends(get_mistral_service)):
    """Check service health and GPU status."""
    
    try:
        memory_usage = service.get_memory_usage()
        
        return {
            "status": "healthy",
            "model_loaded": service.model is not None,
            "gpu_memory": memory_usage,
            "model_name": service.model_name
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```


### 6. Reusing Existing Security Components

```python
# Integration with existing SQL validator

from app.services.sql_validator import SQLValidator

# The existing SQL validator can be reused as-is
validator = SQLValidator()

# Example usage in Mistral service
validation_result = validator.validate(generated_sql)

if not validation_result.is_valid:
    logger.warning(f"SQL validation failed: {validation_result.error}")
    # Retry with additional instructions
    raise ValidationError(validation_result.error)

# The validator already checks:
# - Valid SQL syntax
# - Table existence
# - Column existence
# - No destructive operations (DROP, DELETE, UPDATE, INSERT)
# - Schema access restrictions
```

```python
# Integration with existing results formatter

from app.services.results_formatter import ResultsFormatter

formatter = ResultsFormatter()

# Format query results
formatted = formatter.format_results(
    data=query_results,
    columns=column_info,
    format_dates=True,
    format_currency=True
)

# The formatter already handles:
# - JSON formatting
# - Date formatting (ISO 8601)
# - Currency formatting
# - NULL value handling
# - Result truncation
```

```python
# Integration with existing database client

from app.services.supabase_client import SupabaseClient

db_client = SupabaseClient()

# Execute SQL query
results = await db_client.execute_query(
    sql=generated_sql,
    user_id=user_id,
    organization_id=org_id
)

# The client already handles:
# - Connection pooling
# - Query execution
# - Error handling
# - Permission checks
# - Row-level security
```


## File Structure Changes

### Before Migration (3-Stage Architecture)

```
project/
├── app/
│   ├── services/
│   │   ├── stage1/
│   │   │   ├── orchestrator.py          ❌ DELETE
│   │   │   └── db_clarification.py      ❌ DELETE
│   │   ├── stage2/
│   │   │   ├── t5_sql_generator.py      ❌ DELETE
│   │   │   └── sql_guardrails.py        ✅ KEEP
│   │   ├── stage3/
│   │   │   ├── answer_composer.py       ❌ DELETE
│   │   │   └── clarification_composer.py ❌ DELETE
│   │   ├── intent_router.py             ❌ DELETE
│   │   ├── context_aware_intent_detector.py ❌ DELETE
│   │   ├── query_parser.py              ❌ DELETE
│   │   ├── semantic_extractor.py        ❌ DELETE
│   │   ├── semantic_extractor_v2.py     ❌ DELETE
│   │   ├── text_to_sql_service.py       ❌ DELETE
│   │   ├── router_service.py            ❌ DELETE
│   │   ├── embedding_service.py         ❌ DELETE (if only for old system)
│   │   ├── conversation_db.py           ✅ KEEP
│   │   ├── conversation_handler.py      ✅ KEEP
│   │   ├── schema_provider.py           ✅ KEEP
│   │   ├── sql_validator.py             ✅ KEEP
│   │   ├── results_formatter.py         ✅ KEEP
│   │   └── supabase_client.py           ✅ KEEP
│   └── api/
│       └── routes/
│           └── chat.py                  🔄 MODIFY
├── ml/
│   └── training/
│       ├── adapt_massive_to_stage1.py   ❌ DELETE
│       ├── finetune_t5_construction.py  ❌ DELETE
│       ├── generate_orchestrator_dataset.py ❌ DELETE
│       ├── generate_stage3_dataset.py   ❌ DELETE
│       ├── generate_t5_*.py             ❌ DELETE
│       ├── lora_training*.py            ❌ DELETE
│       ├── train_*.py                   ❌ DELETE
│       ├── *_Training_Colab.ipynb       ❌ DELETE
│       ├── *_TRAINING_GUIDE.md          ❌ DELETE
│       └── data/                        ❌ DELETE (all datasets)
└── docs/
    ├── 3STAGE_ARCHITECTURE.md           ❌ DELETE (or archive)
    ├── TRAINING_GUIDE.md                ❌ DELETE (or archive)
    └── DEPLOYMENT_GUIDE.md              🔄 UPDATE
```

### After Migration (Mistral Architecture)

```
project/
├── app/
│   ├── services/
│   │   ├── mistral_service.py           ✨ NEW
│   │   ├── system_prompt_builder.py    ✨ NEW
│   │   ├── context_manager.py          ✨ NEW
│   │   ├── conversation_db.py          ✅ KEPT
│   │   ├── conversation_handler.py     ✅ KEPT
│   │   ├── conversation_memory_manager.py ✅ KEPT
│   │   ├── schema_provider.py          ✅ KEPT
│   │   ├── schema_introspection.py     ✅ KEPT
│   │   ├── sql_validator.py            ✅ KEPT
│   │   ├── results_formatter.py        ✅ KEPT
│   │   ├── supabase_client.py          ✅ KEPT
│   │   ├── clarification_engine.py     ✅ KEPT
│   │   ├── ambiguity_detector.py       ✅ KEPT
│   │   ├── reference_parser.py         ✅ KEPT
│   │   ├── vocabulary_service.py       ✅ KEPT
│   │   ├── normalizers/
│   │   │   ├── date_normalizer.py      ✅ KEPT
│   │   │   └── amount_normalizer.py    ✅ KEPT
│   │   └── query_handlers/
│   │       └── universal_handler.py    ✅ KEPT (may need updates)
│   ├── config/
│   │   ├── mistral_config.py           ✨ NEW
│   │   └── prompt_templates.py         ✨ NEW
│   ├── models/
│   │   ├── query_result.py             🔄 UPDATE
│   │   └── conversation.py             ✅ KEPT
│   ├── api/
│   │   └── routes/
│   │       └── chat.py                 🔄 MODIFIED
│   └── utils/
│       ├── logger.py                   ✅ KEPT
│       └── permissions.py              ✅ KEPT
├── tests/
│   ├── unit/
│   │   ├── test_mistral_service.py     ✨ NEW
│   │   ├── test_prompt_builder.py     ✨ NEW
│   │   └── test_context_manager.py    ✨ NEW
│   ├── property/
│   │   └── test_properties.py          ✨ NEW
│   └── integration/
│       └── test_end_to_end.py          ✨ NEW
├── docs/
│   ├── MISTRAL_ARCHITECTURE.md         ✨ NEW
│   ├── MIGRATION_GUIDE.md              ✨ NEW
│   └── API_DOCUMENTATION.md            🔄 UPDATE
└── requirements.txt                    🔄 UPDATE
```

### Summary of Changes

**Deleted**: 50+ files (all 3-stage architecture code and training scripts)
**Kept**: 20+ files (database, security, utilities)
**New**: 8 files (Mistral service and supporting components)
**Modified**: 5 files (chat API, config, docs)

**Net Result**: Simpler codebase with ~60% fewer files


## Deployment Considerations

### Hardware Requirements

**Minimum Requirements**:
- GPU: 14GB VRAM (e.g., NVIDIA RTX 3090, A4000)
- RAM: 32GB system memory
- Storage: 50GB for model cache
- CUDA: Version 11.8 or higher

**Recommended Requirements**:
- GPU: 24GB VRAM (e.g., NVIDIA RTX 4090, A5000)
- RAM: 64GB system memory
- Storage: 100GB SSD for model cache
- CUDA: Version 12.0 or higher

### Environment Configuration

```bash
# .env file

# Model Configuration
MISTRAL_MODEL=mistralai/Mistral-7B-v0.1
MISTRAL_QUANTIZATION=8bit
MISTRAL_TEMPERATURE=0.1
MISTRAL_MAX_TOKENS=512

# Performance Configuration
MISTRAL_MAX_RETRIES=3
MISTRAL_RETRY_DELAY=1.0
MISTRAL_GENERATION_TIMEOUT=30

# Context Configuration
MISTRAL_MAX_CONVERSATION_HISTORY=5
MISTRAL_MAX_CONTEXT_TOKENS=2000

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/construction_db
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/mistral-service.log
```

### Docker Deployment

```dockerfile
# Dockerfile

FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY .env .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  mistral-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MISTRAL_MODEL=mistralai/Mistral-7B-v0.1
      - MISTRAL_QUANTIZATION=8bit
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - model-cache:/root/.cache/huggingface
      - ./logs:/var/log
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  model-cache:
```

### Monitoring and Observability

```python
# app/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
query_counter = Counter('mistral_queries_total', 'Total queries processed')
query_duration = Histogram('mistral_query_duration_seconds', 'Query processing duration')
gpu_memory_usage = Gauge('mistral_gpu_memory_bytes', 'GPU memory usage')
error_counter = Counter('mistral_errors_total', 'Total errors', ['error_type'])

class MetricsCollector:
    """Collect metrics for monitoring."""
    
    @staticmethod
    def record_query(duration_ms: float, success: bool):
        """Record query metrics."""
        query_counter.inc()
        query_duration.observe(duration_ms / 1000)
        
        if not success:
            error_counter.labels(error_type='query_failed').inc()
    
    @staticmethod
    def record_gpu_memory(allocated_bytes: float):
        """Record GPU memory usage."""
        gpu_memory_usage.set(allocated_bytes)
    
    @staticmethod
    def record_error(error_type: str):
        """Record error."""
        error_counter.labels(error_type=error_type).inc()
```

### Health Checks

```python
# app/api/routes/health.py

from fastapi import APIRouter
import torch

router = APIRouter()

@router.get("/health")
async def health_check():
    """Comprehensive health check."""
    
    checks = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check GPU
    checks["checks"]["gpu"] = {
        "available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
    }
    
    # Check model
    from app.api.routes.chat import get_mistral_service
    service = get_mistral_service()
    checks["checks"]["model"] = {
        "loaded": service.model is not None,
        "name": service.model_name
    }
    
    # Check database
    try:
        from app.services.supabase_client import SupabaseClient
        db = SupabaseClient()
        await db.health_check()
        checks["checks"]["database"] = {"status": "connected"}
    except Exception as e:
        checks["checks"]["database"] = {"status": "error", "error": str(e)}
        checks["status"] = "degraded"
    
    return checks

@router.get("/ready")
async def readiness_check():
    """Readiness check for load balancer."""
    
    from app.api.routes.chat import get_mistral_service
    service = get_mistral_service()
    
    if service.model is None:
        return {"ready": False, "reason": "Model not loaded"}
    
    if not torch.cuda.is_available():
        return {"ready": False, "reason": "GPU not available"}
    
    return {"ready": True}
```

### Scaling Considerations

**Vertical Scaling** (Recommended):
- Single instance with powerful GPU
- Simpler deployment and management
- Better for model inference workloads

**Horizontal Scaling** (Advanced):
- Multiple instances with load balancer
- Requires model replication across GPUs
- More complex but higher throughput
- Consider using vLLM for efficient serving

**Load Balancing Strategy**:
```nginx
# nginx.conf

upstream mistral_backend {
    least_conn;  # Route to least busy server
    server mistral-1:8000 max_fails=3 fail_timeout=30s;
    server mistral-2:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    
    location /api/chat {
        proxy_pass http://mistral_backend;
        proxy_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```


## Migration Execution Plan

### Pre-Migration Checklist

- [ ] Backup current database
- [ ] Create git backup branch
- [ ] Document current API endpoints
- [ ] Export conversation history
- [ ] Test GPU availability and memory
- [ ] Review and approve design document
- [ ] Set up staging environment
- [ ] Prepare rollback plan

### Phase 1: Backup & Cleanup (Day 1)

**Duration**: 2-4 hours

**Steps**:

1. **Create Backup**:
```bash
# Create backup branch
git checkout -b backup-3stage-architecture
git add .
git commit -m "Backup: 3-stage architecture before migration"
git push origin backup-3stage-architecture

# Backup database
python scripts/backup_database.py --output backup_$(date +%Y%m%d).sql

# Export conversation data
python scripts/export_conversations.py --output conversations_backup.json
```

2. **Delete Old Code**:
```bash
# Return to main branch
git checkout main

# Delete stage directories
rm -rf app/services/stage1/
rm -rf app/services/stage2/t5_sql_generator.py
rm -rf app/services/stage3/

# Delete old service files
rm app/services/intent_router.py
rm app/services/context_aware_intent_detector.py
rm app/services/query_parser.py
rm app/services/semantic_extractor*.py
rm app/services/text_to_sql_service.py
rm app/services/router_service.py

# Delete training code
rm -rf ml/training/

# Commit deletions
git add .
git commit -m "Phase 1: Remove 3-stage architecture code"
```

3. **Verify Kept Files**:
```bash
# Ensure these still exist
ls app/services/conversation_db.py
ls app/services/schema_provider.py
ls app/services/sql_validator.py
ls app/services/results_formatter.py
```

### Phase 2: Install Dependencies (Day 1)

**Duration**: 1-2 hours

**Steps**:

1. **Update requirements.txt**:
```bash
# Add new dependencies
cat >> requirements.txt << EOF

# Mistral 7B Dependencies
torch>=2.1.0
transformers>=4.36.0
accelerate>=0.25.0
bitsandbytes>=0.41.0

# Testing
hypothesis>=6.92.0
pytest-asyncio>=0.21.0
EOF
```

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Verify GPU**:
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

4. **Download Model** (optional pre-download):
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# This will cache the model
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")
print("Model cached successfully")
```

### Phase 3: Implement Core Service (Days 2-3)

**Duration**: 8-12 hours

**Steps**:

1. **Create Configuration**:
```bash
# Create config directory
mkdir -p app/config

# Create mistral_config.py
# (Use code from Components section)

# Create prompt_templates.py
# (Use code from Components section)
```

2. **Create Core Services**:
```bash
# Create mistral_service.py
# (Use code from Code Examples section)

# Create system_prompt_builder.py
# (Use code from Code Examples section)

# Create context_manager.py
# (Use code from Code Examples section)
```

3. **Test Core Services**:
```bash
# Run unit tests
pytest tests/unit/test_mistral_service.py -v
pytest tests/unit/test_prompt_builder.py -v
pytest tests/unit/test_context_manager.py -v
```

4. **Commit**:
```bash
git add app/services/mistral_service.py
git add app/services/system_prompt_builder.py
git add app/services/context_manager.py
git add app/config/
git commit -m "Phase 3: Implement Mistral core services"
```

### Phase 4: Integration (Day 4)

**Duration**: 4-6 hours

**Steps**:

1. **Update Chat API**:
```bash
# Modify app/api/routes/chat.py
# (Use code from Code Examples section)
```

2. **Update Models**:
```bash
# Update app/models/query_result.py if needed
# Ensure compatibility with new response format
```

3. **Integration Tests**:
```bash
# Run integration tests
pytest tests/integration/test_end_to_end.py -v
pytest tests/integration/test_chat_api.py -v
```

4. **Manual Testing**:
```bash
# Start server
uvicorn app.main:app --reload

# Test queries
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me expenses from last month", "user_id": "test"}'
```

5. **Commit**:
```bash
git add app/api/routes/chat.py
git add app/models/
git commit -m "Phase 4: Integrate Mistral with chat API"
```

### Phase 5: Testing & Validation (Days 5-7)

**Duration**: 12-16 hours

**Steps**:

1. **Run Full Test Suite**:
```bash
# Unit tests
pytest tests/unit/ -v --cov=app

# Property tests
pytest tests/property/ -v --hypothesis-show-statistics

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v
```

2. **Manual Testing Scenarios**:
```
Test Case 1: Simple query
- Query: "Show me all expenses"
- Expected: Valid SQL, results returned

Test Case 2: Date range query
- Query: "Show me expenses from last month"
- Expected: SQL with date filter, results returned

Test Case 3: Category query
- Query: "Show me labor expenses"
- Expected: SQL with category filter, results returned

Test Case 4: Conversation context
- Query 1: "Show me projects"
- Query 2: "Show me their expenses"
- Expected: Second query references projects from first

Test Case 5: Ambiguous query
- Query: "Show me expenses for project"
- Expected: Clarification request

Test Case 6: Complex aggregation
- Query: "Total expenses by category for each project"
- Expected: SQL with GROUP BY and JOIN
```

3. **Performance Validation**:
```bash
# Measure query latency
python scripts/benchmark_queries.py

# Monitor GPU memory
python scripts/monitor_gpu.py

# Load testing
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

4. **Comparison with Old System**:
```bash
# Run A/B comparison
python scripts/compare_systems.py --queries test_queries.json
```

### Post-Migration Checklist

- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation updated
- [ ] Monitoring configured
- [ ] Rollback plan tested
- [ ] Team trained on new system
- [ ] Staging deployment successful
- [ ] Production deployment scheduled

### Rollback Plan

If issues occur during migration:

1. **Immediate Rollback**:
```bash
# Revert to backup branch
git checkout backup-3stage-architecture

# Restore database if needed
psql -U user -d construction_db < backup_YYYYMMDD.sql

# Restart services
systemctl restart mistral-service
```

2. **Partial Rollback**:
```bash
# Keep new code but disable Mistral
export ENABLE_MISTRAL=false

# Fall back to old system
# (Requires keeping old code temporarily)
```

3. **Data Recovery**:
```bash
# Restore conversation history
python scripts/import_conversations.py --input conversations_backup.json
```


## Optional: Fine-Tuning Guide

While the system is designed to work with zero-shot prompting, optional fine-tuning can improve accuracy for construction-specific queries.

### When to Consider Fine-Tuning

- After collecting 1000+ real user queries
- When zero-shot accuracy is below 85%
- For highly specialized construction terminology
- To reduce inference latency

### Fine-Tuning Approach: LoRA

Use LoRA (Low-Rank Adaptation) for efficient fine-tuning:

**Advantages**:
- Trains only 0.1% of parameters
- Fast training (hours vs days)
- Small adapter files (~10MB vs 14GB)
- Can switch between base and fine-tuned easily

### Data Preparation

```python
# scripts/prepare_finetuning_data.py

import json
from typing import List, Dict

def prepare_training_data(queries: List[Dict]) -> List[Dict]:
    """
    Prepare training data in instruction format.
    
    Input format:
    {
        "query": "Show me labor expenses last month",
        "sql": "SELECT * FROM expenses WHERE category = 'labor' AND date >= ...",
        "schema": {...}
    }
    
    Output format (instruction tuning):
    {
        "instruction": "Generate SQL for: Show me labor expenses last month",
        "input": "[DATABASE SCHEMA]\n...",
        "output": "SELECT * FROM expenses WHERE category = 'labor' AND date >= ..."
    }
    """
    
    training_data = []
    
    for item in queries:
        # Build schema context
        schema_text = format_schema(item["schema"])
        
        training_data.append({
            "instruction": f"Generate SQL for: {item['query']}",
            "input": schema_text,
            "output": item["sql"]
        })
    
    return training_data

def format_schema(schema: Dict) -> str:
    """Format schema for training."""
    lines = ["[DATABASE SCHEMA]"]
    for table, info in schema.items():
        lines.append(f"Table: {table}")
        for col in info["columns"]:
            lines.append(f"  - {col['name']} ({col['type']})")
    return "\n".join(lines)

# Export to JSONL
def export_training_data(data: List[Dict], output_path: str):
    """Export training data to JSONL format."""
    with open(output_path, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

# Usage
queries = load_user_queries()  # Load from database
training_data = prepare_training_data(queries)
export_training_data(training_data, "training_data.jsonl")
```

### Fine-Tuning Script

```python
# scripts/finetune_mistral_lora.py

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
from trl import SFTTrainer

def finetune_mistral():
    """Fine-tune Mistral 7B with LoRA."""
    
    # Load base model
    model_name = "mistralai/Mistral-7B-v0.1"
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        load_in_8bit=True,
        device_map="auto",
        torch_dtype=torch.float16
    )
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare for training
    model = prepare_model_for_kbit_training(model)
    
    # LoRA configuration
    lora_config = LoraConfig(
        r=16,  # Rank
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    model = get_peft_model(model, lora_config)
    
    # Load training data
    dataset = load_dataset("json", data_files="training_data.jsonl")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir="./mistral-construction-lora",
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        save_steps=100,
        evaluation_strategy="steps",
        eval_steps=100,
        warmup_steps=50,
        save_total_limit=3
    )
    
    # Trainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        tokenizer=tokenizer,
        max_seq_length=2048
    )
    
    # Train
    trainer.train()
    
    # Save adapter
    model.save_pretrained("./mistral-construction-lora-final")
    tokenizer.save_pretrained("./mistral-construction-lora-final")

if __name__ == "__main__":
    finetune_mistral()
```

### Loading Fine-Tuned Model

```python
# app/services/mistral_service.py (modified)

from peft import PeftModel

class MistralService:
    def __init__(self, config: MistralConfig, use_finetuned: bool = False):
        self.config = config
        self.use_finetuned = use_finetuned
        self._load_model()
    
    def _load_model(self):
        """Load model with optional LoRA adapter."""
        
        # Load base model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_8bit=True,
            device_map="auto"
        )
        
        # Load LoRA adapter if fine-tuned
        if self.use_finetuned:
            adapter_path = "./mistral-construction-lora-final"
            self.model = PeftModel.from_pretrained(
                self.model,
                adapter_path
            )
            logger.info("Loaded fine-tuned LoRA adapter")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
```

### Evaluation

```python
# scripts/evaluate_finetuned.py

def evaluate_model(model, test_queries: List[Dict]) -> Dict:
    """Evaluate fine-tuned model accuracy."""
    
    correct = 0
    total = len(test_queries)
    
    for item in test_queries:
        # Generate SQL
        generated_sql = model.generate_sql(item["query"])
        
        # Compare with ground truth
        if sql_equivalent(generated_sql, item["expected_sql"]):
            correct += 1
    
    accuracy = correct / total
    
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total
    }

# Compare base vs fine-tuned
base_results = evaluate_model(base_model, test_queries)
finetuned_results = evaluate_model(finetuned_model, test_queries)

print(f"Base model accuracy: {base_results['accuracy']:.2%}")
print(f"Fine-tuned accuracy: {finetuned_results['accuracy']:.2%}")
print(f"Improvement: {(finetuned_results['accuracy'] - base_results['accuracy']):.2%}")
```

### Configuration for Fine-Tuned Model

```bash
# .env

# Enable fine-tuned model
USE_FINETUNED_MODEL=true
FINETUNED_MODEL_PATH=./mistral-construction-lora-final

# Or use base model
USE_FINETUNED_MODEL=false
```


## Success Criteria

### Functional Requirements

- ✅ System loads Mistral 7B with 8-bit quantization
- ✅ System generates valid SQL from natural language queries
- ✅ System handles date range, category, comparison, and aggregation queries
- ✅ System maintains conversation context across queries
- ✅ System validates SQL before execution
- ✅ System provides user-friendly error messages
- ✅ System formats results consistently

### Performance Requirements

- ✅ Simple queries complete in < 5 seconds
- ✅ Complex queries complete in < 15 seconds
- ✅ GPU memory usage stays within 14GB limit
- ✅ System handles 3+ concurrent queries
- ✅ 99% uptime during business hours

### Quality Requirements

- ✅ SQL generation accuracy > 85% (zero-shot)
- ✅ SQL validation catches 100% of destructive operations
- ✅ Conversation context resolution > 80% accuracy
- ✅ Error rate < 5% for valid queries
- ✅ All 27 correctness properties pass tests

### Migration Requirements

- ✅ Zero data loss during migration
- ✅ API backward compatibility maintained
- ✅ Rollback plan tested and documented
- ✅ All existing features preserved or improved
- ✅ Team trained on new system

## Risk Assessment

### High Risk

**Risk**: GPU memory insufficient for model
- **Mitigation**: Use 8-bit quantization, implement memory monitoring, queue requests when memory high
- **Fallback**: Use 4-bit quantization or smaller model

**Risk**: Model generates invalid SQL frequently
- **Mitigation**: Comprehensive system prompts, retry logic, validation before execution
- **Fallback**: Collect failures for fine-tuning

### Medium Risk

**Risk**: Query latency exceeds targets
- **Mitigation**: Optimize prompts, use caching, consider vLLM for inference
- **Fallback**: Increase GPU resources or use smaller model

**Risk**: Conversation context causes token limit issues
- **Mitigation**: Implement smart truncation, summarize old exchanges
- **Fallback**: Reduce max context length

### Low Risk

**Risk**: Model doesn't understand construction terminology
- **Mitigation**: Comprehensive domain terminology in prompts
- **Fallback**: Fine-tune with construction-specific data

**Risk**: Migration causes temporary service disruption
- **Mitigation**: Thorough testing, staged rollout, rollback plan
- **Fallback**: Revert to backup branch

## Conclusion

This design document specifies a comprehensive migration from the complex 3-stage architecture (DistilBERT + T5 + LoRA) to a simplified generative AI approach using Mistral 7B. The new architecture offers:

**Key Benefits**:
1. **Simplicity**: Single model replaces three separate models
2. **Flexibility**: System prompts replace hardcoded rules
3. **Maintainability**: 60% fewer files, clearer code structure
4. **Extensibility**: Easy to add new query types via prompts
5. **Performance**: Comparable or better latency with proper optimization

**Migration Approach**:
- Clean slate: Delete old code, install new system
- Phased execution: 5 phases over 7 days
- Comprehensive testing: Unit, property, integration, and performance tests
- Risk mitigation: Backup, rollback plan, staged deployment

**Next Steps**:
1. Review and approve this design document
2. Set up staging environment
3. Execute Phase 1: Backup & Cleanup
4. Execute Phase 2: Install Dependencies
5. Execute Phase 3: Implement Core Service
6. Execute Phase 4: Integration
7. Execute Phase 5: Testing & Validation
8. Deploy to production with monitoring

The system is designed to work effectively with zero-shot prompting, with optional fine-tuning available later for further accuracy improvements. All existing security, database, and utility components are preserved and reused, ensuring a smooth transition with minimal risk.

