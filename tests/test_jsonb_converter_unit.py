"""
Unit tests for the JSONB converter (_convert_to_jsonb_sql) in Phi3Service.

Validates that column references are correctly mapped to JSONB accessor patterns
using SchemaRegistry, with proper numeric casting and source_table filtering.

Feature: schema-alignment-dynamic-columns
Requirements: 1.2, 1.4, 2.3, 2.5, 3.5, 4.5, 5.5, 8.1, 8.2, 11.5
"""

import pytest

from app.services.schema_registry import SchemaRegistry
from app.services.phi3_service import Phi3Service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> Phi3Service:
    """Create a Phi3Service with a SchemaRegistry using GLOBAL_SCHEMA (no DB)."""
    registry = SchemaRegistry.__new__(SchemaRegistry)
    registry._cache = {k: list(v) for k, v in SchemaRegistry.GLOBAL_SCHEMA.items()}
    registry._cache_time = float("inf")
    registry._ttl = 300

    service = Phi3Service.__new__(Phi3Service)
    service.schema_registry = registry
    return service


# ---------------------------------------------------------------------------
# Test 1: CashFlow sum uses metadata->>'Amount', NOT metadata->>'Inflow'
# Validates: Requirements 1.2, 1.4
# ---------------------------------------------------------------------------


class TestCashFlowAmountMapping:
    """CashFlow amount queries must use the correct 'Amount' key."""

    def test_cashflow_sum_uses_amount_key(self):
        service = _make_service()
        sql = "SELECT SUM(amount) FROM data"
        intent = {"source_table": "CashFlow"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'Amount'" in result
        assert "metadata->>'Inflow'" not in result

    def test_cashflow_sum_has_numeric_cast(self):
        service = _make_service()
        sql = "SELECT SUM(amount) FROM data"
        intent = {"source_table": "CashFlow"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "(metadata->>'Amount')::numeric" in result


# ---------------------------------------------------------------------------
# Test 2: Expenses total uses metadata->>'Expenses', NOT metadata->>'Amount'
# Validates: Requirements 2.3, 2.5
# ---------------------------------------------------------------------------


class TestExpensesTotalMapping:
    """Expenses amount queries must use the 'Expenses' key, not 'Amount'."""

    def test_expenses_sum_uses_expenses_key(self):
        service = _make_service()
        sql = "SELECT SUM(expenses) FROM data"
        intent = {"source_table": "Expenses"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'Expenses'" in result
        assert "metadata->>'Amount'" not in result

    def test_expenses_sum_has_numeric_cast(self):
        service = _make_service()
        sql = "SELECT SUM(expenses) FROM data"
        intent = {"source_table": "Expenses"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "SUM((metadata->>'Expenses')::numeric)" in result


# ---------------------------------------------------------------------------
# Test 3: Project key mapping
# Validates: Requirements 3.5, 8.1
# ---------------------------------------------------------------------------


class TestProjectKeyMapping:
    """Project metadata keys map to correct JSONB accessors."""

    def test_project_name_filter(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE project_name = 'Alpha'"
        intent = {"source_table": "Project"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'project_name'" in result
        assert "Alpha" in result

    def test_client_name_filter(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE client_name = 'ACME'"
        intent = {"source_table": "Project"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'client_name'" in result
        assert "ACME" in result

    def test_location_filter(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE location = 'Manila'"
        intent = {"source_table": "Project"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'location'" in result
        assert "Manila" in result

    def test_status_filter(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE status = 'active'"
        intent = {"source_table": "Project"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'status'" in result
        assert "active" in result


# ---------------------------------------------------------------------------
# Test 4: Quotation total_amount gets ::numeric in SUM
# Validates: Requirements 4.5, 8.2
# ---------------------------------------------------------------------------


class TestQuotationNumericCasting:
    """Quotation total_amount must receive ::numeric casting in aggregates."""

    def test_quotation_total_amount_sum_numeric(self):
        service = _make_service()
        sql = "SELECT SUM(total_amount) FROM data"
        intent = {"source_table": "Quotation"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "SUM((metadata->>'total_amount')::numeric)" in result


# ---------------------------------------------------------------------------
# Test 5: QuotationItem volume gets ::numeric in aggregates
# Validates: Requirements 5.5, 8.2
# ---------------------------------------------------------------------------


class TestQuotationItemVolume:
    """QuotationItem volume must receive ::numeric casting in aggregates."""

    def test_volume_sum_numeric(self):
        service = _make_service()
        sql = "SELECT SUM(volume) FROM data"
        intent = {"source_table": "QuotationItem"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "SUM((metadata->>'volume')::numeric)" in result


# ---------------------------------------------------------------------------
# Test 6: QuotationItem line_total gets ::numeric in aggregates
# Validates: Requirements 5.5, 8.2
# ---------------------------------------------------------------------------


class TestQuotationItemLineTotal:
    """QuotationItem line_total must receive ::numeric casting in aggregates."""

    def test_line_total_sum_numeric(self):
        service = _make_service()
        sql = "SELECT SUM(line_total) FROM data"
        intent = {"source_table": "QuotationItem"}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "SUM((metadata->>'line_total')::numeric)" in result


# ---------------------------------------------------------------------------
# Test 7: Cross-table query (source_table=None) merges all keys
# Validates: Requirements 8.1, 8.5
# ---------------------------------------------------------------------------


class TestCrossTableQuery:
    """When source_table is None, all keys are merged and no source_table filter is added."""

    def test_cross_table_maps_category_key(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE category = 'fuel'"
        intent = {"source_table": None}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'Category'" in result
        assert "ILIKE '%fuel%'" in result

    def test_cross_table_no_source_table_filter(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE category = 'fuel'"
        intent = {"source_table": None}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "source_table =" not in result


# ---------------------------------------------------------------------------
# Test 8: Unknown column name passes through as-is
# Validates: Requirements 11.5
# ---------------------------------------------------------------------------


class TestUnknownKeyPassthrough:
    """Unknown metadata keys should be used as-is in JSONB accessors."""

    def test_unknown_key_becomes_jsonb_accessor(self):
        service = _make_service()
        sql = "SELECT * FROM data WHERE driver = 'John'"
        intent = {"source_table": None}

        result = service._convert_to_jsonb_sql(sql, intent)

        assert "metadata->>'driver'" in result
        assert "John" in result
