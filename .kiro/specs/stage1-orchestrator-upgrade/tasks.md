# Stage 1 Orchestrator Upgrade - Tasks

**Feature**: stage1-orchestrator-upgrade
**Date**: 2026-02-16
**Status**: In Progress

---

## Task Breakdown

### 1. Train Stage 1 Model (USER'S TASK)
- [ ] 1.1 Update Colab notebook to use `orchestrator_v2.jsonl`
- [ ] 1.2 Configure multi-task learning (4 heads: intent, scope, slots, clarification)
- [ ] 1.3 Train DistilBERT model (3-5 epochs)
- [ ] 1.4 Validate accuracy metrics (intent: 95%+, scope: 90%+)
- [ ] 1.5 Save model to `ml/models/orchestrator_v2/`
- [ ] 1.6 Test model inference with sample queries

**Estimated Time**: 30-45 minutes (on Colab with T4 GPU)

**Files**:
- `ml/training/Orchestrator_Training_Colab.ipynb` (update)
- `ml/training/data/orchestrator_v2.jsonl` (input)
- `ml/models/orchestrator_v2/` (output)

---

### 2. Update Orchestrator Service
- [ ] 2.1 Add scope classification head to model class
- [ ] 2.2 Add `_extract_scope()` method
- [ ] 2.3 Rename "entities" to "slots" in output
- [ ] 2.4 Change "clarify_slot" to "clarify_slots" (array)
- [ ] 2.5 Update `_extract_slots()` to return all 8 slots
- [ ] 2.6 Update `_determine_clarify_slots()` with deterministic rules
- [ ] 2.7 Update `orchestrate()` method to return new format
- [ ] 2.8 Update model loading to use `orchestrator_v2` path

**Estimated Time**: 1-2 hours

**Files**:
- `app/services/stage1/orchestrator.py` (update)

**Testing**:
```python
# Test intent classification
result = orchestrator.orchestrate("find fuel in Francis Gays")
assert result["intent"] == "LOOKUP"

# Test scope classification
assert result["scope"] == "row"

# Test slot extraction
assert result["slots"]["project"] == "Francis Gays"
assert result["slots"]["category"] == "fuel"

# Test clarification
result = orchestrator.orchestrate("find fuel")
assert result["needs_clarification"] == True
assert "project" in result["clarify_slots"]
```

---

### 3. Update T5 SQL Generator
- [ ] 3.1 Update `generate_sql()` signature to accept `orchestration_result`
- [ ] 3.2 Add `_build_t5_input()` method with structured context
- [ ] 3.3 Add `_apply_scope_logic()` method for document_type filtering
- [ ] 3.4 Update SQL generation to use scope field
- [ ] 3.5 Handle all 8 intents correctly
- [ ] 3.6 Handle all 4 scopes correctly

**Estimated Time**: 1 hour

**Files**:
- `app/services/stage2/t5_sql_generator.py` (update)

**Testing**:
```python
# Test T5 input builder
orchestration_result = {
    "intent": "LOOKUP",
    "scope": "row",
    "slots": {"project": "Francis Gays", "category": "fuel"}
}
t5_input = generator._build_t5_input("find fuel", orchestration_result)
assert "[INTENT:LOOKUP]" in t5_input
assert "[SCOPE:row]" in t5_input
assert "[PROJECT:Francis Gays]" in t5_input

# Test scope logic
sql = "SELECT * FROM ai_documents WHERE org_id = $1"
sql_with_scope = generator._apply_scope_logic(sql, "row", {})
assert "document_type = 'row'" in sql_with_scope
```

---

### 4. Update Chat Route Integration
- [ ] 4.1 Update chat route to pass new format to T5 generator
- [ ] 4.2 Update clarification handling to use `clarify_slots` array
- [ ] 4.3 Update response building to include scope information
- [ ] 4.4 Test error handling with new format

**Estimated Time**: 30 minutes

**Files**:
- `app/api/routes/chat.py` (update)

---

### 5. Integration Testing
- [ ] 5.1 Test LOOKUP intent with row scope
- [ ] 5.2 Test LOOKUP intent with file scope
- [ ] 5.3 Test COUNT intent with summary scope
- [ ] 5.4 Test SUM intent with summary scope
- [ ] 5.5 Test AVG intent with summary scope
- [ ] 5.6 Test DISTINCT intent with distinct_values scope
- [ ] 5.7 Test COMPARE intent with summary scope
- [ ] 5.8 Test LOCATE intent with row scope
- [ ] 5.9 Test MULTI_QUERY intent
- [ ] 5.10 Test clarification flow
- [ ] 5.11 Test end-to-end pipeline with real queries

**Estimated Time**: 1 hour

**Test Queries**:
```
# Row-level lookup
"find fuel in Francis Gays"
"show cement in SJDM"
"gcash payments in Manila Tower"

# File-level lookup
"show Francis Gays"
"display SJDM file"

# Summary queries
"how many projects"
"how much fuel in Francis Gays"
"average labor cost"

# DISTINCT queries
"show all categories"
"list all projects"
"what payment methods"

# COMPARE queries
"compare fuel between Francis Gays and SJDM"
"compare labor costs in all projects"

# LOCATE queries
"find REF-001"
"show document REF-123"

# Clarification needed
"find fuel" (missing project)
"show expenses" (missing project and category)
```

---

### 6. Documentation
- [ ] 6.1 Update API documentation with new format
- [ ] 6.2 Update architecture diagrams
- [ ] 6.3 Create migration guide for developers
- [ ] 6.4 Update training guide with new dataset

**Estimated Time**: 30 minutes

**Files**:
- `docs/3STAGE_ARCHITECTURE.md` (update)
- `docs/API_CHANGES.md` (update)
- `STAGE1_UPGRADE_COMPLETE.md` (create)

---

## Progress Tracking

**Overall Progress**: 0/6 tasks complete (0%)

**Current Status**: Waiting for model training (Task 1)

**Next Steps**:
1. User trains model using Colab notebook
2. Once model is ready, proceed with Tasks 2-6

---

## Testing Checklist

### Unit Tests
- [ ] Intent classification (8 intents)
- [ ] Scope classification (4 scopes)
- [ ] Slot extraction (8 slots)
- [ ] Clarification detection
- [ ] T5 input builder
- [ ] Scope logic application

### Integration Tests
- [ ] Full pipeline: Query → Stage 1 → Stage 2 → SQL → Results
- [ ] All intent + scope combinations
- [ ] Clarification flow
- [ ] Multi-query handling
- [ ] Error handling

### Manual Tests
- [ ] Test with real user queries
- [ ] Test with edge cases
- [ ] Test with ambiguous queries
- [ ] Test with multi-language queries (if applicable)

---

## Rollback Plan

If issues arise:
1. Revert to old model: `ml/models/enhanced_orchestrator_model/`
2. Revert code changes via git
3. Feature flag to switch between old/new format
4. Monitor error rates and user feedback

---

## Success Criteria

- [ ] Model accuracy: Intent 95%+, Scope 90%+
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual testing successful
- [ ] No performance degradation (<200ms latency)
- [ ] No increase in error rates
- [ ] Documentation updated
