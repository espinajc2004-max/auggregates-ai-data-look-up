"""
Unit tests for Phi-3 Entity Injection Upgrade — config, imports, and code structure.

Validates:
  - Requirements 1.1: Phi3Config default model_name
  - Requirements 2.5: Prompt template content unchanged
  - Requirements 6.2, 6.3: No parse_intent import in phi3_service.py
  - Requirements 8.2, 8.3, 8.4: No parse_intent, QueryEngine, or _rule_based_fallback in chat_hybrid.py
  - Requirements 7.3: No hardcoded template fallback strings in _format_response
"""

import os
import inspect
import pytest


# ---------------------------------------------------------------------------
# 1. Phi3Config default model_name
# ---------------------------------------------------------------------------

def test_phi3_config_default_model_name():
    """Phi3Config().model_name must default to Phi-3-mini-4k-instruct."""
    from app.config.phi3_config import Phi3Config

    config = Phi3Config()
    assert config.model_name == "microsoft/Phi-3-mini-4k-instruct"


# ---------------------------------------------------------------------------
# 2. Prompt template functions return expected content
# ---------------------------------------------------------------------------

def test_build_stage1_prompt_returns_nonempty_string():
    """build_stage1_prompt() must return a non-empty string with key phrases."""
    from app.config.prompt_templates import build_stage1_prompt

    prompt = build_stage1_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # Should contain identity and intent extraction context
    assert "AU-Ggregates" in prompt
    assert "intent_type" in prompt


def test_build_stage3_prompt_returns_nonempty_string():
    """build_stage3_prompt() must return a non-empty string with key phrases."""
    from app.config.prompt_templates import build_stage3_prompt

    prompt = build_stage3_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # Should contain identity and response formatting rules
    assert "AU-Ggregates" in prompt
    assert "RESPONSE FORMATTING" in prompt


# ---------------------------------------------------------------------------
# 3. phi3_service.py does NOT import parse_intent
# ---------------------------------------------------------------------------

def test_phi3_service_no_parse_intent_import():
    """phi3_service.py source must not import parse_intent."""
    source_path = os.path.join("app", "services", "phi3_service.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Should not contain any import of parse_intent
    assert "import parse_intent" not in source
    assert "from app.services.intent_parser" not in source


# ---------------------------------------------------------------------------
# 4. chat_hybrid.py does NOT import parse_intent or QueryEngine
# ---------------------------------------------------------------------------

def test_chat_hybrid_no_parse_intent_import():
    """chat_hybrid.py source must not import parse_intent."""
    source_path = os.path.join("app", "api", "routes", "chat_hybrid.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    assert "import parse_intent" not in source
    assert "from app.services.intent_parser" not in source


def test_chat_hybrid_no_query_engine_import():
    """chat_hybrid.py source must not import QueryEngine."""
    source_path = os.path.join("app", "api", "routes", "chat_hybrid.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    assert "import QueryEngine" not in source
    assert "from app.services.query_engine" not in source


# ---------------------------------------------------------------------------
# 5. chat_hybrid.py does NOT contain _rule_based_fallback function
# ---------------------------------------------------------------------------

def test_chat_hybrid_no_rule_based_fallback():
    """chat_hybrid.py source must not define _rule_based_fallback."""
    source_path = os.path.join("app", "api", "routes", "chat_hybrid.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    assert "_rule_based_fallback" not in source


# ---------------------------------------------------------------------------
# 6. _format_response has no hardcoded template fallback strings
# ---------------------------------------------------------------------------

def test_format_response_no_hardcoded_template_fallback():
    """phi3_service.py must not contain hardcoded template fallback strings
    like 'Found {n} results' or similar patterns in _format_response."""
    source_path = os.path.join("app", "services", "phi3_service.py")
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Extract the _format_response method source by finding its boundaries
    # Look for the method definition and the next method or end of class
    start_idx = source.find("async def _format_response(")
    assert start_idx != -1, "_format_response method not found in phi3_service.py"

    # Get the source from _format_response to end of file (it's the last method)
    format_response_source = source[start_idx:]

    # These are template fallback patterns that should NOT exist
    forbidden_patterns = [
        "Found {n} results",
        "Found {count} results",
        'f"Found {',
        "f'Found {",
        "Found {} results".format,
        "results for your query",
    ]

    for pattern in forbidden_patterns:
        if callable(pattern):
            continue
        assert pattern not in format_response_source, (
            f"_format_response contains forbidden template fallback pattern: '{pattern}'"
        )


# ---------------------------------------------------------------------------
# Imports for entity injection tests
# ---------------------------------------------------------------------------
from tests.test_entity_injection_properties import (
    inject_entity_filters,
    ENTITY_FILTER_MAP,
    SUPPLIER_MAP,
)


# ---------------------------------------------------------------------------
# 7. Single filter injection with known input/output
# ---------------------------------------------------------------------------

def test_single_filter_injection_category_fuel():
    """Injecting category='fuel' into a base SQL must produce the correct ILIKE condition.

    **Validates: Requirements 5.3**
    """
    sql = "SELECT * FROM ai_documents WHERE source_table = 'Expenses'"
    intent = {
        "source_table": "Expenses",
        "filters": {"category": "fuel"},
    }

    result = inject_entity_filters(sql, intent)

    assert "metadata->>'Category' ILIKE '%fuel%'" in result


# ---------------------------------------------------------------------------
# 8. Supplier + QuotationItem → quarry_location mapping
# ---------------------------------------------------------------------------

def test_supplier_quotation_item_quarry_location():
    """Supplier filter on QuotationItem must map to quarry_location metadata key.

    **Validates: Requirements 5.6**
    """
    sql = "SELECT * FROM ai_documents WHERE source_table = 'QuotationItem'"
    intent = {
        "source_table": "QuotationItem",
        "filters": {"supplier": "ABC Quarry"},
    }

    result = inject_entity_filters(sql, intent)

    assert "metadata->>'quarry_location' ILIKE '%ABC Quarry%'" in result


# ---------------------------------------------------------------------------
# 9. Supplier + Expenses → Name mapping
# ---------------------------------------------------------------------------

def test_supplier_expenses_name_mapping():
    """Supplier filter on Expenses must map to Name metadata key (default).

    **Validates: Requirements 5.6**
    """
    sql = "SELECT * FROM ai_documents WHERE source_table = 'Expenses'"
    intent = {
        "source_table": "Expenses",
        "filters": {"supplier": "Shell"},
    }

    result = inject_entity_filters(sql, intent)

    assert "metadata->>'Name' ILIKE '%Shell%'" in result


# ---------------------------------------------------------------------------
# 10. SQL injection prevention — single quotes stripped
# ---------------------------------------------------------------------------

def test_sql_injection_prevention_single_quotes_stripped():
    """Values with single quotes must have them stripped to prevent SQL injection.

    **Validates: Requirements 5.4**
    """
    sql = "SELECT * FROM ai_documents WHERE source_table = 'Expenses'"
    intent = {
        "source_table": "Expenses",
        "filters": {"category": "fuel'; DROP TABLE--"},
    }

    result = inject_entity_filters(sql, intent)

    # Single quotes must be stripped from the value
    assert "fuel; DROP TABLE--" in result
    # The original malicious value with quotes must NOT appear
    assert "fuel'" not in result
    assert "fuel'; DROP TABLE--" not in result


# ---------------------------------------------------------------------------
# 11. .env contains correct model reference
# ---------------------------------------------------------------------------

def test_env_contains_phi3_model_reference():
    """The .env file must set PHI3_MODEL to Phi-3-mini-4k-instruct.

    **Validates: Requirements 1.4**
    """
    with open(".env", "r", encoding="utf-8") as f:
        env_content = f.read()

    assert "PHI3_MODEL=microsoft/Phi-3-mini-4k-instruct" in env_content


# ---------------------------------------------------------------------------
# 12. Notebook contains correct model reference
# ---------------------------------------------------------------------------

def test_notebook_contains_phi3_model_reference():
    """The Colab notebook must reference Phi-3-mini-4k-instruct.

    **Validates: Requirements 9.1**
    """
    notebook_path = os.path.join("notebooks", "auggregates_ai_colab.ipynb")
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook_content = f.read()

    assert "microsoft/Phi-3-mini-4k-instruct" in notebook_content
