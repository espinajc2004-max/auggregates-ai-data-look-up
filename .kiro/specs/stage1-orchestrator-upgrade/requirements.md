# Stage 1 Orchestrator Upgrade - Requirements

**Feature**: Upgrade Stage 1 Orchestrator to output new format with scope field
**Date**: 2026-02-16
**Status**: In Progress

## Background

The Stage 1 Orchestrator currently outputs an old format without the `scope` field. We need to upgrade it to match the corrected implementation plan based on expert feedback.

## User Stories

### US-1: Train Enhanced Stage 1 Model
As a developer, I want to train a new Stage 1 model using the `orchestrator_v2.jsonl` dataset so that it can predict intent, scope, and slots accurately.

**Acceptance Criteria**:
- Model trained using `ml/training/data/orchestrator_v2.jsonl` (3,000 examples)
- Model predicts 8 intents: LOOKUP, COUNT, SUM, AVG, DISTINCT, COMPARE, LOCATE, MULTI_QUERY
- Model predicts 4 scopes: row, file, summary, distinct_values
- Model extracts 8 slots: source_table, file_name, project, category, method, date_range, amount_range, custom_column
- Model saved to `ml/models/orchestrator_v2/`
- Intent accuracy: 95%+
- Scope accuracy: 90%+

### US-2: Update Orchestrator Service
As a developer, I want the orchestrator service to output the new format so that Stage 2 can receive structured context.

**Acceptance Criteria**:
- `orchestrator.py` outputs new format: `{intent, scope, slots, needs_clarification, clarify_slots}`
- Renamed "entities" to "slots"
- Changed "clarify_slot" to "clarify_slots" (array)
- Added scope extraction (4 classes)
- All 8 slots initialized to None
- Deterministic clarification rules implemented

### US-3: Update T5 SQL Generator
As a developer, I want the T5 SQL generator to accept the new Stage 1 format so that it can generate SQL with scope-specific logic.

**Acceptance Criteria**:
- `t5_sql_generator.py` accepts new format from Stage 1
- Builds T5 input with structured context: `[INTENT:X] [SCOPE:Y] [SLOT:value] translate to SQL: query`
- Applies scope-specific SQL logic (document_type filtering)
- Handles all 8 intents correctly
- Handles all 4 scopes correctly

### US-4: Integration Testing
As a developer, I want to test the full pipeline so that I can verify all components work together.

**Acceptance Criteria**:
- Test all 8 intents end-to-end
- Test all 4 scopes end-to-end
- Test clarification flow
- Test multi-query handling
- All tests pass

## Out of Scope

- Retraining Stage 2 (T5) model
- Retraining Stage 3 (Answer Composer) model
- UI changes
- Database schema changes

## References

- Dataset: `ml/training/data/orchestrator_v2.jsonl`
- Implementation Guide: `new-architecture/training_plan_example_Data_set/STAGE1_IMPLEMENTATION_NEXT_STEPS.md`
- Corrected Plan: `new-architecture/STAGE1_ORCHESTRATOR_CORRECTED_PLAN.md`
