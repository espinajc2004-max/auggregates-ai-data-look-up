"""
Property-based tests for intent parser source table detection.

Uses Hypothesis to verify formal correctness properties across random inputs.
Feature: schema-alignment-dynamic-columns
"""

from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.schema_registry import SchemaRegistry


# ---------------------------------------------------------------------------
# Collect all keywords for reuse in strategies
# ---------------------------------------------------------------------------

_ALL_KEYWORDS: dict[str, list[str]] = dict(SchemaRegistry.SOURCE_TABLE_KEYWORDS)

# Flat set of every keyword (lowercased) across all source tables
_ALL_KEYWORD_STRINGS: set[str] = set()
for _kw_list in _ALL_KEYWORDS.values():
    for _kw in _kw_list:
        _ALL_KEYWORD_STRINGS.add(_kw.lower())


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Pick a random (source_table, keyword) pair from SOURCE_TABLE_KEYWORDS
_source_table_keyword_pair = st.sampled_from([
    (table, kw)
    for table, keywords in _ALL_KEYWORDS.items()
    for kw in keywords
])

# Safe filler words that won't accidentally contain any keyword substring
_SAFE_WORDS = [
    "show", "me", "the", "data", "please", "find", "all", "records",
    "for", "this", "year", "today", "report", "summary", "total",
    "list", "display", "get", "how", "much", "many", "what", "is",
    "are", "from", "last", "month", "week", "hello", "help",
    "info", "details", "number", "count", "average", "minimum",
    "maximum", "per", "each", "every", "recent", "latest",
]

# Filter safe words to ensure none contain any keyword as a substring
_TRULY_SAFE_WORDS = [
    w for w in _SAFE_WORDS
    if not any(kw in w.lower() for kw in _ALL_KEYWORD_STRINGS)
]

# Strategy for filler text that contains no keywords
_safe_filler = st.lists(
    st.sampled_from(_TRULY_SAFE_WORDS),
    min_size=1,
    max_size=8,
).map(lambda words: " ".join(words))


# ---------------------------------------------------------------------------
# Property 4: Source table keyword detection returns correct source_table
# ---------------------------------------------------------------------------


class TestProperty4SourceTableKeywordDetection:
    """
    Property 4: Source table keyword detection returns correct source_table.

    For any keyword in the SOURCE_TABLE_KEYWORDS mapping and for any query
    string containing that keyword, detect_source_table() SHALL return the
    source_table associated with that keyword.

    **Validates: Requirements 3.2, 4.2, 5.2, 7.1, 7.2**

    # Feature: schema-alignment-dynamic-columns, Property 4: Source table keyword detection returns correct source_table
    """

    @given(
        pair=_source_table_keyword_pair,
        prefix=_safe_filler,
        suffix=_safe_filler,
    )
    @settings(max_examples=100)
    def test_keyword_in_query_returns_correct_source_table(
        self, pair: tuple, prefix: str, suffix: str
    ):
        """A query containing exactly one source table's keyword returns that
        source_table.

        **Validates: Requirements 3.2, 4.2, 5.2, 7.1, 7.2**
        """
        expected_table, keyword = pair

        # Build query: safe prefix + keyword + safe suffix
        query = f"{prefix} {keyword} {suffix}"

        # Ensure no OTHER table's keywords accidentally appear in the query
        query_lower = query.lower()
        other_tables_matched = set()
        for table, keywords in _ALL_KEYWORDS.items():
            if table == expected_table:
                continue
            for kw in keywords:
                if kw in query_lower:
                    other_tables_matched.add(table)
                    break

        # Skip ambiguous queries — they'd correctly return None
        assume(len(other_tables_matched) == 0)

        registry = SchemaRegistry(ttl=300)

        # Mock get_schema_registry so _detect_source_table delegates to our registry
        with patch(
            "app.services.intent_parser.get_schema_registry",
            return_value=registry,
        ):
            from app.services.intent_parser import _detect_source_table
            result = _detect_source_table(query)

        assert result == expected_table, (
            f"Expected '{expected_table}' for keyword '{keyword}' in query "
            f"'{query}', got '{result}'"
        )


# ---------------------------------------------------------------------------
# Property 5: Queries without source-table keywords return None
# ---------------------------------------------------------------------------


class TestProperty5NoKeywordsReturnsNone:
    """
    Property 5: Queries without source-table keywords return None.

    For any query string that contains none of the keywords from any
    SOURCE_TABLE_KEYWORDS entry, detect_source_table() SHALL return None.

    **Validates: Requirements 7.3**

    # Feature: schema-alignment-dynamic-columns, Property 5: Queries without source-table keywords return None
    """

    @given(query=_safe_filler)
    @settings(max_examples=100)
    def test_no_keywords_returns_none(self, query: str):
        """A query with no source-table keywords returns None.

        **Validates: Requirements 7.3**
        """
        # Double-check: the generated query must not contain ANY keyword
        query_lower = query.lower()
        assume(
            not any(kw in query_lower for kw in _ALL_KEYWORD_STRINGS)
        )

        registry = SchemaRegistry(ttl=300)

        with patch(
            "app.services.intent_parser.get_schema_registry",
            return_value=registry,
        ):
            from app.services.intent_parser import _detect_source_table
            result = _detect_source_table(query)

        assert result is None, (
            f"Expected None for keyword-free query '{query}', got '{result}'"
        )
