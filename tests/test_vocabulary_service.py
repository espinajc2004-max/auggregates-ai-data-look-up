"""
Unit tests for VocabularyService
Tests DB-driven vocabulary with caching
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from app.services.vocabulary_service import VocabularyService


class TestVocabularyService:
    """Test VocabularyService functionality"""
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_get_categories(self, mock_supabase):
        """Test getting categories from database"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'value': 'fuel', 'count': 45},
            {'value': 'food', 'count': 32}
        ]
        
        mock_client = Mock()
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # Mock cache miss
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache'):
                result = VocabularyService.get_categories("org123", limit=10)
        
        assert len(result) == 2
        assert result[0]['value'] == 'fuel'
        assert result[0]['count'] == 45
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_get_projects(self, mock_supabase):
        """Test getting projects from database"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'metadata': {'project': 'TEST Project'}},
            {'metadata': {'project': 'SJDM Project'}},
            {'metadata': {'project': 'TEST Project'}}  # Duplicate
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # Mock cache miss
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache'):
                result = VocabularyService.get_projects("org123")
        
        assert len(result) == 2  # Duplicates removed
        assert 'SJDM Project' in result
        assert 'TEST Project' in result
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_get_files(self, mock_supabase):
        """Test getting files from database"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'metadata': {'file_name': 'francis gays'}},
            {'metadata': {'file_name': 'JC'}},
            {'metadata': {'file_name': 'francis gays'}}  # Duplicate
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # Mock cache miss
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache'):
                result = VocabularyService.get_files("org123")
        
        assert len(result) == 2  # Duplicates removed
        assert 'JC' in result
        assert 'francis gays' in result
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_get_methods(self, mock_supabase):
        """Test getting payment methods from database"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'metadata': {'method': 'GCASH'}},
            {'metadata': {'method': 'cash'}},  # Lowercase
            {'metadata': {'method': 'BANK TRANSFER'}}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # Mock cache miss
        with patch.object(VocabularyService, '_get_from_cache', return_value=None):
            with patch.object(VocabularyService, '_save_to_cache'):
                result = VocabularyService.get_methods("org123")
        
        assert len(result) == 3
        assert 'GCASH' in result
        assert 'CASH' in result  # Uppercase
        assert 'BANK TRANSFER' in result
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_caching(self, mock_supabase):
        """Test vocabulary caching"""
        # Mock cache hit
        cached_data = [{'value': 'fuel', 'count': 45}]
        
        with patch.object(VocabularyService, '_get_from_cache', return_value=cached_data):
            result = VocabularyService.get_categories("org123")
        
        assert result == cached_data
        # Supabase should NOT be called when cache hits
        mock_supabase.assert_not_called()
    
    @patch('app.services.vocabulary_service.get_supabase_client')
    def test_clear_cache(self, mock_supabase):
        """Test clearing cache"""
        mock_client = Mock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = Mock()
        mock_supabase.return_value = mock_client
        
        VocabularyService.clear_cache("org123")
        
        # Verify delete was called
        mock_client.table.assert_called_with('vocabulary_cache')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
