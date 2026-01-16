"""
Training Dataset Generator for AU-Ggregates AI
================================================
Generates JSONL training examples based on real bugs found in production.
English only. Covers 6 bug categories with diverse phrasing variations.

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

# Real metadata keys found in Expenses rows: Date, Name, Category, Expenses
# Real metadata keys found in CashFlow rows: Type, Amount, Category
# Real metadata keys found in file-type rows: type=file, file_name, description, project_name
EXPENSE_CATEGORIES = ["fuel", "food", "car"]       # from real data
CASHFLOW_CATEGORIES = ["car"]                       # from real data
ALL_CATEGORIES = ["fuel", "food", "car", "labor", "cement", "steel", "sand", "gravel"]

# Real payment methods seen in metadata.Name (Expenses)
METHODS = ["gcash", "jabi", "toyota", "cash", "bank transfer", "check"]

# Real quotation numbers
QUOTATION_NUMBERS = [
    "QUO-2026-0001", "QUO-2026-0002", "QUO-2026-0003",
    "QUO-2026-0004", "QUO-2026-0005", "QUO-2026-0006",
]

# Real materials from QuotationItem
MATERIALS = ["Washed Sand", "Gravel", "Crushed Stone", "Fill Soil"]

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
    for cat in CATEGORIES:
        for verb in FIND_VERBS + SHOW_VERBS:
            examples.append({
                "instruction": f"{verb} {cat}",
                "input": "",
                "output": json.dumps({
                    "intent": "find_category",
                    "scope": "row",
                    "slots": {"category": cat, "file_name": None},
                    "needs_clarification": True,
                    "clarify_slot": "file_name",
                    "clarification_question": f"I found '{cat}' in multiple files. Which file are you looking for? Please specify the file name.",
                    "sql": f"SELECT metadata->>'file_name' as file_name, COUNT(*) as count FROM ai_documents WHERE searchable_text ILIKE '%{cat}%' AND org_id = $1 GROUP BY metadata->>'file_name';"
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
                    "slots": {"category": cat, "file_name": None},
                    "needs_clarification": True,
                    "clarify_slot": "file_name",
                    "clarification_question": f"I found '{cat}' in multiple files. Which file are you looking for?",
                    "sql": f"SELECT metadata->>'file_name' as file_name, COUNT(*) as count FROM ai_documents WHERE searchable_text ILIKE '%{cat}%' AND org_id = $1 GROUP BY metadata->>'file_name';"
                })
            })

    # After clarification — user specifies the file
    for cat in CATEGORIES:
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
                        "slots": {"category": cat, "file_name": file},
                        "needs_clarification": False,
                        "sql": f"SELECT * FROM ai_documents WHERE searchable_text ILIKE '%{cat}%' AND metadata->>'file_name' ILIKE '%{file}%' AND org_id = $1;"
                    })
                })
    return examples


# ============================================================================
# BUG #3: DATE PARSING
# "count all expenses in february" → understand month names
# "find gcash on 2026/2/15" → parse flexible date formats
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
                    "slots": {"date_range": month_name, "date_start": date_start, "date_end": date_end},
                    "needs_clarification": False,
                    "sql": f"SELECT COUNT(*) as count FROM ai_documents WHERE metadata->>'user_date' >= '{date_start}' AND metadata->>'user_date' <= '{date_end}' AND org_id = $1;"
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
                    "slots": {"date_range": month_name, "date_start": date_start, "date_end": date_end},
                    "needs_clarification": False,
                    "sql": f"SELECT * FROM ai_documents WHERE metadata->>'user_date' >= '{date_start}' AND metadata->>'user_date' <= '{date_end}' AND org_id = $1;"
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
    for raw_date, normalized in specific_dates:
        for method in METHODS:
            phrasings = [
                f"find {method} on {raw_date}",
                f"show {method} entries on {raw_date}",
                f"get {method} transactions on {raw_date}",
                f"search for {method} on {raw_date}",
                f"can you find {method} with date {raw_date}",
            ]
            for phrase in phrasings:
                examples.append({
                    "instruction": phrase,
                    "input": "",
                    "output": json.dumps({
                        "intent": "find_by_date_and_method",
                        "scope": "row",
                        "slots": {"method": method, "date": normalized},
                        "needs_clarification": False,
                        "sql": f"SELECT * FROM ai_documents WHERE metadata->>'method' ILIKE '%{method}%' AND metadata->>'user_date' = '{normalized}' AND org_id = $1;"
                    })
                })
        # Date only (no method)
        examples.append({
            "instruction": f"show all entries on {raw_date}",
            "input": "",
            "output": json.dumps({
                "intent": "filter_by_date",
                "scope": "row",
                "slots": {"date": normalized},
                "needs_clarification": False,
                "sql": f"SELECT * FROM ai_documents WHERE metadata->>'user_date' = '{normalized}' AND org_id = $1;"
            })
        })
    return examples


# ============================================================================
# BUG #4: CATEGORY SEARCH
# "show me all categories in francis gays" → DISTINCT list
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
                "slots": {"column": "category"},
                "needs_clarification": False,
                "sql": "SELECT DISTINCT metadata->>'category' as category FROM ai_documents WHERE metadata->>'category' IS NOT NULL AND org_id = $1 ORDER BY category;"
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
                    "slots": {"column": "category", "file_name": file},
                    "needs_clarification": False,
                    "sql": f"SELECT DISTINCT metadata->>'category' as category FROM ai_documents WHERE metadata->>'category' IS NOT NULL AND metadata->>'file_name' ILIKE '%{file}%' AND org_id = $1 ORDER BY category;"
                })
            })
    return examples


# ============================================================================
# BUG #5: COMPARISON QUERIES
# "compare expenses between francis gays and jc"
# ============================================================================
def gen_comparison_queries() -> List[Dict]:
    examples = []
    file_pairs = [
        ("francis gays", "jc"),
        ("francis gays", "sjdm"),
        ("jc", "sjdm"),
        ("manila tower", "sti construction"),
        ("francis gays", "manila tower"),
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
                    "slots": {"files": [f1, f2]},
                    "needs_clarification": False,
                    "sql": f"SELECT metadata->>'file_name' as file_name, COUNT(*) as item_count, SUM(CAST(metadata->>'amount' AS NUMERIC)) as total_amount FROM ai_documents WHERE metadata->>'file_name' IN ('{f1}', '{f2}') AND org_id = $1 GROUP BY metadata->>'file_name';"
                })
            })

        # Category-specific comparison
        for cat in CATEGORIES[:5]:
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
                        "slots": {"category": cat, "files": [f1, f2]},
                        "needs_clarification": False,
                        "sql": f"SELECT metadata->>'file_name' as file_name, COUNT(*) as count, SUM(CAST(metadata->>'amount' AS NUMERIC)) as total FROM ai_documents WHERE metadata->>'category' ILIKE '%{cat}%' AND metadata->>'file_name' IN ('{f1}', '{f2}') AND org_id = $1 GROUP BY metadata->>'file_name';"
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
        ("sjdm project",     "sjdm"),
        ("manila",           "manila tower"),
        ("sti",              "sti construction"),
        ("jash",             "jash gay"),
        ("q1",               "q1 budget"),
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
                    "sql": f"SELECT file_name, description FROM ai_documents WHERE metadata->>'file_name' ILIKE '%{typo.split()[0]}%' AND metadata->>'document_type' = 'file' AND org_id = $1 LIMIT 5;"
                })
            })
    return examples


# ============================================================================
# BONUS: SUM / TOTAL QUERIES
# ============================================================================
def gen_sum_queries() -> List[Dict]:
    examples = []

    for file in FILE_NAMES:
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
                    "slots": {"file_name": file},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM(CAST(metadata->>'amount' AS NUMERIC)) as total FROM ai_documents WHERE metadata->>'file_name' ILIKE '%{file}%' AND org_id = $1;"
                })
            })

    for cat in CATEGORIES:
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
                    "slots": {"category": cat},
                    "needs_clarification": False,
                    "sql": f"SELECT SUM(CAST(metadata->>'amount' AS NUMERIC)) as total FROM ai_documents WHERE metadata->>'category' ILIKE '%{cat}%' AND org_id = $1;"
                })
            })
    return examples


# ============================================================================
# BONUS: CONVERSATION CONTEXT (clarification follow-up)
# ============================================================================
def gen_conversation_context_queries() -> List[Dict]:
    examples = []
    for file in FILE_NAMES[:5]:
        for cat in CATEGORIES[:4]:
            examples.append({
                "instruction": f"[CONTEXT: User asked 'show {cat}'. AI found in multiple files. User chose:] {file}",
                "input": "",
                "output": json.dumps({
                    "intent": "clarification_response",
                    "scope": "row",
                    "slots": {"category": cat, "file_name": file},
                    "needs_clarification": False,
                    "sql": f"SELECT * FROM ai_documents WHERE searchable_text ILIKE '%{cat}%' AND metadata->>'file_name' ILIKE '%{file}%' AND org_id = $1;"
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
                "sql": f"SELECT * FROM ai_documents WHERE metadata->>'file_name' ILIKE '%{file}%' AND org_id = $1;"
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
    print(f"\nTotal: {len(examples)} examples")


if __name__ == "__main__":
    main()
