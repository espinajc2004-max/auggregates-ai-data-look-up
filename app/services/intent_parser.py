"""
Intent Parser
=============
Semantic intent detection for AU-Ggregates AI queries.
Uses sentence-transformers (all-MiniLM-L6-v2) for intent classification
via cosine similarity — no hardcoded keyword patterns needed.

Entity extraction uses:
- rapidfuzz for fuzzy file name matching (typo-tolerant)
- dateparser for smart date parsing (multilingual, relative dates)
- Dynamic DB lookups for categories (no hardcoded lists)
"""

import re
import time
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# MONTH MAPPINGS (English + Tagalog) — kept for QueryEngine._date_label()
# ============================================================================
MONTH_MAP = {
    "january": 1, "jan": 1, "enero": 1,
    "february": 2, "feb": 2, "pebrero": 2,
    "march": 3, "mar": 3, "marso": 3,
    "april": 4, "apr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "june": 6, "jun": 6, "hunyo": 6,
    "july": 7, "jul": 7, "hulyo": 7, 
    "august": 8, "aug": 8, "agosto": 8,
    "september": 9, "sep": 9, "sept": 9, "setyembre": 9,
    "october": 10, "oct": 10, "oktubre": 10,
    "november": 11, "nov": 11, "nobyembre": 11,
    "december": 12, "dec": 12, "disyembre": 12,
}

MONTH_DAYS = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
}


# ============================================================================
# SEMANTIC INTENT MODEL (sentence-transformers)
# ============================================================================
_st_model = None
_intent_embeddings = None
_intent_labels = None

# Intent descriptions — each intent has multiple natural language examples
# The model matches user queries against these via cosine similarity
INTENT_DESCRIPTIONS = {
    "list_files": [
        "list all files",
        "show my expense files",
        "what files do I have",
        "show all records",
        "display all documents",
        "show all expense files",
        "list of expenses file",
        "what are the files in the system",
        "enumerate all files",
        "get all files",
    ],
    "file_summary": [
        "show me this file",
        "open the file",
        "details of this file",
        "show file information",
        "what is in this file",
        "display file contents",
        "file overview",
        "summary of this expense file",
    ],
    "find_in_file": [
        "find fuel in this file",
        "search for labor expenses in file",
        "show category expenses in file",
        "look for items in a specific file",
        "filter expenses by category in file",
        "what are the fuel expenses in this file",
    ],
    "count": [
        "how many rows",
        "count expenses",
        "how many records",
        "count all entries",
        "how many items",
        "number of expenses",
        "how many fuel expenses",
    ],
    "sum": [
        "total expenses",
        "how much total",
        "sum of all amounts",
        "overall total",
        "what is the total amount",
        "grand total of expenses",
        "how much did we spend",
        "total cost",
    ],
    "compare": [
        "compare file A vs file B",
        "difference between two files",
        "compare expenses between files",
        "which file has more expenses",
        "compare two expense files",
    ],
    "list_categories": [
        "what categories exist",
        "list all categories",
        "show categories",
        "what types of expenses are there",
        "enumerate categories",
        "distinct categories",
    ],
    "date_filter": [
        "expenses in January",
        "show records from March",
        "filter by date",
        "expenses last month",
        "records from February 2026",
        "what expenses were in January",
        "show me expenses for this month",
    ],
    "general_search": [
        "search for something",
        "find this term",
        "look up information",
        "search the database",
        "find records matching",
    ],
}


def _load_semantic_model():
    """Load sentence-transformers model and pre-compute intent embeddings."""
    global _st_model, _intent_embeddings, _intent_labels

    if _st_model is not None:
        return

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2")
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence-transformers model loaded (CPU)")

        # Pre-compute embeddings for all intent descriptions
        all_descriptions = []
        all_labels = []
        for intent_name, descriptions in INTENT_DESCRIPTIONS.items():
            for desc in descriptions:
                all_descriptions.append(desc)
                all_labels.append(intent_name)

        _intent_embeddings = _st_model.encode(all_descriptions, normalize_embeddings=True)
        _intent_labels = all_labels
        logger.info(f"Pre-computed {len(all_descriptions)} intent embeddings")

    except Exception as e:
        logger.error(f"Failed to load sentence-transformers: {e}")
        _st_model = None


def _classify_intent_semantic(query: str) -> tuple:
    """
    Classify intent using cosine similarity against pre-computed embeddings.

    Returns:
        (intent_name, confidence_score)
    """
    _load_semantic_model()

    if _st_model is None or _intent_embeddings is None:
        return ("general_search", 0.0)

    # Encode user query
    query_embedding = _st_model.encode([query], normalize_embeddings=True)

    # Cosine similarity (embeddings are already normalized, so dot product = cosine)
    similarities = np.dot(_intent_embeddings, query_embedding.T).flatten()

    # Find best match
    best_idx = int(np.argmax(similarities))
    best_score = float(similarities[best_idx])
    best_intent = _intent_labels[best_idx]

    logger.info(f"Semantic intent: '{best_intent}' (score={best_score:.3f}) for query: '{query}'")

    # Threshold — below this, fall back to general_search
    if best_score < 0.35:
        logger.info(f"Score {best_score:.3f} below threshold 0.35, using general_search")
        return ("general_search", best_score)

    return (best_intent, best_score)


# ============================================================================
# DATE EXTRACTION (dateparser)
# ============================================================================

def _extract_date(text: str) -> Optional[Dict]:
    """
    Extract date info using dateparser library.
    Handles: "last month", "yesterday", "february 15", "2026-02-15", "in january", etc.

    Returns {type, value} or {type, month, start, end} or None.
    """
    try:
        import dateparser
    except ImportError:
        logger.warning("dateparser not installed, falling back to regex date extraction")
        return _extract_date_regex(text)

    year = datetime.now().year

    # First try regex for explicit date formats (more reliable for exact dates)
    regex_result = _extract_date_regex(text)
    if regex_result and regex_result.get("type") == "exact":
        return regex_result

    # Check for month names (English + Tagalog) → month_range
    month_pattern = re.search(
        r'(?:in|nung|sa|ng|noong|during|for|from)?\s*'
        r'(january|february|march|april|may|june|july|august|september|october|november|december|'
        r'jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|'
        r'enero|pebrero|marso|abril|mayo|hunyo|hulyo|agosto|setyembre|oktubre|nobyembre|disyembre)',
        text, re.IGNORECASE
    )
    if month_pattern:
        month_name = month_pattern.group(1).lower()
        month_num = MONTH_MAP.get(month_name)
        if month_num:
            days = MONTH_DAYS.get(month_num, 30)
            return {
                "type": "month_range",
                "month": month_num,
                "start": f"{year}-{month_num:02d}-01",
                "end": f"{year}-{month_num:02d}-{days:02d}"
            }

    # Try dateparser for relative dates ("last month", "yesterday", "2 weeks ago")
    relative_patterns = ["last month", "yesterday", "last week", "today",
                         "this month", "this week", "2 days ago", "a week ago",
                         "kahapon", "kagabi", "noong isang linggo"]
    text_lower = text.lower()
    for pattern in relative_patterns:
        if pattern in text_lower:
            parsed = dateparser.parse(pattern, settings={
                'PREFER_DATES_FROM': 'past',
                'RELATIVE_BASE': datetime.now()
            })
            if parsed:
                if "month" in pattern or "buwan" in pattern:
                    month_num = parsed.month
                    days = MONTH_DAYS.get(month_num, 30)
                    return {
                        "type": "month_range",
                        "month": month_num,
                        "start": f"{parsed.year}-{month_num:02d}-01",
                        "end": f"{parsed.year}-{month_num:02d}-{days:02d}"
                    }
                else:
                    return {
                        "type": "exact",
                        "value": parsed.strftime("%Y-%m-%d")
                    }

    return None


def _extract_date_regex(text: str) -> Optional[Dict]:
    """Fallback regex date extraction for explicit date formats."""
    year = datetime.now().year

    # Exact date: 2026-02-15 or 2026/2/15
    m = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
    if m:
        return {"type": "exact", "value": f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    # Exact date: 2/15/2026
    m = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
    if m:
        return {"type": "exact", "value": f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"}

    # Month + day: "feb 15" or "february 15"
    m = re.search(
        r'(january|february|march|april|may|june|july|august|september|october|november|december|'
        r'jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|'
        r'enero|pebrero|marso|abril|mayo|hunyo|hulyo|agosto|setyembre|oktubre|nobyembre|disyembre)'
        r'\s+(\d{1,2})', text, re.IGNORECASE
    )
    if m:
        month_num = MONTH_MAP.get(m.group(1).lower(), 1)
        day = int(m.group(2))
        return {"type": "exact", "value": f"{year}-{month_num:02d}-{day:02d}"}

    return None


# ============================================================================
# ENTITY EXTRACTORS (fuzzy matching + dynamic DB lookups)
# ============================================================================

def _extract_category(text: str) -> Optional[str]:
    """
    Extract expense category using dynamic DB lookup + fuzzy matching.
    No hardcoded category list — fetches from actual data.
    """
    known_categories = _get_known_categories()

    if not known_categories:
        # Fallback: minimal hardcoded list if DB is unreachable
        known_categories = [
            "fuel", "food", "car", "labor", "cement", "steel", "sand",
            "gravel", "tools", "equipment", "materials", "supplies",
        ]

    text_lower = text.lower()

    # Exact substring match first (fast)
    for cat in known_categories:
        if cat.lower() in text_lower:
            return cat

    # Fuzzy match for typos
    try:
        from rapidfuzz import fuzz
        best_match = None
        best_score = 0
        for cat in known_categories:
            # Check each word in the query against the category
            for word in text_lower.split():
                if len(word) < 3:
                    continue
                score = fuzz.ratio(word, cat.lower())
                if score > best_score and score >= 80:
                    best_score = score
                    best_match = cat
        if best_match:
            logger.info(f"Fuzzy category match: '{best_match}' (score={best_score})")
            return best_match
    except ImportError:
        pass

    return None


def _extract_method(text: str) -> Optional[str]:
    """Extract payment method from query."""
    methods = ["gcash", "cash", "bank transfer", "check", "credit card", "debit"]
    text_lower = text.lower()
    for method in methods:
        if method in text_lower:
            return method
    return None


def _extract_single_file(text: str) -> Optional[str]:
    """
    Extract a single file name using dynamic DB lookup + fuzzy matching.
    Handles typos like "franciss gays" → "francis gays".
    """
    known_files = _get_known_file_names()
    if not known_files:
        return None

    text_lower = text.lower()

    # Sort by length descending so longer names match first
    sorted_files = sorted(known_files, key=len, reverse=True)

    # Exact substring match first
    for file_name in sorted_files:
        if file_name.lower() in text_lower:
            return file_name

    # Fuzzy match for typos
    try:
        from rapidfuzz import fuzz
        best_match = None
        best_score = 0
        for file_name in sorted_files:
            score = fuzz.partial_ratio(text_lower, file_name.lower())
            if score > best_score and score >= 75:
                best_score = score
                best_match = file_name
        if best_match:
            logger.info(f"Fuzzy file match: '{best_match}' (score={best_score})")
            return best_match
    except ImportError:
        pass

    return None


def _extract_multiple_files(text: str) -> List[str]:
    """Extract two file names for comparison queries."""
    m = re.search(r'between\s+(.+?)\s+and\s+(.+?)(?:\s|$)', text)
    if m:
        return [m.group(1).strip(), m.group(2).strip()]

    m = re.search(r'(.+?)\s+(?:and|at|vs|versus)\s+(.+?)(?:\s|$)', text)
    if m:
        f1 = m.group(1).strip()
        f2 = m.group(2).strip()
        for w in ["compare", "ikumpara", "expenses", "between", "the"]:
            f1 = f1.replace(w, "").strip()
            f2 = f2.replace(w, "").strip()
        if f1 and f2:
            return [f1, f2]

    return []


def _detect_source_table(text: str) -> Optional[str]:
    """
    Detect source_table from query context.
    Returns 'Expenses' if user mentions expenses, 'CashFlow' if cashflow.
    Returns None if ambiguous (return all).
    """
    text_lower = text.lower()
    cashflow_words = ["cashflow", "cash flow", "cash-flow", "inflow", "outflow", "balance"]
    expense_words = ["expense", "expenses", "gastos", "cost", "costs", "spending"]

    has_cashflow = any(w in text_lower for w in cashflow_words)
    has_expense = any(w in text_lower for w in expense_words)

    if has_cashflow and not has_expense:
        return "CashFlow"
    if has_expense and not has_cashflow:
        return "Expenses"
    # If both or neither mentioned, return None (show all)
    return None


def _extract_search_term(text: str) -> Optional[str]:
    """Extract general search term after removing verbs."""
    for verb in ["show me", "find me", "get me", "show", "find", "get",
                 "ipakita", "hanapin", "pakita", "display", "search for",
                 "help me find", "help me", "can you find", "can you show"]:
        if text.startswith(verb):
            term = text[len(verb):].strip()
            if term:
                return term
    return text if len(text) > 2 else None


# ============================================================================
# DB CACHES (file names + categories)
# ============================================================================

_file_name_cache: Optional[List[str]] = None
_file_name_cache_time: float = 0
_FILE_NAME_CACHE_TTL: float = 300  # 5 minutes

_category_cache: Optional[List[str]] = None
_category_cache_time: float = 0
_CATEGORY_CACHE_TTL: float = 300


def _get_known_file_names() -> List[str]:
    """Fetch all distinct file_name values from ai_documents. Cached 5 min."""
    global _file_name_cache, _file_name_cache_time

    now = time.time()
    if _file_name_cache is not None and (now - _file_name_cache_time) < _FILE_NAME_CACHE_TTL:
        return _file_name_cache

    try:
        from app.services.supabase_client import get_supabase_client
        client = get_supabase_client()
        rows = client.get("ai_documents", {
            "select": "file_name",
            "document_type": "eq.file",
            "limit": "500"
        })
        if rows:
            _file_name_cache = list(set(r["file_name"] for r in rows if r.get("file_name")))
        else:
            rows = client.get("ai_documents", {"select": "file_name", "limit": "500"})
            _file_name_cache = list(set(r["file_name"] for r in rows if r.get("file_name")))
        _file_name_cache_time = now
        return _file_name_cache
    except Exception:
        return _file_name_cache or []


def _get_known_categories() -> List[str]:
    """Fetch all distinct Category values from ai_documents metadata. Cached 5 min."""
    global _category_cache, _category_cache_time

    now = time.time()
    if _category_cache is not None and (now - _category_cache_time) < _CATEGORY_CACHE_TTL:
        return _category_cache

    try:
        from app.services.supabase_client import get_supabase_client
        client = get_supabase_client()
        rows = client.get("ai_documents", {
            "select": "metadata",
            "document_type": "eq.row",
            "limit": "1000"
        })
        categories = set()
        for row in rows or []:
            meta = row.get("metadata") or {}
            cat = meta.get("Category") or meta.get("category")
            if cat and isinstance(cat, str) and len(cat.strip()) > 0:
                categories.add(cat.strip())
        _category_cache = sorted(categories)
        _category_cache_time = now
        logger.info(f"Loaded {len(_category_cache)} categories from DB: {_category_cache}")
        return _category_cache
    except Exception:
        return _category_cache or []


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def parse_intent(query: str) -> Dict[str, Any]:
    """
    Parse user query into structured intent using semantic classification.

    Uses sentence-transformers for intent detection (replaces hardcoded regex).
    Entity extraction still uses rule-based + fuzzy matching + DB lookups.

    Returns dict with:
    - intent: file_summary | list_files | find_in_file | list_categories |
              compare | count | sum | date_filter | ambiguous | general_search
    - needs_clarification: bool
    - slots: extracted entities
    - clarification_question: str (if needed)
    """
    q = query.strip()
    q_lower = q.lower()
    slots = {}

    # Step 1: Classify intent semantically
    intent_type, confidence = _classify_intent_semantic(q_lower)
    logger.info(f"Semantic classification: intent='{intent_type}', confidence={confidence:.3f}")

    # Step 2: Extract entities regardless of intent
    file_name = _extract_single_file(q_lower)
    category = _extract_category(q_lower)
    date_slot = _extract_date(q_lower)
    method = _extract_method(q_lower)

    # Step 3: Route based on semantic intent + extracted entities

    # --- COMPARE ---
    if intent_type == "compare":
        files = _extract_multiple_files(q_lower)
        if len(files) >= 2:
            slots["files"] = files
            if category:
                slots["category"] = category
            return {"intent": "compare", "needs_clarification": False, "slots": slots}
        else:
            return {
                "intent": "compare",
                "needs_clarification": True,
                "slots": slots,
                "clarification_question": "Which files do you want to compare? Please mention both file names."
            }

    # --- COUNT ---
    if intent_type == "count":
        if date_slot:
            slots["date"] = date_slot
        if file_name:
            slots["file_name"] = file_name
        if category:
            slots["category"] = category
        return {"intent": "count", "needs_clarification": False, "slots": slots}

    # --- SUM ---
    if intent_type == "sum":
        if file_name:
            slots["file_name"] = file_name
        if category:
            slots["category"] = category
        if date_slot:
            slots["date"] = date_slot
        return {"intent": "sum", "needs_clarification": False, "slots": slots}

    # --- LIST CATEGORIES ---
    if intent_type == "list_categories":
        if file_name:
            slots["file_name"] = file_name
        return {"intent": "list_categories", "needs_clarification": False, "slots": slots}

    # --- LIST FILES ---
    if intent_type == "list_files":
        # Detect source_table from query context
        source_table = _detect_source_table(q_lower)
        if source_table:
            slots["source_table"] = source_table
        return {"intent": "list_files", "needs_clarification": False, "slots": slots}

    # --- DATE FILTER ---
    if intent_type == "date_filter" or date_slot:
        if category:
            slots["category"] = category
        if file_name:
            slots["file_name"] = file_name
        if method:
            slots["method"] = method
        if date_slot:
            slots["date"] = date_slot
        return {"intent": "date_filter", "needs_clarification": False, "slots": slots}

    # --- FILE SUMMARY (file name found, no category) ---
    if intent_type == "file_summary" or (file_name and not category):
        if file_name:
            slots["file_name"] = file_name
            return {"intent": "file_summary", "needs_clarification": False, "slots": slots}

    # --- FIND IN FILE (file + category) ---
    if intent_type == "find_in_file" or (file_name and category):
        if file_name:
            slots["file_name"] = file_name
        if category:
            slots["category"] = category
        if method:
            slots["method"] = method
        return {"intent": "find_in_file", "needs_clarification": False, "slots": slots}

    # --- AMBIGUOUS (category found but no file) ---
    if category and not file_name:
        slots["category"] = category
        if method:
            slots["method"] = method
        return {
            "intent": "ambiguous",
            "needs_clarification": True,
            "slots": slots,
            "clarification_question": (
                f"I found '{category}' in multiple files. "
                f"Which file are you looking for? Please specify the file name."
            )
        }

    if method and not file_name:
        slots["method"] = method
        return {
            "intent": "ambiguous",
            "needs_clarification": True,
            "slots": slots,
            "clarification_question": f"I found '{method}' in multiple files. Which file are you looking for?"
        }

    # --- GENERAL SEARCH fallback ---
    search_term = _extract_search_term(q_lower)
    if search_term:
        slots["search_term"] = search_term
    return {"intent": "general_search", "needs_clarification": False, "slots": slots}
