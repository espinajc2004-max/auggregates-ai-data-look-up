"""
Query Engine
============
Rule-based query executor for AU-Ggregates AI.
Queries ai_documents table directly — no ML model needed.
Handles all 6 bug categories from production testing.
"""

import re
import time
from typing import Dict, Any, List, Optional
from app.services.supabase_client import get_supabase_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL_SUFFIX = "ai_documents"


class QueryEngine:
    """
    Executes structured intents against ai_documents table.
    Uses Supabase REST API directly — no SQL generation needed.
    """

    def __init__(self):
        self.supabase = get_supabase_client()

    def execute(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute intent and return results.

        Args:
            intent: Parsed intent from IntentParser

        Returns:
            Dict with data, message, row_count
        """
        start = time.time()
        intent_type = intent.get("intent", "general_search")
        slots = intent.get("slots", {})

        try:
            if intent_type == "file_summary":
                result = self._file_summary(slots)
            elif intent_type == "list_files":
                result = self._list_files(slots)
            elif intent_type == "find_in_file":
                result = self._find_in_file(slots)
            elif intent_type == "list_categories":
                result = self._list_categories(slots)
            elif intent_type == "compare":
                result = self._compare(slots)
            elif intent_type == "count":
                result = self._count(slots)
            elif intent_type == "sum":
                result = self._sum(slots)
            elif intent_type == "date_filter":
                result = self._date_filter(slots)
            elif intent_type == "ambiguous":
                result = self._handle_ambiguous(slots)
            else:
                result = self._general_search(slots)

            elapsed = (time.time() - start) * 1000
            result["elapsed_ms"] = round(elapsed, 2)
            result["intent"] = intent_type
            return result

        except Exception as e:
            logger.error(f"[QueryEngine] Error executing {intent_type}: {e}", exc_info=True)
            return {
                "data": [],
                "message": f"Error during search: {str(e)}",
                "row_count": 0,
                "intent": intent_type,
                "error": str(e)
            }

    # -------------------------------------------------------------------------
    # INTENT HANDLERS
    # -------------------------------------------------------------------------

    def _file_summary(self, slots: Dict) -> Dict:
        """Get summary/overview of a specific file (parent record only)."""
        file_name = slots.get("file_name", "")

        # Try 1: document_type = 'file' (correct way)
        params = {
            "document_type": "eq.file",
            "select": "id,file_name,project_name,source_table,searchable_text,metadata",
            "limit": "10"
        }
        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"

        rows = self._fetch(params)

        # Try 2: maybe it's a project name (still file type)
        if not rows:
            params2 = {
                "document_type": "eq.file",
                "select": "id,file_name,project_name,source_table,searchable_text,metadata",
                "limit": "10"
            }
            if file_name:
                params2["project_name"] = f"ilike.*{file_name}*"
            rows = self._fetch(params2)

        # Try 3: fallback — filter by metadata type='file' in case document_type wasn't set
        if not rows:
            params3 = {
                "select": "id,file_name,project_name,source_table,searchable_text,metadata",
                "metadata->>type": "eq.file",
                "limit": "10"
            }
            if file_name:
                params3["file_name"] = f"ilike.*{file_name}*"
            rows = self._fetch(params3)

        if not rows:
            return {
                "data": [],
                "message": f"No file found matching '{file_name}'. Please check the spelling.",
                "row_count": 0
            }

        return {
            "data": rows,
            "message": f"Found {len(rows)} expense file(s) matching '{file_name}'.",
            "row_count": len(rows)
        }

    def _list_files(self, slots: Dict) -> Dict:
        """List parent file records (document_type = 'file'), filtered by source_table if specified."""
        source_table = slots.get("source_table", "")

        params = {
            "document_type": "eq.file",
            "select": "id,file_name,project_name,source_table,searchable_text,metadata",
            "limit": "50"
        }
        if source_table:
            params["source_table"] = f"eq.{source_table}"

        rows = self._fetch(params)

        if not rows:
            label = f"{source_table} " if source_table else ""
            return {
                "data": [],
                "message": f"No {label}files found in the system.",
                "row_count": 0
            }

        label = f"{source_table} " if source_table else ""
        names = [r.get("file_name", "") for r in rows if r.get("file_name")]
        name_list = ", ".join(f"'{n}'" for n in names[:10])
        suffix = f" and {len(names) - 10} more" if len(names) > 10 else ""
        return {
            "data": rows,
            "message": f"Found {len(rows)} {label}file(s): {name_list}{suffix}.",
            "row_count": len(rows)
        }


    def _find_in_file(self, slots: Dict) -> Dict:
        """Find rows matching a category inside a specific file."""
        file_name = slots.get("file_name", "")
        category = slots.get("category", "")
        method = slots.get("method", "")

        params = {
            "document_type": "eq.row",
            "select": "id,file_name,project_name,searchable_text,metadata",
            "limit": "50"
        }

        # Build search text combining category + method
        search_parts = [p for p in [category, method] if p]
        search_text = " ".join(search_parts)

        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"
        if search_text:
            params["searchable_text"] = f"ilike.*{search_text}*"

        rows = self._fetch(params)

        if not rows:
            return {
                "data": [],
                "message": f"No '{search_text}' found in file '{file_name}'.",
                "row_count": 0
            }

        return {
            "data": rows,
            "message": f"Found {len(rows)} row(s) matching '{search_text}' in '{file_name}'.",
            "row_count": len(rows)
        }

    def _list_categories(self, slots: Dict) -> Dict:
        """List distinct categories from metadata."""
        file_name = slots.get("file_name", "")

        params = {
            "document_type": "eq.row",
            "select": "metadata",
            "limit": "500"
        }
        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"

        rows = self._fetch(params)

        # Extract unique categories from metadata
        categories = set()
        for row in rows:
            meta = row.get("metadata") or {}
            # Real schema uses "Category" key
            cat = meta.get("Category") or meta.get("category") or meta.get("type")
            if cat:
                categories.add(str(cat).strip())

        if not categories:
            # Fallback: extract from searchable_text
            params2 = dict(params)
            params2["select"] = "searchable_text"
            rows2 = self._fetch(params2)
            for row in rows2:
                text = row.get("searchable_text", "")
                # Try to extract category-like tokens
                for token in text.split():
                    if len(token) > 3 and token.isalpha():
                        categories.add(token.lower())

        cat_list = sorted(categories)
        scope = f" in '{file_name}'" if file_name else ""

        return {
            "data": [{"category": c} for c in cat_list],
            "message": f"Found {len(cat_list)} categories{scope}.",
            "row_count": len(cat_list)
        }

    def _compare(self, slots: Dict) -> Dict:
        """Compare two files by count and total amount."""
        files = slots.get("files", [])
        category = slots.get("category", "")

        if len(files) < 2:
            return {
                "data": [],
                "message": "Need two files to compare. Which two files do you want to compare?",
                "row_count": 0,
                "needs_clarification": True
            }

        results = []
        for fname in files:
            params = {
                "document_type": "eq.row",
                "select": "file_name,metadata",
                "file_name": f"ilike.*{fname}*",
                "limit": "500"
            }
            if category:
                params["searchable_text"] = f"ilike.*{category}*"

            rows = self._fetch(params)
            total = 0.0
            for row in rows:
                meta = row.get("metadata") or {}
                # Real schema uses "Expenses" for expense amounts, "Inflow"/"Outflow" for CashFlow
                for key in ["Expenses", "expenses", "Amount", "amount", "Inflow", "Outflow", "Total", "total"]:
                    val = meta.get(key)
                    if val is not None:
                        try:
                            total += float(str(val).replace(",", "").replace("₱", ""))
                        except (ValueError, TypeError):
                            pass
                        break

            results.append({
                "file": fname,
                "count": len(rows),
                "total_amount": round(total, 2)
            })

        msg_parts = [f"'{r['file']}': {r['count']} rows, ₱{r['total_amount']:,.2f}" for r in results]
        return {
            "data": results,
            "message": "Comparison result:\n" + "\n".join(msg_parts),
            "row_count": len(results)
        }

    def _count(self, slots: Dict) -> Dict:
        """Count rows with optional filters."""
        file_name = slots.get("file_name", "")
        category = slots.get("category", "")
        date_slot = slots.get("date")

        params = {
            "document_type": "eq.row",
            "select": "id",
            "limit": "1000"
        }
        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"
        if category:
            params["searchable_text"] = f"ilike.*{category}*"

        rows = self._fetch(params)

        # Apply date filter in-memory if needed
        if date_slot:
            rows = self._apply_date_filter(rows, date_slot)

        scope_parts = []
        if file_name:
            scope_parts.append(f"in '{file_name}'")
        if category:
            scope_parts.append(f"with category '{category}'")
        if date_slot:
            scope_parts.append(self._date_label(date_slot))

        scope = " ".join(scope_parts) or "total"

        return {
            "data": [{"count": len(rows)}],
            "message": f"{len(rows)} rows {scope}.",
            "row_count": len(rows)
        }

    def _sum(self, slots: Dict) -> Dict:
        """Sum amounts with optional filters."""
        file_name = slots.get("file_name", "")
        category = slots.get("category", "")
        date_slot = slots.get("date")

        params = {
            "document_type": "eq.row",
            "select": "metadata,file_name",
            "limit": "1000"
        }
        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"
        if category:
            params["searchable_text"] = f"ilike.*{category}*"

        rows = self._fetch(params)

        if date_slot:
            rows = self._apply_date_filter(rows, date_slot)

        total = 0.0
        for row in rows:
            meta = row.get("metadata") or {}
            # Real schema uses "Expenses" key
            for key in ["Expenses", "expenses", "Amount", "amount", "Total", "total"]:
                val = meta.get(key)
                if val is not None:
                    try:
                        total += float(str(val).replace(",", "").replace("₱", ""))
                    except (ValueError, TypeError):
                        pass
                    break

        scope_parts = []
        if file_name:
            scope_parts.append(f"in '{file_name}'")
        if category:
            scope_parts.append(f"for '{category}'")
        if date_slot:
            scope_parts.append(self._date_label(date_slot))

        scope = " ".join(scope_parts) or "overall"

        return {
            "data": [{"total": round(total, 2), "count": len(rows)}],
            "message": f"Total amount {scope}: ₱{total:,.2f} ({len(rows)} rows)",
            "row_count": len(rows)
        }

    def _date_filter(self, slots: Dict) -> Dict:
        """Filter rows by date."""
        date_slot = slots.get("date")
        file_name = slots.get("file_name", "")
        category = slots.get("category", "")
        method = slots.get("method", "")

        params = {
            "document_type": "eq.row",
            "select": "id,file_name,searchable_text,metadata",
            "limit": "200"
        }
        if file_name:
            params["file_name"] = f"ilike.*{file_name}*"

        search_parts = [p for p in [category, method] if p]
        if search_parts:
            params["searchable_text"] = f"ilike.*{' '.join(search_parts)}*"

        rows = self._fetch(params)

        if date_slot:
            rows = self._apply_date_filter(rows, date_slot)

        label = self._date_label(date_slot) if date_slot else ""
        scope = f" {label}" if label else ""

        return {
            "data": rows,
            "message": f"Found {len(rows)} rows{scope}.",
            "row_count": len(rows)
        }

    def _handle_ambiguous(self, slots: Dict) -> Dict:
        """
        Ambiguous query — check how many files contain the term.
        If only 1 file, return results. If multiple, ask for clarification.
        """
        category = slots.get("category", "")
        method = slots.get("method", "")
        search_term = category or method

        if not search_term:
            return {
                "data": [],
                "message": "I couldn't understand your query. Could you please rephrase it?",
                "row_count": 0,
                "needs_clarification": True
            }

        # Find which files contain this term
        params = {
            "document_type": "eq.row",
            "select": "file_name",
            "searchable_text": f"ilike.*{search_term}*",
            "limit": "500"
        }
        rows = self._fetch(params)

        # Get unique file names
        file_names = list({r.get("file_name", "") for r in rows if r.get("file_name")})

        if len(file_names) == 0:
            return {
                "data": [],
                "message": f"No results found for '{search_term}' in any file.",
                "row_count": 0
            }
        elif len(file_names) == 1:
            # Only one file — just return results
            slots["file_name"] = file_names[0]
            return self._find_in_file(slots)
        else:
            # Multiple files — ask for clarification
            file_list = ", ".join(f"'{f}'" for f in file_names[:5])
            return {
                "data": [{"file_name": f} for f in file_names],
                "message": (
                    f"Found '{search_term}' in {len(file_names)} files: {file_list}. "
                    f"Which file do you want? Please specify the file name."
                ),
                "row_count": len(file_names),
                "needs_clarification": True,
                "clarification_options": file_names
            }

    def _general_search(self, slots: Dict) -> Dict:
        """Full-text search fallback."""
        search_term = slots.get("search_term", "")

        if not search_term:
            return {
                "data": [],
                "message": "No search term provided. What are you looking for?",
                "row_count": 0
            }

        params = {
            "select": "id,file_name,project_name,document_type,searchable_text",
            "searchable_text": f"ilike.*{search_term}*",
            "limit": "20"
        }
        rows = self._fetch(params)

        if not rows:
            return {
                "data": [],
                "message": f"No results found for '{search_term}'.",
                "row_count": 0
            }

        return {
            "data": rows,
            "message": f"Found {len(rows)} results for '{search_term}'.",
            "row_count": len(rows)
        }

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _fetch(self, params: Dict) -> List[Dict]:
        """Fetch rows from ai_documents with given params."""
        try:
            result = self.supabase.get(BASE_URL_SUFFIX, params=params)
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"[QueryEngine] Fetch error: {e}")
            return []

    def _apply_date_filter(self, rows: List[Dict], date_slot: Dict) -> List[Dict]:
        """Filter rows by date using metadata fields."""
        if not date_slot:
            return rows

        date_type = date_slot.get("type")
        filtered = []

        for row in rows:
            meta = row.get("metadata") or {}
            row_date_str = (
                meta.get("Date") or meta.get("date") or
                meta.get("user_date") or meta.get("created_at") or
                row.get("created_at", "")
            )
            if not row_date_str:
                continue

            # Normalize date string
            row_date_str = str(row_date_str)[:10]  # YYYY-MM-DD

            try:
                if date_type == "exact":
                    if row_date_str == date_slot["value"]:
                        filtered.append(row)
                elif date_type == "month_range":
                    start = date_slot["start"]
                    end = date_slot["end"]
                    if start <= row_date_str <= end:
                        filtered.append(row)
            except Exception:
                continue

        return filtered

    def _date_label(self, date_slot: Optional[Dict]) -> str:
        """Human-readable date label."""
        if not date_slot:
            return ""
        if date_slot.get("type") == "exact":
            return f"on {date_slot['value']}"
        elif date_slot.get("type") == "month_range":
            from app.services.intent_parser import MONTH_MAP
            month_num = date_slot.get("month", 0)
            month_name = next((k for k, v in MONTH_MAP.items() if v == month_num and len(k) > 3), str(month_num))
            return f"in {month_name.capitalize()}"
        return ""
