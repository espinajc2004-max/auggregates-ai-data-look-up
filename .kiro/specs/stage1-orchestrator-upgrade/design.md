# Stage 1 Orchestrator Upgrade - Design

**Feature**: stage1-orchestrator-upgrade
**Date**: 2026-02-16

## Overview

Upgrade the Stage 1 Orchestrator to output a new format that includes the `scope` field, enabling better separation of concerns between Stage 1 (understanding) and Stage 2 (SQL generation).

## Architecture

### Current Flow (OLD)
```
User Query → Stage 1 → {intent, entities, needs_clarification, clarify_slot}
                ↓
           Stage 2 → SQL
```

### New Flow
```
User Query → Stage 1 → {intent, scope, slots, needs_clarification, clarify_slots}
                ↓
           Stage 2 → SQL (with scope-specific logic)
```

## Component Design

### 1. Stage 1 Model (DistilBERT)

**Architecture**: Multi-task learning with 4 heads

```python
class EnhancedDistilBERTOrchestrator(nn.Module):
    def __init__(self):
        # Base: DistilBERT
        self.distilbert = DistilBertModel.from_pretrained('distilbert-base-uncased')
        
        # Head 1: Intent Classification (8 classes)
        self.intent_classifier = nn.Linear(hidden_size, 8)
        
        # Head 2: Scope Classification (4 classes) - NEW!
        self.scope_classifier = nn.Linear(hidden_size, 4)
        
        # Head 3: Slot Detection (8 binary classifiers)
        self.slot_detectors = nn.ModuleList([
            nn.Linear(hidden_size, 2) for _ in range(8)
        ])
        
        # Head 4: Clarification Detection (binary)
        self.clarification_classifier = nn.Linear(hidden_size, 2)
```

**Training Data**: `ml/training/data/orchestrator_v2.jsonl` (3,000 examples)

**Training Approach**:
- Optimizer: AdamW
- Learning Rate: 2e-5
- Batch Size: 16
- Epochs: 3-5
- Loss: Cross-entropy for classification, BCE for binary tasks

### 2. Orchestrator Service

**File**: `app/services/stage1/orchestrator.py`

**Output Schema**:
```python
{
    "intent": str,           # LOOKUP|COUNT|SUM|AVG|DISTINCT|COMPARE|LOCATE|MULTI_QUERY
    "scope": str,            # row|file|summary|distinct_values (NEW!)
    "slots": {               # Renamed from "entities"
        "source_table": str | None,
        "file_name": str | None,
        "project": str | None,
        "category": str | None,
        "method": str | None,
        "date_range": str | None,
        "amount_range": str | None,
        "custom_column": str | None
    },
    "needs_clarification": bool,
    "clarify_slots": List[str],  # Array instead of single value (NEW!)
    "confidence": float
}
```

**Key Methods**:
```python
class DistilBERTOrchestrator:
    def orchestrate(query: str) -> Dict:
        # 1. Tokenize query
        # 2. Get model predictions
        # 3. Extract intent (8 classes)
        # 4. Extract scope (4 classes) - NEW!
        # 5. Extract slots (8 slots)
        # 6. Determine clarification needs
        # 7. Return structured output
        
    def _extract_scope(logits) -> str:
        # NEW METHOD
        # Map logits to scope: row|file|summary|distinct_values
        
    def _extract_slots(query, slot_logits) -> Dict:
        # Detector (model) + Resolver (code + DB)
        # Returns all 8 slots
        
    def _determine_clarify_slots(slots, intent) -> List[str]:
        # Deterministic rules:
        # - LOOKUP/COUNT/SUM/AVG need project
        # - DISTINCT needs custom_column
        # - COMPARE needs at least 2 projects
```

### 3. T5 SQL Generator

**File**: `app/services/stage2/t5_sql_generator.py`

**Input**: Stage 1 output (new format)

**Key Changes**:
```python
class T5SQLGenerator:
    def generate_sql(query, orchestration_result, org_id) -> str:
        intent = orchestration_result["intent"]
        scope = orchestration_result["scope"]  # NEW!
        slots = orchestration_result["slots"]  # Renamed from "entities"
        
        # Build T5 input with structured context
        t5_input = self._build_t5_input(query, intent, scope, slots)
        
        # Generate SQL
        sql = self._generate(t5_input)
        
        # Apply scope-specific logic
        sql = self._apply_scope_logic(sql, scope, slots)
        
        return sql
    
    def _build_t5_input(query, intent, scope, slots) -> str:
        # Format: [INTENT:LOOKUP] [SCOPE:row] [PROJECT:Francis Gays] translate to SQL: find fuel
        context_parts = [f"[INTENT:{intent}]", f"[SCOPE:{scope}]"]
        
        for slot_name, slot_value in slots.items():
            if slot_value:
                context_parts.append(f"[{slot_name.upper()}:{slot_value}]")
        
        return f"{' '.join(context_parts)} translate to SQL: {query}"
    
    def _apply_scope_logic(sql, scope, slots) -> str:
        # Apply document_type filtering based on scope
        if scope == "file":
            sql = sql.replace("WHERE", "WHERE document_type = 'file' AND")
        elif scope == "row":
            sql = sql.replace("WHERE", "WHERE document_type = 'row' AND")
        elif scope == "distinct_values":
            sql = sql.replace("SELECT", "SELECT DISTINCT", 1)
        
        return sql
```

## Data Flow

### Example 1: Row-Level Lookup
```
Input: "find fuel in Francis Gays"

Stage 1 Output:
{
    "intent": "LOOKUP",
    "scope": "row",
    "slots": {
        "project": "Francis Gays",
        "category": "fuel"
    },
    "needs_clarification": false,
    "clarify_slots": []
}

T5 Input:
"[INTENT:LOOKUP] [SCOPE:row] [PROJECT:Francis Gays] [CATEGORY:fuel] translate to SQL: find fuel in Francis Gays"

SQL Output:
"SELECT * FROM ai_documents WHERE document_type = 'row' AND metadata->>'project' ILIKE '%Francis Gays%' AND content_vector @@ to_tsquery('fuel') LIMIT 10"
```

### Example 2: File-Level Lookup
```
Input: "show Francis Gays"

Stage 1 Output:
{
    "intent": "LOOKUP",
    "scope": "file",
    "slots": {
        "file_name": "Francis Gays"
    },
    "needs_clarification": false,
    "clarify_slots": []
}

T5 Input:
"[INTENT:LOOKUP] [SCOPE:file] [FILE_NAME:Francis Gays] translate to SQL: show Francis Gays"

SQL Output:
"SELECT * FROM ai_documents WHERE document_type = 'file' AND metadata->>'file_name' ILIKE '%Francis Gays%' LIMIT 10"
```

### Example 3: DISTINCT Query
```
Input: "show all categories"

Stage 1 Output:
{
    "intent": "DISTINCT",
    "scope": "distinct_values",
    "slots": {
        "custom_column": "category"
    },
    "needs_clarification": false,
    "clarify_slots": []
}

T5 Input:
"[INTENT:DISTINCT] [SCOPE:distinct_values] [CUSTOM_COLUMN:category] translate to SQL: show all categories"

SQL Output:
"SELECT DISTINCT metadata->>'category' FROM ai_documents WHERE org_id = $1"
```

## Testing Strategy

### Unit Tests
- Test intent classification (8 intents)
- Test scope classification (4 scopes)
- Test slot extraction (8 slots)
- Test clarification detection
- Test T5 input builder
- Test scope logic application

### Integration Tests
- Test full pipeline: Query → Stage 1 → Stage 2 → SQL → Results
- Test all intent + scope combinations
- Test clarification flow
- Test multi-query handling

### Test Cases
```python
# Intent Classification
assert orchestrate("find fuel")["intent"] == "LOOKUP"
assert orchestrate("how many projects")["intent"] == "COUNT"
assert orchestrate("how much fuel")["intent"] == "SUM"
assert orchestrate("average labor cost")["intent"] == "AVG"
assert orchestrate("show all categories")["intent"] == "DISTINCT"
assert orchestrate("compare Francis Gays and SJDM")["intent"] == "COMPARE"
assert orchestrate("find REF-001")["intent"] == "LOCATE"

# Scope Classification
assert orchestrate("show Francis Gays")["scope"] == "file"
assert orchestrate("find fuel in Francis Gays")["scope"] == "row"
assert orchestrate("how much fuel")["scope"] == "summary"
assert orchestrate("show all categories")["scope"] == "distinct_values"

# Slot Extraction
result = orchestrate("find fuel in Francis Gays")
assert result["slots"]["project"] == "Francis Gays"
assert result["slots"]["category"] == "fuel"

# Clarification
result = orchestrate("find fuel")
assert result["needs_clarification"] == True
assert "project" in result["clarify_slots"]
```

## Migration Plan

### Phase 1: Train Model (User's Task)
- Update Colab notebook to use `orchestrator_v2.jsonl`
- Train DistilBERT with 4 heads
- Save model to `ml/models/orchestrator_v2/`
- Validate accuracy metrics

### Phase 2: Update Orchestrator Service
- Add scope extraction method
- Rename entities to slots
- Update clarification logic
- Update output schema
- Unit test all methods

### Phase 3: Update T5 Generator
- Modify input builder
- Add scope logic
- Update chat route integration
- Integration test full pipeline

### Phase 4: Testing & Validation
- Run all unit tests
- Run all integration tests
- Manual testing with sample queries
- Performance testing

## Rollback Plan

If issues arise:
1. Keep old model at `ml/models/enhanced_orchestrator_model/`
2. Keep old code in git history
3. Feature flag to switch between old/new format
4. Gradual rollout with A/B testing

## Performance Considerations

- Model inference time: ~50-100ms (same as before)
- No additional database queries
- Scope logic adds ~5ms overhead
- Overall latency: <200ms for full pipeline

## Security Considerations

- No changes to SQL injection prevention
- Guardrails still apply in Stage 2
- org_id filtering still enforced
- RLS policies unchanged
