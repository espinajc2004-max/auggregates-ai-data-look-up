"""
SQL Validator
=============
Validates SQL queries for safety and correctness.
"""

import re
import sqlparse
from typing import List, Optional
from dataclasses import dataclass
from app.utils.logger import logger


@dataclass
class ValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_sql: Optional[str]
    user_message: Optional[str] = None  # User-friendly message


class SQLValidator:
    """Validate SQL queries for safety and correctness."""
    
    # Dangerous SQL keywords that indicate write operations
    WRITE_OPERATIONS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
        'TRUNCATE', 'EXECUTE', 'CALL', 'GRANT', 'REVOKE'
    ]
    
    # SQL injection patterns
    INJECTION_PATTERNS = [
        r'(?<!>)--(?!>)',  # SQL comment (but NOT JSONB operator -->> or ->)
        r'/\*',  # Multi-line comment start
        r'\*/',  # Multi-line comment end
        r';\s*DROP',  # Command chaining with DROP
        r';\s*DELETE',  # Command chaining with DELETE
        r';\s*UPDATE',  # Command chaining with UPDATE
        r'UNION\s+SELECT',  # UNION-based injection
        r'OR\s+1\s*=\s*1',  # Always true condition
        r'OR\s+\'1\'\s*=\s*\'1\'',  # Always true condition with quotes
    ]
    
    def validate(self, sql: str, role: str) -> ValidationResult:
        """
        Validate SQL query against security rules.
        
        Checks:
        1. SQL injection patterns
        2. Write operations (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE)
        3. Multiple statements or command chaining
        4. Role-based table access
        5. Syntax correctness
        6. Gibberish detection (non-SQL output from T5)
        
        Args:
            sql: Generated SQL query
            role: User role for RBAC
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []
        
        if not sql or not sql.strip():
            return ValidationResult(
                is_valid=False,
                errors=["Empty SQL query"],
                warnings=[],
                sanitized_sql=None
            )
        
        # Check for gibberish / non-SQL output (T5 bad weights produce repeated non-SQL words)
        gibberish_errors = self._check_gibberish(sql)
        errors.extend(gibberish_errors)
        
        # Check for SQL injection patterns
        injection_errors = self._check_injection(sql)
        errors.extend(injection_errors)
        
        # Check for write operations
        write_errors = self._check_write_operations(sql)
        errors.extend(write_errors)
        
        # Check for multiple statements
        multiple_stmt_errors = self._check_multiple_statements(sql)
        errors.extend(multiple_stmt_errors)
        
        # Check role-based access
        role_errors = self._check_role_access(sql, role)
        errors.extend(role_errors)
        
        # Parse SQL for syntax validation
        parsed = self._parse_sql(sql)
        if parsed is None:
            errors.append("Invalid SQL syntax")
        
        # Determine if valid
        is_valid = len(errors) == 0
        
        # Sanitize SQL if valid
        sanitized_sql = sql.strip() if is_valid else None
        
        # Generate user-friendly message
        user_message = None
        if not is_valid:
            user_message = self._generate_user_message(errors, role)
            logger.error(f"SQL validation failed: {', '.join(errors)}")
        else:
            logger.success("SQL validation passed")
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_sql=sanitized_sql,
            user_message=user_message
        )
    
    def _check_injection(self, sql: str) -> List[str]:
        """Check for SQL injection patterns."""
        errors = []
        
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                errors.append(f"Potential SQL injection detected: {pattern}")
        
        return errors
    
    def _check_gibberish(self, sql: str) -> List[str]:
        """
        Check if SQL output is gibberish (non-SQL text from bad T5 model weights).
        
        Detects:
        - Output missing SELECT keyword entirely
        - Excessive word repetition (hallucination signature)
        - Output that is too short to be valid SQL
        """
        errors = []
        sql_stripped = sql.strip()
        
        # Must start with SELECT (after cleanup, all valid T5 output starts with SELECT)
        if not sql_stripped.upper().startswith("SELECT"):
            errors.append("SQL must start with SELECT")
            return errors
        
        # Must contain FROM (every valid query needs a table reference)
        if not re.search(r'\bFROM\b', sql_stripped, re.IGNORECASE):
            errors.append("SQL missing FROM clause")
        
        # Check for excessive repetition in the full query
        words = sql_stripped.lower().split()
        if len(words) >= 8:
            from collections import Counter
            word_counts = Counter(words)
            most_common_word, most_common_count = word_counts.most_common(1)[0]
            # If a single non-SQL word appears in >40% of all words, it's gibberish
            sql_common_words = {"select", "from", "where", "and", "or", "as", "on", "in", "is", "not", "null", "by"}
            if most_common_word not in sql_common_words and most_common_count > len(words) * 0.4:
                errors.append(f"Gibberish detected: word '{most_common_word}' repeated {most_common_count}/{len(words)} times")
        
        return errors
    
    def _check_write_operations(self, sql: str) -> List[str]:
        """
        Check for write operations.
        
        ALL ROLES (including ADMIN and ACCOUNTANT) are READ-ONLY.
        No user can perform INSERT, UPDATE, DELETE, DROP, ALTER, CREATE operations.
        """
        errors = []
        
        sql_upper = sql.upper()
        for operation in self.WRITE_OPERATIONS:
            # Check if operation appears as a standalone word
            if re.search(r'\b' + operation + r'\b', sql_upper):
                errors.append(f"Write operation not allowed: {operation}")
        
        return errors
    
    def _check_multiple_statements(self, sql: str) -> List[str]:
        """Check for multiple statements or command chaining."""
        errors = []
        
        # Strip trailing semicolons and whitespace before parsing
        # sqlparse.parse("SELECT ...;") can return 2 objects (query + empty)
        cleaned = sql.strip().rstrip(';').strip()
        
        parsed = sqlparse.parse(cleaned)
        # Filter out empty statements
        real_statements = [s for s in parsed if s.get_type() is not None or str(s).strip()]
        
        if len(real_statements) > 1:
            errors.append("Multiple SQL statements not allowed")
        
        # Check for semicolon followed by actual SQL keywords (command chaining)
        # But ignore trailing semicolons with only whitespace after
        if re.search(r';\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b', sql, re.IGNORECASE):
            errors.append("Command chaining detected")
        
        return errors
    
    def _check_role_access(self, sql: str, role: str) -> List[str]:
        """Check role-based table access."""
        errors = []
        
        role = role.upper()
        
        # ENCODER cannot access CashFlow table
        if role == "ENCODER":
            # Check if CashFlow is referenced in the query
            if re.search(r'\bCashFlow\b', sql, re.IGNORECASE):
                errors.append("Access denied: ENCODER role cannot access CashFlow table")
            
            # Check if source_table='CashFlow' is in the query
            if re.search(r"source_table\s*=\s*['\"]CashFlow['\"]", sql, re.IGNORECASE):
                errors.append("Access denied: ENCODER role cannot query CashFlow data")
        
        return errors
    
    def _parse_sql(self, sql: str) -> Optional[sqlparse.sql.Statement]:
        """Parse SQL using sqlparse library."""
        try:
            parsed = sqlparse.parse(sql)
            if parsed and len(parsed) > 0:
                return parsed[0]
            return None
        except Exception as e:
            logger.error(f"SQL parsing error: {e}")
            return None
    
    def _generate_user_message(self, errors: List[str], role: str) -> str:
        """
        Generate user-friendly error message based on validation errors.
        
        Args:
            errors: List of technical error messages
            role: User role
            
        Returns:
            User-friendly error message
        """
        # Check for SQL injection
        if any("SQL injection" in err for err in errors):
            return "⚠️ Security Alert: Your query contains potentially unsafe patterns. Please rephrase your question."
        
        # Check for write operations
        if any("Write operation" in err for err in errors):
            return "⚠️ Access Denied: You don't have permission to modify data. You can only view information."
        
        # Check for RBAC violations
        if any("Access denied" in err and "ENCODER" in err for err in errors):
            return f"⚠️ Access Denied: As an ENCODER, you don't have authorization to access CashFlow data. Please contact your administrator if you need access."
        
        if any("Access denied" in err for err in errors):
            return f"⚠️ Access Denied: You don't have authorization to access this data. Please contact your administrator."
        
        # Check for multiple statements
        if any("Multiple SQL statements" in err or "Command chaining" in err for err in errors):
            return "⚠️ Invalid Query: Please ask one question at a time."
        
        # Check for syntax errors
        if any("Invalid SQL syntax" in err for err in errors):
            return "⚠️ Query Error: There was a problem understanding your question. Please try rephrasing it."
        
        # Generic error
        return "⚠️ Query Error: Unable to process your request. Please try rephrasing your question or contact support."


# Singleton instance
_sql_validator = None

def get_sql_validator() -> SQLValidator:
    """Get SQL validator instance."""
    global _sql_validator
    if _sql_validator is None:
        _sql_validator = SQLValidator()
    return _sql_validator
