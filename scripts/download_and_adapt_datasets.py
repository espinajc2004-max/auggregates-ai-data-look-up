"""
Download & Adapt Public Text-to-SQL Datasets for AU-Ggregates T5
=================================================================
Downloads public text-to-SQL datasets from HuggingFace, evaluates them,
and adapts a subset to our ai_documents Spider format.

Strategy:
  1. Download candidate datasets from HuggingFace
  2. Evaluate each: size, quality, SQL patterns
  3. Adapt general text-to-SQL pairs → AU-Ggregates single-table schema
  4. Merge with existing t5_text2sql_5000_pairs.jsonl
  5. Output final training-ready JSONL

The adaptation remaps multi-table SQL to our single ai_documents table,
injecting JSONB metadata access patterns, source_table/document_type filters,
ILIKE matching, and ::numeric casts.

Usage:
    python scripts/download_and_adapt_datasets.py
    python scripts/download_and_adapt_datasets.py --output data/adapted_public.jsonl --limit 5000
    python scripts/download_and_adapt_datasets.py --evaluate-only
"""

import argparse
import json
import random
import re
import hashlib
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================
SPIDER_PREFIX = (
    "tables: ai_documents (id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type) | query: "
)

VALID_SOURCE_TABLES = ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]

NUMERIC_KEYS = {"Expenses", "Amount", "total_amount", "volume", "line_total"}

# Metadata keys per source table
SCHEMA = {
    "Expenses": ["Category", "Expenses", "Name"],
    "CashFlow": ["Type", "Amount", "Category"],
    "Project": ["project_name", "client_name", "location", "status"],
    "Quotation": ["quote_number", "status", "total_amount", "project_name"],
    "QuotationItem": [
        "plate_no", "dr_no", "material", "quarry_location",
        "truck_type", "volume", "line_total",
    ],
}

# HuggingFace datasets to try (ordered by priority)
DATASETS = [
    {
        "name": "b-mc2/sql-create-context",
        "description": "78k text-to-SQL pairs with CREATE TABLE context",
        "split": "train",
        "question_col": "question",
        "sql_col": "answer",
        "context_col": "context",
    },
    {
        "name": "Clinton/Text-to-sql-v1",
        "description": "Large text-to-SQL collection",
        "split": "train",
        "question_col": "instruction",
        "sql_col": "output",
        "context_col": "input",
    },
    {
        "name": "knowrohit07/know_sql",
        "description": "Curated SQL question-answer pairs",
        "split": "train",
        "question_col": "question",
        "sql_col": "answer",
        "context_col": "context",
    },
]


# ============================================================================
# REALISTIC ENTITY VALUES for adaptation
# ============================================================================
ENTITY_POOLS = {
    "project_names": [
        "SJDM Residences", "Francis Gays", "Manila Tower Phase 2",
        "Highway 5 Extension", "Building C Phase 2", "BGC Tower",
        "Quezon City Mall", "Makati Office", "Taguig Hub",
        "Cavite Housing Phase 1", "Laguna Logistics Park",
        "Bulacan Bypass Road", "Cebu Business Center",
        "Davao Depot Upgrade", "Iloilo Port Expansion",
        "Clark Green City", "Batangas Industrial Zone",
        "Pampanga Flood Control", "Rizal Provincial Road",
        "Alabang Complex", "Pasig Riverside", "Subic Bay Warehouse",
    ],
    "expense_categories": [
        "Fuel", "Labor", "Materials", "Equipment", "Food",
        "Transportation", "Office Supplies", "Cement", "Steel",
        "Sand", "Gravel", "Paint", "Electrical", "Plumbing",
        "Rental", "Safety Gear", "Tools", "Lumber", "Roofing",
    ],
    "cashflow_types": [
        "Income", "Expense", "Transfer", "Loan", "Payment",
        "Refund", "Advance", "Disbursement",
    ],
    "cashflow_categories": [
        "Client Payment", "Material Purchase", "Salary",
        "Loan Disbursement", "Equipment Rental",
        "Subcontractor Payment", "Tax Payment", "Insurance",
    ],
    "person_names": [
        "Juan Dela Cruz", "Maria Santos", "Pedro Cruz",
        "Jose Reyes", "Ana Garcia", "Carlos Mendoza",
        "Rosa Fernandez", "Miguel Torres", "Elena Ramos",
        "Roberto Villanueva", "Carmen Lopez", "Antonio Bautista",
    ],
    "client_names": [
        "DPWH", "Ayala Corp", "SM Prime Holdings", "Megaworld",
        "STI Construction", "ABC Corp", "XYZ Builders",
        "Metro Contractors", "JG Summit", "San Miguel Corp",
    ],
    "locations": [
        "Quezon City", "Makati", "Taguig", "Manila", "Pasig",
        "Cebu City", "Davao City", "Cavite", "Laguna", "Bulacan",
    ],
    "materials": [
        "Gravel", "Sand", "Washed Sand", "Crushed Rock",
        "Fill Material", "Boulders", "Limestone", "Aggregate",
    ],
    "quarry_locations": [
        "Montalban", "Teresa", "Angono", "San Mateo",
        "Rodriguez", "Tanay", "Antipolo", "Binangonan",
    ],
    "plate_numbers": [
        "ABC-1234", "XYZ-5678", "DEF-9012", "GHI-3456",
        "JKL-7890", "MNO-2345", "PQR-6789", "STU-0123",
    ],
    "dr_numbers": [
        "DR-001", "DR-002", "DR-003", "DR-2026-0042",
        "DR-1234", "DR-5001", "DR-100", "DR-2026-0100",
    ],
    "truck_types": [
        "6-Wheeler", "10-Wheeler", "Dump Truck", "Trailer",
        "Mini Dump", "Flatbed", "Mixer Truck",
    ],
    "quote_numbers": [
        "QT-2026-001", "QT-2026-002", "QT-0042", "Q-1234",
        "QT-2026-100", "QUO-2026-0001",
    ],
    "file_names": [
        "francis gays", "jc", "main expenses", "Q1 report",
        "site A costs", "monthly summary", "january expenses",
        "fuel log", "labor costs", "material purchases",
        "equipment rental", "petty cash", "payroll",
    ],
    "statuses_project": ["Active", "Completed", "On Hold", "Cancelled", "Pending"],
    "statuses_quotation": ["Draft", "Sent", "Approved", "Rejected", "Expired"],
}


# ============================================================================
# DATASET DOWNLOAD & EVALUATION
# ============================================================================
def download_dataset(ds_config: Dict) -> Optional[List[Dict]]:
    """Download a single HuggingFace dataset and extract question/SQL pairs."""
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("pip install datasets  — required for HuggingFace downloads")
        return None

    name = ds_config["name"]
    logger.info(f"Downloading {name}...")

    try:
        ds = load_dataset(name, split=ds_config["split"], trust_remote_code=True)
    except Exception as e:
        logger.warning(f"Failed to download {name}: {e}")
        return None

    pairs = []
    q_col = ds_config["question_col"]
    s_col = ds_config["sql_col"]

    for row in ds:
        question = row.get(q_col, "")
        sql = row.get(s_col, "")
        if question and sql:
            pairs.append({
                "question": str(question).strip(),
                "sql": str(sql).strip(),
                "source_dataset": name,
            })

    logger.info(f"  {name}: {len(pairs)} pairs extracted")
    return pairs


def evaluate_dataset(pairs: List[Dict], name: str) -> Dict:
    """Evaluate a downloaded dataset for quality and adaptability."""
    stats = {
        "name": name,
        "total": len(pairs),
        "select_only": 0,
        "has_aggregate": 0,
        "has_where": 0,
        "has_group_by": 0,
        "has_join": 0,
        "single_table": 0,
        "multi_table": 0,
        "avg_sql_length": 0,
        "avg_question_length": 0,
    }

    sql_lengths = []
    q_lengths = []

    for p in pairs:
        sql_upper = p["sql"].upper().strip()
        q = p["question"]

        if sql_upper.startswith("SELECT"):
            stats["select_only"] += 1
        if any(agg in sql_upper for agg in ["SUM(", "AVG(", "COUNT(", "MAX(", "MIN("]):
            stats["has_aggregate"] += 1
        if "WHERE" in sql_upper:
            stats["has_where"] += 1
        if "GROUP BY" in sql_upper:
            stats["has_group_by"] += 1
        if "JOIN" in sql_upper:
            stats["has_join"] += 1
            stats["multi_table"] += 1
        elif sql_upper.startswith("SELECT"):
            # Count FROM clauses to detect multi-table
            from_count = len(re.findall(r'\bFROM\b', sql_upper))
            comma_tables = sql_upper.split("FROM")[-1].split("WHERE")[0] if "FROM" in sql_upper else ""
            if "," in comma_tables.split("WHERE")[0].split("GROUP")[0].split("ORDER")[0]:
                stats["multi_table"] += 1
            else:
                stats["single_table"] += 1

        sql_lengths.append(len(p["sql"]))
        q_lengths.append(len(q))

    if sql_lengths:
        stats["avg_sql_length"] = sum(sql_lengths) / len(sql_lengths)
    if q_lengths:
        stats["avg_question_length"] = sum(q_lengths) / len(q_lengths)

    return stats


def print_evaluation(stats: Dict):
    """Print evaluation report for a dataset."""
    n = max(stats["total"], 1)
    print(f"\n{'='*55}")
    print(f"  {stats['name']}")
    print(f"{'='*55}")
    print(f"  Total pairs:       {stats['total']:,}")
    print(f"  SELECT only:       {stats['select_only']:,} ({stats['select_only']/n*100:.1f}%)")
    print(f"  Has WHERE:         {stats['has_where']:,} ({stats['has_where']/n*100:.1f}%)")
    print(f"  Has aggregates:    {stats['has_aggregate']:,} ({stats['has_aggregate']/n*100:.1f}%)")
    print(f"  Has GROUP BY:      {stats['has_group_by']:,} ({stats['has_group_by']/n*100:.1f}%)")
    print(f"  Single-table:      {stats['single_table']:,} ({stats['single_table']/n*100:.1f}%)")
    print(f"  Multi-table/JOIN:  {stats['multi_table']:,} ({stats['multi_table']/n*100:.1f}%)")
    print(f"  Avg SQL length:    {stats['avg_sql_length']:.0f} chars")
    print(f"  Avg question len:  {stats['avg_question_length']:.0f} chars")

    # Adaptability score
    select_pct = stats["select_only"] / n
    single_pct = stats["single_table"] / n
    where_pct = stats["has_where"] / n
    score = (select_pct * 30 + single_pct * 30 + where_pct * 20 + min(stats["has_aggregate"]/n, 0.3)/0.3 * 20)
    print(f"  Adaptability:      {score:.0f}/100")
    print(f"{'='*55}")

    return score



# ============================================================================
# ADAPTATION ENGINE — remap general SQL to AU-Ggregates schema
# ============================================================================

# SQL pattern classifiers
AGG_PATTERNS = {
    "sum": re.compile(r'\bSUM\s*\(', re.IGNORECASE),
    "avg": re.compile(r'\bAVG\s*\(', re.IGNORECASE),
    "count": re.compile(r'\bCOUNT\s*\(', re.IGNORECASE),
    "max": re.compile(r'\bMAX\s*\(', re.IGNORECASE),
    "min": re.compile(r'\bMIN\s*\(', re.IGNORECASE),
}

# Question pattern classifiers for intent detection
INTENT_PATTERNS = {
    "sum": [
        r'\btotal\b', r'\bsum\b', r'\bhow much\b', r'\badd up\b',
        r'\bcombined\b', r'\baggregate\b',
    ],
    "count": [
        r'\bhow many\b', r'\bcount\b', r'\bnumber of\b', r'\btotal number\b',
    ],
    "average": [
        r'\baverage\b', r'\bavg\b', r'\bmean\b',
    ],
    "list_files": [
        r'\blist.*files?\b', r'\bshow.*files?\b', r'\bwhat files?\b',
        r'\bdocuments?\b', r'\bavailable files?\b',
    ],
    "list_categories": [
        r'\bdistinct\b', r'\bunique\b', r'\bcategories\b', r'\btypes of\b',
        r'\blist all\b.*\btypes\b', r'\bwhat.*kinds\b',
    ],
    "compare": [
        r'\bcompare\b', r'\bvs\b', r'\bversus\b', r'\bdifference\b',
        r'\bbreakdown\b', r'\bby\b.*\bgroup\b',
    ],
}


def classify_intent(question: str, sql: str) -> str:
    """Classify the intent of a question/SQL pair."""
    q_lower = question.lower()
    sql_upper = sql.upper()

    # Check SQL patterns first (more reliable)
    if AGG_PATTERNS["sum"].search(sql):
        return "sum"
    if AGG_PATTERNS["avg"].search(sql):
        return "average"
    if AGG_PATTERNS["count"].search(sql):
        return "count"
    if "DISTINCT" in sql_upper and "GROUP BY" not in sql_upper:
        return "list_categories"
    if "GROUP BY" in sql_upper:
        return "compare"

    # Fall back to question patterns
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q_lower):
                return intent

    return "query_data"


def pick_source_table_for_intent(intent: str) -> Tuple[str, str]:
    """Pick a source_table and document_type appropriate for the intent."""
    if intent == "list_files":
        table = random.choice(VALID_SOURCE_TABLES)
        return table, "file"

    # Weight towards Expenses/CashFlow for numeric intents
    if intent in ("sum", "average"):
        weights = [0.40, 0.30, 0.0, 0.15, 0.15]
    elif intent == "count":
        weights = [0.30, 0.20, 0.15, 0.15, 0.20]
    else:
        weights = [0.35, 0.25, 0.15, 0.15, 0.10]

    table = random.choices(VALID_SOURCE_TABLES, weights=weights, k=1)[0]
    return table, "row"


def pick_metadata_key(source_table: str, need_numeric: bool = False) -> str:
    """Pick a metadata key for the given source table."""
    keys = SCHEMA[source_table]
    if need_numeric:
        numeric_in_table = [k for k in keys if k in NUMERIC_KEYS]
        if numeric_in_table:
            return random.choice(numeric_in_table)
    return random.choice(keys)


def pick_entity_value(source_table: str, key: str) -> str:
    """Pick a realistic entity value for a given source_table + key."""
    pool_map = {
        ("Expenses", "Category"): "expense_categories",
        ("Expenses", "Name"): "person_names",
        ("CashFlow", "Type"): "cashflow_types",
        ("CashFlow", "Category"): "cashflow_categories",
        ("Project", "project_name"): "project_names",
        ("Project", "client_name"): "client_names",
        ("Project", "location"): "locations",
        ("Project", "status"): "statuses_project",
        ("Quotation", "quote_number"): "quote_numbers",
        ("Quotation", "status"): "statuses_quotation",
        ("Quotation", "total_amount"): None,  # numeric
        ("Quotation", "project_name"): "project_names",
        ("QuotationItem", "plate_no"): "plate_numbers",
        ("QuotationItem", "dr_no"): "dr_numbers",
        ("QuotationItem", "material"): "materials",
        ("QuotationItem", "quarry_location"): "quarry_locations",
        ("QuotationItem", "truck_type"): "truck_types",
        ("QuotationItem", "volume"): None,  # numeric
        ("QuotationItem", "line_total"): None,  # numeric
    }

    pool_name = pool_map.get((source_table, key))
    if pool_name and pool_name in ENTITY_POOLS:
        return random.choice(ENTITY_POOLS[pool_name])

    # Numeric value
    if key in NUMERIC_KEYS:
        return str(random.choice([500, 1000, 2500, 5000, 10000, 25000, 50000]))

    return "sample value"


def adapt_pair(question: str, sql: str) -> Optional[Dict]:
    """
    Adapt a general text-to-SQL pair to AU-Ggregates format.

    This is the core adaptation logic. It:
    1. Classifies the intent
    2. Picks appropriate source_table + document_type
    3. Generates a new SQL using our schema patterns
    4. Rewrites the question to fit our domain

    Returns None if the pair can't be meaningfully adapted.
    """
    intent = classify_intent(question, sql)
    source_table, doc_type = pick_source_table_for_intent(intent)

    # Build the adapted SQL
    if intent == "list_files":
        adapted_sql = (
            f"SELECT id, file_name, project_name FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'file'"
        )
        # Maybe add project filter
        if random.random() < 0.4:
            proj = random.choice(ENTITY_POOLS["project_names"])
            adapted_sql += f" AND project_name ILIKE '%{proj.lower()}%'"
        adapted_sql += " ORDER BY file_name;"

        adapted_q = _rewrite_question_list_files(question, source_table)

    elif intent == "count":
        key = pick_metadata_key(source_table)
        val = pick_entity_value(source_table, key)

        adapted_sql = (
            f"SELECT COUNT(*) AS count FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'row'"
        )
        if key not in NUMERIC_KEYS and random.random() < 0.7:
            adapted_sql += f" AND metadata->>'{key}' ILIKE '%{val.lower()}%'"

        adapted_sql += ";"
        adapted_q = _rewrite_question_count(question, source_table, key, val)

    elif intent == "sum":
        num_key = pick_metadata_key(source_table, need_numeric=True)
        filter_key = pick_metadata_key(source_table, need_numeric=False)
        filter_val = pick_entity_value(source_table, filter_key)

        adapted_sql = (
            f"SELECT SUM((metadata->>'{num_key}')::numeric) AS total "
            f"FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'row'"
        )
        if filter_key != num_key and filter_key not in NUMERIC_KEYS and random.random() < 0.6:
            adapted_sql += f" AND metadata->>'{filter_key}' ILIKE '%{filter_val.lower()}%'"

        # Maybe add project filter
        if random.random() < 0.3:
            proj = random.choice(ENTITY_POOLS["project_names"])
            adapted_sql += f" AND project_name ILIKE '%{proj.lower()}%'"

        adapted_sql += ";"
        adapted_q = _rewrite_question_sum(question, source_table, num_key, filter_key, filter_val)

    elif intent == "average":
        num_key = pick_metadata_key(source_table, need_numeric=True)

        adapted_sql = (
            f"SELECT AVG((metadata->>'{num_key}')::numeric) AS average "
            f"FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'row'"
        )
        if random.random() < 0.4:
            filter_key = pick_metadata_key(source_table, need_numeric=False)
            if filter_key != num_key and filter_key not in NUMERIC_KEYS:
                filter_val = pick_entity_value(source_table, filter_key)
                adapted_sql += f" AND metadata->>'{filter_key}' ILIKE '%{filter_val.lower()}%'"

        adapted_sql += ";"
        adapted_q = _rewrite_question_avg(question, source_table, num_key)

    elif intent == "list_categories":
        key = pick_metadata_key(source_table, need_numeric=False)
        if key in NUMERIC_KEYS:
            key = pick_metadata_key(source_table, need_numeric=False)

        adapted_sql = (
            f"SELECT DISTINCT metadata->>'{key}' AS {key.lower().replace(' ', '_')} "
            f"FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'row' "
            f"ORDER BY {key.lower().replace(' ', '_')};"
        )
        adapted_q = _rewrite_question_distinct(question, source_table, key)

    elif intent == "compare":
        num_key = pick_metadata_key(source_table, need_numeric=True)
        group_key = pick_metadata_key(source_table, need_numeric=False)
        if group_key == num_key or group_key in NUMERIC_KEYS:
            # Pick a different non-numeric key
            non_numeric = [k for k in SCHEMA[source_table] if k not in NUMERIC_KEYS]
            if non_numeric:
                group_key = random.choice(non_numeric)
            else:
                group_key = "project_name"  # fallback to regular column

        if group_key in ["project_name", "file_name", "source_table"]:
            # Regular column
            adapted_sql = (
                f"SELECT {group_key}, SUM((metadata->>'{num_key}')::numeric) AS total "
                f"FROM ai_documents "
                f"WHERE source_table = '{source_table}' AND document_type = 'row' "
                f"GROUP BY {group_key} ORDER BY total DESC;"
            )
        else:
            adapted_sql = (
                f"SELECT metadata->>'{group_key}' AS {group_key.lower()}, "
                f"SUM((metadata->>'{num_key}')::numeric) AS total "
                f"FROM ai_documents "
                f"WHERE source_table = '{source_table}' AND document_type = 'row' "
                f"GROUP BY {group_key.lower()} ORDER BY total DESC;"
            )
        adapted_q = _rewrite_question_compare(question, source_table, num_key, group_key)

    else:  # query_data
        keys = SCHEMA[source_table]
        select_keys = random.sample(keys, min(random.randint(2, 4), len(keys)))
        select_parts = []
        for k in select_keys:
            select_parts.append(f"metadata->>'{k}' AS {k.lower().replace(' ', '_')}")

        adapted_sql = (
            f"SELECT {', '.join(select_parts)} FROM ai_documents "
            f"WHERE source_table = '{source_table}' AND document_type = 'row'"
        )

        # Add 1-2 filters
        filter_keys = [k for k in keys if k not in NUMERIC_KEYS]
        if filter_keys and random.random() < 0.7:
            fk = random.choice(filter_keys)
            fv = pick_entity_value(source_table, fk)
            adapted_sql += f" AND metadata->>'{fk}' ILIKE '%{fv.lower()}%'"

        if random.random() < 0.3:
            proj = random.choice(ENTITY_POOLS["project_names"])
            adapted_sql += f" AND project_name ILIKE '%{proj.lower()}%'"

        adapted_sql += " LIMIT 25;"
        adapted_q = _rewrite_question_query(question, source_table, select_keys)

    # Build final pair
    adapted_input = SPIDER_PREFIX + adapted_q
    return {"input": adapted_input, "target": adapted_sql}



# ============================================================================
# QUESTION REWRITING — make questions sound natural for our domain
# ============================================================================

# Phrasing templates per intent
_LIST_FILES_TEMPLATES = [
    "show all {table} files",
    "list {table} documents",
    "what {table} files are available",
    "display all {table} file records",
    "show me the {table} files",
    "get all {table} files",
    "what files do we have for {table}",
    "pull up {table} files",
    "retrieve {table} file list",
    "find all {table} documents",
]

_COUNT_TEMPLATES = [
    "how many {table} entries have {key} as {val}",
    "count {table} records where {key} is {val}",
    "how many {table} rows with {key} {val}",
    "total number of {table} entries for {key} {val}",
    "count of {val} in {table}",
    "how many {val} records in {table}",
    "number of {table} entries with {val} {key}",
]

_SUM_TEMPLATES = [
    "total {num_key} for {table}",
    "what is the total {num_key} in {table}",
    "how much {num_key} for {filter_val} in {table}",
    "sum of {num_key} for {table} {filter_key} {filter_val}",
    "calculate total {num_key} in {table}",
    "add up all {num_key} for {filter_val}",
    "give me the total {table} {num_key}",
    "what's the sum of {num_key} for {filter_val}",
    "total {table} {num_key} for {filter_val}",
]

_AVG_TEMPLATES = [
    "average {num_key} for {table}",
    "what is the average {num_key} in {table}",
    "mean {num_key} across {table} records",
    "avg {table} {num_key}",
    "what's the average {num_key} for {table}",
]

_DISTINCT_TEMPLATES = [
    "list all {key} values in {table}",
    "what are the distinct {key} in {table}",
    "show unique {key} for {table}",
    "what {key} types exist in {table}",
    "list all unique {key} in {table} records",
    "get distinct {key} from {table}",
]

_COMPARE_TEMPLATES = [
    "compare {num_key} by {group_key} in {table}",
    "breakdown of {num_key} per {group_key} for {table}",
    "{table} {num_key} grouped by {group_key}",
    "show {num_key} by {group_key} in {table}",
    "total {num_key} per {group_key} for {table}",
]

_QUERY_TEMPLATES = [
    "show {table} data for {keys}",
    "get {table} records with {keys}",
    "display {table} {keys}",
    "retrieve {keys} from {table}",
    "pull up {table} {keys} data",
    "find {table} entries showing {keys}",
    "what are the {keys} in {table}",
    "show me {table} {keys}",
]


def _friendly_table(table: str) -> str:
    """Make source_table name more natural in questions."""
    mapping = {
        "Expenses": random.choice(["expense", "expenses", "cost"]),
        "CashFlow": random.choice(["cash flow", "cashflow", "cash"]),
        "Project": random.choice(["project", "projects"]),
        "Quotation": random.choice(["quotation", "quote"]),
        "QuotationItem": random.choice(["delivery", "deliveries", "line item"]),
    }
    return mapping.get(table, table.lower())


def _friendly_key(key: str) -> str:
    """Make metadata key name more natural."""
    mapping = {
        "Expenses": "amount",
        "Amount": "amount",
        "total_amount": "total amount",
        "volume": "volume",
        "line_total": "line total",
        "Category": "category",
        "Name": "name",
        "Type": "type",
        "project_name": "project name",
        "client_name": "client",
        "location": "location",
        "status": "status",
        "quote_number": "quote number",
        "plate_no": "plate number",
        "dr_no": "DR number",
        "material": "material",
        "quarry_location": "quarry",
        "truck_type": "truck type",
    }
    return mapping.get(key, key.lower().replace("_", " "))


def _rewrite_question_list_files(orig: str, table: str) -> str:
    t = random.choice(_LIST_FILES_TEMPLATES)
    return t.format(table=_friendly_table(table))


def _rewrite_question_count(orig: str, table: str, key: str, val: str) -> str:
    t = random.choice(_COUNT_TEMPLATES)
    return t.format(table=_friendly_table(table), key=_friendly_key(key), val=val)


def _rewrite_question_sum(orig: str, table: str, num_key: str,
                          filter_key: str, filter_val: str) -> str:
    t = random.choice(_SUM_TEMPLATES)
    return t.format(
        table=_friendly_table(table),
        num_key=_friendly_key(num_key),
        filter_key=_friendly_key(filter_key),
        filter_val=filter_val,
    )


def _rewrite_question_avg(orig: str, table: str, num_key: str) -> str:
    t = random.choice(_AVG_TEMPLATES)
    return t.format(table=_friendly_table(table), num_key=_friendly_key(num_key))


def _rewrite_question_distinct(orig: str, table: str, key: str) -> str:
    t = random.choice(_DISTINCT_TEMPLATES)
    return t.format(table=_friendly_table(table), key=_friendly_key(key))


def _rewrite_question_compare(orig: str, table: str, num_key: str, group_key: str) -> str:
    t = random.choice(_COMPARE_TEMPLATES)
    return t.format(
        table=_friendly_table(table),
        num_key=_friendly_key(num_key),
        group_key=_friendly_key(group_key),
    )


def _rewrite_question_query(orig: str, table: str, keys: List[str]) -> str:
    t = random.choice(_QUERY_TEMPLATES)
    friendly_keys = ", ".join(_friendly_key(k) for k in keys[:3])
    return t.format(table=_friendly_table(table), keys=friendly_keys)

