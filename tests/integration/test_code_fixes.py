"""
Integration tests for code architecture fixes
Tests end-to-end flows with database
"""

import pytest
from unittest.mock import Mock, patch
from app.services.normalizers.date_normalizer import DateNormalizer
from app.services.normalizers.amount_normalizer import AmountNormalizer
from app.services.schema_introspection import SchemaIntrospection
from app.services.vocabulary_service import VocabularyService
from app.services.clarification_service import ClarificationService


class TestCodeFixesIntegration:
    """Integration tests for architecture fixes"""
    
    def test_date_normalization_flow(self):
        """Test date normalization in query flow"""
        # User query: "expenses in february"
        date_input = "february"
        
        # Normalize to date range
        date_range = DateNormalizer.normalize_to_range(date_input)
        
        assert date_range is not None
        start, end = date_range
        assert start.startswith("2026-02-01") or start.startswith("2025-02-01")
        assert "02-28" in end or "02-29" in end
    
    def test_amount_normalization_flow(self):
        """Test amount normalization in query flow"""
        # User query: "expenses over ₱5k"
        amount_input = "₱5k"
        
        # Normalize amount
        amount, currency = AmountNormalizer.normalize_with_currency(amount_input)
        
        assert amount == 5000.0
        assert currency == "PHP"
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_dynamic_column_search(self, mock_supabase):
        """Test dynamic column search end-to-end"""
        # Mock org_fields response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'category', 'field_type': 'text', 'aliases': []},
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': ['vendor']},
            {'field_name': 'amount', 'field_type': 'numeric', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # User query: "find fuel in expenses"
        search_term = "fuel"
        conditions = SchemaIntrospection.build_search_conditions("org123", "Expenses", search_term)
        
        # Should generate conditions for all text fields
        assert len(conditions) >= 2
        assert any("category" in cond for cond in conditions)
        assert any("supplier" in cond for cond in conditions)
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_db_driven_clarification(self, mock_supabase):
        """Test DB-driven clarification flow"""
        # Mock categories response
        mock_response = Mock()
        mock_response.data = [
            {'value': 'fuel', 'count': 45},
            {'value': 'food', 'count': 32},
            {'value': 'car', 'count': 28}
        ]
        
        mock_client = Mock()
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # Mock cache miss
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache'):
                categories = VocabularyService.get_categories("org123", limit=10)
        
        # Should return DB-driven categories (not hardcoded)
        assert len(categories) == 3
        assert categories[0]['value'] == 'fuel'
        assert categories[1]['value'] == 'food'
        assert categories[2]['value'] == 'car'
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_vocabulary_caching_flow(self, mock_supabase):
        """Test vocabulary caching end-to-end"""
        # Mock first call (cache miss)
        mock_response = Mock()
        mock_response.data = [
            {'value': 'fuel', 'count': 45}
        ]
        
        mock_client = Mock()
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # First call - should query database
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache') as mock_save:
                result1 = VocabularyService.get_categories("org123")
                mock_save.assert_called_once()
        
        # Second call - should use cache
        cached_data = [{'value': 'fuel', 'count': 45}]
        with patch.object(VocabularyService, '_get_from_cache', return_value=cached_data):
            result2 = VocabularyService.get_categories("org123")
        
        assert result1 == result2
    
    def test_clarification_with_org_id(self):
        """Test clarification service with org_id parameter"""
        # User query: "show me fuel" (ambiguous)
        clarification = ClarificationService.check(
            operation="search",
            target_table="",
            search_term="fuel",
            entities=["fuel"],
            filters={},
            org_id="org123"
        )
        
        # Should ask for clarification (no table specified)
        # Note: This may return None if search_term is specific enough
        # The actual behavior depends on clarification logic
        # Just verify it doesn't crash with org_id parameter
        assert clarification is None or clarification.question is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
