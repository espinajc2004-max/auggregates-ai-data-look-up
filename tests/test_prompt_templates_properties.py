"""
Property-based tests for prompt template correctness properties.

Uses hypothesis to verify formal correctness properties across random inputs.
Feature: mistral-prompt-template-upgrade
"""

import re
from itertools import combinations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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

# SQL statement patterns to detect
SQL_PATTERNS = [
    r"SELECT\s+.+\s+FROM\s+",
    r"INSERT\s+INTO\s+",
    r"UPDATE\s+.+\s+SET\s+",
    r"DELETE\s+FROM\s+",
    r"DROP\s+",
    r"ALTER\s+",
    r"TRUNCATE\s+",
]


def _contains_sql(text: str) -> bool:
    """Check if text contains any SQL statement patterns."""
    for pattern in SQL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


class TestProperty1NoSqlStatements:
    """Property 1: No SQL statements in any prompt template or assembled prompt.

    **Validates: Requirements 1.1, 1.2, 1.3**

    Feature: mistral-prompt-template-upgrade, Property 1: No SQL statements
    """

    def test_constants_have_no_sql(self):
        """All template constants should contain zero SQL statements."""
        constants = {
            "SYSTEM_IDENTITY": SYSTEM_IDENTITY,
            "SCHEMA_CONTEXT": SCHEMA_CONTEXT,
            "JSON_INTENT_EXAMPLES": JSON_INTENT_EXAMPLES,
            "SAFETY_RULES": SAFETY_RULES,
            "RESPONSE_FORMATTING_RULES": RESPONSE_FORMATTING_RULES,
            "EXAMPLE_QUERIES": EXAMPLE_QUERIES,
        }
        for name, value in constants.items():
            assert not _contains_sql(value), (
                f"SQL statement found in {name}"
            )

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_build_system_prompt_no_sql(self, context: str):
        """build_system_prompt() output should contain no SQL for any context.

        **Validates: Requirements 1.2**
        """
        prompt = build_system_prompt(conversation_context=context)
        assert not _contains_sql(prompt), (
            f"SQL found in build_system_prompt() with context: {context!r}"
        )

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_build_stage1_prompt_no_sql(self, context: str):
        """build_stage1_prompt() output should contain no SQL for any context.

        **Validates: Requirements 1.1, 1.3**
        """
        prompt = build_stage1_prompt(conversation_context=context)
        assert not _contains_sql(prompt), (
            f"SQL found in build_stage1_prompt() with context: {context!r}"
        )

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_build_stage3_prompt_no_sql(self, context: str):
        """build_stage3_prompt() output should contain no SQL for any context.

        **Validates: Requirements 1.3**
        """
        prompt = build_stage3_prompt(conversation_context=context)
        assert not _contains_sql(prompt), (
            f"SQL found in build_stage3_prompt() with context: {context!r}"
        )


class TestProperty2StageContentIsolation:
    """Property 2: Stage content isolation.

    **Validates: Requirements 4.3, 4.4, 7.2**

    Feature: mistral-prompt-template-upgrade, Property 2: Stage content isolation
    """

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_stage1_excludes_response_formatting(self, context: str):
        """Stage 1 prompt should not contain RESPONSE_FORMATTING_RULES content."""
        prompt = build_stage1_prompt(conversation_context=context)
        assert RESPONSE_FORMATTING_RULES.strip() not in prompt, (
            "RESPONSE_FORMATTING_RULES found in Stage 1 prompt"
        )

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_stage3_excludes_intent_examples(self, context: str):
        """Stage 3 prompt should not contain JSON_INTENT_EXAMPLES content."""
        prompt = build_stage3_prompt(conversation_context=context)
        assert JSON_INTENT_EXAMPLES.strip() not in prompt, (
            "JSON_INTENT_EXAMPLES found in Stage 3 prompt"
        )

    @given(context=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_stage3_excludes_schema_context(self, context: str):
        """Stage 3 prompt should not contain SCHEMA_CONTEXT content."""
        prompt = build_stage3_prompt(conversation_context=context)
        assert SCHEMA_CONTEXT.strip() not in prompt, (
            "SCHEMA_CONTEXT found in Stage 3 prompt"
        )


class TestProperty3IntentJsonRequiredFields:
    """Property 3: All Intent_JSON examples contain required fields.

    **Validates: Requirements 3.4, 6.3**

    Feature: mistral-prompt-template-upgrade, Property 3: Intent_JSON required fields
    """

    REQUIRED_FIELDS = [
        "intent_type",
        "source_table",
        "entities",
        "filters",
        "needs_clarification",
    ]

    def _parse_json_examples(self) -> list:
        """Extract all JSON objects from Output lines in JSON_INTENT_EXAMPLES."""
        import json
        examples = []
        for match in re.finditer(r'Output:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', JSON_INTENT_EXAMPLES):
            try:
                obj = json.loads(match.group(1))
                examples.append(obj)
            except json.JSONDecodeError:
                continue
        return examples

    def test_all_examples_have_required_fields(self):
        """Every Intent_JSON example must contain all required fields."""
        examples = self._parse_json_examples()
        assert len(examples) >= 18, f"Expected 18+ examples, found {len(examples)}"
        for i, example in enumerate(examples):
            for field in self.REQUIRED_FIELDS:
                assert field in example, (
                    f"Example {i + 1} missing required field '{field}': {example}"
                )

    def test_intent_type_values_are_valid(self):
        """Every intent_type should be one of the allowed values."""
        valid_types = {
            "list_files", "query_data", "sum", "count",
            "average", "compare", "list_categories", "date_filter",
            "out_of_scope",
        }
        examples = self._parse_json_examples()
        for i, example in enumerate(examples):
            assert example["intent_type"] in valid_types, (
                f"Example {i + 1} has invalid intent_type: {example['intent_type']}"
            )

    def test_source_table_values_are_valid(self):
        """Every source_table should be 'Expenses' or 'CashFlow'."""
        valid_tables = {"Expenses", "CashFlow"}
        examples = self._parse_json_examples()
        for i, example in enumerate(examples):
            assert example["source_table"] in valid_tables, (
                f"Example {i + 1} has invalid source_table: {example['source_table']}"
            )


class TestProperty4NoContentDuplication:
    """Property 4: No significant content duplication across template constants.

    **Validates: Requirements 7.3**

    Feature: mistral-prompt-template-upgrade, Property 4: No content duplication
    """

    TEMPLATE_CONSTANTS = {
        "SYSTEM_IDENTITY": SYSTEM_IDENTITY,
        "SCHEMA_CONTEXT": SCHEMA_CONTEXT,
        "JSON_INTENT_EXAMPLES": JSON_INTENT_EXAMPLES,
        "SAFETY_RULES": SAFETY_RULES,
        "RESPONSE_FORMATTING_RULES": RESPONSE_FORMATTING_RULES,
    }

    SUBSTRING_LENGTH = 50

    def _get_substrings(self, text: str, length: int) -> set:
        """Extract all contiguous substrings of given length from text."""
        text = text.strip()
        substrings = set()
        for i in range(len(text) - length + 1):
            substr = text[i:i + length]
            # Skip substrings that are mostly whitespace
            if len(substr.strip()) < length // 2:
                continue
            substrings.add(substr)
        return substrings

    def test_no_50_char_overlap_between_constants(self):
        """No contiguous substring of 50+ chars should appear in two different constants."""
        names = list(self.TEMPLATE_CONSTANTS.keys())
        for i, j in combinations(range(len(names)), 2):
            name_a, name_b = names[i], names[j]
            text_a = self.TEMPLATE_CONSTANTS[name_a]
            text_b = self.TEMPLATE_CONSTANTS[name_b]

            substrings_a = self._get_substrings(text_a, self.SUBSTRING_LENGTH)
            substrings_b = self._get_substrings(text_b, self.SUBSTRING_LENGTH)

            overlap = substrings_a & substrings_b
            assert len(overlap) == 0, (
                f"Found {len(overlap)} duplicated 50-char substring(s) between "
                f"{name_a} and {name_b}. First overlap: {next(iter(overlap))!r}"
            )
