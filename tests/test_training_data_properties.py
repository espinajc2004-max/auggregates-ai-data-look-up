"""
Property-based tests for Training Data Generator (Property 11).

Validates that generated training data references only valid metadata keys
per source_table as defined by GLOBAL_SCHEMA, covers all 5 source tables,
and contains no phantom keys.

Feature: schema-alignment-dynamic-columns, Property 11: Training data references only valid metadata keys per source_table
**Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7**
"""

import json
import re
import sys
import os

import pytest

# Add scripts directory to path so we can import the generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from generate_training_data import generate_all_examples
from app.services.schema_registry import SchemaRegistry


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOBAL_SCHEMA = SchemaRegistry.GLOBAL_SCHEMA

ALL_SOURCE_TABLES = set(GLOBAL_SCHEMA.keys())

# Metadata key pattern: metadata->>'KeyName'
METADATA_KEY_PATTERN = re.compile(r"metadata->>'([^']+)'")

# Keys that appear in SQL but are not source-table-specific metadata keys.
# These are column-level references (file_name, user_date, etc.) or
# cross-table keys that are acceptable in any context.
NON_METADATA_COLUMNS = {
    "description", "project_name", "file_name", "category",
    "user_date", "type",
}

# Phantom keys that must NEVER appear as metadata keys for specific tables
CASHFLOW_PHANTOM_KEYS = {"Inflow", "Outflow", "Balance"}
EXPENSES_PHANTOM_KEYS = {"Description", "Supplier", "Method", "Remarks"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_training_pairs():
    """Generate all training examples once for the module."""
    return generate_all_examples()


@pytest.fixture(scope="module")
def pairs_with_source_table(all_training_pairs):
    """Extract pairs that have a source_table in their slots."""
    result = []
    for pair in all_training_pairs:
        output = json.loads(pair["output"])
        source_table = output.get("slots", {}).get("source_table")
        if source_table and source_table in ALL_SOURCE_TABLES:
            result.append((pair, output, source_table))
    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_metadata_keys_from_sql(sql: str) -> set:
    """Extract all metadata->>'KeyName' references from SQL."""
    return set(METADATA_KEY_PATTERN.findall(sql))


def _valid_keys_for_table(source_table: str) -> set:
    """Get the set of valid metadata keys for a source_table."""
    return set(GLOBAL_SCHEMA.get(source_table, []))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTrainingDataValidKeys:
    """
    Property 11: Training data references only valid metadata keys per source_table.
    **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7**
    """

    def test_all_sql_metadata_keys_are_valid_for_source_table(self, pairs_with_source_table):
        """
        For each training pair with a source_table, every metadata->>'Key'
        reference in the SQL must be a valid key for that source_table
        according to GLOBAL_SCHEMA.
        """
        violations = []

        for pair, output, source_table in pairs_with_source_table:
            sql = output.get("sql", "")
            referenced_keys = _extract_metadata_keys_from_sql(sql)
            valid_keys = _valid_keys_for_table(source_table)

            for key in referenced_keys:
                if key not in valid_keys:
                    violations.append(
                        f"source_table={source_table}, invalid key='{key}', "
                        f"instruction='{pair['instruction'][:60]}...'"
                    )

        assert not violations, (
            f"Found {len(violations)} invalid metadata key references:\n"
            + "\n".join(violations[:20])
        )

    def test_dataset_covers_all_five_source_tables(self, pairs_with_source_table):
        """
        The generated dataset must contain training pairs for all 5 source tables:
        Expenses, CashFlow, Project, Quotation, QuotationItem.
        """
        covered_tables = {source_table for _, _, source_table in pairs_with_source_table}
        missing = ALL_SOURCE_TABLES - covered_tables

        assert not missing, (
            f"Missing training pairs for source tables: {missing}"
        )

    def test_no_cashflow_phantom_keys(self, pairs_with_source_table):
        """
        No CashFlow training pair SQL should reference phantom keys:
        Inflow, Outflow, Balance.
        """
        violations = []

        for pair, output, source_table in pairs_with_source_table:
            if source_table != "CashFlow":
                continue
            sql = output.get("sql", "")
            referenced_keys = _extract_metadata_keys_from_sql(sql)
            phantom_found = referenced_keys & CASHFLOW_PHANTOM_KEYS

            if phantom_found:
                violations.append(
                    f"CashFlow phantom keys {phantom_found} in: "
                    f"'{pair['instruction'][:60]}...'"
                )

        assert not violations, (
            f"Found {len(violations)} CashFlow phantom key references:\n"
            + "\n".join(violations[:10])
        )

    def test_no_expenses_phantom_keys(self, pairs_with_source_table):
        """
        No Expenses training pair SQL should reference phantom keys:
        Description, Supplier, Method, Remarks.
        """
        violations = []

        for pair, output, source_table in pairs_with_source_table:
            if source_table != "Expenses":
                continue
            sql = output.get("sql", "")
            referenced_keys = _extract_metadata_keys_from_sql(sql)
            phantom_found = referenced_keys & EXPENSES_PHANTOM_KEYS

            if phantom_found:
                violations.append(
                    f"Expenses phantom keys {phantom_found} in: "
                    f"'{pair['instruction'][:60]}...'"
                )

        assert not violations, (
            f"Found {len(violations)} Expenses phantom key references:\n"
            + "\n".join(violations[:10])
        )

    def test_each_source_table_has_multiple_pairs(self, pairs_with_source_table):
        """Each source table should have a meaningful number of training pairs."""
        table_counts = {}
        for _, _, source_table in pairs_with_source_table:
            table_counts[source_table] = table_counts.get(source_table, 0) + 1

        for table in ALL_SOURCE_TABLES:
            count = table_counts.get(table, 0)
            assert count >= 3, (
                f"source_table '{table}' has only {count} training pairs "
                f"(expected at least 3)"
            )

    def test_total_dataset_is_non_trivial(self, all_training_pairs):
        """The full dataset should have a substantial number of examples."""
        assert len(all_training_pairs) >= 50, (
            f"Dataset has only {len(all_training_pairs)} examples, expected >= 50"
        )
