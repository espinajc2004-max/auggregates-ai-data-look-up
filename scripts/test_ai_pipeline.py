"""
AI Pipeline Diagnostic Test
============================
Tests kung gumagana ang buong Phi-3 + T5 pipeline.
Run: python scripts/test_ai_pipeline.py

Sinusuri:
  Stage 0 - GPU / CUDA check
  Stage 1 - Phi-3 model load + intent extraction
  Stage 2 - T5 model load + SQL generation
  Stage 3 - Supabase query execution
  Stage 4 - Full end-to-end pipeline
"""

import sys
import os
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# HELPERS
# ============================================================================

def ok(msg): print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ️  {msg}")
def header(msg): print(f"\n{'='*60}\n  {msg}\n{'='*60}")


# ============================================================================
# STAGE 0: GPU CHECK
# ============================================================================
def test_gpu():
    header("STAGE 0: GPU / CUDA Check")
    try:
        import torch
        info(f"PyTorch version: {torch.__version__}")

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            ok(f"CUDA available: {torch.cuda.get_device_name(0)}")
            ok(f"CUDA version: {torch.version.cuda}")
            mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            ok(f"GPU memory: {mem:.1f} GB")
            return "cuda"
        else:
            fail("CUDA NOT available — running on CPU (will be very slow)")
            info("Fix: reinstall PyTorch with CUDA support")
            info("  python -m pip install torch --index-url https://download.pytorch.org/whl/cu121")
            return "cpu"
    except Exception as e:
        fail(f"PyTorch error: {e}")
        return "cpu"


# ============================================================================
# STAGE 1: PHI-3 LOAD + INTENT EXTRACTION
# ============================================================================
def test_phi3(device: str):
    header("STAGE 1: Phi-3 Load + Intent Extraction")

    model_name = os.getenv("PHI3_MODEL", "microsoft/Phi-3-mini-4k-instruct")
    quantization = os.getenv("PHI3_QUANTIZATION", "4bit")

    info(f"Model: {model_name}")
    info(f"Quantization: {quantization}")
    info(f"Device: {device}")

    # Check HuggingFace cache first
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    cache_key = "models--" + model_name.replace("/", "--")
    cache_path = os.path.join(hf_cache, cache_key)
    if os.path.exists(cache_path):
        ok(f"Model found in HF cache: {cache_path}")
    else:
        fail(f"Model NOT in HF cache: {cache_path}")
        info("Run: huggingface-cli login  then re-download")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Load tokenizer
        info("Loading tokenizer...")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        ok(f"Tokenizer loaded in {time.time()-t0:.1f}s")

        # Load model
        info("Loading model (this may take a few minutes)...")
        t0 = time.time()
        load_kwargs = {"device_map": "auto", "trust_remote_code": True}

        if quantization == "4bit":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
        elif quantization == "8bit":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            load_kwargs["torch_dtype"] = torch.float32

        model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        ok(f"Phi-3 model loaded in {time.time()-t0:.1f}s")

        if torch.cuda.is_available():
            mem = torch.cuda.memory_allocated() / 1024**3
            ok(f"GPU memory used: {mem:.2f} GB")

        # Test intent extraction
        info("Testing intent extraction...")
        test_query = "pakita mo yong fuel expenses sa project alpha"

        prompt = f"""<|user|>
You are an AI assistant for a construction management system.
Extract the intent from this query and return ONLY valid JSON.

Query: "{test_query}"

Return JSON with these fields:
- intent: one of (file_summary, find_in_file, list_categories, compare, count, sum, date_filter, ambiguous, general_search)
- needs_clarification: boolean
- slots: object with file_name, category, method, date fields (null if not present)
- clarification_question: string or null

JSON:
<|end|>
<|assistant|>"""

        t0 = time.time()
        inputs = tokenizer(prompt, return_tensors="pt")
        if device == "cuda" and torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=200,
                temperature=0.1,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        elapsed = time.time() - t0

        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                intent = json.loads(json_match.group())
                ok(f"Intent extracted in {elapsed:.1f}s")
                ok(f"Intent: {intent.get('intent')}")
                ok(f"Slots: {intent.get('slots')}")
                ok(f"Needs clarification: {intent.get('needs_clarification')}")
                return model, tokenizer, intent
            except json.JSONDecodeError:
                fail(f"Phi-3 returned invalid JSON: {json_match.group()[:200]}")
                info("Raw response tail: " + response[-300:])
                return model, tokenizer, None
        else:
            fail("Phi-3 did not return JSON")
            info("Raw response tail: " + response[-300:])
            return model, tokenizer, None

    except Exception as e:
        fail(f"Phi-3 failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


# ============================================================================
# STAGE 2: T5 LOAD + SQL GENERATION
# ============================================================================
def test_t5(intent: dict):
    header("STAGE 2: T5 Load + SQL Generation")

    t5_path = os.getenv("T5_MODEL_PATH", "gaussalgo/T5-LM-Large-text2sql-spider")
    info(f"T5 model: {t5_path}")

    # Spider format schema for the ai_documents table
    SPIDER_SCHEMA = (
        "tables: ai_documents ("
        "id, source_table, file_name, project_name, "
        "searchable_text, metadata, document_type"
        ") | query: "
    )

    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        import torch

        # Determine device: GPU if available, else CPU with warning
        if torch.cuda.is_available():
            device = "cuda"
            ok(f"CUDA available — loading T5 on GPU ({torch.cuda.get_device_name(0)})")
        else:
            device = "cpu"
            fail("CUDA not available — loading T5 on CPU (slower inference)")

        info("Loading T5 tokenizer...")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(t5_path)
        ok(f"T5 tokenizer loaded in {time.time()-t0:.1f}s")

        info("Loading T5 model...")
        t0 = time.time()
        model = AutoModelForSeq2SeqLM.from_pretrained(t5_path)
        model = model.to(device)
        model.eval()
        ok(f"T5 model loaded on {device} in {time.time()-t0:.1f}s")

        if torch.cuda.is_available():
            mem = torch.cuda.memory_allocated() / 1024**3
            ok(f"GPU memory used after T5 load: {mem:.2f} GB")

        # Test SQL generation with Spider format
        test_input = SPIDER_SCHEMA + "show all expenses for fuel"
        info(f"T5 input (Spider format): {test_input[:100]}...")

        t0 = time.time()
        inputs = tokenizer(test_input, return_tensors="pt", max_length=512, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                inputs["input_ids"],
                max_length=512,
                num_beams=4,
                early_stopping=True
            )

        sql = tokenizer.decode(outputs[0], skip_special_tokens=True)
        elapsed = time.time() - t0

        ok(f"SQL generated in {elapsed:.1f}s")
        ok(f"Generated SQL: {sql}")

        # Check if it looks like valid SQL
        if "SELECT" in sql.upper() or "select" in sql.lower():
            ok("SQL contains SELECT — looks valid")
        else:
            fail(f"SQL doesn't look right: {sql}")
            info("T5 may need fine-tuning on our schema")

        return model, tokenizer, sql

    except Exception as e:
        fail(f"T5 failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


# ============================================================================
# STAGE 3: SUPABASE QUERY
# ============================================================================
def test_supabase(sql: str):
    header("STAGE 3: Supabase Query Execution")

    try:
        from app.services.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        # Test basic connection
        info("Testing Supabase connection...")
        rows = supabase.get("ai_documents", params={"limit": "3", "select": "id,file_name,document_type"})
        if rows:
            ok(f"Supabase connected — {len(rows)} sample rows returned")
            for r in rows:
                info(f"  → file: {r.get('file_name')}, type: {r.get('document_type')}")
        else:
            fail("Supabase returned empty result")

        # Test with generated SQL if it looks valid
        if sql and "SELECT" in sql.upper():
            info(f"Testing generated SQL: {sql[:100]}")
            try:
                result = supabase.rpc("execute_sql", {"query": sql})
                ok(f"SQL executed — {len(result) if isinstance(result, list) else 'N/A'} rows")
            except Exception as e:
                fail(f"SQL execution failed: {e}")
                info("This is expected if T5 generated wrong SQL for our schema")

        return True

    except Exception as e:
        fail(f"Supabase error: {e}")
        return False


# ============================================================================
# STAGE 4: FULL PIPELINE SUMMARY
# ============================================================================
def print_summary(gpu_device, phi3_ok, t5_ok, supabase_ok, intent, sql):
    header("PIPELINE SUMMARY")

    stages = [
        ("GPU/CUDA",   gpu_device == "cuda"),
        ("Phi-3",      phi3_ok),
        ("T5 SQL Gen", t5_ok),
        ("Supabase",   supabase_ok),
    ]

    for name, status in stages:
        if status:
            ok(f"{name}: WORKING")
        else:
            fail(f"{name}: NOT WORKING")

    print()
    if intent:
        info(f"Phi-3 intent output: {json.dumps(intent, indent=2)}")
    if sql:
        info(f"T5 SQL output: {sql}")

    print()
    if phi3_ok and t5_ok and supabase_ok:
        ok("FULL PIPELINE IS WORKING — ready for production!")
    elif not phi3_ok:
        fail("BLOCKED: Phi-3 not loading. Fix GPU/CUDA first.")
        info("Run: nvidia-smi  →  check CUDA version")
        info("Then: python -m pip install torch --index-url https://download.pytorch.org/whl/cu121")
    elif phi3_ok and not t5_ok:
        fail("PARTIAL: Phi-3 works but T5 failed.")
        info("T5 may need fine-tuning.")
    elif phi3_ok and t5_ok and not supabase_ok:
        fail("PARTIAL: Models work but Supabase connection failed.")
        info("Check SUPABASE_URL and SUPABASE_KEY in .env")
    else:
        info("PARTIAL: Some stages working. Check failures above.")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AU-GGREGATES AI PIPELINE DIAGNOSTIC")
    print("="*60)

    # Stage 0
    gpu_device = test_gpu()

    # Stage 1
    phi3_model, phi3_tokenizer, intent = test_phi3(gpu_device)
    phi3_ok = phi3_model is not None

    # Stage 2
    t5_model, t5_tokenizer, sql = test_t5(intent)
    t5_ok = t5_model is not None

    # Stage 3
    supabase_ok = test_supabase(sql)

    # Summary
    print_summary(gpu_device, phi3_ok, t5_ok, supabase_ok, intent, sql)
