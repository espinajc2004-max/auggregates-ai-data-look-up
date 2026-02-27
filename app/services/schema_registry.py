"""
Schema Registry — Single source of truth for metadata schema discovery.

Dynamically discovers metadata keys from ai_documents, caches them with TTL,
and provides schema info to all consumers (prompt templates, JSONB converter,
intent parser, query engine).

When the database is unreachable, falls back to known GLOBAL column definitions.
"""

import time
from typing import Dict, List, Optional, Set

from app.utils.logger import get_logger
from app.services.supabase_client import get_supabase_client, SupabaseError

logger = get_logger("schema_registry")


class SchemaRegistry:
    """
    Discovers actual metadata keys from ai_documents, caches them,
    and provides schema info to all consumers.
    """

    # Known GLOBAL columns per source_table (fallback if DB unreachable)
    GLOBAL_SCHEMA: Dict[str, List[str]] = {
        "Expenses": ["Category", "Expenses", "Name"],
        "CashFlow": ["Type", "Amount", "Category"],
        "Project": ["project_name", "client_name", "location", "status"],
        "Quotation": ["quote_number", "status", "total_amount", "project_name"],
        "QuotationItem": [
            "plate_no", "dr_no", "material", "quarry_location",
            "truck_type", "volume", "line_total",
        ],
    }

    # Numeric keys that need ::numeric casting in aggregates
    NUMERIC_KEYS: Set[str] = {
        "Expenses", "Amount", "total_amount", "volume", "line_total",
    }

    # Keyword-to-source-table mapping (extensible)
    SOURCE_TABLE_KEYWORDS: Dict[str, List[str]] = {
        "Expenses": ["expense", "expenses", "gastos", "cost", "costs", "spending"],
        "CashFlow": ["cashflow", "cash flow", "cash-flow", "inflow", "outflow"],
        "Project": ["project", "client", "location"],
        "Quotation": ["quotation", "quote", "quote number"],
        "QuotationItem": [
            "delivery", "deliveries", "dr number", "dr no",
            "plate number", "plate no", "line item", "line items",
            "material", "volume",
        ],
    }

    DEFAULT_TTL: int = 300  # 5 minutes
    FALLBACK_TTL: int = 60  # 1 minute on DB failure

    def __init__(self, ttl: int = DEFAULT_TTL):
        self._cache: Dict[str, List[str]] = {}
        self._cache_time: float = 0
        self._ttl: int = ttl

    def _discover_keys_from_db(self) -> Dict[str, List[str]]:
        """
        Query ai_documents for distinct source_table + metadata keys.

        Returns:
            Dict mapping source_table to sorted list of metadata keys.

        Raises:
            SupabaseError: If the database query fails.
        """
        client = get_supabase_client()
        sql = (
            "SELECT source_table, jsonb_object_keys(metadata) AS key "
            "FROM ai_documents "
            "WHERE document_type = 'row' "
            "GROUP BY source_table, key "
            "ORDER BY source_table, key"
        )
        result = client.execute_sql(sql)
        rows = result.get("data", [])

        schema: Dict[str, List[str]] = {}
        for row in rows:
            table = row.get("source_table")
            key = row.get("key")
            if table and key:
                schema.setdefault(table, []).append(key)

        return schema

    def _refresh_cache(self) -> None:
        """
        Refresh the in-memory cache from the database.
        Falls back to GLOBAL_SCHEMA on any DB failure, using a shorter TTL.
        """
        try:
            discovered = self._discover_keys_from_db()
            if discovered:
                self._cache = discovered
                self._ttl = self.__class__.DEFAULT_TTL
            else:
                # Empty result — likely no data ingested yet
                logger.warning("Schema discovery returned empty; using GLOBAL_SCHEMA fallback")
                self._cache = {k: list(v) for k, v in self.GLOBAL_SCHEMA.items()}
                self._ttl = self.FALLBACK_TTL
        except Exception as exc:
            logger.warning(f"Schema discovery failed ({exc}); using GLOBAL_SCHEMA fallback")
            self._cache = {k: list(v) for k, v in self.GLOBAL_SCHEMA.items()}
            self._ttl = self.FALLBACK_TTL

        self._cache_time = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_schema(self) -> Dict[str, List[str]]:
        """Return {source_table: [metadata_keys]} — from cache or DB."""
        if not self._cache or (time.time() - self._cache_time) >= self._ttl:
            self._refresh_cache()
        return dict(self._cache)

    def get_metadata_keys(self, source_table: str) -> List[str]:
        """Return metadata keys for a specific source_table."""
        schema = self.get_schema()
        return list(schema.get(source_table, []))

    def get_all_source_tables(self) -> List[str]:
        """Return all known source_table values."""
        return list(self.get_schema().keys())

    def get_numeric_keys(self) -> Set[str]:
        """Return set of keys that need ::numeric casting."""
        return set(self.NUMERIC_KEYS)

    def detect_source_table(self, text: str) -> Optional[str]:
        """
        Detect source_table from query text using keyword mapping.

        Returns the matched source_table, or None when:
        - No keywords match
        - Multiple source tables match (ambiguous)
        """
        text_lower = text.lower()
        matched_tables: Set[str] = set()

        for table, keywords in self.SOURCE_TABLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    matched_tables.add(table)
                    break  # one keyword is enough per table

        if len(matched_tables) == 1:
            return matched_tables.pop()
        return None

    def build_schema_context(self) -> str:
        """Generate the SCHEMA_CONTEXT string dynamically for prompt injection."""
        schema = self.get_schema()
        lines: List[str] = []
        for table in sorted(schema.keys()):
            keys = schema[table]
            lines.append(f"Source Table: {table}")
            lines.append(f"  Metadata Keys: {', '.join(keys)}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def invalidate_cache(self) -> None:
        """Force cache refresh on next access."""
        self._cache = {}
        self._cache_time = 0


# Module-level singleton for easy import by consumers
schema_registry = SchemaRegistry()


def get_schema_registry() -> SchemaRegistry:
    """Get the SchemaRegistry singleton instance."""
    return schema_registry
