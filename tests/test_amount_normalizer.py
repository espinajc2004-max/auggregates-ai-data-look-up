"""
Unit tests for AmountNormalizer
Tests amount parsing and currency detection
"""

import pytest
from app.services.normalizers.amount_normalizer import AmountNormalizer


class TestAmountNormalizer:
    """Test AmountNormalizer functionality"""
    
    def test_normalize_plain_number(self):
        """Test plain number parsing"""
        result = AmountNormalizer.normalize("5000")
        assert result == 5000.0
    
    def test_normalize_with_commas(self):
        """Test number with commas"""
        result = AmountNormalizer.normalize("5,000")
        assert result == 5000.0
    
    def test_normalize_with_php_symbol(self):
        """Test PHP currency symbol"""
        result = AmountNormalizer.normalize("₱5000")
        assert result == 5000.0
    
    def test_normalize_with_usd_symbol(self):
        """Test USD currency symbol"""
        result = AmountNormalizer.normalize("$100")
        assert result == 100.0
    
    def test_normalize_with_k_suffix(self):
        """Test k suffix (thousands)"""
        result = AmountNormalizer.normalize("5k")
        assert result == 5000.0
    
    def test_normalize_with_decimal_k(self):
        """Test decimal with k suffix"""
        result = AmountNormalizer.normalize("5.5k")
        assert result == 5500.0
    
    def test_normalize_with_m_suffix(self):
        """Test M suffix (millions)"""
        result = AmountNormalizer.normalize("1.2M")
        assert result == 1200000.0
    
    def test_normalize_with_currency_detection(self):
        """Test currency detection"""
        result = AmountNormalizer.normalize_with_currency("₱5000")
        assert result == (5000.0, "PHP")
        
        result = AmountNormalizer.normalize_with_currency("$100")
        assert result == (100.0, "USD")
    
    def test_normalize_invalid_amount(self):
        """Test invalid amount returns None"""
        result = AmountNormalizer.normalize("invalid")
        assert result is None
    
    def test_format_amount_with_symbol(self):
        """Test amount formatting with currency symbol"""
        result = AmountNormalizer.format_amount(5000.0, "PHP", True)
        assert result == "₱5,000.00"
    
    def test_format_amount_without_symbol(self):
        """Test amount formatting without currency symbol"""
        result = AmountNormalizer.format_amount(5000.0, "PHP", False)
        assert result == "5,000.00"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
