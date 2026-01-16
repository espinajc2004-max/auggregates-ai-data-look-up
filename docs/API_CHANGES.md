# API Changes & Migration Guide

**Upgrading to 3-Stage AI Query System**

---

## Table of Contents
1. [Overview](#overview)
2. [Breaking Changes](#breaking-changes)
3. [New Features](#new-features)
4. [API Endpoint Changes](#api-endpoint-changes)
5. [Configuration Changes](#configuration-changes)
6. [Migration Steps](#migration-steps)
7. [Backward Compatibility](#backward-compatibility)
8. [Testing Your Migration](#testing-your-migration)

---

## Overview

The 3-Stage AI Query System introduces significant improvements to query processing:
- **Stage 1**: Intent detection and entity extraction
- **Stage 1.5**: Database-driven clarification
- **Stage 2**: T5 SQL generation with security guardrails
- **Stage 3**: Natural language composition (optional)

This guide helps you migrate from the old system to the new architecture.

---

## Breaking Changes

### 1. Chat Endpoint Request Format

**OLD** (Before):
```json
{
  "query": "find gcash payments",
  "org_id": 1,
  "user_id": "user123"
}
```

**NEW** (After):
```json
{
  "query": "find gcash payments",
  "org_id": 1,
  "user_id": "user123",
  "conversation_id": "conv_123"  // Optional: for conversation context
}
```

**Impact**: `conversation_id` is now optional but recommended for better context handling.

### 2. Response Format Changes

**OLD** (Before):
```json
{
  "answer": "Found 5 GCASH payments",
  "sql": "SELECT * FROM ai_documents WHERE method = 'GCASH'",
  "results": [...]
}
```

**NEW** (After):
```json
{
  "answer": "Found 5 GCASH payments",
  "sql": "SELECT * FROM ai_documents WHERE org_id = 1 AND metadata->>'method' = 'GCASH' LIMIT 10",
  "results": [...],
  "metadata": {
    "stage1": {
      "intent": "LOOKUP",
      "entities": {"method": "gcash"},
      "needs_clarification": false,
      "confidence": 0.92
    },
    "stage2": {
      "confidence": 0.85,
      "guardrails_applied": ["org_id_injection", "limit_added"]
    }
  }
}
```

**Impact**: Response now includes detailed metadata about processing stages.

### 3. Clarification Flow

**OLD** (Before):
- System guessed ambiguous queries
- No clarification mechanism

**NEW** (After):
```json
// First request
{
  "query": "how many projects",
  "org_id": 1,
  "user_id": "user123"
}

// Response (needs clarification)
{
  "needs_clarification": true,
  "clarification_question": "Which project?",
  "options": [
    {"id": 1, "label": "SJDM"},
    {"id": 2, "label": "Francis Gays"},
    {"id": 3, "label": "All projects"}
  ],
  "conversation_id": "conv_123"
}

// Follow-up request
{
  "query": "1",  // User selects option 1
  "org_id": 1,
  "user_id": "user123",
  "conversation_id": "conv_123"
}

// Final response
{
  "answer": "SJDM has 15 records",
  "sql": "SELECT COUNT(*) FROM ai_documents WHERE org_id = 1 AND project_id = 1",
  "results": [{"count": 15}]
}
```

**Impact**: Clients must handle clarification flow with conversation context.

---

## New Features

### 1. Multi-Query Support

**Request**:
```json
{
  "query": "how many expenses and how many cashflow",
  "org_id": 1,
  "user_id": "user123"
}
```

**Response**:
```json
{
  "multi_query": true,
  "answers": [
    {
      "query": "how many expenses",
      "answer": "Found 25 expenses",
      "sql": "SELECT COUNT(*) FROM ai_documents WHERE org_id = 1 AND source_table = 'Expenses'",
      "results": [{"count": 25}]
    },
    {
      "query": "how many cashflow",
      "answer": "Found 10 cashflow records",
      "sql": "SELECT COUNT(*) FROM ai_documents WHERE org_id = 1 AND source_table = 'Cashflow'",
      "results": [{"count": 10}]
    }
  ]
}
```

### 2. Enhanced Entity Extraction

The system now extracts:
- `project`: Project name (e.g., "SJDM", "Francis Gays")
- `method`: Payment method (e.g., "GCASH", "Cash")
- `ref_no`: Reference number (e.g., "REF-2024-001")
- `date_range`: Date filters (e.g., "last month", "January 2024")

**Example**:
```json
{
  "query": "find gcash payments in SJDM last month",
  "org_id": 1,
  "user_id": "user123"
}

// Response includes extracted entities
{
  "metadata": {
    "stage1": {
      "entities": {
        "method": "gcash",
        "project": "SJDM",
        "date_range": "last month"
      }
    }
  }
}
```

### 3. SQL Guardrails

All SQL queries now automatically include:
- **org_id filter**: Multi-tenancy enforcement
- **DDL blocking**: No DROP, DELETE, UPDATE, INSERT
- **Schema validation**: Only allowed tables
- **LIMIT clause**: Prevents large result sets

**Example**:
```json
// User query: "SELECT * FROM ai_documents"
// Generated SQL (with guardrails):
"SELECT * FROM ai_documents WHERE org_id = 1 LIMIT 10"
```

### 4. Confidence Scoring

Every query includes confidence scores:
```json
{
  "metadata": {
    "stage1": {
      "confidence": 0.92  // Intent detection confidence
    },
    "stage2": {
      "confidence": 0.85  // SQL generation confidence
    }
  }
}
```

If confidence < 0.7, system falls back to Universal Handler.

---

## API Endpoint Changes

### Chat Endpoint

**Endpoint**: `POST /api/chat`

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer <token>  // Optional
```

**Request Body**:
```json
{
  "query": "string (required)",
  "org_id": "integer (required)",
  "user_id": "string (required)",
  "conversation_id": "string (optional)"
}
```

**Response** (Success):
```json
{
  "answer": "string",
  "sql": "string",
  "results": "array",
  "needs_clarification": "boolean",
  "clarification_question": "string (optional)",
  "options": "array (optional)",
  "conversation_id": "string",
  "metadata": {
    "stage1": {...},
    "stage2": {...}
  }
}
```

**Response** (Error):
```json
{
  "error": "string",
  "details": "string",
  "stage": "string"  // Which stage failed
}
```

### New Status Endpoint

**Endpoint**: `GET /api/status`

**Response**:
```json
{
  "t5_available": true,
  "orchestrator_available": true,
  "guardrails_enabled": true,
  "version": "1.0.0"
}
```

### Health Check Endpoint

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "t5_model": "loaded",
  "orchestrator": "loaded",
  "database": "connected"
}
```

---

## Configuration Changes

### New Environment Variables

Add to `.env`:

```env
# T5 Configuration
TEXT_TO_SQL_USE_T5=true
T5_MODEL_PATH=ml/models/t5_text_to_sql
T5_CONFIDENCE_THRESHOLD=0.7

# Orchestrator Configuration
ORCHESTRATOR_ENABLED=true
ORCHESTRATOR_MODEL_PATH=ml/models/enhanced_orchestrator_model

# DB Clarification
DB_CLARIFICATION_ENABLED=true
DB_CLARIFICATION_MAX_OPTIONS=10

# Security
ALLOWED_TABLES=ai_documents,projects,conversations
SQL_GUARDRAILS_ENABLED=true
```

### Deprecated Variables

These variables are no longer used:
- `OLLAMA_ENABLED` - Replaced by `TEXT_TO_SQL_USE_T5`
- `OLLAMA_MODEL` - No longer needed

---

## Migration Steps

### Step 1: Update Dependencies

```bash
pip install -r requirements.txt
```

New dependencies:
- `torch==2.1.0`
- `transformers==4.36.0`
- `sentencepiece==0.1.99`

### Step 2: Download Models

```bash
python scripts/download_models.py
```

This downloads:
- T5 Text-to-SQL model (~242MB)
- Enhanced DistilBERT Orchestrator (~250MB)

### Step 3: Update Configuration

1. Copy `.env.example` to `.env`
2. Add new environment variables (see above)
3. Update `ALLOWED_TABLES` with your tables

### Step 4: Update Client Code

**Before**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "query": "find gcash payments",
        "org_id": 1,
        "user_id": "user123"
    }
)

answer = response.json()["answer"]
```

**After**:
```python
import requests

# First request
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "query": "find gcash payments",
        "org_id": 1,
        "user_id": "user123",
        "conversation_id": "conv_123"  # Optional but recommended
    }
)

data = response.json()

# Handle clarification if needed
if data.get("needs_clarification"):
    print(data["clarification_question"])
    for option in data["options"]:
        print(f"{option['id']}: {option['label']}")
    
    # User selects option
    user_choice = input("Select option: ")
    
    # Follow-up request
    response = requests.post(
        "http://localhost:8000/api/chat",
        json={
            "query": user_choice,
            "org_id": 1,
            "user_id": "user123",
            "conversation_id": data["conversation_id"]
        }
    )
    data = response.json()

# Get final answer
answer = data["answer"]
```

### Step 5: Test Migration

Run tests:
```bash
# Unit tests
python -m pytest tests/ -v

# Integration tests
python -m pytest tests/integration/ -v
```

### Step 6: Deploy

Follow deployment guide: `docs/DEPLOYMENT_GUIDE.md`

---

## Backward Compatibility

### Gradual Migration

You can enable/disable new features:

```env
# Disable T5 (use old system)
TEXT_TO_SQL_USE_T5=false

# Disable Orchestrator (use old router)
ORCHESTRATOR_ENABLED=false

# Disable Clarification (no clarification flow)
DB_CLARIFICATION_ENABLED=false
```

This allows gradual migration:
1. Deploy with all features disabled
2. Enable Orchestrator first
3. Enable T5 SQL generation
4. Enable Clarification last

### Fallback Behavior

If T5 confidence < 0.7, system automatically falls back to Universal Handler (old system).

---

## Testing Your Migration

### Test 1: Simple Query

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "find gcash payments",
    "org_id": 1,
    "user_id": "test"
  }'
```

Expected: Direct answer without clarification.

### Test 2: Ambiguous Query

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how many projects",
    "org_id": 1,
    "user_id": "test"
  }'
```

Expected: Clarification response with options.

### Test 3: Multi-Query

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how many expenses and how many cashflow",
    "org_id": 1,
    "user_id": "test"
  }'
```

Expected: Multiple answers in response.

### Test 4: SQL Guardrails

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "DROP TABLE ai_documents",
    "org_id": 1,
    "user_id": "test"
  }'
```

Expected: Error response (DDL operation blocked).

---

## Common Migration Issues

### Issue 1: Models Not Loading

**Symptom**: `FileNotFoundError: Model files not found`

**Solution**:
```bash
python scripts/download_models.py
```

### Issue 2: Slow Performance

**Symptom**: Queries taking >5 seconds

**Solution**:
- Enable GPU if available
- Consider model quantization
- Reduce number of workers

### Issue 3: Clarification Not Working

**Symptom**: No clarification questions shown

**Solution**:
1. Check `DB_CLARIFICATION_ENABLED=true` in `.env`
2. Verify database connection
3. Check logs for errors

### Issue 4: SQL Guardrails Too Strict

**Symptom**: Legitimate queries rejected

**Solution**:
Update `ALLOWED_TABLES` in `.env`:
```env
ALLOWED_TABLES=ai_documents,projects,conversations,your_table
```

---

## Support

For migration assistance:
- Review documentation: `docs/`
- Check logs: `logs/app_*.log`
- Run tests: `python -m pytest tests/ -v`
- Contact: [support email]

---

## Summary

**Key Changes**:
- ✅ New 3-stage processing pipeline
- ✅ Enhanced entity extraction
- ✅ Database-driven clarification
- ✅ Comprehensive SQL guardrails
- ✅ Multi-query support
- ✅ Confidence scoring
- ✅ Backward compatibility

**Migration Time**: ~1-2 hours for basic setup

**Testing Time**: ~30 minutes

**Total**: ~2-3 hours for complete migration

---

**Last Updated**: February 15, 2026  
**Version**: 1.0  
**Author**: Kiro AI Assistant
