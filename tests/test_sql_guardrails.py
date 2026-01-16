"""
Unit Tests for Server SQL Guardrails
Tests security enforcement on generated SQL.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.stage2.sql_guardrails import ServerSQLGuardrails, GuardrailResult


def test_block_ddl_operations():
    """Test that DDL operations are blocked."""
    guardrails = ServerSQLGuardrails(allowed_tables=["ai_documents", "projects"])
    
    # Test dangerous operations
    dangerous_sqls = [
        "DROP TABLE ai_documents;",
        "DELETE FROM ai_documents WHERE id = 1;",
        "UPDATE ai_documents SET content = 'hacked';",
        "INSERT INTO ai_documents VALUES ('malicious');",
        "CREATE TABLE evil (id INT);",
        "ALTER TABLE ai_documents ADD COLUMN evil TEXT;",
        "TRUNCATE TABLE ai_documents;",
    ]
    
    for sql in dangerous_sqls:
        result = guardrails.block_ddl(sql)
        assert not result.safe, f"Should block: {sql}"
        assert result.rejection_reason is not None
        print(f"✅ Blocked: {sql[:50]}... - Reason: {result.rejection_reason}")
    
    # Test safe SELECT query
    safe_sql = "SELECT * FROM ai_documents WHERE content @@ 'fuel';"
    result = guardrails.block_ddl(safe_sql)
    assert result.safe, "Should allow SELECT query"
    print(f"✅ Allowed: {safe_sql}")


def test_inject_org_id():
    """Test that org_id is always injected."""
    guardrails = ServerSQLGuardrails(allowed_tables=["ai_documents"])
    
    # Test 1: SQL with existing WHERE clause
    sql1 = "SELECT * FROM ai_documents WHERE content @@ 'fuel';"
    result1 = guardrails.inject_org_id(sql1, org_id=123)
    assert result1.safe
    assert "org_id = 123" in result1.safe_sql
    assert "WHERE org_id = 123 AND" in result1.safe_sql
    print(f"✅ Injected org_id into WHERE clause")
    print(f"   Original: {sql1}")
    print(f"   Safe SQL: {result1.safe_sql}")
    
    # Test 2: SQL without WHERE clause
    sql2 = "SELECT * FROM ai_documents;"
    result2 = guardrails.inject_org_id(sql2, org_id=456)
    assert result2.safe
    assert "org_id = 456" in result2.safe_sql
    assert "WHERE org_id = 456" in result2.safe_sql
    print(f"✅ Added WHERE clause with org_id")
    print(f"   Original: {sql2}")
    print(f"   Safe SQL: {result2.safe_sql}")
    
    # Test 3: SQL with ORDER BY
    sql3 = "SELECT * FROM ai_documents ORDER BY created_at DESC;"
    result3 = guardrails.inject_org_id(sql3, org_id=789)
    assert result3.safe
    assert "org_id = 789" in result3.safe_sql
    assert "WHERE org_id = 789 ORDER BY" in result3.safe_sql
    print(f"✅ Injected org_id before ORDER BY")
    print(f"   Original: {sql3}")
    print(f"   Safe SQL: {result3.safe_sql}")
    
    # Test 4: SQL with LIMIT
    sql4 = "SELECT * FROM ai_documents LIMIT 10;"
    result4 = guardrails.inject_org_id(sql4, org_id=999)
    assert result4.safe
    assert "org_id = 999" in result4.safe_sql
    assert "WHERE org_id = 999 LIMIT" in result4.safe_sql
    print(f"✅ Injected org_id before LIMIT")
    print(f"   Original: {sql4}")
    print(f"   Safe SQL: {result4.safe_sql}")


def test_validate_schema():
    """Test that only allowed tables are permitted."""
    guardrails = ServerSQLGuardrails(allowed_tables=["ai_documents", "projects", "conversations"])
    
    # Test 1: Allowed table
    sql1 = "SELECT * FROM ai_documents WHERE content @@ 'fuel';"
    result1 = guardrails.validate_schema(sql1)
    assert result1.safe
    print(f"✅ Allowed table: ai_documents")
    
    # Test 2: Disallowed table
    sql2 = "SELECT * FROM users WHERE email = 'hacker@evil.com';"
    result2 = guardrails.validate_schema(sql2)
    assert not result2.safe
    assert "not in allowed tables" in result2.rejection_reason
    print(f"✅ Blocked disallowed table: users")
    
    # Test 3: Multiple allowed tables (JOIN)
    sql3 = "SELECT * FROM ai_documents JOIN projects ON ai_documents.project_id = projects.id;"
    result3 = guardrails.validate_schema(sql3)
    assert result3.safe
    print(f"✅ Allowed multiple tables: ai_documents, projects")


def test_add_limit_if_missing():
    """Test that LIMIT is added to SELECT queries without aggregation."""
    guardrails = ServerSQLGuardrails(allowed_tables=["ai_documents"])
    
    # Test 1: SELECT without LIMIT (should add)
    sql1 = "SELECT * FROM ai_documents WHERE content @@ 'fuel';"
    safe_sql1 = guardrails._add_limit_if_missing(sql1)
    assert "LIMIT 10" in safe_sql1
    print(f"✅ Added LIMIT to SELECT query")
    print(f"   Original: {sql1}")
    print(f"   With LIMIT: {safe_sql1}")
    
    # Test 2: SELECT with existing LIMIT (should not add)
    sql2 = "SELECT * FROM ai_documents LIMIT 5;"
    safe_sql2 = guardrails._add_limit_if_missing(sql2)
    assert safe_sql2 == sql2
    print(f"✅ Did not add LIMIT (already present)")
    
    # Test 3: SELECT with aggregation (should not add)
    sql3 = "SELECT COUNT(*) FROM ai_documents;"
    safe_sql3 = guardrails._add_limit_if_missing(sql3)
    assert "LIMIT" not in safe_sql3
    print(f"✅ Did not add LIMIT (aggregation query)")
    
    # Test 4: SELECT with SUM (should not add)
    sql4 = "SELECT SUM(amount) FROM ai_documents;"
    safe_sql4 = guardrails._add_limit_if_missing(sql4)
    assert "LIMIT" not in safe_sql4
    print(f"✅ Did not add LIMIT (SUM aggregation)")


def test_enforce_guardrails_full_pipeline():
    """Test the complete guardrail enforcement pipeline."""
    guardrails = ServerSQLGuardrails(allowed_tables=["ai_documents", "projects"])
    
    # Test 1: Safe query (should pass all checks)
    sql1 = "SELECT * FROM ai_documents WHERE content @@ 'fuel';"
    result1 = guardrails.enforce_guardrails(sql1, org_id=123, user_id=1)
    assert result1.safe
    assert "org_id = 123" in result1.safe_sql
    assert "LIMIT 10" in result1.safe_sql
    print(f"✅ Full pipeline passed for safe query")
    print(f"   Original: {sql1}")
    print(f"   Safe SQL: {result1.safe_sql}")
    
    # Test 2: Dangerous query (should be blocked)
    sql2 = "DROP TABLE ai_documents;"
    result2 = guardrails.enforce_guardrails(sql2, org_id=123, user_id=1)
    assert not result2.safe
    assert "Dangerous operation blocked" in result2.rejection_reason
    print(f"✅ Full pipeline blocked dangerous query")
    print(f"   Blocked: {sql2}")
    print(f"   Reason: {result2.rejection_reason}")
    
    # Test 3: Disallowed table (should be blocked)
    sql3 = "SELECT * FROM evil_table WHERE id = 1;"
    result3 = guardrails.enforce_guardrails(sql3, org_id=123, user_id=1)
    assert not result3.safe
    assert "not in allowed tables" in result3.rejection_reason
    print(f"✅ Full pipeline blocked disallowed table")
    print(f"   Blocked: {sql3}")
    print(f"   Reason: {result3.rejection_reason}")
    
    # Test 4: Aggregation query (should not add LIMIT)
    sql4 = "SELECT COUNT(*) FROM ai_documents WHERE content @@ 'fuel';"
    result4 = guardrails.enforce_guardrails(sql4, org_id=456, user_id=2)
    assert result4.safe
    assert "org_id = 456" in result4.safe_sql
    assert "LIMIT" not in result4.safe_sql  # Should not add LIMIT for aggregation
    print(f"✅ Full pipeline passed for aggregation query (no LIMIT added)")
    print(f"   Original: {sql4}")
    print(f"   Safe SQL: {result4.safe_sql}")


if __name__ == "__main__":
    print("=" * 80)
    print("SERVER SQL GUARDRAILS UNIT TESTS")
    print("=" * 80)
    print()
    
    print("TEST 1: Block DDL Operations")
    print("-" * 80)
    test_block_ddl_operations()
    print()
    
    print("TEST 2: Inject org_id")
    print("-" * 80)
    test_inject_org_id()
    print()
    
    print("TEST 3: Validate Schema")
    print("-" * 80)
    test_validate_schema()
    print()
    
    print("TEST 4: Add LIMIT if Missing")
    print("-" * 80)
    test_add_limit_if_missing()
    print()
    
    print("TEST 5: Full Guardrail Pipeline")
    print("-" * 80)
    test_enforce_guardrails_full_pipeline()
    print()
    
    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
