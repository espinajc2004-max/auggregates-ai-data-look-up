"""
Unit tests for SchemaRegistry.

Tests specific examples, edge cases, and integration points for the
SchemaRegistry component.

Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.2, 6.3, 6.7, 7.1, 7.2, 7.3
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.schema_registry import SchemaRegistry
from app.services.supabase_client import SupabaseError


def _make_db_rows(schema: dict) -> list:
    """Convert {source_table: [keys]} to flat DB row format."""
    rows = []
    for table, keys in schema.items():
        for key in keys:
            rows.append({"source_table": table, "key": key})
    return rows


def _make_mock_client(return_value=None, side_effect=None):
    """Create a mock supabase client with execute_sql configured."""
    client = MagicMock()
    if side_effect is not None:
        client.execute_sql.side_effect = side_effect
    else:
        client.execute_sql.return_value = return_value or {"data": []}
    return client


# ---------------------------------------------------------------------------
# get_metadata_keys tests
# ---------------------------------------------------------------------------


class TestGetMetadataKeys:
    """Test get_metadata_keys returns correct keys for known source tables."""

    def test_cashflow_keys(self):
        """CashFlow returns [Type, Amount, Category].

        Validates: Requirements 1.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("CashFlow")

        assert set(keys) == {"Type", "Amount", "Category"}

    def test_expenses_keys(self):
        """Expenses returns [Category, Expenses, Name].

        Validates: Requirements 2.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("Expenses")

        assert set(keys) == {"Category", "Expenses", "Name"}

    def test_project_keys(self):
        """Project returns [project_name, client_name, location, status].

        Validates: Requirements 3.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("Project")

        assert set(keys) == {"project_name", "client_name", "location", "status"}

    def test_quotation_keys(self):
        """Quotation returns [quote_number, status, total_amount, project_name].

        Validates: Requirements 4.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("Quotation")

        assert set(keys) == {"quote_number", "status", "total_amount", "project_name"}

    def test_quotation_item_keys(self):
        """QuotationItem returns correct keys.

        Validates: Requirements 5.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("QuotationItem")

        assert set(keys) == {
            "plate_no", "dr_no", "material", "quarry_location",
            "truck_type", "volume", "line_total",
        }

    def test_unknown_table_returns_empty(self):
        """Unknown source table returns empty list.

        Validates: Requirements 6.1
        """
        registry = SchemaRegistry(ttl=0)
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("NonExistent")

        assert keys == []


# ---------------------------------------------------------------------------
# detect_source_table tests
# ---------------------------------------------------------------------------


class TestDetectSourceTable:
    """Test detect_source_table keyword matching."""

    def test_project_detection(self):
        """'list all projects' returns 'Project'.

        Validates: Requirements 7.1
        """
        registry = SchemaRegistry()
        result = registry.detect_source_table("list all projects")
        assert result == "Project"

    def test_quotation_detection(self):
        """'total amount of all quotations' returns 'Quotation'.

        Validates: Requirements 7.1
        """
        registry = SchemaRegistry()
        result = registry.detect_source_table("total amount of all quotations")
        assert result == "Quotation"

    def test_quotation_item_detection(self):
        """'show deliveries for plate ABC-123' returns 'QuotationItem'.

        Validates: Requirements 7.2
        """
        registry = SchemaRegistry()
        result = registry.detect_source_table("show deliveries for plate ABC-123")
        assert result == "QuotationItem"

    def test_no_keywords_returns_none(self):
        """'what is the weather' returns None (no matching keywords).

        Validates: Requirements 7.3
        """
        registry = SchemaRegistry()
        result = registry.detect_source_table("what is the weather")
        assert result is None

    def test_expenses_detection(self):
        """Expense-related queries detect Expenses table.

        Validates: Requirements 7.1
        """
        registry = SchemaRegistry()
        assert registry.detect_source_table("show all expenses") == "Expenses"

    def test_cashflow_detection(self):
        """CashFlow-related queries detect CashFlow table.

        Validates: Requirements 7.1
        """
        registry = SchemaRegistry()
        assert registry.detect_source_table("total cash flow this month") == "CashFlow"

    def test_ambiguous_returns_none(self):
        """Query matching multiple tables returns None.

        Validates: Requirements 7.3
        """
        registry = SchemaRegistry()
        # "volume" matches QuotationItem, "expense" matches Expenses
        result = registry.detect_source_table("volume of expenses")
        assert result is None


# ---------------------------------------------------------------------------
# Cache expiry tests
# ---------------------------------------------------------------------------


class TestCacheExpiry:
    """Test cache TTL behavior with mocked time."""

    def test_cache_expires_after_ttl(self):
        """Cache expires and triggers DB refresh after TTL.

        Validates: Requirements 6.2, 6.3
        """
        initial_rows = _make_db_rows({"CashFlow": ["Type", "Amount", "Category"]})
        refreshed_rows = _make_db_rows({
            "CashFlow": ["Type", "Amount", "Category", "NewKey"],
        })

        registry = SchemaRegistry(ttl=300)
        client = _make_mock_client(side_effect=[
            {"data": initial_rows},
            {"data": refreshed_rows},
        ])

        with patch("app.services.schema_registry.time") as mock_time, \
             patch("app.services.schema_registry.get_supabase_client", return_value=client):
            # First call at t=0
            mock_time.time.return_value = 0.0
            result1 = registry.get_schema()
            assert "NewKey" not in result1.get("CashFlow", [])

            # Force TTL back to 300 (refresh resets it to DEFAULT_TTL)
            registry._ttl = 300

            # Call within TTL — should use cache
            mock_time.time.return_value = 299.0
            result2 = registry.get_schema()
            assert client.execute_sql.call_count == 1

            # Call at TTL boundary — should refresh
            mock_time.time.return_value = 300.0
            result3 = registry.get_schema()
            assert client.execute_sql.call_count == 2
            assert "NewKey" in result3["CashFlow"]

    def test_invalidate_cache_forces_refresh(self):
        """invalidate_cache() forces next get_schema() to hit DB.

        Validates: Requirements 6.2
        """
        rows = _make_db_rows(SchemaRegistry.GLOBAL_SCHEMA)
        client = _make_mock_client({"data": rows})

        registry = SchemaRegistry(ttl=9999)

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            registry.get_schema()
            assert client.execute_sql.call_count == 1

            registry.invalidate_cache()
            registry.get_schema()
            assert client.execute_sql.call_count == 2


# ---------------------------------------------------------------------------
# DB failure fallback tests
# ---------------------------------------------------------------------------


class TestDBFailureFallback:
    """Test fallback to GLOBAL_SCHEMA when DB is unreachable."""

    def test_supabase_error_returns_global_schema(self):
        """SupabaseError falls back to GLOBAL_SCHEMA.

        Validates: Requirements 6.7
        """
        registry = SchemaRegistry(ttl=0)
        client = _make_mock_client(side_effect=SupabaseError("connection refused"))

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            result = registry.get_schema()

        for table, keys in SchemaRegistry.GLOBAL_SCHEMA.items():
            assert table in result
            assert set(result[table]) == set(keys)

    def test_connection_error_returns_global_schema(self):
        """ConnectionError falls back to GLOBAL_SCHEMA.

        Validates: Requirements 6.7
        """
        registry = SchemaRegistry(ttl=0)
        client = _make_mock_client(side_effect=ConnectionError("network down"))

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            result = registry.get_schema()

        assert set(result.keys()) == set(SchemaRegistry.GLOBAL_SCHEMA.keys())

    def test_fallback_uses_shorter_ttl(self):
        """DB failure sets TTL to FALLBACK_TTL (60s) for faster retry.

        Validates: Requirements 6.7
        """
        registry = SchemaRegistry(ttl=300)
        client = _make_mock_client(side_effect=SupabaseError("timeout"))

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            registry.get_schema()

        assert registry._ttl == SchemaRegistry.FALLBACK_TTL


# ---------------------------------------------------------------------------
# Custom column discovery tests
# ---------------------------------------------------------------------------


class TestCustomColumnDiscovery:
    """Test dynamic discovery of custom/extra metadata keys."""

    def test_custom_key_discovered_from_db(self):
        """DB returning extra key like 'Driver' is included in schema.

        Validates: Requirements 6.1, 6.6
        """
        schema_with_custom = {
            "Expenses": ["Category", "Expenses", "Name", "Driver"],
            "CashFlow": ["Type", "Amount", "Category"],
        }
        rows = _make_db_rows(schema_with_custom)
        client = _make_mock_client({"data": rows})

        registry = SchemaRegistry(ttl=0)

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            keys = registry.get_metadata_keys("Expenses")

        assert "Driver" in keys
        assert set(keys) == {"Category", "Expenses", "Name", "Driver"}

    def test_new_source_table_discovered(self):
        """A completely new source table from DB is discovered.

        Validates: Requirements 6.1
        """
        schema_with_new = {
            "Expenses": ["Category", "Expenses", "Name"],
            "Trip": ["trip_id", "driver", "destination"],
        }
        rows = _make_db_rows(schema_with_new)
        client = _make_mock_client({"data": rows})

        registry = SchemaRegistry(ttl=0)

        with patch("app.services.schema_registry.get_supabase_client", return_value=client):
            tables = registry.get_all_source_tables()
            trip_keys = registry.get_metadata_keys("Trip")

        assert "Trip" in tables
        assert set(trip_keys) == {"trip_id", "driver", "destination"}

    def test_custom_key_appears_after_cache_refresh(self):
        """Custom key appears after cache refresh when DB data changes.

        Validates: Requirements 6.2, 6.3
        """
        initial_rows = _make_db_rows({"Expenses": ["Category", "Expenses", "Name"]})
        updated_rows = _make_db_rows({
            "Expenses": ["Category", "Expenses", "Name", "Driver"],
        })

        client = _make_mock_client(side_effect=[
            {"data": initial_rows},
            {"data": updated_rows},
        ])

        registry = SchemaRegistry(ttl=10)

        with patch("app.services.schema_registry.time") as mock_time, \
             patch("app.services.schema_registry.get_supabase_client", return_value=client):
            mock_time.time.return_value = 0.0
            keys1 = registry.get_metadata_keys("Expenses")
            assert "Driver" not in keys1

            registry._ttl = 10
            mock_time.time.return_value = 10.0
            keys2 = registry.get_metadata_keys("Expenses")
            assert "Driver" in keys2
