# T5 Text-to-SQL Training Guide — AU-Ggregates

> Comprehensive reference para sa tamang pag-train ng T5 model natin.
> Kung nakalimutan mo kung paano, basahin mo lang ito.

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [What the T5 Model Does](#2-what-the-t5-model-does)
3. [Training Data Requirements](#3-training-data-requirements)
4. [Hyperparameter Reference](#4-hyperparameter-reference)
5. [Training Methods: Full Fine-Tuning vs LoRA](#5-training-methods-full-fine-tuning-vs-lora)
6. [Step-by-Step Training Procedure](#6-step-by-step-training-procedure)
7. [Evaluation & Validation](#7-evaluation--validation)
8. [Common Problems & Solutions](#8-common-problems--solutions)
9. [Dataset Improvement Strategy](#9-dataset-improvement-strategy)
10. [File Reference](#10-file-reference)

---

## 1. System Architecture Overview

The AI system uses a 2-stage pipeline:

```
User Query (text)
    │
    ▼
┌─────────────────────────────┐
│  STAGE 1: Phi-3-mini-4k     │  ← Intent extraction (JSON)
│  (phi3_service.py)           │    Extracts: intent_type, source_table,
│                              │    file_name, project_name, entities
└──────────┬──────────────────┘
           │ Intent JSON
           ▼
┌─────────────────────────────┐
│  STAGE 2: T5-LM-Large       │  ← SQL generation
│  (text2sql-spider)           │    Input: Spider schema + intent_type + source_table
│                              │    Output: Raw SQL query
└──────────┬──────────────────┘
           │ Raw SQL
           ▼
┌─────────────────────────────┐
│  POST-PROCESSING (code)      │  ← Entity injection + JSONB conversion
│  _inject_entity_filters()    │    Adds WHERE clauses from Phi-3 entities
│  _convert_to_jsonb_sql()     │    Converts column refs to metadata->>
└──────────┬──────────────────┘
           │ Final SQL
           ▼
┌─────────────────────────────┐
│  SQL VALIDATOR               │  ← Security + gibberish check
│  (sql_validator.py)          │    SELECT-only, no injection, RBAC
└──────────┬──────────────────┘
           │ Validated SQL
           ▼
┌─────────────────────────────┐
│  SUPABASE EXECUTION          │  ← Execute on PostgreSQL
│  (supabase_client.py)        │    Returns data rows
└──────────┬──────────────────┘
           │ Query results
           ▼
┌─────────────────────────────┐
│  STAGE 3: Phi-3-mini-4k     │  ← Response formatting
│  (phi3_service.py)           │    Formats results into natural language
└─────────────────────────────┘
```

Key points:
- T5 does NOT connect to the database. It only generates SQL from learned patterns.
- Entity names (project names, file names, etc.) are injected by code AFTER T5 generates the SQL template.
- T5 receives only `intent_type + source_table` (e.g., "sum Expenses"), not the actual entity values.
- The `SchemaRegistry` connects to DB but is used by Phi-3 and post-processing, not T5.

---

## 2. What the T5 Model Does

### Base Model
- **Name**: `gaussalgo/T5-LM-Large-text2sql-spider`
- **Architecture**: T5ForConditionalGeneration (encoder-decoder)
- **Parameters**: ~783M
- **Base**: Fine-tuned from `t5-large-LM-adapt` on Spider + Spider-Syn datasets
- **Spider dev accuracy**: 49.2% (execution accuracy)

### Input Format (Spider format)
```
tables: ai_documents (id, source_table, file_name, project_name, searchable_text, metadata, document_type) | query: <natural_language_question>
```

### Output Format
```sql
SELECT ... FROM ai_documents WHERE source_table = '...' AND document_type = '...' ...;
```

### What T5 Learns
- Mapping natural language patterns → SQL structure
- Which columns to SELECT based on intent
- Which WHERE clauses to generate based on source_table
- JSONB access patterns: `metadata->>'Key'`
- Aggregation patterns: `SUM((...) ::numeric)`, `COUNT(*)`, `AVG(...)`
- ILIKE matching patterns

---

## 3. Training Data Requirements

### Format
JSONL file, one JSON object per line:
```json
{"input": "tables: ai_documents (...) | query: show all expense files", "target": "SELECT file_name, project_name FROM ai_documents WHERE source_table = 'Expenses' AND document_type = 'file';"}
```

### Current Dataset
- **Custom pairs**: 5,000 (file: `t5_text2sql_5000_pairs.jsonl`)
- **Spider pairs**: ~3,000 (downloaded in notebook Cell 5)
- **Total merged**: ~8,000 pairs

### Dataset Quality Rules

1. Every `input` MUST start with the exact Spider schema prefix
2. Every `target` MUST be a valid SELECT-only SQL statement
3. Every `target` MUST include `source_table = '...'` filter
4. Every `target` MUST include `document_type = 'file'` or `document_type = 'row'`
5. Use `metadata->>'Key'` for JSONB access (double arrow)
6. Use `ILIKE '%value%'` for text matching
7. Cast numeric keys with `::numeric` for aggregation

### Intent Distribution (Target)

Ang 5k custom dataset natin ay heavily skewed sa `list_files`. Ideal distribution:

| Intent | Target % | Current Issue |
|--------|----------|---------------|
| list_files | 8% | ⚠️ Over-represented (~60%+) |
| query_data | 18% | Under-represented |
| sum | 18% | Under-represented |
| count | 15% | Under-represented |
| average | 10% | Under-represented |
| compare | 10% | Under-represented |
| list_categories | 10% | Under-represented |
| date_filter | 11% | Missing |

### Source Table Distribution (Target)

| Source Table | Target % |
|-------------|----------|
| Expenses | ~35% |
| CashFlow | ~25% |
| Project | ~15% |
| Quotation | ~15% |
| QuotationItem | ~10% |

### Improving Dataset Diversity

Use `scripts/download_and_adapt_datasets.py` to supplement with public datasets:
- `b-mc2/sql-create-context` — 78k pairs (best adaptability)
- `Clinton/Text-to-sql-v1` — Large collection
- `knowrohit07/know_sql` — Curated pairs

The script adapts general text-to-SQL pairs to our `ai_documents` schema by:
1. Classifying intent (sum, count, average, list_files, etc.)
2. Picking appropriate source_table + document_type
3. Generating new SQL using our schema patterns
4. Rewriting questions to fit our domain

---

## 4. Hyperparameter Reference

### gaussalgo's Original Training Settings
Source: [HuggingFace model card](https://huggingface.co/gaussalgo/T5-LM-Large-text2sql-spider)

```python
learning_rate = 5e-5
warmup_steps = 1000
gradient_accumulation_steps = 8
num_train_epochs = 10
stopping_patience = 8
bf16 = True
eval_steps = 200
```

### Our Corrected Settings (for second-stage fine-tuning)

| Parameter | Old (BROKEN) | New (FIXED) | Why |
|-----------|-------------|-------------|-----|
| `learning_rate` | 3e-4 | **3e-5** | 3e-4 was 6x too high → catastrophic forgetting. For second-stage fine-tuning on a pre-trained model, use 1e-5 to 5e-5. |
| `epochs` | 10 | **5** | 10 epochs with no early stopping → overfitting. 3-5 epochs is enough with early stopping. |
| `batch_size` | 8 | **2-4** | Smaller batch + gradient accumulation = more stable training. Effective batch = batch_size × gradient_accumulation. |
| `warmup_steps` | 0 | **200** | Warmup prevents early divergence by gradually increasing LR from 0. |
| `gradient_accumulation` | 1 | **4** | Simulates larger batch size without VRAM cost. Effective batch = 2×4 = 8 or 4×4 = 16. |
| `early_stopping` | None | **patience=3** | Stops training when validation loss stops improving for 3 epochs. Prevents overfitting. |
| `fp16` | False | **True** | Half-precision training: 2x faster, 50% less VRAM. |
| `weight_decay` | 0 | **0.01** | L2 regularization prevents overfitting. |
| `max_grad_norm` | None | **1.0** | Gradient clipping prevents exploding gradients. |

### LoRA-Specific Settings (Kaggle notebook)

| Parameter | Value | Why |
|-----------|-------|-----|
| `lora_r` | 16 | Rank of low-rank matrices. 8-32 is typical. Higher = more capacity but more params. |
| `lora_alpha` | 32 | Scaling factor. Usually 2× lora_r. |
| `lora_dropout` | 0.05 | Regularization on LoRA layers. |
| `target_modules` | `['q', 'v']` | Apply LoRA to query and value attention matrices only. |
| Trainable params | ~2.4M (~0.3%) | vs 783M total. Prevents catastrophic forgetting by freezing base model. |

### Learning Rate Guidelines

| Scenario | Recommended LR | Notes |
|----------|---------------|-------|
| Full fine-tuning (from scratch) | 1e-4 to 3e-4 | Only for training from base T5, not pre-trained text2sql |
| Second-stage fine-tuning | **1e-5 to 5e-5** | Our case: fine-tuning gaussalgo's already-trained model |
| LoRA fine-tuning | 1e-5 to 3e-5 | Can be slightly higher since base is frozen |
| If model outputs gibberish | Lower the LR | Gibberish = catastrophic forgetting from too-high LR |

---

## 5. Training Methods: Full Fine-Tuning vs LoRA

### Full Fine-Tuning
- Updates ALL 783M parameters
- Higher risk of catastrophic forgetting
- Needs lower learning rate (1e-5 to 3e-5)
- Needs more VRAM (~16GB+)
- Used by: `scripts/fine_tune_t5.py`, `notebooks/t5_fine_tune_colab.ipynb`

### LoRA (Low-Rank Adaptation) — RECOMMENDED
- Freezes base model, trains only ~2.4M adapter parameters (~0.3%)
- Much lower risk of catastrophic forgetting
- Needs less VRAM (~8-10GB)
- After training, merges adapter back into base model → normal T5
- Used by: `notebooks/t5_fine_tune_kaggle.ipynb` (primary training notebook)

### Why LoRA is Better for Our Case

Research confirms (sources: [LoRA Learns Less and Forgets Less](https://hesamsheikh.substack.com/p/lora-learns-less-and-forgets-less), [NeurIPS 2023](https://neurips.cc/virtual/2023/poster/72516)):

1. LoRA prevents catastrophic forgetting by keeping the base model frozen
2. The base model (gaussalgo) already knows SQL generation — we just need to teach it our specific schema patterns
3. With only 8k training pairs, full fine-tuning risks overfitting; LoRA's parameter efficiency acts as implicit regularization
4. LoRA training is 3-5x faster and uses 50% less VRAM

---

## 6. Step-by-Step Training Procedure

### Prerequisites
- Kaggle account with GPU enabled (T4 x2 or P100)
- `t5_text2sql_5000_pairs.jsonl` uploaded as Kaggle dataset
- HuggingFace account + API token (for pushing trained model)

### Procedure

#### Step 1: Push Code to GitHub
```bash
git add -A
git commit -m "Update training notebook with fixed hyperparameters"
git push
```

#### Step 2: Import Notebook to Kaggle
1. Go to [kaggle.com/code](https://kaggle.com/code)
2. Click "New Notebook"
3. File → Import Notebook → paste GitHub URL for `notebooks/t5_fine_tune_kaggle.ipynb`
4. Settings → Accelerator → **GPU T4 x2** or **P100**
5. Add Data → upload `t5_text2sql_5000_pairs.jsonl`

#### Step 3: Run Cells in Order

| Cell | What | Expected Output | Time |
|------|------|----------------|------|
| 1 | Install deps | "All dependencies installed!" | ~2 min |
| 2 | GPU check | "✅ GPU ready!" | instant |
| 3 | Load data | "Found: /kaggle/input/.../t5_text2sql_5000_pairs.jsonl" | instant |
| 4 | Validate | "✅ Data looks good! 5000 valid pairs ready." | ~10 sec |
| 5 | Clean + Merge | "✅ ~8000 pairs ready for training!" | ~3-5 min |
| 6 | Train (LoRA) | Training logs + "Model pushed to HuggingFace" | ~30-60 min |
| 7 | Evaluate | Exact-match accuracy + sample predictions | ~5 min |
| 8 | Test | Interactive SQL generation results | instant |
| 9 | Export | Zip file for download | ~2 min |

#### Step 4: Check Results

After Cell 7 (Evaluate), check these metrics:

| Metric | Good | Great | Action if Low |
|--------|------|-------|---------------|
| Exact-match accuracy | ≥50% | ≥70% | Add more diverse training data |
| Valid SQL rate | ≥90% | ≥95% | Check training data quality |
| Avg inference time | <500ms | <200ms | Normal for T5-Large |

#### Step 5: Deploy

After training, the model is automatically pushed to HuggingFace.
Set in `.env`:
```
T5_MODEL_PATH=espinajc/t5-auggregates-text2sql
```

Or download the zip from Cell 9 and set `T5_MODEL_PATH` to the local folder path.

---

## 7. Evaluation & Validation

### Metrics

| Metric | What it Measures | How |
|--------|-----------------|-----|
| Exact Match (EM) | Generated SQL == Expected SQL (character-level) | Strictest metric |
| Execution Accuracy (EX) | Generated SQL parses as valid SELECT statement | Uses `sqlparse` |
| Logical Form Accuracy (LFAcc) | Match after normalization (lowercase, whitespace) | More lenient than EM |
| BLEU | N-gram overlap between generated and expected | Surface similarity |

### What to Look For in Sample Predictions

Good signs:
- SQL starts with SELECT
- Correct source_table filter
- Correct document_type filter
- Correct JSONB access patterns (`metadata->>'Key'`)
- Correct aggregation functions (SUM, COUNT, AVG)

Bad signs:
- Non-SQL output (gibberish, Romanian text, repeated words)
- Missing source_table or document_type filters
- Wrong table names or column names
- INSERT/UPDATE/DELETE statements

### Gibberish Detection (Safety Net)

Two layers of gibberish detection protect against bad model output:

1. **Inline check** (`phi3_service.py` → `_generate_sql_with_t5_model`):
   - No SQL keywords present → `GenerationError`
   - Word repetition >50% → `GenerationError`

2. **Validator check** (`sql_validator.py` → `_check_gibberish`):
   - Must start with SELECT
   - Must contain FROM
   - Non-SQL word repeated >40% of all words → rejected

---

## 8. Common Problems & Solutions

### Problem: Model outputs gibberish (Romanian text, repeated words)
**Cause**: Catastrophic forgetting from too-high learning rate or too many epochs.
**Solution**:
- Lower `learning_rate` to 1e-5 or 3e-5
- Use LoRA instead of full fine-tuning
- Reduce epochs to 3-5 with early stopping
- Verify training data quality

### Problem: Model outputs valid SQL but wrong structure
**Cause**: Training data doesn't cover the query pattern.
**Solution**:
- Check intent distribution in training data (Cell 4)
- Add more diverse training pairs for underrepresented intents
- Use `scripts/download_and_adapt_datasets.py` to supplement

### Problem: CUDA out of memory
**Cause**: Batch size too large for GPU VRAM.
**Solution**:
- Reduce `BATCH_SIZE` to 1 or 2
- Increase `gradient_accumulation_steps` to compensate
- Enable gradient checkpointing (already enabled in Kaggle notebook)
- Use LoRA (uses ~50% less VRAM than full fine-tuning)

### Problem: Training loss not decreasing
**Cause**: Learning rate too low, or training data has issues.
**Solution**:
- Check training data for duplicates or invalid pairs
- Try slightly higher learning rate (5e-5)
- Check that labels are not empty (Cell 6 has diagnostic)

### Problem: Validation loss increases while training loss decreases
**Cause**: Overfitting.
**Solution**:
- Early stopping will handle this (patience=3)
- Add more training data
- Increase `weight_decay` to 0.02
- Reduce epochs

### Problem: Model ignores source_table or document_type filters
**Cause**: Training data doesn't consistently include these filters.
**Solution**:
- Run Cell 4 validation — check for missing filters
- Every training pair MUST have `source_table = '...'` and `document_type = '...'`
- Clean data with Cell 5 before training

---

## 9. Dataset Improvement Strategy

### Current State
- 5,000 custom pairs (heavily skewed to `list_files`)
- 3,000 Spider pairs (general SQL, different schema format)
- ~4,000 b-mc2 adapted pairs (remapped to our schema with diverse intents)
- Total: ~12,000 pairs

### What's Already Integrated (Cell 5 of Kaggle notebook)

The Kaggle notebook Cell 5 now automatically:
1. Cleans and validates your 5k custom pairs
2. Downloads Spider dataset (~3k raw SQL pairs)
3. Downloads b-mc2/sql-create-context (78k pairs), adapts ~4k to our schema
4. Merges all three sources, deduplicates, shuffles

The b-mc2 adaptation engine classifies intent from the original SQL, remaps to our `ai_documents` single-table schema, injects JSONB patterns (metadata->>'key', ::numeric casts, ILIKE), and rewrites questions to fit our construction domain.

### Further Improvement Options (in order of impact)

#### Option 1: Rebalance Custom Dataset
Re-generate the 5,000 custom pairs with better intent distribution using the prompt in `docs/t5_training_data_prompt.md`. Target distribution:
- list_files: 8% (400 pairs) — currently over-represented
- query_data: 18% (900 pairs)
- sum: 18% (900 pairs)
- count: 15% (750 pairs)
- average: 10% (500 pairs)
- compare: 10% (500 pairs)
- list_categories: 10% (500 pairs)
- date_filter: 11% (550 pairs)

#### Option 2: Add More Public Datasets
Use `scripts/download_and_adapt_datasets.py` to download and adapt additional public datasets beyond b-mc2:

```bash
python scripts/download_and_adapt_datasets.py --output data/adapted_public.jsonl --limit 5000
```

This can also adapt from `Clinton/Text-to-sql-v1` and `knowrohit07/know_sql`. The adaptation:
1. Classifies intent from the original SQL
2. Remaps to our `ai_documents` single-table schema
3. Injects JSONB patterns, ILIKE matching, ::numeric casts
4. Rewrites questions to fit our domain

#### Option 3: Generate Gold-Standard Pairs
Use `scripts/generate_gold_training_data.py` to generate high-quality pairs with controlled distribution.

### Quality Checklist Before Training

- [ ] All pairs have Spider schema prefix
- [ ] All targets are SELECT-only
- [ ] All targets have source_table filter
- [ ] All targets have document_type filter
- [ ] Intent distribution is balanced (not >30% any single intent)
- [ ] All 5 source tables are represented
- [ ] Numeric keys use ::numeric casting
- [ ] Text matching uses ILIKE
- [ ] No duplicate pairs (check with Cell 5 dedup)
- [ ] At least 8,000 total pairs (10,000+ recommended with b-mc2)

---

## 10. File Reference

### Training Scripts & Notebooks

| File | Purpose | Platform |
|------|---------|----------|
| `notebooks/t5_fine_tune_kaggle.ipynb` | **Primary training notebook** (LoRA) | Kaggle |
| `notebooks/t5_fine_tune_colab.ipynb` | Alternative training (full fine-tune) | Google Colab |
| `notebooks/t5_fine_tune_lightning.ipynb` | PyTorch Lightning version | Any GPU |
| `scripts/fine_tune_t5.py` | CLI training script (full fine-tune) | Local/Server |

### Data Scripts

| File | Purpose |
|------|---------|
| `t5_text2sql_5000_pairs.jsonl` | Custom training data (5k pairs) |
| `scripts/download_and_adapt_datasets.py` | Download + adapt public datasets |
| `scripts/generate_training_data.py` | Generate training pairs |
| `scripts/generate_gold_training_data.py` | Generate high-quality pairs |
| `scripts/clean_and_merge_training_data.py` | Clean + merge + deduplicate |
| `scripts/validate_training_data.py` | Validate JSONL format |
| `scripts/check_dataset.py` | Check dataset statistics |
| `docs/t5_training_data_prompt.md` | Prompt for generating 5k pairs with external AI |

### Deployment

| File | Purpose |
|------|---------|
| `notebooks/auggregates_ai_kaggle.ipynb` | Kaggle deployment notebook |
| `notebooks/auggregates_ai_colab.ipynb` | Colab deployment notebook |
| `upload_t5_to_hf.py` | Upload trained model to HuggingFace |

### Runtime (Production)

| File | Purpose |
|------|---------|
| `app/services/phi3_service.py` | Stage 1 (Phi-3) + Stage 2 (T5) + post-processing |
| `app/services/sql_validator.py` | SQL validation + gibberish detection |
| `app/services/schema_registry.py` | Dynamic schema discovery from DB |
| `app/config/phi3_config.py` | Model configuration + Spider schema prefix |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│  T5 TRAINING QUICK REFERENCE                     │
├─────────────────────────────────────────────────┤
│  Base model:  gaussalgo/T5-LM-Large-text2sql-   │
│               spider                             │
│  Method:      LoRA (r=16, alpha=32)              │
│  LR:          3e-5 (NEVER higher than 5e-5)      │
│  Epochs:      5 (with early stopping patience=3) │
│  Batch:       2 (effective=8 with accum=4)       │
│  Warmup:      200 steps                          │
│  Data:        5k custom + 3k Spider + 4k b-mc2 adapted = ~12k pairs  │
│  Platform:    Kaggle (GPU T4 x2)                 │
│  Notebook:    notebooks/t5_fine_tune_kaggle.ipynb │
│  Output:      espinajc/t5-auggregates-text2sql   │
├─────────────────────────────────────────────────┤
│  ⚠️  NEVER use learning_rate > 5e-5              │
│  ⚠️  NEVER train > 10 epochs without early stop  │
│  ⚠️  ALWAYS use LoRA for second-stage fine-tune  │
│  ⚠️  ALWAYS validate data before training        │
└─────────────────────────────────────────────────┘
```

---

*Last updated: February 27, 2026*
*Sources: [gaussalgo model card](https://huggingface.co/gaussalgo/T5-LM-Large-text2sql-spider), [arxiv:2508.04623](https://arxiv.org/html/2508.04623v1), LoRA research, project experience*
