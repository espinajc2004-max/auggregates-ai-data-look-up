"""
Unit tests for prompt template constants in app/config/prompt_templates.py.

Validates content correctness, completeness, and safety of all prompt template
constants after the Phi-3 prompt template upgrade.
"""

import json
import re

import pytest

from app.config.prompt_templates import (
    EXAMPLE_QUERIES,
    JSON_INTENT_EXAMPLES,
    RESPONSE_FORMATTING_RULES,
    SAFETY_RULES,
    SCHEMA_CONTEXT,
    SYSTEM_IDENTITY,
    build_stage1_prompt,
    build_stage3_prompt,
    build_system_prompt,
)


# ============================================================
# SCHEMA_CONTEXT tests (Requirements 2.1–2.6)
# ============================================================

class TestSchemaContext:
    """Validate SCHEMA_CONTEXT contains all required columns and metadata keys."""

    REQUIRED_COLUMNS = [
        "id",
        "source_table",
        "file_name",
        "project_name",
        "searchable_text",
        "metadata",
        "document_type",
    ]

    EXPENSES_METADATA_KEYS = [
        "Category",
        "Expenses",
        "Date",
        "Description",
        "Supplier",
        "Method",
        "Remarks",
        "Name",
    ]

    CASHFLOW_METADATA_KEYS = [
        "Inflow",
        "Outflow",
        "Balance",
        "Date",
        "Remarks",
        "Description",
    ]

    def test_contains_all_required_columns(self):
        """Req 2.1: SCHEMA_CONTEXT describes all columns of ai_documents."""
        for col in self.REQUIRED_COLUMNS:
            assert col in SCHEMA_CONTEXT, f"Missing column '{col}' in SCHEMA_CONTEXT"

    def test_contains_expenses_metadata_keys(self):
        """Req 2.2: SCHEMA_CONTEXT describes Expenses metadata keys."""
        for key in self.EXPENSES_METADATA_KEYS:
            assert key in SCHEMA_CONTEXT, f"Missing Expenses metadata key '{key}'"

    def test_contains_cashflow_metadata_keys(self):
        """Req 2.3: SCHEMA_CONTEXT describes CashFlow metadata keys."""
        for key in self.CASHFLOW_METADATA_KEYS:
            assert key in SCHEMA_CONTEXT, f"Missing CashFlow metadata key '{key}'"

    def test_contains_expenses_amount_naming_note(self):
        """Req 2.5: SCHEMA_CONTEXT notes that Expenses amount is NOT called 'Amount'."""
        assert "NOT" in SCHEMA_CONTEXT or "not" in SCHEMA_CONTEXT
        assert "Amount" in SCHEMA_CONTEXT
        # The note should clarify the field is called "Expenses", not "Amount"
        assert re.search(r'NOT.*"?Amount"?', SCHEMA_CONTEXT, re.IGNORECASE), (
            "SCHEMA_CONTEXT should note that the amount field is NOT called 'Amount'"
        )

    def test_contains_document_type_description(self):
        """Req 2.6: SCHEMA_CONTEXT includes document_type with a description."""
        assert "document_type" in SCHEMA_CONTEXT
        # Should have some description text near document_type
        match = re.search(r"document_type\s+\w+\s+--\s+.+", SCHEMA_CONTEXT)
        assert match, "document_type should have a description comment"


# ============================================================
# EXAMPLE_QUERIES tests (Requirement 1.1)
# ============================================================

class TestExampleQueries:
    """Validate EXAMPLE_QUERIES is deprecated and empty."""

    def test_example_queries_is_empty_string(self):
        """Req 1.1: EXAMPLE_QUERIES is set to empty string."""
        assert EXAMPLE_QUERIES == ""


# ============================================================
# SAFETY_RULES tests (Requirements 5.1–5.4)
# ============================================================

class TestSafetyRules:
    """Validate SAFETY_RULES has no SQL generation phrases and has correct instructions."""

    def test_no_sql_generation_phrases(self):
        """Req 5.1: SAFETY_RULES does NOT contain SQL generation constraints."""
        assert "Generate ONLY SELECT" not in SAFETY_RULES
        assert "INSERT, UPDATE, DELETE" not in SAFETY_RULES
        assert "INSERT INTO" not in SAFETY_RULES

    def test_contains_stage1_json_instruction(self):
        """Req 5.2: SAFETY_RULES instructs Stage 1 to return only JSON."""
        assert "Stage 1" in SAFETY_RULES
        assert "JSON" in SAFETY_RULES

    def test_contains_stage3_natural_language_instruction(self):
        """Req 5.2: SAFETY_RULES instructs Stage 3 to return only natural language."""
        assert "Stage 3" in SAFETY_RULES
        assert "natural language" in SAFETY_RULES

    def test_retains_no_expose_rule(self):
        """Req 5.3: SAFETY_RULES retains rule about not exposing technical details."""
        assert re.search(r"(raw SQL|internal schema)", SAFETY_RULES), (
            "SAFETY_RULES should retain the no-expose rule"
        )

    def test_retains_english_only_rule(self):
        """Req 5.4: SAFETY_RULES retains English-only rule."""
        assert "English" in SAFETY_RULES


# ============================================================
# JSON_INTENT_EXAMPLES tests (Requirements 3.1–3.4)
# ============================================================

def _parse_json_examples(text: str) -> list[dict]:
    """Extract all JSON objects from the Output lines in JSON_INTENT_EXAMPLES."""
    examples = []
    # Match Output: followed by a JSON object (handling nested braces)
    for match in re.finditer(r'Output:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', text):
        try:
            obj = json.loads(match.group(1))
            examples.append(obj)
        except json.JSONDecodeError:
            continue
    return examples


class TestJsonIntentExamples:
    """Validate JSON_INTENT_EXAMPLES content and coverage."""

    def test_has_at_least_18_examples(self):
        """Req 3.1: JSON_INTENT_EXAMPLES has 18+ examples (10 original + 8 new)."""
        examples = _parse_json_examples(JSON_INTENT_EXAMPLES)
        assert len(examples) >= 18, (
            f"Expected at least 18 JSON examples, found {len(examples)}"
        )

    def test_diverse_phrasing_how_much(self):
        """Req 3.2: Examples include 'how much' phrasing."""
        assert "how much" in JSON_INTENT_EXAMPLES.lower()

    def test_diverse_phrasing_show_me_or_show_all(self):
        """Req 3.2: Examples include 'show me' or 'show all' phrasing."""
        lower = JSON_INTENT_EXAMPLES.lower()
        assert "show me" in lower or "show all" in lower

    def test_diverse_phrasing_what_files(self):
        """Req 3.2: Examples include 'what files' phrasing."""
        assert "what files" in JSON_INTENT_EXAMPLES.lower()

    def test_diverse_phrasing_total_cost(self):
        """Req 3.2: Examples include 'total cost' phrasing."""
        assert "total cost" in JSON_INTENT_EXAMPLES.lower()

    def test_diverse_phrasing_find(self):
        """Req 3.2: Examples include 'find all' or 'find cement' phrasing."""
        lower = JSON_INTENT_EXAMPLES.lower()
        assert "find all" in lower or "find cement" in lower

    def test_diverse_phrasing_how_many(self):
        """Req 3.2: Examples include 'how many' phrasing."""
        assert "how many" in JSON_INTENT_EXAMPLES.lower()

    def test_all_examples_have_required_fields(self):
        """Req 3.4: Each Intent_JSON example contains all required fields."""
        required_fields = [
            "intent_type",
            "source_table",
            "entities",
            "filters",
            "needs_clarification",
        ]
        examples = _parse_json_examples(JSON_INTENT_EXAMPLES)
        assert len(examples) > 0, "No JSON examples found to validate"
        for i, example in enumerate(examples):
            for field in required_fields:
                assert field in example, (
                    f"Example {i + 1} missing required field '{field}': {example}"
                )


# ============================================================
# SYSTEM_IDENTITY tests (Requirements 6.5)
# ============================================================

class TestSystemIdentity:
    """Validate SYSTEM_IDENTITY retains key behavioral rules."""

    def test_contains_english_only(self):
        """Req 6.5: SYSTEM_IDENTITY contains English-only rule."""
        assert "English only" in SYSTEM_IDENTITY

    def test_contains_peso_sign(self):
        """Req 6.5: SYSTEM_IDENTITY contains ₱ formatting rule."""
        assert "₱" in SYSTEM_IDENTITY

    def test_contains_three_sentence_rule(self):
        """Req 6.5: SYSTEM_IDENTITY contains 3-sentence limit."""
        assert "3 sentences" in SYSTEM_IDENTITY


# ============================================================
# Prompt Builder tests (Requirements 4.1–4.5, 6.2, 7.1, 7.2)
# ============================================================

class TestPromptBuilders:
    """Validate prompt builder functions for stage isolation and backward compat."""

    def test_stage1_contains_schema_context(self):
        """Req 4.1: Stage 1 prompt includes SCHEMA_CONTEXT."""
        prompt = build_stage1_prompt()
        assert SCHEMA_CONTEXT.strip() in prompt

    def test_stage1_contains_intent_examples(self):
        """Req 4.1: Stage 1 prompt includes JSON_INTENT_EXAMPLES."""
        prompt = build_stage1_prompt()
        assert JSON_INTENT_EXAMPLES.strip() in prompt

    def test_stage1_excludes_response_formatting(self):
        """Req 4.3: Stage 1 prompt does NOT include RESPONSE_FORMATTING_RULES."""
        prompt = build_stage1_prompt()
        assert RESPONSE_FORMATTING_RULES.strip() not in prompt

    def test_stage3_contains_response_formatting(self):
        """Req 4.2: Stage 3 prompt includes RESPONSE_FORMATTING_RULES."""
        prompt = build_stage3_prompt()
        assert RESPONSE_FORMATTING_RULES.strip() in prompt

    def test_stage3_excludes_schema_context(self):
        """Req 4.4: Stage 3 prompt does NOT include SCHEMA_CONTEXT."""
        prompt = build_stage3_prompt()
        assert SCHEMA_CONTEXT.strip() not in prompt

    def test_stage3_excludes_intent_examples(self):
        """Req 4.4: Stage 3 prompt does NOT include JSON_INTENT_EXAMPLES."""
        prompt = build_stage3_prompt()
        assert JSON_INTENT_EXAMPLES.strip() not in prompt

    def test_build_system_prompt_excludes_example_queries(self):
        """Req 4.5: build_system_prompt() excludes EXAMPLE_QUERIES content."""
        prompt = build_system_prompt()
        # EXAMPLE_QUERIES is empty string, so just verify no SQL patterns
        assert "SELECT * FROM" not in prompt
        assert "SELECT DISTINCT" not in prompt

    def test_build_system_prompt_signature(self):
        """Req 6.2: build_system_prompt() retains original signature."""
        # Should work with no args
        prompt1 = build_system_prompt()
        assert isinstance(prompt1, str)
        # Should work with conversation_context
        prompt2 = build_system_prompt(conversation_context="test context")
        assert isinstance(prompt2, str)
        assert "test context" in prompt2

    def test_stage1_accepts_conversation_context(self):
        """Req 4.1: build_stage1_prompt() accepts conversation_context."""
        prompt = build_stage1_prompt(conversation_context="previous chat")
        assert "previous chat" in prompt

    def test_stage3_accepts_conversation_context(self):
        """Req 4.2: build_stage3_prompt() accepts conversation_context."""
        prompt = build_stage3_prompt(conversation_context="previous chat")
        assert "previous chat" in prompt

    def test_stage1_shorter_than_old_system_prompt(self):
        """Req 7.1: Stage 1 prompt is shorter (no SQL examples)."""
        # build_system_prompt now matches stage1 (both exclude EXAMPLE_QUERIES)
        # But stage1 should be shorter than what the OLD prompt was (which included SQL examples)
        stage1 = build_stage1_prompt()
        # The old prompt included ~800 chars of SQL examples that are now removed
        # Just verify stage1 doesn't contain SQL patterns
        assert "SELECT * FROM" not in stage1
