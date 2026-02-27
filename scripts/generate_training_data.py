"""
Training Dataset Generator for AU-Ggregates AI
================================================
Generates JSONL training examples based on real bugs found in production.
English only. Covers 6 bug categories with diverse phrasing variations,
plus training pairs for all 5 source tables (Expenses, CashFlow, Project,
Quotation, QuotationItem).

Schema Reference (from SchemaRegistry GLOBAL_SCHEMA):
  Expenses:      Category, Expenses, Name
  CashFlow:      Type, Amount, Category
  Project:       project_name, client_name, location, status
  Quotation:     quote_number, status, total_amount, project_name
  QuotationItem: plate_no, dr_no, material, quarry_location, truck_type, volume, line_total

Numeric keys (need ::numeric casting): Expenses, Amount, total_amount, volume, line_total

Usage:
    python scripts/generate_training_data.py
    python scripts/generate_training_data.py --output data/training.jsonl --count 3000
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Dict

# ============================================================================
# REAL DATA FROM PRODUCTION (pulled directly from Supabase)
# ============================================================================

# Real file names from ai_documents.file_name
FILE_NAMES = [
    "francis gays", "jc", "jash gay", "TEST",
    "QUO-2026-0001", "QUO-2026-0002", "QUO-2026-0003",
    "QUO-2026-0004", "QUO-2026-0005", "QUO-2026-0006",
]

# Real project names from ai_documents.project_name
PROJECTS = ["TEST", "STI construction", "Natours-official", "Auggregates-db"]

# Real source tables in ai_documents
SOURCE_TABLES = ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]

# Real metadata keys found in Expenses rows: Category, Expenses, Name
# Real metadata keys found in CashFlow rows: Type, Amount, Category
# Real metadata keys found in Project rows: project_name, client_name, location, status
# Real metadata keys found in Quotation rows: quote_number, status, total_amount, project_name
# Real metadata keys found in QuotationItem rows: plate_no, dr_no, material, quarry_location, truck_type, volume, line_total
EXPENSE_CATEGORIES = ["fuel", "food", "car"]       # from real data
CASHFLOW_CATEGORIES = ["car"]                       # from real data
ALL_CATEGORIES = ["fuel", "food", "car", "labor", "cement", "steel", "sand", "gravel"]

# Real quotation numbers
QUOTATION_NUMBERS = [
    "QUO-2026-0001", "QUO-2026-0002", "QUO-2026-0003",
    "QUO-2026-0004", "QUO-2026-0005", "QUO-2026-0006",
]

# Real materials from QuotationItem
MATERIALS = ["Washed Sand", "Gravel", "Crushed Stone", "Fill Soil"]

# Real statuses for Projects and Quotations
PROJECT_STATUSES = ["active", "completed", "pending", "on hold"]
QUOTATION_STATUSES = ["draft", "sent", "approved", "rejected"]

# Real locations
LOCATIONS = ["Manila", "Quezon City", "Makati", "Cebu", "Davao"]

# Real client names
CLIENT_NAMES = ["STI construction", "ABC Corp", "XYZ Builders", "Metro Contractors"]

# Real plate numbers
PLATE_NUMBERS = ["ABC-123", "XYZ-456", "DEF-789", "GHI-012"]

# Real DR numbers
DR_NUMBERS = ["DR-001", "DR-002", "DR-003", "DR-004", "DR-005"]

# Real truck types
TRUCK_TYPES = ["6-wheeler", "10-wheeler", "dump truck", "trailer"]

# Real quarry locations
QUARRY_LOCATIONS = ["Montalban", "Teresa", "Angono", "San Mateo"]

# ============================================================================
# ENGLISH VERB VARIATIONS
# ============================================================================
SHOW_VERBS = [
    "show", "display", "get", "retrieve", "open", "view",
    "show me", "get me", "let me see", "pull up", "bring up"
]
FIND_VERBS = [
    "find", "search", "look for", "search for", "locate",
    "find me", "search for", "look up", "get"
]
COUNT_VERBS = [
    "count", "count all", "how many", "give me the count of",
    "tell me how many", "what is the count of", "count the number of"
]
COMPARE_VERBS = [
    "compare", "compare the expenses between", "show the difference between",
    "what is the difference between", "contrast", "compare expenses for"
]
LIST_VERBS = [
    "list", "list all", "show all", "get all", "what are the",
    "give me all", "display all", "enumerate"
]


# ============================================================================
# BUG #1: ROOT vs CHILD DATA
# "show francis gays" → should return ONLY the file summary (1 result)
# NOT all child rows
# ============================================================================
def gen_file_level_queries() -> List[Dict]:
    examples = []
    # Real schema: document_type='file' rows have metadata: {type, file_name, description, project_name}
    sql_template = "SELECT file_name, metadata->>'description' as description, metadata->>'project_name' as project FROM ai_documents WHERE file_name ILIKE '%{file}%' AND document_type = 'file' LIMIT 1;"
    for file in FILE_NAMES:
        for verb in SHOW_VERBS:
            examples.append({
                "instruction": f"{verb} {file}",
                "input": "",
                "output": json.dumps({
                    "intent": "get_file_summary",
                    "scope": "file",
                    "slots": {"file_name": file},
                    "needs_clarification": False,
                    "sql": sql_template.format(file=file)
                })
            })
        extras = [
            f"open the {file} file",
            f"what is in {file}",
            f"give me the summary of {file}",
            f"show the {file} expense file",
            f"I want to see {file}",
            f"pull up {file}",
            f"show details for {file}",
        ]
        for phrase in extras:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "get_file_summary",
                    "scope": "file",
                    "slots": {"file_name": file},
                    "needs_clarification": False,
                    "sql": sql_template.format(file=file)
                })
            })
    return examples


# ============================================================================
# BUG #2: AMBIGUOUS QUERY → needs clarification
# "show me the fuel" → found in multiple files → ask which one
# ============================================================================
def gen_ambiguous_clarification_queries() -> List[Dict]:
    examples = []

    # Vague queries with no file specified
    for cat in ALL_CATEGORIES:
        for verb in FIND_VERBS + SHOW_VERBS:
            examples.append({
                "instruction": f"{verb} {cat}",
                "input": "",
                "output": json.dumps({
                    "intent": "find_category",
                    "scope": "row",
                    "slots": {"category": cat, "file_name": None, "source_table": "Expenses"},
                    "needs_clarification": True,
                    "clarify_slot": "file_name",
                    "clarification_question": f"I found '{cat}' in multiple files. Which file are you looking for? Please specify the file name.",
                    "sql": f"SELECT file_name, COUNT(*) as count FROM ai_documents WHERE metadata->>'Category' ILIKE '%{cat}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 GROUP BY file_name;"
                })
            })
        extras = [
            f"where is the {cat}",
            f"I need the {cat} data",
            f"can you find {cat} for me",
            f"look up {cat}",
            f"what {cat} do we have",
        ]
        for phrase in extras:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "find_category",
                    "scope": "row",
                    "slots": {"category": cat, "file_name": None, "source_table": "Expenses"},
                    "needs_clarification": True,
                    "clarify_slot": "file_name",
                    "clarification_question": f"I found '{cat}' in multiple files. Which file are you looking for?",
                    "sql": f"SELECT file_name, COUNT(*) as count FROM ai_documents WHERE metadata->>'Category' ILIKE '%{cat}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 GROUP BY file_name;"
                })
            })

    # After clarification — user specifies the file
    for cat in ALL_CATEGORIES:
        for file in FILE_NAMES[:5]:
            phrasings = [
                f"show me {cat} in {file}",
                f"find {cat} in {file}",
                f"get {cat} from {file}",
                f"show {cat} entries in {file}",
                f"look for {cat} inside {file}",
                f"help me find the {cat} in {file}",
                f"search {cat} in {file}",
            ]
            for phrase in phrasings:
                examples.append({
                    "instruction": phrase,
                    "input": "",
                    "output": json.dumps({
                        "intent": "find_category_in_file",
                        "scope": "row",
                        "slots": {"category": cat, "file_name": file, "source_table": "Expenses"},
                        "needs_clarification": False,
                        "sql": f"SELECT * FROM ai_documents WHERE metadata->>'Category' ILIKE '%{cat}%' AND file_name ILIKE '%{file}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                    })
                })
    return examples


# ============================================================================
# BUG #3: DATE PARSING
# "count all expenses in february" → understand month names
# Uses user_date column (not metadata key) for date filtering
# ============================================================================
MONTHS = {
    "january":   ("01", "01", "31"),
    "february":  ("02", "01", "28"),
    "march":     ("03", "01", "31"),
    "april":     ("04", "01", "30"),
    "may":       ("05", "01", "31"),
    "june":      ("06", "01", "30"),
    "july":      ("07", "01", "31"),
    "august":    ("08", "01", "31"),
    "september": ("09", "01", "30"),
    "october":   ("10", "01", "31"),
    "november":  ("11", "01", "30"),
    "december":  ("12", "01", "31"),
}

def gen_date_queries() -> List[Dict]:
    examples = []
    year = "2026"

    for month_name, (month_num, day_start, day_end) in MONTHS.items():
        date_start = f"{year}-{month_num}-{day_start}"
        date_end = f"{year}-{month_num}-{day_end}"

        # Count with month name
        count_phrasings = [
            f"count all expenses in {month_name}",
            f"how many expenses in {month_name}",
            f"count the expenses for {month_name}",
            f"give me the count of expenses in {month_name}",
            f"how many entries are there in {month_name}",
            f"total count of expenses in {month_name}",
        ]
        for phrase in count_phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "count_with_date_filter",
                    "scope": "summary",
                    "slots": {"date_range": month_name, "date_start": date_start, "date_end": date_end, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT COUNT(*) as count FROM ai_documents WHERE user_date >= '{date_start}' AND user_date <= '{date_end}' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                })
            })

        # Show with month name
        show_phrasings = [
            f"show expenses in {month_name}",
            f"get all expenses for {month_name}",
            f"display {month_name} expenses",
            f"list expenses from {month_name}",
            f"find all entries in {month_name}",
        ]
        for phrase in show_phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "filter_by_date",
                    "scope": "row",
                    "slots": {"date_range": month_name, "date_start": date_start, "date_end": date_end, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT * FROM ai_documents WHERE user_date >= '{date_start}' AND user_date <= '{date_end}' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Specific date formats (the real bug: "2026/2/15" returned 20 results for year only)
    specific_dates = [
        ("2026-02-15", "2026-02-15"),
        ("2026/2/15",  "2026-02-15"),
        ("2/15/2026",  "2026-02-15"),
        ("Feb 15",     "2026-02-15"),
        ("Feb 15 2026","2026-02-15"),
        ("february 15","2026-02-15"),
    ]
    # Use Name (Expenses metadata key) instead of non-existent 'method' key
    expense_names = ["gcash", "jabi", "toyota", "cash", "bank transfer", "check"]
    for raw_date, normalized in specific_dates:
        for name in expense_names:
            phrasings = [
                f"find {name} on {raw_date}",
                f"show {name} entries on {raw_date}",
                f"get {name} transactions on {raw_date}",
                f"search for {name} on {raw_date}",
                f"can you find {name} with date {raw_date}",
            ]
            for phrase in phrasings:
                examples.append({
                    "instruction": phrase,
                    "input": "",
                    "output": json.dumps({
                        "intent": "find_by_date_and_name",
                        "scope": "row",
                        "slots": {"name": name, "date": normalized, "source_table": "Expenses"},
                        "needs_clarification": False,
                        "sql": f"SELECT * FROM ai_documents WHERE metadata->>'Name' ILIKE '%{name}%' AND user_date = '{normalized}' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                    })
                })
        # Date only (no name filter)
        examples.append({
            "instruction": f"show all entries on {raw_date}",
            "input": "",
            "output": json.dumps({
                "intent": "filter_by_date",
                "scope": "row",
                "slots": {"date": normalized},
                "needs_clarification": False,
                "sql": f"SELECT * FROM ai_documents WHERE user_date = '{normalized}' AND document_type = 'row' AND org_id = $1;"
            })
        })
    return examples


# ============================================================================
# BUG #4: CATEGORY SEARCH
# "show me all categories in francis gays" → DISTINCT list
# Uses metadata->>'Category' (correct Expenses key)
# ============================================================================
def gen_category_queries() -> List[Dict]:
    examples = []

    # List all categories globally
    global_phrasings = [
        "show all categories",
        "list all categories",
        "what categories do we have",
        "get all categories",
        "display all categories",
        "what are the available categories",
        "give me a list of all categories",
        "show me the categories",
        "what category options are there",
        "enumerate all categories",
    ]
    for phrase in global_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "list_categories",
                "scope": "distinct_values",
                "slots": {"column": "Category", "source_table": "Expenses"},
                "needs_clarification": False,
                "sql": "SELECT DISTINCT metadata->>'Category' as category FROM ai_documents WHERE metadata->>'Category' IS NOT NULL AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 ORDER BY category;"
            })
        })

    # Categories in a specific file
    for file in FILE_NAMES:
        phrasings = [
            f"show all categories in {file}",
            f"list categories in {file}",
            f"what categories are in {file}",
            f"get all categories from {file}",
            f"display categories for {file}",
            f"what are the categories in {file}",
            f"show me the categories inside {file}",
            f"list all category types in {file}",
            f"find all categories in {file}",
            f"what category does {file} have",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "list_categories_in_file",
                    "scope": "distinct_values",
                    "slots": {"column": "Category", "file_name": file, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT DISTINCT metadata->>'Category' as category FROM ai_documents WHERE metadata->>'Category' IS NOT NULL AND file_name ILIKE '%{file}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 ORDER BY category;"
                })
            })
    return examples


# ============================================================================
# BUG #5: COMPARISON QUERIES
# "compare expenses between francis gays and jc"
# Uses metadata->>'Expenses' (correct key, not 'amount')
# ============================================================================
def gen_comparison_queries() -> List[Dict]:
    examples = []
    file_pairs = [
        ("francis gays", "jc"),
        ("francis gays", "jash gay"),
        ("jc", "jash gay"),
        ("francis gays", "TEST"),
        ("jc", "TEST"),
    ]

    for f1, f2 in file_pairs:
        # General expense comparison
        phrasings = [
            f"compare expenses between {f1} and {f2}",
            f"compare {f1} and {f2}",
            f"show the difference between {f1} and {f2}",
            f"what is the difference between {f1} and {f2}",
            f"compare the expenses for {f1} and {f2}",
            f"how do {f1} and {f2} compare",
            f"give me a comparison of {f1} and {f2}",
            f"contrast {f1} with {f2}",
            f"show expenses comparison for {f1} vs {f2}",
            f"compare totals between {f1} and {f2}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "compare_expenses",
                    "scope": "summary",
                    "slots": {"files": [f1, f2], "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT file_name, COUNT(*) as item_count, SUM((metadata->>'Expenses')::numeric) as total_amount FROM ai_documents WHERE file_name IN ('{f1}', '{f2}') AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 GROUP BY file_name;"
                })
            })

        # Category-specific comparison
        for cat in ALL_CATEGORIES[:5]:
            cat_phrasings = [
                f"compare {cat} between {f1} and {f2}",
                f"compare {cat} expenses in {f1} and {f2}",
                f"show {cat} difference between {f1} and {f2}",
                f"how much {cat} in {f1} vs {f2}",
            ]
            for phrase in cat_phrasings:
                examples.append({
                    "instruction": phrase,
                    "input": "",
                    "output": json.dumps({
                        "intent": "compare_category_between_files",
                        "scope": "summary",
                        "slots": {"category": cat, "files": [f1, f2], "source_table": "Expenses"},
                        "needs_clarification": False,
                        "sql": f"SELECT file_name, COUNT(*) as count, SUM((metadata->>'Expenses')::numeric) as total FROM ai_documents WHERE metadata->>'Category' ILIKE '%{cat}%' AND file_name IN ('{f1}', '{f2}') AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1 GROUP BY file_name;"
                    })
                })
    return examples


# ============================================================================
# BUG #6: FUZZY MATCHING
# "expensive gays" → should match "francis gays"
# ============================================================================
def gen_fuzzy_matching_queries() -> List[Dict]:
    examples = []
    typo_pairs = [
        ("francis gay",      "francis gays"),
        ("expensive gays",   "francis gays"),
        ("francis",          "francis gays"),
        ("gays",             "francis gays"),
        ("jc project",       "jc"),
        ("jash",             "jash gay"),
    ]
    for typo, correct in typo_pairs:
        phrasings = [
            f"show me {typo}",
            f"find {typo}",
            f"open {typo}",
            f"get {typo}",
            f"display {typo}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "fuzzy_file_lookup",
                    "scope": "file",
                    "slots": {"file_name_query": typo, "file_name_match": correct},
                    "needs_clarification": True,
                    "clarification_question": f"Did you mean '{correct}'? I couldn't find an exact match for '{typo}'.",
                    "sql": f"SELECT file_name, metadata->>'description' as description FROM ai_documents WHERE file_name ILIKE '%{typo.split()[0]}%' AND document_type = 'file' AND org_id = $1 LIMIT 5;"
                })
            })
    return examples


# ============================================================================
# BONUS: SUM / TOTAL QUERIES
# Uses metadata->>'Expenses' for expense amounts (correct key)
# Uses metadata->>'Amount' for CashFlow amounts (correct key)
# ============================================================================
def gen_sum_queries() -> List[Dict]:
    examples = []

    # Expense sum queries — uses metadata->>'Expenses' with ::numeric
    for file in FILE_NAMES[:5]:
        phrasings = [
            f"how much is the total expenses in {file}",
            f"what is the total amount in {file}",
            f"get the total for {file}",
            f"sum up all expenses in {file}",
            f"what is the grand total of {file}",
            f"show total expenses for {file}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "sum_expenses",
                    "scope": "summary",
                    "slots": {"file_name": file, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM((metadata->>'Expenses')::numeric) as total FROM ai_documents WHERE file_name ILIKE '%{file}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                })
            })

    for cat in ALL_CATEGORIES:
        phrasings = [
            f"total {cat} expenses",
            f"what is the total amount for {cat}",
            f"sum all {cat} entries",
            f"how much did we spend on {cat}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "sum_by_category",
                    "scope": "summary",
                    "slots": {"category": cat, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM((metadata->>'Expenses')::numeric) as total FROM ai_documents WHERE metadata->>'Category' ILIKE '%{cat}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # CashFlow sum queries — uses metadata->>'Amount' with ::numeric
    cashflow_phrasings = [
        "total cash flow amount",
        "what is the total cash flow",
        "sum all cash flow entries",
        "how much is the total cash flow",
        "get the total amount of cash flow",
    ]
    for phrase in cashflow_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "sum_cashflow",
                "scope": "summary",
                "slots": {"source_table": "CashFlow"},
                "needs_clarification": False,
                "sql": "SELECT SUM((metadata->>'Amount')::numeric) as total FROM ai_documents WHERE source_table = 'CashFlow' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # CashFlow by type
    for cf_type in ["income", "expense", "transfer"]:
        phrasings = [
            f"total {cf_type} in cash flow",
            f"sum of {cf_type} cash flow",
            f"how much {cf_type} in cash flow",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "sum_cashflow_by_type",
                    "scope": "summary",
                    "slots": {"type": cf_type, "source_table": "CashFlow"},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM((metadata->>'Amount')::numeric) as total FROM ai_documents WHERE metadata->>'Type' ILIKE '%{cf_type}%' AND source_table = 'CashFlow' AND document_type = 'row' AND org_id = $1;"
                })
            })

    return examples


# ============================================================================
# BONUS: CONVERSATION CONTEXT (clarification follow-up)
# Uses file_name column (not metadata->>'file_name')
# ============================================================================
def gen_conversation_context_queries() -> List[Dict]:
    examples = []
    for file in FILE_NAMES[:5]:
        for cat in ALL_CATEGORIES[:4]:
            examples.append({
                "instruction": f"[CONTEXT: User asked 'show {cat}'. AI found in multiple files. User chose:] {file}",
                "input": "",
                "output": json.dumps({
                    "intent": "clarification_response",
                    "scope": "row",
                    "slots": {"category": cat, "file_name": file, "source_table": "Expenses"},
                    "needs_clarification": False,
                    "sql": f"SELECT * FROM ai_documents WHERE searchable_text ILIKE '%{cat}%' AND file_name ILIKE '%{file}%' AND source_table = 'Expenses' AND document_type = 'row' AND org_id = $1;"
                })
            })
        examples.append({
            "instruction": f"[CONTEXT: AI asked which file. Options: 1. {file} 2. jc. User chose:] 1",
            "input": "",
            "output": json.dumps({
                "intent": "clarification_response_numeric",
                "scope": "row",
                "slots": {"selected_option": 1, "file_name": file},
                "needs_clarification": False,
                "sql": f"SELECT * FROM ai_documents WHERE file_name ILIKE '%{file}%' AND document_type = 'row' AND org_id = $1;"
            })
        })
    return examples


# ============================================================================
# PROJECT QUERIES
# Source table: Project
# Metadata keys: project_name, client_name, location, status
# ============================================================================
def gen_project_queries() -> List[Dict]:
    examples = []

    # List all projects
    list_phrasings = [
        "list all projects",
        "show all projects",
        "get all projects",
        "what projects do we have",
        "display all projects",
        "show me the projects",
        "enumerate all projects",
    ]
    for phrase in list_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "list_projects",
                "scope": "row",
                "slots": {"source_table": "Project"},
                "needs_clarification": False,
                "sql": "SELECT metadata->>'project_name' as project_name, metadata->>'client_name' as client_name, metadata->>'location' as location, metadata->>'status' as status FROM ai_documents WHERE source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Query by project name
    for project in PROJECTS:
        phrasings = [
            f"show project {project}",
            f"find project {project}",
            f"get details for project {project}",
            f"show me {project} project",
            f"what is the status of {project}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_project",
                    "scope": "row",
                    "slots": {"project_name": project, "source_table": "Project"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'project_name' as project_name, metadata->>'client_name' as client_name, metadata->>'location' as location, metadata->>'status' as status FROM ai_documents WHERE metadata->>'project_name' ILIKE '%{project}%' AND source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by client name
    for client in CLIENT_NAMES:
        phrasings = [
            f"show projects for {client}",
            f"find projects by {client}",
            f"what projects does {client} have",
            f"list projects for client {client}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_project_by_client",
                    "scope": "row",
                    "slots": {"client_name": client, "source_table": "Project"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'project_name' as project_name, metadata->>'client_name' as client_name, metadata->>'location' as location, metadata->>'status' as status FROM ai_documents WHERE metadata->>'client_name' ILIKE '%{client}%' AND source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by location
    for loc in LOCATIONS:
        phrasings = [
            f"show projects in {loc}",
            f"find projects located in {loc}",
            f"what projects are in {loc}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_project_by_location",
                    "scope": "row",
                    "slots": {"location": loc, "source_table": "Project"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'project_name' as project_name, metadata->>'client_name' as client_name, metadata->>'location' as location, metadata->>'status' as status FROM ai_documents WHERE metadata->>'location' ILIKE '%{loc}%' AND source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by status
    for status in PROJECT_STATUSES:
        phrasings = [
            f"show {status} projects",
            f"list all {status} projects",
            f"what projects are {status}",
            f"find projects with status {status}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_project_by_status",
                    "scope": "row",
                    "slots": {"status": status, "source_table": "Project"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'project_name' as project_name, metadata->>'client_name' as client_name, metadata->>'location' as location, metadata->>'status' as status FROM ai_documents WHERE metadata->>'status' ILIKE '%{status}%' AND source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Count projects
    count_phrasings = [
        "how many projects do we have",
        "count all projects",
        "total number of projects",
        "how many projects are there",
    ]
    for phrase in count_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "count_projects",
                "scope": "summary",
                "slots": {"source_table": "Project"},
                "needs_clarification": False,
                "sql": "SELECT COUNT(*) as count FROM ai_documents WHERE source_table = 'Project' AND document_type = 'row' AND org_id = $1;"
            })
        })

    return examples


# ============================================================================
# QUOTATION QUERIES
# Source table: Quotation
# Metadata keys: quote_number, status, total_amount, project_name
# Numeric keys: total_amount
# ============================================================================
def gen_quotation_queries() -> List[Dict]:
    examples = []

    # List all quotations
    list_phrasings = [
        "list all quotations",
        "show all quotations",
        "get all quotes",
        "what quotations do we have",
        "display all quotations",
        "show me the quotes",
    ]
    for phrase in list_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "list_quotations",
                "scope": "row",
                "slots": {"source_table": "Quotation"},
                "needs_clarification": False,
                "sql": "SELECT metadata->>'quote_number' as quote_number, metadata->>'status' as status, metadata->>'total_amount' as total_amount, metadata->>'project_name' as project_name FROM ai_documents WHERE source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Query by quote number
    for qnum in QUOTATION_NUMBERS:
        phrasings = [
            f"show quotation {qnum}",
            f"find quote {qnum}",
            f"get details for {qnum}",
            f"show me {qnum}",
            f"what is the status of {qnum}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_quotation",
                    "scope": "row",
                    "slots": {"quote_number": qnum, "source_table": "Quotation"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'quote_number' as quote_number, metadata->>'status' as status, metadata->>'total_amount' as total_amount, metadata->>'project_name' as project_name FROM ai_documents WHERE metadata->>'quote_number' ILIKE '%{qnum}%' AND source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by quotation status
    for status in QUOTATION_STATUSES:
        phrasings = [
            f"show {status} quotations",
            f"list all {status} quotes",
            f"what quotations are {status}",
            f"find quotes with status {status}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_quotation_by_status",
                    "scope": "row",
                    "slots": {"status": status, "source_table": "Quotation"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'quote_number' as quote_number, metadata->>'status' as status, metadata->>'total_amount' as total_amount, metadata->>'project_name' as project_name FROM ai_documents WHERE metadata->>'status' ILIKE '%{status}%' AND source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query quotations by project name
    for project in PROJECTS:
        phrasings = [
            f"show quotations for {project}",
            f"find quotes for project {project}",
            f"what quotations are for {project}",
            f"list quotes for {project}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_quotation_by_project",
                    "scope": "row",
                    "slots": {"project_name": project, "source_table": "Quotation"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'quote_number' as quote_number, metadata->>'status' as status, metadata->>'total_amount' as total_amount, metadata->>'project_name' as project_name FROM ai_documents WHERE metadata->>'project_name' ILIKE '%{project}%' AND source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Sum total_amount (numeric key)
    sum_phrasings = [
        "total amount of all quotations",
        "what is the total quotation amount",
        "sum all quotation amounts",
        "how much are all the quotations worth",
        "get the total value of all quotes",
    ]
    for phrase in sum_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "sum_quotation_amount",
                "scope": "summary",
                "slots": {"source_table": "Quotation"},
                "needs_clarification": False,
                "sql": "SELECT SUM((metadata->>'total_amount')::numeric) as total FROM ai_documents WHERE source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Count quotations
    count_phrasings = [
        "how many quotations do we have",
        "count all quotations",
        "total number of quotes",
        "how many quotes are there",
    ]
    for phrase in count_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "count_quotations",
                "scope": "summary",
                "slots": {"source_table": "Quotation"},
                "needs_clarification": False,
                "sql": "SELECT COUNT(*) as count FROM ai_documents WHERE source_table = 'Quotation' AND document_type = 'row' AND org_id = $1;"
            })
        })

    return examples


# ============================================================================
# QUOTATION ITEM QUERIES
# Source table: QuotationItem
# Metadata keys: plate_no, dr_no, material, quarry_location, truck_type, volume, line_total
# Numeric keys: volume, line_total
# ============================================================================
def gen_quotation_item_queries() -> List[Dict]:
    examples = []

    # List all deliveries/line items
    list_phrasings = [
        "list all deliveries",
        "show all line items",
        "get all delivery records",
        "what deliveries do we have",
        "display all line items",
        "show me the deliveries",
    ]
    for phrase in list_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "list_quotation_items",
                "scope": "row",
                "slots": {"source_table": "QuotationItem"},
                "needs_clarification": False,
                "sql": "SELECT metadata->>'plate_no' as plate_no, metadata->>'dr_no' as dr_no, metadata->>'material' as material, metadata->>'quarry_location' as quarry_location, metadata->>'truck_type' as truck_type, metadata->>'volume' as volume, metadata->>'line_total' as line_total FROM ai_documents WHERE source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Query by plate number
    for plate in PLATE_NUMBERS:
        phrasings = [
            f"show deliveries for plate {plate}",
            f"find deliveries with plate number {plate}",
            f"get all records for plate {plate}",
            f"show me plate {plate} deliveries",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_by_plate",
                    "scope": "row",
                    "slots": {"plate_no": plate, "source_table": "QuotationItem"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'plate_no' as plate_no, metadata->>'dr_no' as dr_no, metadata->>'material' as material, metadata->>'volume' as volume, metadata->>'line_total' as line_total FROM ai_documents WHERE metadata->>'plate_no' ILIKE '%{plate}%' AND source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by DR number
    for dr in DR_NUMBERS:
        phrasings = [
            f"show delivery {dr}",
            f"find DR {dr}",
            f"get details for {dr}",
            f"show me DR number {dr}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_by_dr",
                    "scope": "row",
                    "slots": {"dr_no": dr, "source_table": "QuotationItem"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'plate_no' as plate_no, metadata->>'dr_no' as dr_no, metadata->>'material' as material, metadata->>'volume' as volume, metadata->>'line_total' as line_total FROM ai_documents WHERE metadata->>'dr_no' ILIKE '%{dr}%' AND source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Query by material
    for mat in MATERIALS:
        phrasings = [
            f"show all {mat} deliveries",
            f"find deliveries of {mat}",
            f"get all {mat} line items",
            f"how many {mat} deliveries",
            f"list {mat} records",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "query_by_material",
                    "scope": "row",
                    "slots": {"material": mat, "source_table": "QuotationItem"},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'plate_no' as plate_no, metadata->>'dr_no' as dr_no, metadata->>'material' as material, metadata->>'volume' as volume, metadata->>'line_total' as line_total FROM ai_documents WHERE metadata->>'material' ILIKE '%{mat}%' AND source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Sum volume (numeric key)
    volume_phrasings = [
        "total volume delivered",
        "what is the total volume",
        "sum all delivery volumes",
        "how much volume was delivered",
        "get the total volume of all deliveries",
    ]
    for phrase in volume_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "sum_volume",
                "scope": "summary",
                "slots": {"source_table": "QuotationItem"},
                "needs_clarification": False,
                "sql": "SELECT SUM((metadata->>'volume')::numeric) as total_volume FROM ai_documents WHERE source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Sum line_total (numeric key)
    total_phrasings = [
        "total line total of all deliveries",
        "what is the total cost of all line items",
        "sum all line totals",
        "how much are all deliveries worth",
        "get the total value of all deliveries",
    ]
    for phrase in total_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "sum_line_total",
                "scope": "summary",
                "slots": {"source_table": "QuotationItem"},
                "needs_clarification": False,
                "sql": "SELECT SUM((metadata->>'line_total')::numeric) as total FROM ai_documents WHERE source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
            })
        })

    # Sum volume by material
    for mat in MATERIALS:
        phrasings = [
            f"total volume of {mat}",
            f"how much {mat} was delivered",
            f"sum volume for {mat}",
        ]
        for phrase in phrasings:
            examples.append({
                "instruction": phrase,
                "input": "",
                "output": json.dumps({
                    "intent": "sum_volume_by_material",
                    "scope": "summary",
                    "slots": {"material": mat, "source_table": "QuotationItem"},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM((metadata->>'volume')::numeric) as total_volume FROM ai_documents WHERE metadata->>'material' ILIKE '%{mat}%' AND source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
                })
            })

    # Count deliveries
    count_phrasings = [
        "how many deliveries do we have",
        "count all deliveries",
        "total number of line items",
        "how many line items are there",
    ]
    for phrase in count_phrasings:
        examples.append({
            "instruction": phrase,
            "input": "",
            "output": json.dumps({
                "intent": "count_deliveries",
                "scope": "summary",
                "slots": {"source_table": "QuotationItem"},
                "needs_clarification": False,
                "sql": "SELECT COUNT(*) as count FROM ai_documents WHERE source_table = 'QuotationItem' AND document_type = 'row' AND org_id = $1;"
            })
        })

    return examples


# ============================================================================
# MAIN GENERATOR
# ============================================================================
def generate_all_examples() -> List[Dict]:
    all_examples = []
    all_examples.extend(gen_file_level_queries())
    all_examples.extend(gen_ambiguous_clarification_queries())
    all_examples.extend(gen_date_queries())
    all_examples.extend(gen_category_queries())
    all_examples.extend(gen_comparison_queries())
    all_examples.extend(gen_fuzzy_matching_queries())
    all_examples.extend(gen_sum_queries())
    all_examples.extend(gen_conversation_context_queries())
    all_examples.extend(gen_project_queries())
    all_examples.extend(gen_quotation_queries())
    all_examples.extend(gen_quotation_item_queries())
    return all_examples


def save_jsonl(examples: List[Dict], output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"Saved {len(examples)} examples to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate training data for AU-Ggregates AI")
    parser.add_argument("--output", default="data/training_bugfix.jsonl", help="Output JSONL file path")
    parser.add_argument("--count", type=int, default=0, help="Max examples (0 = all)")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle examples")
    args = parser.parse_args()

    print("Generating training examples...")
    examples = generate_all_examples()

    if args.shuffle:
        random.shuffle(examples)

    if args.count > 0:
        examples = examples[:args.count]

    save_jsonl(examples, args.output)

    # Breakdown by intent
    intents = {}
    for ex in examples:
        try:
            out = json.loads(ex["output"])
            intent = out.get("intent", "unknown")
            intents[intent] = intents.get(intent, 0) + 1
        except Exception:
            pass

    print("\nBreakdown by intent:")
    for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
        print(f"  {intent}: {count}")

    # Breakdown by source_table
    source_tables = {}
    for ex in examples:
        try:
            out = json.loads(ex["output"])
            st = out.get("slots", {}).get("source_table", "unspecified")
            source_tables[st] = source_tables.get(st, 0) + 1
        except Exception:
            pass

    print("\nBreakdown by source_table:")
    for st, count in sorted(source_tables.items(), key=lambda x: -x[1]):
        print(f"  {st}: {count}")

    print(f"\nTotal: {len(examples)} examples")


if __name__ == "__main__":
    main()
