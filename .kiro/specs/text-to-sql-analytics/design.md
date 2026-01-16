# Design Document: Text-to-SQL Analytics

## Overview

This design adds Text-to-SQL capability to the AU-Ggregates AI system, enabling complex analytics queries that go beyond keyword search. The system will use a hybrid deployment architecture: lightweight embeddings and routing on the main server, with the heavy Text-to-SQL model deployed on remote GPU infrastructure (Modal.com).

The implementation follows a three-phase approach:
1. **Phase 1**: Semantic search using embeddings + pgvector (3-4 days)
2. **Phase 2**: Text-to-SQL model integration on remote GPU (1-2 weeks)
3. **Phase 3**: Integration, testing, and optimization (3-4 days)

### Key Design Principles

- **No Code Deletion**: Only additions and enhancements to existing system
- **Hybrid Deployment**: Main app stays lightweight, GPU-intensive work on Modal.com
- **Graceful Degradation**: Fallback to keyword search if Text-to-SQL fails
- **Security First**: SQL injection prevention, read-only enforcement, RBAC
- **Multilingual**: Support for English and Tagalog queries
- **Performance**: 150-300ms for embeddings, 500ms-1s for Text-to-SQL

## Architecture

### Current System (Before)

```
User Query
    ↓
Router (DistilBERT)
    ↓
Universal Handler
    ↓
ai_documents (keyword search)
    ↓
Results
```

### Enhanced System (After)

```
User Query
    ↓
Router (DistilBERT) ← Enhanced with ANALYTICS intent
    ↓
    ├─→ Universal Handler (keyword search)
    │       ↓
    │   ai_documents (keyword + semantic)
    │       ↓
    │   Results
    │
    └─→ Analytics Handler (NEW)
            ↓
        Text-to-SQL Service (Modal.com)
            ↓
        SQL Validator
            ↓
        Supabase PostgreSQL
            ↓
        Results Formatter
            ↓
        Results (or fallback to Universal Handler)
```

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Main Application Server (Lightweight)                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Router     │  │  Universal   │  │  Analytics   │ │
│  │ (DistilBERT) │  │   Handler    │  │   Handler    │ │
│  │   250MB      │  │              │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                              │          │
│  ┌──────────────┐                           │          │
│  │  Embeddings  │                           │          │
│  │   Service    │                           │          │
│  │   (E5-base)  │                           │          │
│  │    500MB     │                           │          │
│  └──────────────┘                           │          │
│         │                                    │          │
└─────────┼────────────────────────────────────┼──────────┘
          │                                    │
          ↓                                    ↓
┌─────────────────────┐          ┌─────────────────────────┐
│  Supabase           │          │  Modal.com (GPU)        │
│  ┌───────────────┐  │          │  ┌───────────────────┐  │
│  │ PostgreSQL    │  │          │  │  Text-to-SQL      │  │
│  │ + pgvector    │  │          │  │  (SQLCoder-7B-2)  │  │
│  └───────────────┘  │          │  │  8GB (8-bit)      │  │
│                     │          │  └───────────────────┘  │
└─────────────────────┘          └─────────────────────────┘
```

## Components and Interfaces

### 1. Router Enhancement

**Purpose**: Add ANALYTICS intent classification to existing DistilBERT router

**Changes**:
- Add "ANALYTICS" to INTENT_LABELS list
- Retrain router with analytics query examples
- No architectural changes needed

**Interface**:
```python
@dataclass
class RouterOutput:
    intent: str  # Can now be "ANALYTICS"
    intent_confidence: float
    table_hint: str
    table_confidence: float
    entity_type: str
    entity_confidence: float
    needs_clarification: bool
    overall_confidence: float
```

**Analytics Intent Detection Patterns**:
- Aggregations: "total", "sum", "average", "count", "kabuuan", "average", "bilang"
- Date ranges: "last month", "this year", "nakaraang buwan", "ngayong taon"
- Comparisons: "compare", "vs", "difference", "ihambing"
- Grouping: "by project", "per category", "kada proyekto"

### 2. Embeddings Service (NEW - Phase 1)

**Purpose**: Generate semantic embeddings for queries and documents

**Model**: `intfloat/multilingual-e5-base`
- Size: 500MB
- Languages: English + Tagalog
- Embedding dimension: 768
- Performance: 150-300ms per query

**Interface**:
```python
class EmbeddingsService:
    """Generate semantic embeddings for text."""
    
    def __init__(self):
        self.model = SentenceTransformer('intfloat/multilingual-e5-base')
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    def encode_query(self, query: str) -> List[float]:
        """
        Encode a user query into embedding vector.
        
        Args:
            query: Natural language query
            
        Returns:
            768-dimensional embedding vector
        """
        pass
    
    def encode_document(self, text: str) -> List[float]:
        """
        Encode a document into embedding vector.
        
        Args:
            text: Document text
            
        Returns:
            768-dimensional embedding vector
        """
        pass
    
    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode multiple texts in batch for efficiency.
        
        Args:
            texts: List of texts to encode
            
        Returns:
            List of embedding vectors
        """
        pass
```

**Usage**:
```python
embeddings_service = EmbeddingsService()
query_embedding = embeddings_service.encode_query("total fuel expenses last month")
```

### 3. pgvector Integration (NEW - Phase 1)

**Purpose**: Store and search document embeddings using vector similarity

**Database Changes**:
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to ai_documents
ALTER TABLE ai_documents 
ADD COLUMN embedding vector(768);

-- Create vector similarity index
CREATE INDEX ON ai_documents 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Hybrid search function (semantic + keyword)
CREATE OR REPLACE FUNCTION ai_search_hybrid(
    p_query_embedding vector(768),
    p_search_term TEXT,
    p_source_table TEXT DEFAULT NULL,
    p_project_id TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20,
    p_semantic_weight FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    source_table TEXT,
    source_id TEXT,
    file_id TEXT,
    file_name TEXT,
    project_id TEXT,
    project_name TEXT,
    searchable_text TEXT,
    metadata JSONB,
    semantic_score FLOAT,
    keyword_score FLOAT,
    combined_score FLOAT,
    matched_highlights TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ad.id,
        ad.source_table,
        ad.source_id,
        ad.file_id,
        ad.file_name,
        ad.project_id,
        ad.project_name,
        ad.searchable_text,
        ad.metadata,
        (1 - (ad.embedding <=> p_query_embedding)) AS semantic_score,
        ts_rank(ad.search_vector, plainto_tsquery('english', p_search_term)) AS keyword_score,
        (p_semantic_weight * (1 - (ad.embedding <=> p_query_embedding)) + 
         (1 - p_semantic_weight) * ts_rank(ad.search_vector, plainto_tsquery('english', p_search_term))) AS combined_score,
        ts_headline('english', ad.searchable_text, plainto_tsquery('english', p_search_term), 
            'StartSel=<b>, StopSel=</b>, MaxWords=20, MinWords=5') AS matched_highlights
    FROM ai_documents ad
    WHERE 
        (p_source_table IS NULL OR ad.source_table = p_source_table)
        AND (p_project_id IS NULL OR ad.project_id = p_project_id)
        AND ad.embedding IS NOT NULL
    ORDER BY combined_score DESC
    LIMIT p_limit;
END;
$$;
```

**Indexing Strategy**:
- Generate embeddings for all existing ai_documents rows
- Update embeddings when documents are added/modified
- Use batch processing for initial indexing (100 documents at a time)

### 4. Text-to-SQL Service (NEW - Phase 2)

**Purpose**: Translate natural language to SQL queries using fine-tuned model

**Model**: `defog/sqlcoder-7b-2`
- Size: 8GB (with 8-bit quantization)
- Deployment: Modal.com GPU (T4 or A10G)
- Performance: 500ms-1s per query
- Fine-tuning: 500-1000 construction domain query-SQL pairs

**Interface**:
```python
class TextToSQLService:
    """
    Text-to-SQL translation service deployed on Modal.com.
    Communicates via HTTP API.
    """
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = 10  # seconds
    
    def generate_sql(
        self, 
        query: str, 
        schema: Dict[str, Any],
        role: str = "ADMIN"
    ) -> SQLGenerationResult:
        """
        Generate SQL from natural language query.
        
        Args:
            query: Natural language question
            schema: Database schema information
            role: User role for access control
            
        Returns:
            SQLGenerationResult with generated SQL and metadata
        """
        pass
    
    def health_check(self) -> bool:
        """Check if Text-to-SQL service is available."""
        pass
```

**Modal.com Deployment**:
```python
# modal_text_to_sql.py
import modal

stub = modal.Stub("text-to-sql")

@stub.function(
    gpu="T4",
    image=modal.Image.debian_slim().pip_install(
        "transformers", "torch", "accelerate", "bitsandbytes"
    ),
    timeout=60,
)
def generate_sql(query: str, schema: dict, role: str) -> dict:
    """Generate SQL from natural language query."""
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    
    # Load model (cached after first call)
    model_name = "defog/sqlcoder-7b-2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        load_in_8bit=True,
        device_map="auto"
    )
    
    # Build prompt with schema
    prompt = build_prompt(query, schema, role)
    
    # Generate SQL
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    outputs = model.generate(**inputs, max_new_tokens=200)
    sql = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    return {"sql": sql, "confidence": 0.85}

@stub.local_entrypoint()
def main():
    """Deploy the service."""
    print("Text-to-SQL service deployed!")
```

**Prompt Template**:
```
### Task
Generate a PostgreSQL query to answer the following question.

### Database Schema
{schema_info}

### User Role
{role}

### Access Rules
- ENCODER role: Cannot access CashFlow table
- ADMIN role: Can access all tables
- All queries must be read-only (SELECT only)

### Question
{user_query}

### SQL Query
```

### 5. SQL Validator (NEW - Phase 2)

**Purpose**: Validate generated SQL for safety and correctness

**Interface**:
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_sql: Optional[str]

class SQLValidator:
    """Validate SQL queries for safety and correctness."""
    
    def validate(self, sql: str, role: str) -> ValidationResult:
        """
        Validate SQL query against security rules.
        
        Checks:
        1. SQL injection patterns
        2. Write operations (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE)
        3. Multiple statements or command chaining
        4. Role-based table access
        5. Syntax correctness
        
        Args:
            sql: Generated SQL query
            role: User role for RBAC
            
        Returns:
            ValidationResult with validation status and errors
        """
        pass
    
    def _check_injection(self, sql: str) -> List[str]:
        """Check for SQL injection patterns."""
        pass
    
    def _check_write_operations(self, sql: str) -> List[str]:
        """Check for write operations."""
        pass
    
    def _check_role_access(self, sql: str, role: str) -> List[str]:
        """Check role-based table access."""
        pass
    
    def _parse_sql(self, sql: str) -> Optional[Any]:
        """Parse SQL using sqlparse library."""
        pass
```

**Validation Rules**:

1. **SQL Injection Prevention**:
   - No comment sequences (`--`, `/*`, `*/`)
   - No string concatenation with user input
   - No UNION-based injection patterns
   - No time-based blind injection patterns

2. **Read-Only Enforcement**:
   - Reject: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE
   - Reject: EXECUTE, CALL (stored procedures)
   - Allow: SELECT only

3. **Command Chaining Prevention**:
   - Reject multiple statements (`;` followed by another statement)
   - Reject batch execution patterns

4. **Role-Based Access Control**:
   - ENCODER: Cannot access CashFlow table
   - ADMIN/ACCOUNTANT: Can access all tables
   - Inject WHERE clauses for row-level security if needed

5. **Syntax Validation**:
   - Use `sqlparse` library to parse SQL
   - Reject malformed queries

### 6. Analytics Handler (NEW - Phase 2)

**Purpose**: Handle analytics-intent queries using Text-to-SQL

**Interface**:
```python
class AnalyticsHandler:
    """
    Handler for analytics queries using Text-to-SQL.
    Falls back to Universal Handler if Text-to-SQL fails.
    """
    
    def __init__(
        self,
        text_to_sql_service: TextToSQLService,
        sql_validator: SQLValidator,
        supabase_client: Any
    ):
        self.text_to_sql = text_to_sql_service
        self.validator = sql_validator
        self.supabase = supabase_client
        self.max_retries = 3
        self.query_timeout = 10  # seconds
    
    def handle_query(
        self,
        query: str,
        role: str,
        filters: Dict[str, Any] = None
    ) -> SmartQueryResult:
        """
        Handle analytics query using Text-to-SQL pipeline.
        
        Pipeline:
        1. Generate SQL from natural language
        2. Validate SQL for safety and correctness
        3. Execute SQL against database
        4. Format results for user
        5. Fallback to Universal Handler if any step fails
        
        Args:
            query: Natural language analytics question
            role: User role for RBAC
            filters: Optional filters (project_id, etc.)
            
        Returns:
            SmartQueryResult with analytics results or fallback results
        """
        pass
    
    def _generate_sql(self, query: str, role: str) -> Optional[str]:
        """Generate SQL with retries."""
        pass
    
    def _execute_sql(self, sql: str) -> Optional[List[Dict]]:
        """Execute SQL with timeout."""
        pass
    
    def _format_results(
        self, 
        results: List[Dict], 
        query: str
    ) -> SmartQueryResult:
        """Format SQL results into user-friendly response."""
        pass
    
    def _fallback_to_universal(
        self, 
        query: str, 
        filters: Dict[str, Any],
        role: str,
        reason: str
    ) -> SmartQueryResult:
        """Fallback to Universal Handler."""
        pass
```

**Fallback Conditions**:
- Text-to-SQL service unavailable
- SQL generation fails after 3 retries
- SQL validation fails (safety concerns)
- SQL execution error
- Query timeout (>10 seconds)

### 7. Schema Provider (NEW - Phase 2)

**Purpose**: Provide database schema information to Text-to-SQL model

**Interface**:
```python
@dataclass
class TableSchema:
    name: str
    columns: List[ColumnInfo]
    foreign_keys: List[ForeignKeyInfo]
    description: str

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    description: str

@dataclass
class ForeignKeyInfo:
    column: str
    references_table: str
    references_column: str

class SchemaProvider:
    """Provide database schema information for Text-to-SQL."""
    
    def get_schema(self, role: str = "ADMIN") -> Dict[str, TableSchema]:
        """
        Get database schema filtered by role.
        
        Args:
            role: User role for access control
            
        Returns:
            Dictionary of table schemas accessible to role
        """
        pass
    
    def format_for_prompt(self, schema: Dict[str, TableSchema]) -> str:
        """Format schema for Text-to-SQL prompt."""
        pass
```

**Schema Information**:

```python
SCHEMA = {
    "Expenses": TableSchema(
        name="Expenses",
        description="Expense records with categories and amounts",
        columns=[
            ColumnInfo("id", "UUID", False, "Primary key"),
            ColumnInfo("file_name", "TEXT", True, "Source file name"),
            ColumnInfo("project_id", "TEXT", True, "Associated project"),
            ColumnInfo("created_at", "TIMESTAMP", False, "Creation timestamp"),
        ],
        foreign_keys=[
            ForeignKeyInfo("project_id", "Project", "id")
        ]
    ),
    "CashFlow": TableSchema(
        name="CashFlow",
        description="Cash flow records (inflow/outflow)",
        columns=[
            ColumnInfo("id", "UUID", False, "Primary key"),
            ColumnInfo("file_name", "TEXT", True, "Source file name"),
            ColumnInfo("project_id", "TEXT", True, "Associated project"),
            ColumnInfo("created_at", "TIMESTAMP", False, "Creation timestamp"),
        ],
        foreign_keys=[
            ForeignKeyInfo("project_id", "Project", "id")
        ]
    ),
    "Project": TableSchema(
        name="Project",
        description="Construction projects",
        columns=[
            ColumnInfo("id", "UUID", False, "Primary key"),
            ColumnInfo("project_name", "TEXT", False, "Project name"),
            ColumnInfo("created_at", "TIMESTAMP", False, "Creation timestamp"),
        ],
        foreign_keys=[]
    ),
    "Quotation": TableSchema(
        name="Quotation",
        description="Price quotations",
        columns=[
            ColumnInfo("id", "UUID", False, "Primary key"),
            ColumnInfo("project_id", "TEXT", True, "Associated project"),
            ColumnInfo("created_at", "TIMESTAMP", False, "Creation timestamp"),
        ],
        foreign_keys=[
            ForeignKeyInfo("project_id", "Project", "id")
        ]
    )
}
```

Note: The actual schema will be extracted from ai_documents metadata structure, which contains the full row data in JSONB format.

### 8. Results Formatter (NEW - Phase 2)

**Purpose**: Format SQL query results into human-readable responses

**Interface**:
```python
class ResultsFormatter:
    """Format SQL results for user consumption."""
    
    def format_analytics_results(
        self,
        results: List[Dict],
        query: str,
        sql: str,
        language: str = "en"
    ) -> str:
        """
        Format analytics results into natural language response.
        
        Args:
            results: SQL query results
            query: Original user query
            sql: Generated SQL (for context)
            language: Response language (en/tl)
            
        Returns:
            Formatted natural language response
        """
        pass
    
    def _detect_aggregation_type(self, sql: str) -> str:
        """Detect type of aggregation (SUM, COUNT, AVG, etc.)."""
        pass
    
    def _format_number(self, value: float, language: str) -> str:
        """Format numbers with proper locale."""
        pass
    
    def _translate_response(self, text: str, target_lang: str) -> str:
        """Translate response to target language."""
        pass
```

**Formatting Examples**:

Query: "What's the total fuel expenses last month?"
SQL: `SELECT SUM(amount) FROM expenses WHERE category='fuel' AND date >= '2024-01-01'`
Results: `[{"sum": 15000}]`
Response: "The total fuel expenses last month is ₱15,000.00"

Query: "Magkano ang kabuuang gastos sa transportation?"
SQL: `SELECT SUM(amount) FROM expenses WHERE category='transportation'`
Results: `[{"sum": 25000}]`
Response: "Ang kabuuang gastos sa transportation ay ₱25,000.00"

## Data Models

### Embeddings Storage

```python
# ai_documents table (enhanced)
{
    "id": "uuid",
    "source_table": "Expenses",
    "source_id": "row_123",
    "file_id": "file_456",
    "file_name": "January Expenses.xlsx",
    "project_id": "proj_789",
    "project_name": "Building A",
    "searchable_text": "fuel transportation 5000 2024-01-15",
    "metadata": {
        "id": "row_123",
        "category": "fuel",
        "amount": "5000",
        "date": "2024-01-15",
        "description": "Gasoline for truck"
    },
    "search_vector": "tsvector",
    "embedding": "[0.123, -0.456, ...]",  # NEW: 768-dimensional vector
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
}
```

### Text-to-SQL Request/Response

```python
# Request to Modal.com
{
    "query": "What's the total fuel expenses last month?",
    "schema": {
        "Expenses": {
            "columns": ["id", "category", "amount", "date", "file_name", "project_id"],
            "foreign_keys": [{"column": "project_id", "references": "Project.id"}]
        }
    },
    "role": "ADMIN"
}

# Response from Modal.com
{
    "sql": "SELECT SUM(CAST(metadata->>'amount' AS NUMERIC)) FROM ai_documents WHERE source_table='Expenses' AND metadata->>'category'='fuel' AND (metadata->>'date')::date >= CURRENT_DATE - INTERVAL '1 month'",
    "confidence": 0.85,
    "execution_time_ms": 450
}
```

### SQL Validation Result

```python
{
    "is_valid": True,
    "errors": [],
    "warnings": ["Query may be slow without index on metadata->>'date'"],
    "sanitized_sql": "SELECT SUM(CAST(metadata->>'amount' AS NUMERIC)) FROM ai_documents WHERE source_table='Expenses' AND metadata->>'category'='fuel' AND (metadata->>'date')::date >= CURRENT_DATE - INTERVAL '1 month'"
}
```

### Analytics Query Result

```python
{
    "success": True,
    "data": [
        {
            "total": 15000,
            "currency": "PHP"
        }
    ],
    "count": 1,
    "sql_used": "SELECT SUM(...)",
    "execution_time_ms": 125,
    "formatted_response": "The total fuel expenses last month is ₱15,000.00",
    "operation": "analytics",
    "fallback_used": False
}
```

