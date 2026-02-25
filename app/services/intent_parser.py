"""
Intent Parser
=============
Rule-based intent detection for AU-Ggregates AI queries.
Handles Taglish, typos, date parsing, and all 6 bug categories.
No ML model needed — pure logic based on real schema.
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime, date


# ============================================================================
# MONTH MAPPINGS (English + Tagalog)
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
# INTENT KEYWORDS
# ============================================================================
SHOW_WORDS = ["show", "ipakita", "pakita", "display", "tingnan", "i-show", "open", "buksan", "view"]
FIND_WORDS = ["find", "hanapin", "hanap", "search", "look for", "i-search", "locate", "get"]
COUNT_WORDS = ["count", "bilang", "ilang", "how many", "magkano", "count all", "how much"]
COMPARE_WORDS = ["compare", "ikumpara", "icompare", "difference", "vs", "versus", "between", "ano ang diff"]
LIST_WORDS = ["list", "ilista", "all", "lahat", "enumerate", "what are"]
SUM_WORDS = ["total", "sum", "kabuuan", "magkano lahat", "how much total", "overall"]


def parse_intent(query: str) -> Dict[str, Any]:
    """
    Parse user query into structured intent.
    
    Returns dict with:
    - intent: file_summary | find_category | list_categories | compare |
               count | sum | date_filter | ambiguous | general
    - needs_clarification: bool
    - slots: extracted entities
    - clarification_question: str (if needed)
    """
    q = query.strip()
    q_lower = q.lower()
    tokens = q_lower.split()

    slots = {}

    # ----------------------------------------------------------------
    # 1. COMPARE intent
    # ----------------------------------------------------------------
    if any(w in q_lower for w in COMPARE_WORDS):
        files = _extract_multiple_files(q_lower)
        category = _extract_category(q_lower)
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

    # ----------------------------------------------------------------
    # 2. COUNT intent
    # ----------------------------------------------------------------
    if any(q_lower.startswith(w) or f" {w} " in q_lower for w in COUNT_WORDS):
        date_slot = _extract_date(q_lower)
        file_name = _extract_single_file(q_lower)
        category = _extract_category(q_lower)
        if date_slot:
            slots["date"] = date_slot
        if file_name:
            slots["file_name"] = file_name
        if category:
            slots["category"] = category
        return {"intent": "count", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 3. SUM / TOTAL intent
    # ----------------------------------------------------------------
    if any(w in q_lower for w in SUM_WORDS):
        file_name = _extract_single_file(q_lower)
        category = _extract_category(q_lower)
        date_slot = _extract_date(q_lower)
        if file_name:
            slots["file_name"] = file_name
        if category:
            slots["category"] = category
        if date_slot:
            slots["date"] = date_slot
        return {"intent": "sum", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 4. LIST CATEGORIES intent
    # ----------------------------------------------------------------
    category_list_patterns = [
        r"(all|lahat).*(categor|kategorya)",
        r"(list|ilista).*(categor|kategorya)",
        r"(what|ano).*(categor|kategorya)",
        r"(show|pakita).*(categor|kategorya)",
        r"(categor|kategorya).*(list|all|lahat)",
    ]
    if any(re.search(p, q_lower) for p in category_list_patterns):
        file_name = _extract_single_file(q_lower)
        if file_name:
            slots["file_name"] = file_name
        return {"intent": "list_categories", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 4b. LIST FILES intent — "show all files", "list expenses files"
    # ----------------------------------------------------------------
    list_files_patterns = [
        r"(list|show|display|get)\b.*\b(all|my)?\s*(files?|records?|documents?)",
        r"(all|lahat)\b.*\b(files?|records?|documents?)",
        r"\b(files?|records?|documents?)\s*(list|all|lahat)",
        r"(list|show)\b.*\b(expenses?|cashflow)\s*(files?|records?)",
        r"\blist\s+of\b.*\b(expenses?|files?)",
    ]
    if any(re.search(p, q_lower) for p in list_files_patterns):
        return {"intent": "list_files", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 5. DATE FILTER intent
    # ----------------------------------------------------------------
    date_slot = _extract_date(q_lower)
    if date_slot:
        category = _extract_category(q_lower)
        file_name = _extract_single_file(q_lower)
        method = _extract_method(q_lower)
        if category:
            slots["category"] = category
        if file_name:
            slots["file_name"] = file_name
        if method:
            slots["method"] = method
        slots["date"] = date_slot
        return {"intent": "date_filter", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 6. FILE SUMMARY intent — query is just a file name or "show <file>"
    # ----------------------------------------------------------------
    file_name = _extract_single_file(q_lower)
    category = _extract_category(q_lower)

    # If we have a file name but NO category → file summary
    if file_name and not category:
        # Check if it's a pure file lookup (no row-level keywords)
        row_keywords = ["category", "kategorya", "fuel", "food", "car", "labor",
                        "cement", "steel", "sand", "gravel", "gcash", "cash",
                        "amount", "halaga", "method", "column"]
        has_row_keyword = any(w in q_lower for w in row_keywords)
        if not has_row_keyword:
            slots["file_name"] = file_name
            return {"intent": "file_summary", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 7. FIND CATEGORY IN FILE intent
    # ----------------------------------------------------------------
    if file_name and category:
        slots["file_name"] = file_name
        slots["category"] = category
        method = _extract_method(q_lower)
        if method:
            slots["method"] = method
        return {"intent": "find_in_file", "needs_clarification": False, "slots": slots}

    # ----------------------------------------------------------------
    # 8. AMBIGUOUS — category/method found but no file specified
    # ----------------------------------------------------------------
    if category:
        slots["category"] = category
        method = _extract_method(q_lower)
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

    method = _extract_method(q_lower)
    if method and not file_name:
        slots["method"] = method
        return {
            "intent": "ambiguous",
            "needs_clarification": True,
            "slots": slots,
            "clarification_question": (
                f"I found '{method}' in multiple files. "
                f"Which file are you looking for?"
            )
        }

    # ----------------------------------------------------------------
    # 9. GENERAL SEARCH fallback
    # ----------------------------------------------------------------
    # Strip common verbs and use remaining as search term
    search_term = _extract_search_term(q_lower)
    if search_term:
        slots["search_term"] = search_term
    return {"intent": "general_search", "needs_clarification": False, "slots": slots}


# ============================================================================
# ENTITY EXTRACTORS
# ============================================================================

def _extract_date(text: str) -> Optional[Dict]:
    """Extract date info — returns {type, value} or None."""
    year = datetime.now().year

    # Exact date: 2026-02-15 or 2026/2/15 or 2/15/2026
    m = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
    if m:
        return {"type": "exact", "value": f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"}

    m = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
    if m:
        return {"type": "exact", "value": f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"}

    # Month + day: "feb 15" or "february 15"
    m = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|'
                  r'jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|'
                  r'enero|pebrero|marso|abril|mayo|hunyo|hulyo|agosto|setyembre|oktubre|nobyembre|disyembre)'
                  r'\s+(\d{1,2})', text)
    if m:
        month_num = MONTH_MAP.get(m.group(1), 1)
        day = int(m.group(2))
        return {"type": "exact", "value": f"{year}-{month_num:02d}-{day:02d}"}

    # Month only: "in february", "nung february", "sa february"
    m = re.search(r'(?:in|nung|sa|ng|noong|during)?\s*(january|february|march|april|may|june|july|august|'
                  r'september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|'
                  r'enero|pebrero|marso|abril|mayo|hunyo|hulyo|agosto|setyembre|oktubre|nobyembre|disyembre)', text)
    if m:
        month_num = MONTH_MAP.get(m.group(1))
        if month_num:
            days = MONTH_DAYS.get(month_num, 30)
            return {
                "type": "month_range",
                "month": month_num,
                "start": f"{year}-{month_num:02d}-01",
                "end": f"{year}-{month_num:02d}-{days:02d}"
            }

    return None


def _extract_category(text: str) -> Optional[str]:
    """Extract expense category from query."""
    known_categories = [
        "fuel", "food", "car", "labor", "cement", "steel", "sand",
        "gravel", "tools", "equipment", "materials", "supplies",
        "electricity", "water", "rent", "salary", "wages"
    ]
    for cat in known_categories:
        if cat in text:
            return cat
    return None


def _extract_method(text: str) -> Optional[str]:
    """Extract payment method from query."""
    methods = ["gcash", "cash", "bank transfer", "check", "credit card", "debit"]
    for method in methods:
        if method in text:
            return method
    return None


def _extract_single_file(text: str) -> Optional[str]:
    """
    Extract a single file name from query by matching against actual
    file names in the database. Fully dynamic — no hardcoded patterns.
    """
    # Get known file names from database (cached)
    known_files = _get_known_file_names()
    
    if not known_files:
        return None
    
    text_lower = text.lower()
    
    # Sort by length descending so longer names match first
    # e.g., "francis gays" matches before "francis"
    sorted_files = sorted(known_files, key=len, reverse=True)
    
    for file_name in sorted_files:
        if file_name.lower() in text_lower:
            return file_name
    
    return None


# Cache for known file names
_file_name_cache: Optional[List[str]] = None
_file_name_cache_time: float = 0
_FILE_NAME_CACHE_TTL: float = 300  # 5 minutes


def _get_known_file_names() -> List[str]:
    """
    Fetch all distinct file_name values from ai_documents.
    Cached for 5 minutes to avoid hitting DB on every query.
    """
    import time as _time
    global _file_name_cache, _file_name_cache_time
    
    now = _time.time()
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
            # Fallback: get all distinct file names if no 'file' type entries
            rows = client.get("ai_documents", {
                "select": "file_name",
                "limit": "500"
            })
            _file_name_cache = list(set(r["file_name"] for r in rows if r.get("file_name")))
        
        _file_name_cache_time = now
        return _file_name_cache
    except Exception:
        return _file_name_cache or []


def _extract_multiple_files(text: str) -> List[str]:
    """Extract two file names for comparison queries."""
    # Pattern: "between X and Y" or "X and Y" or "X at Y" (Tagalog)
    m = re.search(r'between\s+(.+?)\s+and\s+(.+?)(?:\s|$)', text)
    if m:
        return [m.group(1).strip(), m.group(2).strip()]
    
    m = re.search(r'(.+?)\s+(?:and|at|vs|versus)\s+(.+?)(?:\s|$)', text)
    if m:
        f1 = m.group(1).strip()
        f2 = m.group(2).strip()
        # Clean up common words
        for w in ["compare", "ikumpara", "expenses", "between", "the"]:
            f1 = f1.replace(w, "").strip()
            f2 = f2.replace(w, "").strip()
        if f1 and f2:
            return [f1, f2]
    
    return []


def _looks_like_file_name(text: str) -> bool:
    """Heuristic: does this look like a file name vs a common word?"""
    common_words = {
        "show", "find", "get", "the", "all", "list", "count", "sum",
        "total", "compare", "help", "please", "what", "how", "many",
        "much", "are", "is", "for", "from", "with", "this", "that",
        "expenses", "cashflow", "category", "project", "file",
    }
    return text not in common_words and not text.isdigit()


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
