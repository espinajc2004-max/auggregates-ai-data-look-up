"""
Entity extraction utilities for extracting search keywords from user queries.
"""

from typing import List, Optional


# Common words to ignore when extracting search keywords
STOP_WORDS = {
    "show", "find", "search", "get", "list", "display",
    "all", "the", "a", "an", "for", "in", "on", "at", "to", "of", "with",
    "expenses", "expense", "cashflow", "cash", "flow", "quotation", "product",
    "data", "entry", "value", "values", "records", "record", "please",
    "today", "project", "projects", "look", "up", "lookup",
    "price", "amount", "cost", "total", "specific", "only", "just", "that"
}


def extract_search_terms(query: str) -> List[str]:
    """Extract potential search keywords from user query.
    
    Args:
        query: The user's natural language query
        
    Returns:
        List of extracted keywords (excluding stop words)
    """
    words = query.lower().split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    return keywords


def extract_search_term(query: str) -> Optional[str]:
    """Extract the first search keyword from user query.
    
    Args:
        query: The user's natural language query
        
    Returns:
        First keyword found, or None if no keywords
    """
    terms = extract_search_terms(query)
    return terms[0] if terms else None
