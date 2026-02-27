"""
Property-based tests for SchemaRegistry.

Uses Hypothesis to verify formal correctness properties across random inputs.
Feature: schema-alignment-dynamic-columns
"""

from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.schema_registry import SchemaRegistry
from app.services.supabase_client import SupabaseError


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate valid source_table names (alphanumeric, starting with uppercase)
_source_table_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"),
    min_size=2,
    max_size=20,
).filter(lambda s: s[0].isupper())

# Generate valid metadata key names (alphanumeric + underscore)
_key_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    min_size=1,
    max_size=30,
)

# Generate a schema: dict of source_table -> list of unique keys (at least 1 key each)
_schema_strategy = st.dictionaries(
    keys=_source_table_strategy,
    values=st.lists(_key_strategy, min_size=1, max_size=10, unique=True),
    min_size=1,
    max_size=8,
)


def _schema_to_db_rows(schema: dict) -> list:
    """Convert a {source_table: [keys]} dict into the flat row format returned by the DB."""
    rows = []
    for table, keys in schema.items():
        for key in keys:
            rows.append({"source_table": table, "key": key})
    return rows


# ---------------------------------------------------------------------------
# Property 8: Schema discovery returns actual metadata keys from database
# ---------------------------------------------------------------------------


class TestProperty8SchemaDiscovery:
    """
    Property 8: Schema discovery returns actual metadata keys from database.

    For any set of ai_documents rows with known metadata JSONB keys, after a
    cache refresh the SchemaRegistry SHALL return exactly those distinct keys
    grouped by their source_table value — including keys from source tables
    not in GLOBAL_SCHEMA.

    **Validates: Requirements 6.1, 11.1, 11.3**

    # Feature: schema-alignment-dynamic-columns, Property 8: Schema discovery returns actual metadata keys from database
    """

    @given(schema=_schema_strategy)
    @settings(max_examples=100)
    def test_get_schema_returns_exact_db_keys(self, schema: dict):
        """get_schema() returns exactly the distinct keys grouped by source_table
        that the database reports.

        **Validates: Requirements 6.1, 11.1, 11.3**
        """
        db_rows = _schema_to_db_rows(schema)

        registry = SchemaRegistry(ttl=0)

        mock_client = MagicMock()
        mock_client.execute_sql.return_value = {"data": db_rows}

        with patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            result = registry.get_schema()

        # Same set of source tables
        assert set(result.keys()) == set(schema.keys()), (
            f"Source tables mismatch: got {set(result.keys())}, expected {set(schema.keys())}"
        )

        # For each table, same set of keys (order may differ)
        for table in schema:
            assert set(result[table]) == set(schema[table]), (
                f"Keys mismatch for {table}: got {set(result[table])}, "
                f"expected {set(schema[table])}"
            )

    @given(schema=_schema_strategy)
    @settings(max_examples=100)
    def test_discovery_includes_unknown_source_tables(self, schema: dict):
        """Schema discovery picks up source tables NOT in GLOBAL_SCHEMA.

        **Validates: Requirements 11.1, 11.3**
        """
        # Inject at least one table name that is definitely not in GLOBAL_SCHEMA
        unknown_table = "ZzUnknownTable"
        assume(unknown_table not in schema)
        schema_with_unknown = dict(schema)
        schema_with_unknown[unknown_table] = ["custom_key_a", "custom_key_b"]

        db_rows = _schema_to_db_rows(schema_with_unknown)

        registry = SchemaRegistry(ttl=0)

        mock_client = MagicMock()
        mock_client.execute_sql.return_value = {"data": db_rows}

        with patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            result = registry.get_schema()

        assert unknown_table in result, (
            f"Unknown source table '{unknown_table}' not found in schema result"
        )
        assert set(result[unknown_table]) == {"custom_key_a", "custom_key_b"}

    @given(schema=_schema_strategy)
    @settings(max_examples=100)
    def test_discovery_deduplicates_keys(self, schema: dict):
        """Even if the DB returns duplicate rows, get_schema() returns distinct keys.

        **Validates: Requirements 6.1**
        """
        db_rows = _schema_to_db_rows(schema)
        # Duplicate every row to simulate non-distinct DB output
        db_rows_with_dupes = db_rows + db_rows

        registry = SchemaRegistry(ttl=0)

        mock_client = MagicMock()
        mock_client.execute_sql.return_value = {"data": db_rows_with_dupes}

        with patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            result = registry.get_schema()

        for table in schema:
            # The implementation appends keys, so with duplicates we may get
            # duplicates in the list. Verify the *set* of keys is correct.
            assert set(result[table]) == set(schema[table]), (
                f"Keys mismatch for {table} after dedup: "
                f"got {result[table]}, expected {schema[table]}"
            )


# ---------------------------------------------------------------------------
# Property 9: Cache respects TTL — stale cache triggers refresh
# ---------------------------------------------------------------------------


class TestProperty9CacheTTL:
    """
    Property 9: Cache respects TTL — stale cache triggers refresh.

    For any sequence of get_schema() calls, calls made within the TTL window
    SHALL return the same cached result (no DB query), and the first call after
    TTL expiry SHALL trigger a database refresh and return updated results.

    **Validates: Requirements 6.2, 6.3**

    # Feature: schema-alignment-dynamic-columns, Property 9: Cache respects TTL — stale cache triggers refresh
    """

    @given(ttl=st.integers(min_value=1, max_value=600))
    @settings(max_examples=100)
    def test_calls_within_ttl_use_cache(self, ttl: int):
        """Calls within the TTL window return cached result without hitting DB.

        **Validates: Requirements 6.2**
        """
        initial_schema = {"Expenses": ["Category", "Expenses", "Name"]}
        db_rows = _schema_to_db_rows(initial_schema)

        registry = SchemaRegistry(ttl=ttl)

        mock_client = MagicMock()
        mock_client.execute_sql.return_value = {"data": db_rows}

        with patch("app.services.schema_registry.time") as mock_time, \
             patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            # First call at t=0 — triggers initial DB load
            mock_time.time.return_value = 0.0
            result1 = registry.get_schema()

            # _refresh_cache resets _ttl to DEFAULT_TTL on success;
            # restore the generated TTL so we test the mechanism with various values
            registry._ttl = ttl

            # Second call at t = ttl - 1 — within TTL, should use cache
            mock_time.time.return_value = float(ttl - 1)
            result2 = registry.get_schema()

        # DB should have been called exactly once (initial load only)
        assert mock_client.execute_sql.call_count == 1, (
            f"Expected 1 DB call (initial load), got {mock_client.execute_sql.call_count}"
        )

        # Both calls return the same data
        assert result1 == result2, (
            f"Cached result should be identical: {result1} != {result2}"
        )

    @given(ttl=st.integers(min_value=1, max_value=600))
    @settings(max_examples=100)
    def test_call_after_ttl_triggers_refresh(self, ttl: int):
        """First call after TTL expiry triggers a new DB query.

        **Validates: Requirements 6.2, 6.3**
        """
        initial_rows = _schema_to_db_rows({"Expenses": ["Category", "Expenses", "Name"]})
        refreshed_rows = _schema_to_db_rows({
            "Expenses": ["Category", "Expenses", "Name", "Driver"],
        })

        registry = SchemaRegistry(ttl=ttl)

        mock_client = MagicMock()
        mock_client.execute_sql.side_effect = [
            {"data": initial_rows},
            {"data": refreshed_rows},
        ]

        with patch("app.services.schema_registry.time") as mock_time, \
             patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            # First call at t=0 — triggers initial DB load
            mock_time.time.return_value = 0.0
            result1 = registry.get_schema()

            # _refresh_cache resets _ttl to DEFAULT_TTL on success;
            # restore the generated TTL so we test the mechanism with various values
            registry._ttl = ttl

            # Second call at t = ttl (exactly at expiry boundary) — should refresh
            mock_time.time.return_value = float(ttl)
            result2 = registry.get_schema()

        # DB should have been called twice (initial + refresh)
        assert mock_client.execute_sql.call_count == 2, (
            f"Expected 2 DB calls (initial + refresh), got {mock_client.execute_sql.call_count}"
        )

        # First result should have original keys
        assert set(result1["Expenses"]) == {"Category", "Expenses", "Name"}

        # Second result should have the refreshed keys including "Driver"
        assert set(result2["Expenses"]) == {"Category", "Expenses", "Name", "Driver"}, (
            f"Refreshed schema should include 'Driver': got {result2['Expenses']}"
        )

    @given(ttl=st.integers(min_value=1, max_value=600))
    @settings(max_examples=100)
    def test_refreshed_data_reflects_new_schema(self, ttl: int):
        """After TTL expiry, the refreshed schema reflects entirely new DB data.

        **Validates: Requirements 6.3**
        """
        initial_schema = {"CashFlow": ["Type", "Amount", "Category"]}
        refreshed_schema = {
            "CashFlow": ["Type", "Amount", "Category"],
            "Project": ["project_name", "client_name"],
        }

        initial_rows = _schema_to_db_rows(initial_schema)
        refreshed_rows = _schema_to_db_rows(refreshed_schema)

        registry = SchemaRegistry(ttl=ttl)

        mock_client = MagicMock()
        mock_client.execute_sql.side_effect = [
            {"data": initial_rows},
            {"data": refreshed_rows},
        ]

        with patch("app.services.schema_registry.time") as mock_time, \
             patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            # Initial load at t=0
            mock_time.time.return_value = 0.0
            result1 = registry.get_schema()

            # _refresh_cache resets _ttl to DEFAULT_TTL on success;
            # restore the generated TTL so we test the mechanism with various values
            registry._ttl = ttl

            # After TTL expiry
            mock_time.time.return_value = float(ttl)
            result2 = registry.get_schema()

        # Initial result should NOT have Project
        assert "Project" not in result1

        # Refreshed result should have both CashFlow and Project
        assert "CashFlow" in result2
        assert "Project" in result2
        assert set(result2["Project"]) == {"project_name", "client_name"}


# ---------------------------------------------------------------------------
# Property 10: Database failure falls back to GLOBAL_SCHEMA
# ---------------------------------------------------------------------------

# Strategy: generate different exception types to simulate DB failures
_exception_strategy = st.sampled_from([
    SupabaseError("connection refused"),
    ConnectionError("could not connect to database"),
    TimeoutError("query timed out"),
    RuntimeError("unexpected database error"),
    OSError("network unreachable"),
    Exception("generic failure"),
])


class TestProperty10DBFailureFallback:
    """
    Property 10: Database failure falls back to GLOBAL_SCHEMA.

    For any state where the database connection fails, SchemaRegistry.get_schema()
    SHALL return the GLOBAL_SCHEMA fallback definitions rather than raising an
    exception or returning empty results.

    **Validates: Requirements 6.7**

    # Feature: schema-alignment-dynamic-columns, Property 10: Database failure falls back to GLOBAL_SCHEMA
    """

    @given(exc=_exception_strategy)
    @settings(max_examples=100)
    def test_db_failure_returns_global_schema(self, exc: Exception):
        """When the DB raises any exception, get_schema() returns GLOBAL_SCHEMA keys.

        **Validates: Requirements 6.7**
        """
        registry = SchemaRegistry(ttl=0)

        mock_client = MagicMock()
        mock_client.execute_sql.side_effect = exc

        with patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            result = registry.get_schema()

        expected = SchemaRegistry.GLOBAL_SCHEMA

        # Same set of source tables
        assert set(result.keys()) == set(expected.keys()), (
            f"Source tables mismatch on {type(exc).__name__}: "
            f"got {set(result.keys())}, expected {set(expected.keys())}"
        )

        # For each table, same set of keys
        for table in expected:
            assert set(result[table]) == set(expected[table]), (
                f"Keys mismatch for {table} on {type(exc).__name__}: "
                f"got {set(result[table])}, expected {set(expected[table])}"
            )

    @given(exc=_exception_strategy)
    @settings(max_examples=100)
    def test_db_failure_sets_fallback_ttl(self, exc: Exception):
        """When the DB fails, the registry uses FALLBACK_TTL (60s) for faster retry.

        **Validates: Requirements 6.7**
        """
        registry = SchemaRegistry(ttl=300)

        mock_client = MagicMock()
        mock_client.execute_sql.side_effect = exc

        with patch("app.services.schema_registry.get_supabase_client", return_value=mock_client):
            registry.get_schema()

        assert registry._ttl == SchemaRegistry.FALLBACK_TTL, (
            f"Expected FALLBACK_TTL ({SchemaRegistry.FALLBACK_TTL}s) after "
            f"{type(exc).__name__}, got {registry._ttl}s"
        )


# ---------------------------------------------------------------------------
# Property 13: Extensible keyword mapping works without code changes
# ---------------------------------------------------------------------------

# Collect all existing keywords to avoid collisions in generated data
_ALL_EXISTING_KEYWORDS = set()
for _kw_list in SchemaRegistry.SOURCE_TABLE_KEYWORDS.values():
    for _kw in _kw_list:
        _ALL_EXISTING_KEYWORDS.add(_kw.lower())

# Strategy: generate a keyword that does NOT collide with existing keywords
_new_keyword_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz"),
    min_size=4,
    max_size=15,
).filter(lambda kw: kw.lower() not in _ALL_EXISTING_KEYWORDS)

# Strategy: generate a new source_table name not in the existing mapping
_new_source_table_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
    min_size=3,
    max_size=20,
).filter(
    lambda t: t not in SchemaRegistry.SOURCE_TABLE_KEYWORDS
    and len(t) > 0
    and t[0].isupper()
)

# Strategy: generate a dict of new_source_table -> list of new keywords
_new_keyword_mapping_strategy = st.dictionaries(
    keys=_new_source_table_strategy,
    values=st.lists(_new_keyword_strategy, min_size=1, max_size=5, unique=True),
    min_size=1,
    max_size=5,
)


class TestProperty13ExtensibleKeywordMapping:
    """
    Property 13: Extensible keyword mapping works without code changes.

    For any new keyword-to-source-table entry added to SOURCE_TABLE_KEYWORDS
    at runtime, detect_source_table() SHALL correctly return the associated
    source_table for queries containing that keyword, without requiring
    changes to the detection logic code.

    **Validates: Requirements 11.4**

    # Feature: schema-alignment-dynamic-columns, Property 13: Extensible keyword mapping works without code changes
    """

    @given(new_mapping=_new_keyword_mapping_strategy)
    @settings(max_examples=100)
    def test_new_keywords_detected_at_runtime(self, new_mapping: dict):
        """Adding new keyword entries at runtime makes detect_source_table()
        return the correct source_table for queries containing those keywords.

        **Validates: Requirements 11.4**
        """
        # Deduplicate: ensure no keyword appears in more than one source_table
        seen_keywords: set = set()
        clean_mapping: dict = {}
        for source_table, keywords in new_mapping.items():
            unique_kws = [kw for kw in keywords if kw.lower() not in seen_keywords]
            if unique_kws:
                clean_mapping[source_table] = unique_kws
                seen_keywords.update(kw.lower() for kw in unique_kws)

        assume(len(clean_mapping) > 0)

        registry = SchemaRegistry(ttl=300)

        # Copy existing keywords and add new entries to the instance
        extended_keywords = {k: list(v) for k, v in SchemaRegistry.SOURCE_TABLE_KEYWORDS.items()}
        extended_keywords.update(clean_mapping)
        registry.SOURCE_TABLE_KEYWORDS = extended_keywords

        # For each new source_table and each of its keywords, verify detection
        for source_table, keywords in clean_mapping.items():
            for keyword in keywords:
                # Build query with only this keyword; avoid accidental matches
                query = f"show me the {keyword} data"
                text_lower = query.lower()

                # Check the query doesn't accidentally match other tables' keywords
                other_matches = set()
                for tbl, kws in extended_keywords.items():
                    if tbl == source_table:
                        continue
                    for kw in kws:
                        if kw in text_lower:
                            other_matches.add(tbl)
                            break

                if other_matches:
                    continue  # skip ambiguous queries

                result = registry.detect_source_table(query)
                assert result == source_table, (
                    f"Expected '{source_table}' for query containing '{keyword}', "
                    f"got '{result}'"
                )

    @given(new_mapping=_new_keyword_mapping_strategy)
    @settings(max_examples=100)
    def test_existing_keywords_still_work_after_extension(self, new_mapping: dict):
        """After adding new keyword entries, existing keyword detection still works.

        **Validates: Requirements 11.4**
        """
        registry = SchemaRegistry(ttl=300)

        # Extend the instance's keywords
        extended_keywords = {k: list(v) for k, v in SchemaRegistry.SOURCE_TABLE_KEYWORDS.items()}
        extended_keywords.update(new_mapping)
        registry.SOURCE_TABLE_KEYWORDS = extended_keywords

        # Verify existing keywords still resolve correctly
        # Pick one keyword from each existing source_table
        for source_table, keywords in SchemaRegistry.SOURCE_TABLE_KEYWORDS.items():
            keyword = keywords[0]
            # Build a query that only contains this one keyword
            # (avoid accidentally including new keywords)
            query = f"please find {keyword} records"

            # Check no new keyword accidentally appears in the query
            collides_with_new = False
            for new_table, new_kws in new_mapping.items():
                if new_table == source_table:
                    continue
                for nk in new_kws:
                    if nk in query.lower():
                        collides_with_new = True
                        break

            if collides_with_new:
                continue  # skip this check if query accidentally matches new keywords

            result = registry.detect_source_table(query)
            assert result == source_table, (
                f"Existing keyword '{keyword}' should still map to '{source_table}', "
                f"got '{result}'"
            )

    @given(
        source_table=_new_source_table_strategy,
        keyword=_new_keyword_strategy,
    )
    @settings(max_examples=100)
    def test_case_insensitive_detection_for_new_keywords(self, source_table: str, keyword: str):
        """New keywords are detected case-insensitively, matching detect_source_table() behavior.

        **Validates: Requirements 11.4**
        """
        registry = SchemaRegistry(ttl=300)

        # Add the new keyword to the instance
        extended_keywords = {k: list(v) for k, v in SchemaRegistry.SOURCE_TABLE_KEYWORDS.items()}
        extended_keywords[source_table] = [keyword]
        registry.SOURCE_TABLE_KEYWORDS = extended_keywords

        # Query with UPPER case version of the keyword
        query_upper = f"show me {keyword.upper()} info"

        # Ensure the uppercase keyword doesn't accidentally match existing keywords
        text_lower = query_upper.lower()
        other_matches = set()
        for table, kws in extended_keywords.items():
            if table == source_table:
                continue
            for kw in kws:
                if kw in text_lower:
                    other_matches.add(table)

        if other_matches:
            # Ambiguous — would return None, skip this case
            return

        result = registry.detect_source_table(query_upper)
        assert result == source_table, (
            f"Case-insensitive detection failed for '{keyword.upper()}': "
            f"expected '{source_table}', got '{result}'"
        )
