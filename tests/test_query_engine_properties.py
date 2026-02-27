"""
Property-based tests for QueryEngine.

Uses Hypothesis to verify formal correctness properties across random inputs.
Feature: schema-alignment-dynamic-columns
"""

from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.schema_registry import SchemaRegistry


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# All recognized source_table values plus None
_source_table_strategy = st.sampled_from(
    ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem", None]
)

# Intent types the QueryEngine dispatches on
_intent_type_strategy = st.sampled_from(
    [
        "list_files",
        "query_data",
        "count",
        "sum",
        "general_search",
        "list_categories",
        "date_filter",
    ]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_query_engine():
    """
    Create a QueryEngine with mocked Supabase client and real SchemaRegistry
    (backed by GLOBAL_SCHEMA, no DB calls).
    """
    from app.services.query_engine import QueryEngine

    mock_supabase = MagicMock()
    # supabase.get() returns an empty list (no rows) for any call
    mock_supabase.get.return_value = []

    # Use a real SchemaRegistry that falls back to GLOBAL_SCHEMA
    registry = SchemaRegistry(ttl=0)
    # Pre-populate cache with GLOBAL_SCHEMA so no DB call is attempted
    registry._cache = {k: list(v) for k, v in SchemaRegistry.GLOBAL_SCHEMA.items()}
    registry._cache_time = float("inf")  # never expires

    with patch("app.services.query_engine.get_supabase_client", return_value=mock_supabase), \
         patch("app.services.query_engine.get_schema_registry", return_value=registry):
        engine = QueryEngine()

    return engine


# ---------------------------------------------------------------------------
# Property 6: Query engine handles all source_table values without error
# ---------------------------------------------------------------------------


class TestProperty6QueryEngineAllSourceTables:
    """
    Property 6: Query engine handles all source_table values without error.

    For any recognized source_table value (Expenses, CashFlow, Project,
    Quotation, QuotationItem, or None), the QueryEngine.execute() method
    SHALL process the intent without raising an unhandled exception, and
    SHALL return a result dict with ``data``, ``message``, and ``row_count`` keys.

    **Validates: Requirements 3.3, 4.3, 5.3, 7.4**

    # Feature: schema-alignment-dynamic-columns, Property 6: Query engine handles all source_table values without error
    """

    @given(
        source_table=_source_table_strategy,
        intent_type=_intent_type_strategy,
    )
    @settings(max_examples=100)
    def test_execute_returns_valid_result_for_all_source_tables(
        self, source_table, intent_type
    ):
        """execute() returns a result dict with data, message, row_count keys
        for every combination of source_table and intent_type.

        **Validates: Requirements 3.3, 4.3, 5.3, 7.4**
        """
        engine = _make_query_engine()

        intent = {
            "intent": intent_type,
            "slots": {"source_table": source_table},
        }

        # Must not raise
        result = engine.execute(intent)

        # Result must be a dict with the required keys
        assert isinstance(result, dict), (
            f"Expected dict, got {type(result).__name__}"
        )
        assert "data" in result, (
            f"Missing 'data' key for source_table={source_table}, intent={intent_type}"
        )
        assert "message" in result, (
            f"Missing 'message' key for source_table={source_table}, intent={intent_type}"
        )
        assert "row_count" in result, (
            f"Missing 'row_count' key for source_table={source_table}, intent={intent_type}"
        )

    @given(source_table=_source_table_strategy)
    @settings(max_examples=100)
    def test_execute_no_unhandled_exception(self, source_table):
        """execute() never raises an unhandled exception for any source_table,
        even with minimal/empty slots.

        **Validates: Requirements 3.3, 4.3, 5.3, 7.4**
        """
        engine = _make_query_engine()

        # Minimal intent — just source_table, no other slots
        intent = {
            "intent": "general_search",
            "slots": {"source_table": source_table, "search_term": "test"},
        }

        # Must not raise
        result = engine.execute(intent)

        assert isinstance(result, dict)
        assert "data" in result
        assert "message" in result
        assert "row_count" in result
