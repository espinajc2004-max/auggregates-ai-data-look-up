"""
Property-based tests for JSONB converter in Phi3Service.

Uses Hypothesis to verify that _convert_to_jsonb_sql correctly maps column
references to JSONB accessor patterns using SchemaRegistry.

Feature: schema-alignment-dynamic-columns
"""

import re

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.schema_registry import SchemaRegistry
from app.services.phi3_service import Phi3Service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_with_schema(schema: dict) -> SchemaRegistry:
    """Create a SchemaRegistry pre-loaded with the given schema (no DB calls)."""
    registry = SchemaRegistry.__new__(SchemaRegistry)
    registry._cache = {k: list(v) for k, v in schema.items()}
    registry._cache_time = float("inf")  # never expires
    registry._ttl = SchemaRegistry.DEFAULT_TTL
    return registry


def _make_service(registry: SchemaRegistry) -> Phi3Service:
    """Create a Phi3Service without loading models, wired to the given registry."""
    service = Phi3Service.__new__(Phi3Service)
    service.schema_registry = registry
    return service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Pick a source_table from GLOBAL_SCHEMA keys
_source_table_strategy = st.sampled_from(list(SchemaRegistry.GLOBAL_SCHEMA.keys()))


@st.composite
def _source_table_and_key(draw):
    """Draw a (source_table, key) pair from GLOBAL_SCHEMA."""
    source_table = draw(_source_table_strategy)
    keys = SchemaRegistry.GLOBAL_SCHEMA[source_table]
    key = draw(st.sampled_from(keys))
    return source_table, key


# ---------------------------------------------------------------------------
# Property 2: JSONB converter maps column references to correct metadata accessors
# ---------------------------------------------------------------------------


class TestProperty2JSONBConverterKeyMapping:
    """
    # Feature: schema-alignment-dynamic-columns, Property 2: JSONB converter maps column references to correct metadata accessors

    For any source_table and for any metadata key known to the SchemaRegistry
    for that source_table, when the JSONB converter processes SQL containing a
    column reference matching that key (case-insensitive), the output SQL SHALL
    contain `metadata->>'CorrectKey'` with the properly-cased key name.

    **Validates: Requirements 1.2, 1.4, 1.5, 2.3, 2.5, 3.5, 6.5, 8.1, 8.3, 8.4**
    """

    @given(data=_source_table_and_key())
    @settings(max_examples=100)
    def test_key_mapped_to_correct_jsonb_accessor(self, data):
        """Column reference in WHERE clause maps to metadata->>'CorrectKey'.

        **Validates: Requirements 1.2, 1.4, 1.5, 2.3, 2.5, 3.5, 6.5, 8.1, 8.3, 8.4**
        """
        source_table, key = data

        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        # Build SQL with the key lowercased (simulating T5 output)
        sql = f"SELECT * FROM expenses WHERE {key.lower()} = 'test_value'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert f"metadata->>'{key}'" in result, (
            f"Expected metadata->>'{key}' in output for source_table={source_table}, "
            f"key={key}.\nInput SQL: {sql}\nOutput SQL: {result}"
        )

    @given(data=_source_table_and_key())
    @settings(max_examples=100)
    def test_case_insensitive_key_matching(self, data):
        """Column references match case-insensitively but output uses proper case.

        **Validates: Requirements 8.3, 8.4**
        """
        source_table, key = data

        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        # Use UPPERCASE version of the key in the SQL
        sql = f"SELECT * FROM data WHERE {key.upper()} = 'some_value'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert f"metadata->>'{key}'" in result, (
            f"Case-insensitive match failed: expected metadata->>'{key}' "
            f"for uppercase input '{key.upper()}'.\nOutput SQL: {result}"
        )

    @given(data=_source_table_and_key())
    @settings(max_examples=100)
    def test_key_produces_ilike_pattern(self, data):
        """WHERE clause with key = 'value' is converted to ILIKE pattern.

        **Validates: Requirements 8.1**
        """
        source_table, key = data

        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = f"SELECT * FROM expenses WHERE {key.lower()} = 'test_value'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        expected_fragment = f"metadata->>'{key}' ILIKE '%test_value%'"
        assert expected_fragment in result, (
            f"Expected ILIKE pattern '{expected_fragment}' in output.\n"
            f"Output SQL: {result}"
        )

    @given(source_table=_source_table_strategy)
    @settings(max_examples=100)
    def test_all_keys_for_source_table_are_mappable(self, source_table):
        """Every key for a given source_table can be mapped by the converter.

        **Validates: Requirements 6.5, 8.1, 8.4**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        keys = SchemaRegistry.GLOBAL_SCHEMA[source_table]

        for key in keys:
            sql = f"SELECT * FROM data WHERE {key.lower()} = 'val'"
            intent = {"source_table": source_table}
            result = service._convert_to_jsonb_sql(sql, intent)

            assert f"metadata->>'{key}'" in result, (
                f"Key '{key}' for source_table '{source_table}' was not mapped.\n"
                f"Output SQL: {result}"
            )


# ---------------------------------------------------------------------------
# Strategies for Property 3
# ---------------------------------------------------------------------------

# Numeric keys mapped to a source_table that contains them
_numeric_key_to_source_table = {
    "Expenses": "Expenses",
    "Amount": "CashFlow",
    "total_amount": "Quotation",
    "volume": "QuotationItem",
    "line_total": "QuotationItem",
}

_numeric_key_strategy = st.sampled_from(list(_numeric_key_to_source_table.keys()))
_aggregate_fn_strategy = st.sampled_from(["SUM", "AVG", "MIN", "MAX"])


# ---------------------------------------------------------------------------
# Property 3: Numeric keys receive ::numeric casting in aggregates
# ---------------------------------------------------------------------------


class TestProperty3NumericKeyCasting:
    """
    # Feature: schema-alignment-dynamic-columns, Property 3: Numeric keys receive ::numeric casting in aggregates

    For any metadata key in the NUMERIC_KEYS set and for any SQL aggregate
    function (SUM, AVG, MIN, MAX), the JSONB converter SHALL produce
    FUNC((metadata->>'Key')::numeric) in the output SQL.

    **Validates: Requirements 4.5, 5.5, 8.2**
    """

    @given(numeric_key=_numeric_key_strategy, agg_fn=_aggregate_fn_strategy)
    @settings(max_examples=100)
    def test_numeric_key_gets_numeric_cast_in_aggregate(self, numeric_key, agg_fn):
        """Aggregate on a numeric key produces ::numeric casting.

        **Validates: Requirements 4.5, 5.5, 8.2**
        """
        source_table = _numeric_key_to_source_table[numeric_key]

        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = f"SELECT {agg_fn}({numeric_key.lower()}) FROM data"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        expected = f"{agg_fn}((metadata->>'{numeric_key}')::numeric)"
        assert expected in result, (
            f"Expected '{expected}' in output for key={numeric_key}, "
            f"agg={agg_fn}.\nInput SQL: {sql}\nOutput SQL: {result}"
        )

    @given(numeric_key=_numeric_key_strategy, agg_fn=_aggregate_fn_strategy)
    @settings(max_examples=100)
    def test_numeric_cast_present_regardless_of_aggregate_function(self, numeric_key, agg_fn):
        """All aggregate functions (SUM, AVG, MIN, MAX) apply ::numeric to numeric keys.

        **Validates: Requirements 8.2**
        """
        source_table = _numeric_key_to_source_table[numeric_key]

        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = f"SELECT {agg_fn}({numeric_key.lower()}) FROM data"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "::numeric" in result, (
            f"Expected ::numeric casting for numeric key '{numeric_key}' "
            f"with {agg_fn}.\nOutput SQL: {result}"
        )


# ---------------------------------------------------------------------------
# Strategies for Property 7
# ---------------------------------------------------------------------------

_source_table_or_none_strategy = st.sampled_from(
    ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem", None]
)


# ---------------------------------------------------------------------------
# Property 7: JSONB converter injects correct source_table filter
# ---------------------------------------------------------------------------


class TestProperty7SourceTableFilterInjection:
    """
    # Feature: schema-alignment-dynamic-columns, Property 7: JSONB converter injects correct source_table filter

    For any source_table value provided in the intent, the JSONB converter SHALL
    inject source_table = 'Value' into the WHERE clause of the output SQL. When
    source_table is None, no source_table filter SHALL be injected.

    **Validates: Requirements 8.5**
    """

    @given(source_table=_source_table_or_none_strategy)
    @settings(max_examples=100)
    def test_source_table_filter_injected_when_provided(self, source_table):
        """source_table = 'Value' appears in output when source_table is not None.

        **Validates: Requirements 8.5**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = "SELECT * FROM data WHERE metadata->>'Category' ILIKE '%fuel%'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        if source_table is not None:
            assert f"source_table = '{source_table}'" in result, (
                f"Expected source_table = '{source_table}' in output.\n"
                f"Output SQL: {result}"
            )
        else:
            assert "source_table" not in result.lower(), (
                f"Expected NO source_table filter when source_table is None.\n"
                f"Output SQL: {result}"
            )

    @given(source_table=st.sampled_from(
        ["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]
    ))
    @settings(max_examples=100)
    def test_source_table_filter_in_where_clause(self, source_table):
        """source_table filter is placed in the WHERE clause.

        **Validates: Requirements 8.5**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = "SELECT * FROM data WHERE metadata->>'Category' ILIKE '%fuel%'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        # The filter should be in the WHERE clause
        where_idx = result.upper().find("WHERE")
        assert where_idx >= 0, f"No WHERE clause found.\nOutput SQL: {result}"

        where_clause = result[where_idx:]
        assert f"source_table = '{source_table}'" in where_clause, (
            f"source_table filter not in WHERE clause.\nOutput SQL: {result}"
        )

    @given(source_table=st.just(None))
    @settings(max_examples=100)
    def test_no_source_table_filter_when_none(self, source_table):
        """No source_table filter injected when source_table is None (cross-table).

        **Validates: Requirements 8.5**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = "SELECT * FROM data WHERE metadata->>'Category' ILIKE '%fuel%'"
        intent = {"source_table": source_table}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "source_table =" not in result, (
            f"source_table filter should NOT be present when source_table is None.\n"
            f"Output SQL: {result}"
        )


# ---------------------------------------------------------------------------
# Strategies for Property 12
# ---------------------------------------------------------------------------

# Collect all known keys (lowercased) from GLOBAL_SCHEMA
_all_known_keys_lower = set()
for _keys in SchemaRegistry.GLOBAL_SCHEMA.values():
    for _k in _keys:
        _all_known_keys_lower.add(_k.lower())

# SQL keywords to avoid in generated key names
_sql_keywords = {
    "select", "from", "where", "and", "or", "not", "in", "like", "ilike",
    "order", "group", "by", "limit", "offset", "as", "on", "join",
    "source_table", "file_name", "project_name", "document_type", "metadata",
}

_unknown_key_strategy = st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True).filter(
    lambda k: k not in _all_known_keys_lower and k not in _sql_keywords
)


# ---------------------------------------------------------------------------
# Property 12: Unknown metadata keys pass through as-is
# ---------------------------------------------------------------------------


class TestProperty12UnknownKeysPassthrough:
    """
    # Feature: schema-alignment-dynamic-columns, Property 12: Unknown metadata keys pass through as-is

    For any metadata key name not present in the SchemaRegistry's known keys,
    the JSONB converter SHALL use that key name directly in the JSONB accessor
    pattern (metadata->>'unknown_key') without error.

    **Validates: Requirements 11.5**
    """

    @given(unknown_key=_unknown_key_strategy)
    @settings(max_examples=100)
    def test_unknown_key_becomes_jsonb_accessor(self, unknown_key):
        """Unknown keys are converted to metadata->>'{key}' passthrough.

        **Validates: Requirements 11.5**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = f"SELECT * FROM data WHERE {unknown_key} = 'some_value'"
        intent = {"source_table": None}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert f"metadata->>'{unknown_key}'" in result, (
            f"Expected metadata->>'{unknown_key}' for unknown key passthrough.\n"
            f"Input SQL: {sql}\nOutput SQL: {result}"
        )

    @given(unknown_key=_unknown_key_strategy)
    @settings(max_examples=100)
    def test_unknown_key_does_not_raise(self, unknown_key):
        """Processing unknown keys does not raise any exception.

        **Validates: Requirements 11.5**
        """
        registry = _make_registry_with_schema(SchemaRegistry.GLOBAL_SCHEMA)
        service = _make_service(registry)

        sql = f"SELECT * FROM data WHERE {unknown_key} = 'test'"
        intent = {"source_table": None}

        # Should not raise
        result = service._convert_to_jsonb_sql(sql, intent)
        assert isinstance(result, str)
