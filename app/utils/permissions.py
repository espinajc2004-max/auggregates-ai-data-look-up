"""
Role-Based Access Control (RBAC) permissions for the AI API.
Defines which intents each role can access.
Updated for new RouterService intent names.
"""

from typing import List, Dict


# Permission mappings for each role
# Now includes both legacy intent names AND new RouterService intent names
PERMISSIONS: Dict[str, List[str]] = {
    "ADMIN": [
        # Legacy intent names (for backward compatibility)
        "lookup_quotation", "lookup_trip", "lookup_expense", 
        "lookup_cashflow", "lookup_project", "lookup_product", 
        "lookup_client", "lookup_driver", "lookup_summary",
        "greet", "help_request", "out_of_scope", "followup_more",
        "followup_previous", "goodbye",
        # NEW: RouterService intent names
        "SEARCH", "COUNT", "LIST", "SUM", "LIST_FILES", 
        "FOLLOWUP_SELECT", "CLARIFY_NEEDED"
    ],
    "ACCOUNTANT": [
        # Legacy
        "lookup_quotation", "lookup_expense", "lookup_cashflow", 
        "lookup_project", "lookup_client", "lookup_summary",
        "greet", "help_request", "out_of_scope", "followup_more",
        "followup_previous", "goodbye",
        # NEW
        "SEARCH", "COUNT", "LIST", "SUM", "LIST_FILES", 
        "FOLLOWUP_SELECT", "CLARIFY_NEEDED"
    ],
    "ENCODER": [
        # Legacy - ENCODER can only access Expenses, Quotation, Project (NOT CashFlow per thesis)
        "lookup_quotation", "lookup_trip", "lookup_expense", 
        "lookup_product", "lookup_client", "lookup_driver", 
        "lookup_project", "lookup_summary",
        "greet", "help_request", "out_of_scope", "followup_more",
        "followup_previous", "goodbye",
        # NEW
        "SEARCH", "COUNT", "LIST", "SUM", "LIST_FILES", 
        "FOLLOWUP_SELECT", "CLARIFY_NEEDED",
        # LoRA intents
        "general_greeting", "general_help", "general_unknown",
        "lookup_expenses", "lookup_universal",
        "count_files", "list_files", "search_value"
    ]
}

# Intent to Supabase table mapping
INTENT_TABLE_MAP: Dict[str, Dict[str, str]] = {
    "lookup_quotation": {"table": "Quotation", "display": "quotations"},
    "lookup_expense": {"table": "Expenses", "display": "expenses"},
    "lookup_cashflow": {"table": "CashFlow", "display": "cash flow records"},
    "lookup_project": {"table": "Project", "display": "projects"},
    "lookup_product": {"table": "product", "display": "products"},
    "lookup_client": {"table": "user", "display": "clients"},
    "lookup_trip": {"table": "Project", "display": "trips/projects"},
    "lookup_driver": {"table": "employee_profile", "display": "employees"},
}


def check_permission(role: str, intent: str) -> bool:
    """Check if a role has permission to perform an intent."""
    # Handle None or empty role - default to ENCODER (most restrictive)
    if not role:
        role = "ENCODER"
    allowed = PERMISSIONS.get(role.upper(), [])
    return intent in allowed


def get_table_mapping(intent: str) -> dict:
    """Get the Supabase table mapping for an intent."""
    return INTENT_TABLE_MAP.get(intent)
