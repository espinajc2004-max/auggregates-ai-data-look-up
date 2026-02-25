"""
Training Data Validation Script
================================
Validates AI-generated JSONL training data before T5 fine-tuning.
Checks SQL validity, table references, SELECT-only, and Spider format.

Usage:
    python scripts/validate_training_data.py --input data/training_data.jsonl --output data/training_data_validated.jsonl
"""

import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sqlparse

# Spider schema prefix expected in every training pair input
SPIDER_PREFIX = (
    "tables: ai_documents (id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type) | query: "
)

# SQL statement types that are NOT allowed (only SELECT is allowed)
DISALLOWED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"}

# The only table allowed in target SQL
ALLOWED_TABLE = "ai_documents"

logger = logging.getLogger(__name__)


def _extract_tables(parsed: sqlparse.sql.Statement) -> List[str]:
    """Extract table names referenced in a parsed SQL statement."""
    tables = []
    from_seen = False
    join_seen = False

    for token in parsed.tokens:
        if token.ttype is sqlparse.tokens.Keyword:
            upper = token.value.upper()
            if upper == "FROM":
                from_seen = True
                join_seen = False
            elif "JOIN" in upper:
                join_seen = True
                from_seen = False
            else:
                from_seen = False
                join_seen = False
        elif from_seen or join_seen:
            if token.ttype is sqlparse.tokens.Name or token.ttype is sqlparse.tokens.Keyword:
                tables.append(token.value.strip().lower())
                from_seen = False
                join_seen = False
            elif hasattr(token, "get_name") and token.get_name():
                tables.append(token.get_name().strip().lower())
                from_seen = False
                join_seen = False

    return tables


def _extract_tables_regex(sql: str) -> List[str]:
    """Fallback regex-based table extraction from SQL."""
    tables = []
    # Match FROM <table> and JOIN <table>
    for match in re.finditer(r'\bFROM\s+(\w+)', sql, re.IGNORECASE):
        tables.append(match.group(1).lower())
    for match in re.finditer(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE):
        tables.append(match.group(1).lower())
    return tables


def validate_training_pair(pair: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate a single training pair.

    Checks:
    - Target SQL parses via sqlparse
    - Target SQL is a single SELECT statement (no INSERT/UPDATE/DELETE/DROP)
    - Target SQL references only the ai_documents table
    - Input field starts with the Spider schema prefix
    - Input field contains a non-empty query after the prefix

    Args:
        pair: Dict with 'input' and 'target' keys.

    Returns:
        Tuple of (is_valid, reason_if_invalid).
    """
    # Check required keys
    if "input" not in pair or "target" not in pair:
        return False, "missing 'input' or 'target' key"

    input_text = pair["input"]
    target_sql = pair["target"]

    # Check input uses Spider format prefix
    if not input_text.startswith(SPIDER_PREFIX):
        return False, "input does not start with Spider schema prefix"

    # Check non-empty query after prefix
    query_part = input_text[len(SPIDER_PREFIX):].strip()
    if not query_part:
        return False, "input has empty query after Spider prefix"

    # Check target SQL is non-empty
    if not target_sql or not target_sql.strip():
        return False, "target SQL is empty"

    # Parse target SQL
    try:
        parsed_statements = sqlparse.parse(target_sql)
    except Exception as e:
        return False, f"SQL parse error: {e}"

    if not parsed_statements:
        return False, "SQL parsed to zero statements"

    # Check it's a single statement
    # Filter out empty/whitespace-only statements
    non_empty = [s for s in parsed_statements if s.tokens and str(s).strip()]
    if len(non_empty) != 1:
        return False, f"expected 1 SQL statement, found {len(non_empty)}"

    stmt = non_empty[0]
    stmt_type = stmt.get_type()

    # Check SELECT-only (no write operations)
    if stmt_type and stmt_type.upper() != "SELECT":
        return False, f"SQL is {stmt_type}, not SELECT"

    # Also check for disallowed keywords at the statement level
    sql_upper = target_sql.upper().strip()
    first_keyword = sql_upper.split()[0] if sql_upper.split() else ""
    if first_keyword in DISALLOWED_KEYWORDS:
        return False, f"SQL starts with disallowed keyword: {first_keyword}"

    # Check table references — only ai_documents allowed
    tables = _extract_tables(stmt)
    if not tables:
        tables = _extract_tables_regex(target_sql)

    for table in tables:
        if table != ALLOWED_TABLE:
            return False, f"SQL references disallowed table: '{table}'"

    return True, None


def _detect_intent_type(pair: Dict) -> str:
    """Heuristically detect intent type from a training pair for summary stats."""
    query = pair.get("input", "")[len(SPIDER_PREFIX):].lower().strip()
    target = pair.get("target", "").upper()

    if "document_type = 'file'" in pair.get("target", "") or "document_type='file'" in pair.get("target", ""):
        return "list_files"
    if "SUM(" in target:
        return "sum"
    if "COUNT(" in target:
        return "count"
    if "AVG(" in target:
        return "average"
    if "DISTINCT" in target and ("category" in query or "categories" in query or "DISTINCT" in target):
        return "list_categories"

    # Check for date filtering
    date_keywords = ["date", "month", "year", "january", "february", "march", "april",
                     "may", "june", "july", "august", "september", "october", "november", "december"]
    if any(kw in query for kw in date_keywords) and ("Date" in pair.get("target", "") or "date" in pair.get("target", "")):
        return "date_filter"

    # Check for comparison
    compare_keywords = ["compare", "difference", "versus", "vs", "between"]
    if any(kw in query for kw in compare_keywords):
        return "compare"

    return "query_data"


def validate_jsonl(input_path: str, output_path: str) -> Dict:
    """
    Read JSONL, validate each pair, write valid pairs to output, return summary stats.

    Args:
        input_path: Path to input JSONL file.
        output_path: Path to write validated JSONL output.

    Returns:
        Summary dict with total_checked, total_valid, total_invalid, by_intent_type.
    """
    input_file = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        logger.error(f"Input file not found: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")

    total_checked = 0
    total_valid = 0
    total_invalid = 0
    by_intent_type: Dict[str, int] = {}
    valid_pairs: List[Dict] = []

    lines = input_file.read_text(encoding="utf-8").splitlines()

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        total_checked += 1

        # Parse JSON
        try:
            pair = json.loads(line)
        except json.JSONDecodeError as e:
            total_invalid += 1
            logger.warning(f"Line {line_num}: invalid JSON — {e}")
            continue

        # Validate the pair
        is_valid, reason = validate_training_pair(pair)

        if is_valid:
            total_valid += 1
            valid_pairs.append(pair)

            # Track intent type
            intent = _detect_intent_type(pair)
            by_intent_type[intent] = by_intent_type.get(intent, 0) + 1
        else:
            total_invalid += 1
            logger.warning(f"Line {line_num}: {reason}")

    # Write valid pairs to output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        for pair in valid_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Warn if output count is low
    if total_valid < 1000:
        logger.warning(
            f"Only {total_valid} valid pairs after validation (recommended: 1,000+)"
        )

    summary = {
        "total_checked": total_checked,
        "total_valid": total_valid,
        "total_invalid": total_invalid,
        "by_intent_type": by_intent_type,
    }

    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate AI-generated JSONL training data for T5 fine-tuning."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input JSONL file (e.g., data/training_data.jsonl)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output validated JSONL file (e.g., data/training_data_validated.jsonl)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    print(f"\n🔍 Validating: {args.input}")
    print("=" * 60)

    try:
        summary = validate_jsonl(args.input, args.output)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    # Print summary
    print(f"\n📊 Validation Summary")
    print("-" * 40)
    print(f"  Total checked:  {summary['total_checked']}")
    print(f"  Valid:          {summary['total_valid']}")
    print(f"  Invalid:        {summary['total_invalid']}")

    if summary["by_intent_type"]:
        print(f"\n📂 Breakdown by Intent Type")
        print("-" * 40)
        for intent, count in sorted(summary["by_intent_type"].items()):
            print(f"  {intent:20s} {count}")

    print("=" * 60)

    if summary["total_invalid"] == 0:
        print(f"✅ All {summary['total_valid']} pairs valid → {args.output}")
    else:
        print(
            f"⚠️  {summary['total_invalid']} invalid pairs excluded → "
            f"{summary['total_valid']} valid pairs written to {args.output}"
        )


if __name__ == "__main__":
    main()
