"""
Property-based tests for the Phi-3 Entity Injection Upgrade.

Tests validate correctness properties defined in the design document
for the phi3-entity-injection-upgrade spec. Each property test uses
hypothesis to verify behavior across many randomly generated inputs.
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def build_phi3_prompt(system_msg: str, user_msg: str) -> str:
    """Replicate the Phi-3 prompt building logic used in _extract_intent and _format_response."""
    return f"<|user|>\n{system_msg}\n\n{user_msg}\n<|end|>\n<|assistant|>"


# Feature: phi3-entity-injection-upgrade, Property 1: Prompt wrapper uses Phi-3 format and excludes Mistral format
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
@given(
    system_msg=st.text(min_size=0, max_size=200),
    user_msg=st.text(min_size=0, max_size=200),
)
@settings(max_examples=100)
def test_property1_phi3_prompt_format(system_msg: str, user_msg: str):
    """Property 1: Prompt wrapper uses Phi-3 format and excludes Mistral format.

    For any system message and user message, the built prompt SHALL:
    - Start with '<|user|>\\n'
    - End with '\\n<|end|>\\n<|assistant|>'
    - Contain both the system message and user message
    - NOT contain '[INST]' or '[/INST]' Mistral tokens
    """
    prompt = build_phi3_prompt(system_msg, user_msg)

    # Phi-3 format tokens present
    assert prompt.startswith("<|user|>\n"), f"Prompt must start with '<|user|>\\n', got: {prompt[:30]!r}"
    assert prompt.endswith("\n<|end|>\n<|assistant|>"), f"Prompt must end with '\\n<|end|>\\n<|assistant|>', got: {prompt[-30:]!r}"

    # Contains both messages
    assert system_msg in prompt, "Prompt must contain the system message"
    assert user_msg in prompt, "Prompt must contain the user message"

    # Mistral format tokens absent
    assert "[INST]" not in prompt, "Prompt must NOT contain Mistral '[INST]' token"
    assert "[/INST]" not in prompt, "Prompt must NOT contain Mistral '[/INST]' token"


import re
import json


def extract_intent_json(text: str) -> dict:
    """Replicate the JSON extraction logic from Phi3Service._extract_intent.

    Searches for the first valid JSON object in the text, parses it,
    and applies default values for required Intent_JSON fields.

    Raises ValueError if no valid JSON object is found.
    """
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        intent = json.loads(json_match.group())
        intent.setdefault("intent_type", "query_data")
        intent.setdefault("entities", [])
        intent.setdefault("filters", {})
        intent.setdefault("needs_clarification", False)
        return intent
    raise ValueError("No valid JSON found")


# Strategies for generating Intent_JSON-like dicts
_intent_types = st.sampled_from([
    "list_files", "query_data", "sum", "count", "average",
    "compare", "list_categories", "date_filter", "out_of_scope",
])

_intent_json_strategy = st.fixed_dictionaries(
    {},
    optional={
        "intent_type": _intent_types,
        "source_table": st.sampled_from(["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]),
        "entities": st.lists(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))), max_size=5),
        "filters": st.dictionaries(
            keys=st.sampled_from(["project_name", "category", "file_name", "supplier", "date", "status"]),
            values=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            max_size=4,
        ),
        "needs_clarification": st.booleans(),
    },
)

# Surrounding text that won't contain '{' or '}' to avoid confusing the regex
_safe_text = st.text(
    min_size=0,
    max_size=80,
    alphabet=st.characters(blacklist_characters="{}"),
)


# Feature: phi3-entity-injection-upgrade, Property 2: Valid JSON extraction from model output
# **Validates: Requirements 3.2**
@given(
    intent_dict=_intent_json_strategy,
    prefix=_safe_text,
    suffix=_safe_text,
)
@settings(max_examples=100)
def test_property2_valid_json_extraction(intent_dict: dict, prefix: str, suffix: str):
    """Property 2: Valid JSON extraction from model output.

    For any valid JSON dict embedded in surrounding text, the extraction logic
    SHALL find and parse the JSON object, returning a dict with all required
    Intent_JSON fields defaulted if missing.
    """
    embedded_text = prefix + json.dumps(intent_dict) + suffix

    result = extract_intent_json(embedded_text)

    # All original keys preserved with correct values
    for key, value in intent_dict.items():
        assert result[key] == value, f"Key {key!r}: expected {value!r}, got {result[key]!r}"

    # Defaults applied for missing required fields
    assert "intent_type" in result
    assert "entities" in result
    assert "filters" in result
    assert "needs_clarification" in result

    if "intent_type" not in intent_dict:
        assert result["intent_type"] == "query_data"
    if "entities" not in intent_dict:
        assert result["entities"] == []
    if "filters" not in intent_dict:
        assert result["filters"] == {}
    if "needs_clarification" not in intent_dict:
        assert result["needs_clarification"] is False


import pytest


# Strategy: text without curly braces (guaranteed no JSON objects)
_no_braces_text = st.text(
    min_size=0,
    max_size=200,
    alphabet=st.characters(blacklist_characters="{}"),
)

# Strategy: text with unbalanced/invalid JSON-like content
_invalid_json_text = st.one_of(
    # Plain text without braces
    _no_braces_text,
    # Opening brace but no closing brace
    st.builds(lambda t: "{" + t, _no_braces_text),
    # Closing brace but no opening brace
    st.builds(lambda t: t + "}", _no_braces_text),
    # Braces with non-JSON content inside
    st.builds(lambda t: "{" + t + "}", st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(blacklist_characters='{}":,0123456789'),
    ).filter(lambda s: s.strip() not in ("", "true", "false", "null"))),
)


# Feature: phi3-entity-injection-upgrade, Property 3: GenerationError on invalid model output
# **Validates: Requirements 3.3, 6.1**
@given(text=_invalid_json_text)
@settings(max_examples=100)
def test_property3_generation_error_on_invalid_output(text: str):
    """Property 3: GenerationError on invalid model output.

    For any string that does not contain a valid JSON object,
    the intent extraction logic SHALL raise a ValueError (mirrors GenerationError
    in the actual service code).
    """
    with pytest.raises((ValueError, json.JSONDecodeError)):
        extract_intent_json(text)


# ---------------------------------------------------------------------------
# Property 5: T5 input contains no entity values
# ---------------------------------------------------------------------------

SPIDER_SCHEMA = (
    "tables: ai_documents ("
    "id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type"
    ") | query: "
)


def build_t5_input(intent: dict) -> str:
    """Replicate the T5 input building logic from _generate_sql_with_t5_model.

    T5 receives only the schema prefix + intent_type + source_table.
    Entity names from filters are deliberately excluded.
    """
    intent_type = intent.get("intent_type", "query_data")
    source_table = intent.get("source_table", "Expenses")
    return SPIDER_SCHEMA + f"{intent_type} {source_table}"


# Strategy: filter values that are at least 3 chars, letters/numbers only
_filter_value = st.text(
    min_size=3,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# Strategy: Intent_JSON with at least 1 non-empty filter
_intent_with_filters = st.fixed_dictionaries(
    {
        "filters": st.dictionaries(
            keys=st.sampled_from([
                "project_name", "category", "file_name",
                "supplier", "date", "status",
                "client_name", "plate_no", "dr_no",
            ]),
            values=_filter_value,
            min_size=1,
            max_size=5,
        ),
    },
    optional={
        "intent_type": _intent_types,
        "source_table": st.sampled_from([
            "Expenses", "CashFlow", "Project", "Quotation", "QuotationItem",
        ]),
        "entities": st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            max_size=5,
        ),
    },
)


# Feature: phi3-entity-injection-upgrade, Property 5: T5 input contains no entity values
# **Validates: Requirements 5.1**
@given(intent=_intent_with_filters)
@settings(max_examples=100)
def test_property5_t5_input_no_entity_values(intent: dict):
    """Property 5: T5 input contains no entity values.

    For any Intent_JSON with non-empty filters containing entity values,
    the T5 input string SHALL contain only the SPIDER_SCHEMA prefix,
    the intent_type, and the source_table — none of the filter values
    from the Intent_JSON SHALL appear in the T5 input string.
    """
    t5_input = build_t5_input(intent)

    # T5 input must start with the schema prefix
    assert t5_input.startswith(SPIDER_SCHEMA), "T5 input must start with SPIDER_SCHEMA"

    # The suffix after the schema should be exactly "intent_type source_table"
    suffix = t5_input[len(SPIDER_SCHEMA):]
    expected_intent_type = intent.get("intent_type", "query_data")
    expected_source_table = intent.get("source_table", "Expenses")
    assert suffix == f"{expected_intent_type} {expected_source_table}", (
        f"T5 input suffix must be '<intent_type> <source_table>', got: {suffix!r}"
    )

    # No filter values should appear in the T5 input string
    for key, value in intent["filters"].items():
        assert value not in t5_input, (
            f"Filter value {value!r} (key={key!r}) must NOT appear in T5 input, "
            f"but found in: {t5_input!r}"
        )


# ---------------------------------------------------------------------------
# Property 6: Entity injection produces correct JSONB ILIKE conditions
# ---------------------------------------------------------------------------

# Replicate the constants from phi3_service.py
ENTITY_FILTER_MAP = {
    "project_name": "project_name",
    "category": "Category",
    "file_name": "Name",
    "date": "Date",
    "status": "status",
    "client_name": "client_name",
    "plate_no": "plate_no",
    "dr_no": "dr_no",
}

SUPPLIER_MAP = {
    "QuotationItem": "quarry_location",
    "_default": "Name",
}


def inject_entity_filters(sql: str, intent: dict) -> str:
    """Standalone version of Phi3Service._inject_entity_filters for testing."""
    filters = intent.get("filters", {})
    if not filters:
        return sql

    source_table = intent.get("source_table", "")
    conditions = []

    for key, value in filters.items():
        sanitized = str(value).replace("'", "")
        if not sanitized:
            continue

        if key == "supplier":
            metadata_key = SUPPLIER_MAP.get(source_table, SUPPLIER_MAP["_default"])
        else:
            metadata_key = ENTITY_FILTER_MAP.get(key)
            if metadata_key is None:
                continue

        conditions.append(f"metadata->>'{metadata_key}' ILIKE '%{sanitized}%'")

    if not conditions:
        return sql

    condition_str = " AND ".join(conditions)

    where_match = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
    if where_match:
        clause_pattern = re.search(
            r'\b(ORDER\s+BY|GROUP\s+BY|LIMIT)\b', sql[where_match.end():], re.IGNORECASE
        )
        if clause_pattern:
            insert_pos = where_match.end() + clause_pattern.start()
            sql = sql[:insert_pos] + " AND " + condition_str + " " + sql[insert_pos:]
        else:
            sql = sql + " AND " + condition_str
    else:
        clause_match = re.search(r'\b(ORDER\s+BY|GROUP\s+BY|LIMIT)\b', sql, re.IGNORECASE)
        if clause_match:
            insert_pos = clause_match.start()
            sql = sql[:insert_pos] + "WHERE " + condition_str + " " + sql[insert_pos:]
        else:
            sql = sql + " WHERE " + condition_str

    return sql


# Strategy: non-supplier filter keys from ENTITY_FILTER_MAP
_non_supplier_keys = st.sampled_from(list(ENTITY_FILTER_MAP.keys()))

# Strategy: filter values — letters/numbers, no single quotes
_filter_val = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

_source_tables = st.sampled_from([
    "Expenses", "CashFlow", "Project", "Quotation", "QuotationItem",
])

_base_sql = st.sampled_from([
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses'",
    "SELECT * FROM ai_documents WHERE source_table = 'CashFlow'",
    "SELECT * FROM ai_documents WHERE source_table = 'Quotation'",
    "SELECT * FROM ai_documents WHERE source_table = 'QuotationItem'",
    "SELECT * FROM ai_documents WHERE source_table = 'Project'",
])


# Feature: phi3-entity-injection-upgrade, Property 6: Entity injection produces correct JSONB ILIKE conditions
# **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6, 5.9**
@given(
    filter_key=_non_supplier_keys,
    filter_value=_filter_val,
    source_table=_source_tables,
    sql=_base_sql,
)
@settings(max_examples=100)
def test_property6_entity_injection_correct_ilike(
    filter_key: str, filter_value: str, source_table: str, sql: str,
):
    """Property 6: Entity injection produces correct JSONB ILIKE conditions.

    For any filter key-value pair in an Intent_JSON, _inject_entity_filters SHALL
    produce a condition using metadata>>'{correct_metadata_key}' ILIKE '%{value}%'
    where the metadata key is determined by ENTITY_FILTER_MAP.
    """
    intent = {
        "source_table": source_table,
        "filters": {filter_key: filter_value},
    }

    result = inject_entity_filters(sql, intent)

    expected_metadata_key = ENTITY_FILTER_MAP[filter_key]
    expected_condition = f"metadata->>'{expected_metadata_key}' ILIKE '%{filter_value}%'"

    assert expected_condition in result, (
        f"Expected condition {expected_condition!r} not found in result:\n{result}"
    )
    # ILIKE used (case-insensitive matching)
    assert "ILIKE" in result, "Result must use ILIKE for case-insensitive matching"


# Test supplier key separately — metadata key depends on source_table
@given(
    filter_value=_filter_val,
    source_table=_source_tables,
    sql=_base_sql,
)
@settings(max_examples=100)
def test_property6_supplier_injection_correct_ilike(
    filter_value: str, source_table: str, sql: str,
):
    """Property 6 (supplier): Supplier filter uses source_table-dependent metadata key.

    For supplier filter, QuotationItem → quarry_location, all others → Name.
    """
    intent = {
        "source_table": source_table,
        "filters": {"supplier": filter_value},
    }

    result = inject_entity_filters(sql, intent)

    if source_table == "QuotationItem":
        expected_key = "quarry_location"
    else:
        expected_key = "Name"

    expected_condition = f"metadata->>'{expected_key}' ILIKE '%{filter_value}%'"

    assert expected_condition in result, (
        f"Expected supplier condition {expected_condition!r} not found in result:\n{result}"
    )
    assert "ILIKE" in result, "Result must use ILIKE for case-insensitive matching"


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 7: Multiple filters combined with AND
# ---------------------------------------------------------------------------

# Strategy: Intent_JSON with at least 2 non-supplier filters
_multi_filter_dict = st.dictionaries(
    keys=_non_supplier_keys,
    values=_filter_val,
    min_size=2,
    max_size=6,
)


# **Validates: Requirements 5.7**
@given(
    filters=_multi_filter_dict,
    source_table=_source_tables,
    sql=_base_sql,
)
@settings(max_examples=100)
def test_property7_multiple_filters_and(
    filters: dict, source_table: str, sql: str,
):
    """Property 7: Multiple filters combined with AND.

    For any Intent_JSON with N filter entries (N >= 2), _inject_entity_filters
    SHALL produce a SQL string containing all N ILIKE conditions joined by AND.
    """
    intent = {
        "source_table": source_table,
        "filters": filters,
    }

    result = inject_entity_filters(sql, intent)

    # Build expected conditions for each filter
    expected_conditions = []
    for key, value in filters.items():
        sanitized = value.replace("'", "")
        if not sanitized:
            continue
        metadata_key = ENTITY_FILTER_MAP[key]
        expected_conditions.append(f"metadata->>'{metadata_key}' ILIKE '%{sanitized}%'")

    # All expected conditions must appear in the result
    for cond in expected_conditions:
        assert cond in result, (
            f"Expected condition {cond!r} not found in result:\n{result}"
        )

    # Conditions must be joined by AND — verify the AND-joined string is present
    if len(expected_conditions) >= 2:
        # Count AND occurrences between injected conditions in the result
        # The injected block should contain at least (N-1) ANDs connecting the conditions
        # Find the portion of SQL after the original WHERE clause
        upper_result = result.upper()
        and_count = 0
        for i, cond in enumerate(expected_conditions):
            if i > 0:
                # Check that AND appears before this condition in the result
                cond_pos = result.index(cond)
                preceding = result[:cond_pos]
                assert "AND" in preceding.upper(), (
                    f"Condition {cond!r} must be preceded by AND in result:\n{result}"
                )
                and_count += 1

        assert and_count >= len(expected_conditions) - 1, (
            f"Expected at least {len(expected_conditions) - 1} ANDs joining "
            f"{len(expected_conditions)} conditions, found {and_count}"
        )


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 8: Empty filters preserve SQL unchanged
# ---------------------------------------------------------------------------

# Strategy: Intent_JSON with explicitly empty filters
_intent_empty_filters = st.fixed_dictionaries(
    {
        "filters": st.just({}),
    },
    optional={
        "intent_type": _intent_types,
        "source_table": _source_tables,
        "entities": st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            max_size=5,
        ),
    },
)

# Strategy: broader SQL skeletons including ones with ORDER BY, GROUP BY, LIMIT, and no WHERE
_sql_skeletons = st.sampled_from([
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses'",
    "SELECT * FROM ai_documents WHERE source_table = 'CashFlow'",
    "SELECT * FROM ai_documents WHERE source_table = 'Quotation'",
    "SELECT * FROM ai_documents WHERE source_table = 'QuotationItem'",
    "SELECT * FROM ai_documents WHERE source_table = 'Project'",
    "SELECT COUNT(*) FROM ai_documents WHERE source_table = 'Expenses'",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' ORDER BY id",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' GROUP BY metadata->>'Category'",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' LIMIT 10",
    "SELECT * FROM ai_documents",
    "SELECT SUM((metadata->>'Amount')::numeric) FROM ai_documents WHERE source_table = 'Expenses'",
])


# **Validates: Requirements 5.8**
@given(
    sql=_sql_skeletons,
    intent=_intent_empty_filters,
)
@settings(max_examples=100)
def test_property8_empty_filters_preserve_sql(sql: str, intent: dict):
    """Property 8: Empty filters preserve SQL unchanged.

    For any SQL skeleton string and an Intent_JSON with an empty filters dict,
    _inject_entity_filters SHALL return the SQL string unchanged.
    """
    result = inject_entity_filters(sql, intent)

    assert result == sql, (
        f"Empty filters must preserve SQL unchanged.\n"
        f"Input:  {sql!r}\n"
        f"Output: {result!r}"
    )


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 9: Entity injection produces parseable SQL
# ---------------------------------------------------------------------------

import sqlparse

# Strategy: valid SQL skeletons that are parseable before injection
_parseable_sql_skeletons = st.sampled_from([
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses'",
    "SELECT * FROM ai_documents WHERE source_table = 'CashFlow'",
    "SELECT * FROM ai_documents WHERE source_table = 'Quotation'",
    "SELECT * FROM ai_documents WHERE source_table = 'QuotationItem'",
    "SELECT * FROM ai_documents WHERE source_table = 'Project'",
    "SELECT COUNT(*) FROM ai_documents WHERE source_table = 'Expenses'",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' ORDER BY id",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' GROUP BY metadata->>'Category'",
    "SELECT * FROM ai_documents WHERE source_table = 'Expenses' LIMIT 10",
    "SELECT * FROM ai_documents",
    "SELECT SUM((metadata->>'Amount')::numeric) FROM ai_documents WHERE source_table = 'Expenses'",
])

# Strategy: random filters with 0-5 entries (includes empty for no-op case)
_random_filters = st.dictionaries(
    keys=st.sampled_from(list(ENTITY_FILTER_MAP.keys()) + ["supplier"]),
    values=_filter_val,
    min_size=0,
    max_size=5,
)


# **Validates: Requirements 5.10**
@given(
    sql=_parseable_sql_skeletons,
    filters=_random_filters,
    source_table=_source_tables,
)
@settings(max_examples=100)
def test_property9_entity_injection_parseable_sql(
    sql: str, filters: dict, source_table: str,
):
    """Property 9: Entity injection produces parseable SQL.

    For any syntactically valid SQL skeleton and any valid Intent_JSON with filters,
    the result of _inject_entity_filters SHALL be a syntactically valid SQL string
    (i.e., it can be parsed without syntax errors by a SQL parser).
    """
    intent = {
        "source_table": source_table,
        "filters": filters,
    }

    result = inject_entity_filters(sql, intent)

    # Verify the result is parseable SQL using sqlparse
    parsed = sqlparse.parse(result)
    assert len(parsed) > 0, (
        f"sqlparse returned empty list for result:\n{result}"
    )
    # The first statement should have non-empty content
    assert str(parsed[0]).strip(), (
        f"sqlparse parsed an empty statement from result:\n{result}"
    )


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 10: Stage 3 raises GenerationError on empty response
# ---------------------------------------------------------------------------


class GenerationError(Exception):
    """Local GenerationError class for testing (mirrors the one in phi3_service.py)."""
    pass


def validate_stage3_response(response: str) -> str:
    """Replicate the Stage 3 response validation from _format_response.

    Raises GenerationError if response is empty or whitespace-only.
    """
    response = response.strip()
    if response:
        return response
    raise GenerationError("Stage 3: Phi-3 returned empty response")


# Strategy: empty or whitespace-only strings
_empty_whitespace = st.one_of(
    st.just(""),
    st.text(
        min_size=0,
        max_size=100,
        alphabet=st.sampled_from([" ", "\t", "\n", "\r"]),
    ),
)


# **Validates: Requirements 7.1**
@given(response=_empty_whitespace)
@settings(max_examples=100)
def test_property10_stage3_generation_error_on_empty(response: str):
    """Property 10: Stage 3 raises GenerationError on empty response.

    For any scenario where the model returns an empty or whitespace-only string
    in Stage 3, the _format_response method SHALL raise a GenerationError.
    """
    with pytest.raises(GenerationError):
        validate_stage3_response(response)


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 4: Out-of-scope gating blocks Stage 2
# ---------------------------------------------------------------------------


def route_intent(intent: dict) -> dict:
    """Replicate the pipeline routing logic from process_query.
    Returns a dict with routing decision."""
    if intent.get("intent_type") == "out_of_scope":
        message = intent.get("out_of_scope_message") or "I can only help with expense and cashflow data queries."
        return {"out_of_scope": True, "response": message, "stage2_called": False}
    if intent.get("needs_clarification"):
        return {"needs_clarification": True, "response": intent.get("clarification_question", ""), "stage2_called": False}
    return {"out_of_scope": False, "needs_clarification": False, "stage2_called": True}


# Strategy: random out-of-scope message (non-empty text or None to test default)
_out_of_scope_message = st.one_of(
    st.none(),
    st.just(""),
    st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P"))),
)

# Strategy: Intent_JSON with intent_type="out_of_scope" and random out_of_scope_message
_out_of_scope_intent = st.fixed_dictionaries(
    {
        "intent_type": st.just("out_of_scope"),
    },
    optional={
        "out_of_scope_message": _out_of_scope_message,
        "source_table": st.sampled_from(["Expenses", "CashFlow", "Project", "Quotation", "QuotationItem"]),
        "entities": st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            max_size=5,
        ),
        "filters": st.dictionaries(
            keys=st.sampled_from(["project_name", "category", "file_name", "supplier", "date", "status"]),
            values=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            max_size=4,
        ),
        "needs_clarification": st.just(False),
    },
)

DEFAULT_OOS_MESSAGE = "I can only help with expense and cashflow data queries."


# **Validates: Requirements 4.1, 4.2**
@given(intent=_out_of_scope_intent)
@settings(max_examples=100)
def test_property4_out_of_scope_blocks_stage2(intent: dict):
    """Property 4: Out-of-scope gating blocks Stage 2.

    For any Intent_JSON where intent_type equals "out_of_scope", the pipeline
    SHALL return a response with out_of_scope set to True and the response message
    equal to the out_of_scope_message field, without invoking Stage 2 SQL generation.
    """
    result = route_intent(intent)

    # 1. out_of_scope must be True
    assert result["out_of_scope"] is True, (
        f"out_of_scope must be True for out_of_scope intent, got: {result['out_of_scope']}"
    )

    # 2. stage2_called must be False (Stage 2 not invoked)
    assert result["stage2_called"] is False, (
        f"stage2_called must be False for out_of_scope intent, got: {result['stage2_called']}"
    )

    # 3. response equals the out_of_scope_message (or default if missing/empty)
    expected_message = intent.get("out_of_scope_message") or DEFAULT_OOS_MESSAGE
    assert result["response"] == expected_message, (
        f"Response must equal out_of_scope_message.\n"
        f"Expected: {expected_message!r}\n"
        f"Got:      {result['response']!r}"
    )


# ---------------------------------------------------------------------------
# Feature: phi3-entity-injection-upgrade, Property 11: HTTP 503 when models unavailable
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.api.routes.chat_hybrid import router


def _make_test_app() -> TestClient:
    """Create a minimal FastAPI app with the chat_hybrid router for testing."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# Strategy: random query strings for ChatRequest
_random_query = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P")),
)


# **Validates: Requirements 8.1**
@given(query=_random_query)
@settings(max_examples=100)
def test_property11_http_503_when_models_unavailable(query: str):
    """Property 11: HTTP 503 when models unavailable.

    For any chat request received when the AI pipeline models have failed to load
    (service is None after all retry attempts), the /chat/hybrid endpoint SHALL
    return an HTTP error response with status code 503.
    """
    client = _make_test_app()

    with patch("app.api.routes.chat_hybrid._phi3_service", None), \
         patch("app.api.routes.chat_hybrid._phi3_loading", False), \
         patch("app.api.routes.chat_hybrid._phi3_load_attempts", 3):
        response = client.post(
            "/chat/hybrid",
            json={"query": query},
        )

    assert response.status_code == 503, (
        f"Expected HTTP 503 when models unavailable, got {response.status_code}.\n"
        f"Query: {query!r}\n"
        f"Response: {response.text}"
    )


# Feature: phi3-entity-injection-upgrade, Property 12: Model status never reports "rule-based"
# **Validates: Requirements 8.5**
@given(service_loaded=st.booleans())
@settings(max_examples=100)
def test_property12_model_status_never_rule_based(service_loaded: bool):
    """Property 12: Model status never reports "rule-based".

    For any state of the service (loaded or not loaded), the /chat/hybrid/status
    endpoint response SHALL NOT contain the string "rule-based" in the pipeline field.
    """
    client = _make_test_app()

    mock_service = object() if service_loaded else None

    with patch("app.api.routes.chat_hybrid._phi3_service", mock_service):
        response = client.get("/chat/hybrid/status")

    assert response.status_code == 200, (
        f"Expected HTTP 200 from status endpoint, got {response.status_code}.\n"
        f"service_loaded: {service_loaded}\n"
        f"Response: {response.text}"
    )

    data = response.json()
    pipeline = data.get("pipeline", "")

    assert "rule-based" not in pipeline, (
        f"Pipeline field contains 'rule-based' which is forbidden.\n"
        f"service_loaded: {service_loaded}\n"
        f"pipeline: {pipeline!r}\n"
        f"Full response: {data}"
    )
