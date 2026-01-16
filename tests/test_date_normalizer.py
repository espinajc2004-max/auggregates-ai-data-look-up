"""
Unit tests for DateNormalizer
Tests date parsing and normalization functionality
"""

import pytest
from datetime import datetime
from app.services.normalizers.date_normalizer import DateNormalizer


class TestDateNormalizer:
    """Test DateNormalizer functionality"""
    
    def test_normalize_iso_format(self):
        """Test ISO 8601 format (YYYY-MM-DD)"""
        result = DateNormalizer.normalize("2026-02-15")
        assert result == "2026-02-15"
    
    def test_normalize_slash_format(self):
        """Test slash format (YYYY/M/D)"""
        result = DateNormalizer.normalize("2026/2/15")
        assert result == "2026-02-15"
    
    def test_normalize_month_name_full(self):
        """Test full month name"""
        result = DateNormalizer.normalize("february 15", current_year=2026)
        assert result == "2026-02-15"
    
    def test_normalize_month_name_abbrev(self):
        """Test abbreviated month name"""
        result = DateNormalizer.normalize("feb 15", current_year=2026)
        assert result == "2026-02-15"
    
    def test_normalize_relative_today(self):
        """Test relative date: today"""
        result = DateNormalizer.normalize("today")
        expected = datetime.now().strftime('%Y-%m-%d')
        assert result == expected
    
    def test_normalize_relative_yesterday(self):
        """Test relative date: yesterday"""
        result = DateNormalizer.normalize("yesterday")
        from datetime import timedelta
        expected = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert result == expected
    
    def test_normalize_to_range_month(self):
        """Test month name to date range"""
        result = DateNormalizer.normalize_to_range("february")
        assert result is not None
        start, end = result
        assert start.startswith("2026-02-01") or start.startswith(str(datetime.now().year) + "-02-01")
        assert "02-28" in end or "02-29" in end  # Handle leap years
    
    def test_normalize_to_range_single_date(self):
        """Test single date to range (same start and end)"""
        result = DateNormalizer.normalize_to_range("2026-02-15")
        assert result == ("2026-02-15", "2026-02-15")
    
    def test_normalize_invalid_date(self):
        """Test invalid date returns None"""
        result = DateNormalizer.normalize("invalid date xyz")
        assert result is None
    
    def test_normalize_empty_string(self):
        """Test empty string returns None"""
        result = DateNormalizer.normalize("")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
