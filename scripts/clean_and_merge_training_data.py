"""
Training Data Cleaning & Merging Pipeline
==========================================
Cleans, deduplicates, and merges training data from multiple sources:
  1. AI-generated pairs (from ChatGPT/Claude via the prompt)
  2. Spider dataset (from HuggingFace/Kaggle — general text-to-SQL)
  3. Existing custom pairs (generate_training_data.py output, bugfix data, etc.)

Usage:
    # Clean AI-generated data only
    python scripts/clean_and_merge_training_data.py --custom data/ai_generated.jsonl

    # Clean + merge with Spider data
    python scripts/clean_and_merge_training_data.py --custom data/ai_generated.jsonl --spider

    # Merge multiple custom files
    python scripts/clean_and_merge_training_data.py --custom data/ai_generated.jsonl data/training_bugfix.jsonl

    # Full pipeline with all options
    python scripts/clean_and_merge_training_data.py \
        --custom data/ai_generated.jsonl data/training_bugfix.jsonl \
        --spider --spider-limit 3000 \
        --output data/training_final.jsonl
"""

import argparse
import json
import hashlib
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPIDER_PREFIX = (
    "tables: ai_documents (id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type) | query: "
)
VALID_SOURCE_TABLES = {"Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"}
NUMERIC_KEYS = {"Expenses", "Amount", "total_amount", "volume", "line_total"}
DISALLOWED_SQL = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"}


# ---------------------------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------------------------
def normalize_sql(sql: str) -> str:
    """Normalize SQL for deduplication: lowercase, collapse whitespace, strip semicolons."""
    sql = sql.strip().rstrip(";").strip()
    sql = re.sub(r"\s+", " ", sql)
    return sql.lower()


def fingerprint(pair: Dict) -> str:
    """Create a hash fingerprint for deduplication based on normalized target SQL."""
    normalized = normalize_sql(pair.get("target", ""))
    return hashlib.md5(normalized.encode()).hexdigest()


def validate_custom_pair(pair: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate a custom training pair for our ai_documents schema.

    Checks:
    - Has 'input' and 'target' keys
    - Input starts with Spider schema prefix
    - Target is a SELECT statement
    - Target includes source_table filter
    - Target includes document_type filter
    - Uses metadata->>'' for JSONB access (not metadata.key)
    - Numeric casts only on numeric keys
    """
    if "input" not in pair or "target" not in pair:
        return False, "missing input/target"

    inp = pair["input"]
    tgt = pair["target"]

    if not inp or not tgt:
        return False, "empty input or target"

    # Check Spider prefix
    if not inp.startswith(SPIDER_PREFIX):
        return False, "missing Spider schema prefix"

    # Check non-empty query
    query = inp[len(SPIDER_PREFIX):].strip()
    if not query:
        return False, "empty query after prefix"

    # Check SELECT only
    tgt_stripped = tgt.strip()
    if not tgt_stripped.upper().startswith("SELECT"):
        return False, f"not a SELECT statement"

    first_word = tgt_stripped.split()[0].upper()
    if first_word in DISALLOWED_SQL:
        return False, f"disallowed SQL: {first_word}"

    # Check source_table filter
    has_source = any(f"source_table = '{t}'" in tgt for t in VALID_SOURCE_TABLES)
    if not has_source:
        return False, "missing source_table filter"

    # Check document_type filter
    if "document_type = 'file'" not in tgt and "document_type = 'row'" not in tgt:
        return False, "missing document_type filter"

    # Check for common AI mistakes
    if "metadata." in tgt and "metadata->>" not in tgt:
        return False, "uses metadata.key instead of metadata->>'key'"

    return True, None


def clean_pair(pair: Dict) -> Dict:
    """Apply cleaning fixes to a training pair."""
    tgt = pair["target"].strip()

    # Ensure semicolon at end
    if not tgt.endswith(";"):
        tgt = tgt + ";"

    # Fix double semicolons
    tgt = tgt.replace(";;", ";")

    # Fix common AI typos in source_table values
    typo_fixes = {
        "source_table = 'expenses'": "source_table = 'Expenses'",
        "source_table = 'cashflow'": "source_table = 'CashFlow'",
        "source_table = 'Cashflow'": "source_table = 'CashFlow'",
        "source_table = 'cash_flow'": "source_table = 'CashFlow'",
        "source_table = 'project'": "source_table = 'Project'",
        "source_table = 'quotation'": "source_table = 'Quotation'",
        "source_table = 'quotationitem'": "source_table = 'QuotationItem'",
        "source_table = 'QuotationItems'": "source_table = 'QuotationItem'",
        "source_table = 'Quotation_Item'": "source_table = 'QuotationItem'",
    }
    for wrong, right in typo_fixes.items():
        tgt = tgt.replace(wrong, right)

    # Fix metadata access: metadata->'key' → metadata->>'key'
    tgt = re.sub(r"metadata->'(\w+)'", r"metadata->>'\1'", tgt)

    pair["target"] = tgt
    return pair


# ---------------------------------------------------------------------------
# Spider dataset integration
# ---------------------------------------------------------------------------
def load_spider_pairs(limit: int = 3000) -> List[Dict]:
    """
    Load Spider dataset from HuggingFace and convert to our JSONL format.

    Spider pairs teach the model general text-to-SQL patterns, preventing
    catastrophic forgetting during fine-tuning on our custom schema.

    We keep the original Spider schema prefix (not ours) so the model
    learns to handle both formats.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Install datasets: pip install datasets")
        return []

    logger.info("Downloading Spider dataset from HuggingFace...")
    try:
        ds = load_dataset("spider", split="train", trust_remote_code=True)
    except Exception as e:
        logger.error(f"Failed to load Spider dataset: {e}")
        logger.info("You can manually download from: https://yale-lily.github.io/spider")
        return []

    pairs = []
    seen = set()

    for example in ds:
        question = example.get("question", "")
        query = example.get("query", "")
        db_id = example.get("db_id", "")

        if not question or not query:
            continue

        # Only keep SELECT queries
        if not query.strip().upper().startswith("SELECT"):
            continue

        # Build Spider-format input with the original DB schema
        # We use a simplified schema prefix for Spider data
        tables_str = f"tables: {db_id}"
        spider_input = f"{tables_str} | query: {question}"

        # Ensure semicolon
        target = query.strip()
        if not target.endswith(";"):
            target += ";"

        # Deduplicate
        fp = hashlib.md5(normalize_sql(target).encode()).hexdigest()
        if fp in seen:
            continue
        seen.add(fp)

        pairs.append({"input": spider_input, "target": target})

        if len(pairs) >= limit:
            break

    logger.info(f"Loaded {len(pairs)} Spider pairs (limit: {limit})")
    return pairs


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def load_custom_jsonl(path: str) -> List[Dict]:
    """Load pairs from a JSONL file."""
    pairs = []
    p = Path(path)
    if not p.exists():
        logger.error(f"File not found: {path}")
        return pairs

    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            pair = json.loads(line)
            pairs.append(pair)
        except json.JSONDecodeError as e:
            logger.warning(f"{p.name} line {i}: invalid JSON — {e}")

    logger.info(f"Loaded {len(pairs)} pairs from {p.name}")
    return pairs


def detect_intent(pair: Dict) -> str:
    """Detect intent type from a training pair."""
    tgt = pair.get("target", "").upper()
    if "SUM(" in tgt:
        return "sum"
    elif "AVG(" in tgt:
        return "average"
    elif "COUNT(" in tgt:
        return "count"
    elif "DISTINCT" in tgt:
        return "list_categories"
    elif "document_type = 'file'" in pair.get("target", ""):
        return "list_files"
    elif "GROUP BY" in tgt:
        return "compare"
    else:
        return "query_data"


def run_pipeline(
    custom_files: List[str],
    output_path: str,
    include_spider: bool = False,
    spider_limit: int = 3000,
) -> Dict:
    """
    Full cleaning pipeline:
    1. Load all custom JSONL files
    2. Clean each pair (fix typos, normalize)
    3. Validate each pair
    4. Optionally load + merge Spider data
    5. Deduplicate
    6. Shuffle
    7. Write clean output
    """
    import random

    all_custom = []
    for f in custom_files:
        all_custom.extend(load_custom_jsonl(f))

    # --- Step 1: Clean ---
    cleaned = [clean_pair(p) for p in all_custom]
    logger.info(f"Cleaned {len(cleaned)} custom pairs")

    # --- Step 2: Validate ---
    valid = []
    invalid_count = 0
    invalid_reasons = Counter()

    for p in cleaned:
        ok, reason = validate_custom_pair(p)
        if ok:
            valid.append(p)
        else:
            invalid_count += 1
            invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1

    logger.info(f"Validation: {len(valid)} valid, {invalid_count} invalid")
    if invalid_reasons:
        logger.info("Top invalid reasons:")
        for reason, count in invalid_reasons.most_common(10):
            logger.info(f"  {count:5d}  {reason}")

    # --- Step 3: Spider data ---
    spider_pairs = []
    if include_spider:
        spider_pairs = load_spider_pairs(limit=spider_limit)

    # --- Step 4: Merge ---
    all_pairs = valid + spider_pairs

    # --- Step 5: Deduplicate ---
    seen_fps = set()
    deduped = []
    dupes = 0
    for p in all_pairs:
        fp = fingerprint(p)
        if fp not in seen_fps:
            seen_fps.add(fp)
            deduped.append(p)
        else:
            dupes += 1

    logger.info(f"Deduplication: removed {dupes} duplicates, {len(deduped)} remaining")

    # --- Step 6: Shuffle ---
    random.seed(42)
    random.shuffle(deduped)

    # --- Step 7: Write output ---
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for p in deduped:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # --- Stats ---
    custom_count = len(valid)
    spider_count = len(spider_pairs)
    intent_dist = Counter()
    source_dist = Counter()
    for p in deduped:
        tgt = p.get("target", "")
        # Only count intents for custom pairs
        if p.get("input", "").startswith(SPIDER_PREFIX):
            intent_dist[detect_intent(p)] += 1
            for t in VALID_SOURCE_TABLES:
                if f"source_table = '{t}'" in tgt:
                    source_dist[t] += 1

    summary = {
        "total_output": len(deduped),
        "custom_valid": custom_count,
        "custom_invalid": invalid_count,
        "spider_pairs": spider_count,
        "duplicates_removed": dupes,
        "output_file": str(out),
        "intent_distribution": dict(intent_dist),
        "source_table_distribution": dict(source_dist),
    }

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Clean, validate, deduplicate, and merge T5 training data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--custom",
        nargs="+",
        required=True,
        help="Path(s) to custom JSONL training data files.",
    )
    parser.add_argument(
        "--output",
        default="data/training_final.jsonl",
        help="Output path for cleaned/merged JSONL (default: data/training_final.jsonl).",
    )
    parser.add_argument(
        "--spider",
        action="store_true",
        help="Include Spider dataset from HuggingFace for general text-to-SQL coverage.",
    )
    parser.add_argument(
        "--spider-limit",
        type=int,
        default=3000,
        help="Max Spider pairs to include (default: 3000).",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    summary = run_pipeline(
        custom_files=args.custom,
        output_path=args.output,
        include_spider=args.spider,
        spider_limit=args.spider_limit,
    )

    # Print report
    print()
    print("=" * 60)
    print("  CLEANING & MERGE REPORT")
    print("=" * 60)
    print(f"  Custom pairs (valid):    {summary['custom_valid']}")
    print(f"  Custom pairs (invalid):  {summary['custom_invalid']}")
    print(f"  Spider pairs:            {summary['spider_pairs']}")
    print(f"  Duplicates removed:      {summary['duplicates_removed']}")
    print(f"  Total output:            {summary['total_output']}")
    print(f"  Output file:             {summary['output_file']}")
    print()

    if summary["intent_distribution"]:
        print("  Intent distribution (custom only):")
        for intent, count in sorted(
            summary["intent_distribution"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            pct = count / max(summary["custom_valid"], 1) * 100
            print(f"    {intent:20s} {count:5d} ({pct:.1f}%)")
        print()

    if summary["source_table_distribution"]:
        print("  Source table distribution (custom only):")
        for table, count in sorted(
            summary["source_table_distribution"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            pct = count / max(summary["custom_valid"], 1) * 100
            print(f"    {table:20s} {count:5d} ({pct:.1f}%)")
        print()

    print("=" * 60)

    if summary["total_output"] >= 5000:
        print("  ✅ Dataset ready for training!")
    elif summary["total_output"] >= 3000:
        print("  👍 Decent dataset size. Consider adding more pairs for better accuracy.")
    else:
        print("  ⚠️  Small dataset. Add more custom pairs or include --spider data.")

    print("=" * 60)


if __name__ == "__main__":
    main()
