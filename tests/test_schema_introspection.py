"""
Unit tests for SchemaIntrospection
Tests dynamic column queries
"""

import pytest
from unittest.mock import Mock, patch
from app.services.schema_introspection import SchemaIntrospection


class TestSchemaIntrospection:
    """Test SchemaIntrospection functionality"""
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_get_org_fields(self, mock_supabase):
        """Test getting org fields"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': ['vendor']},
            {'field_name': 'amount', 'field_type': 'numeric', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        result = SchemaIntrospection.get_org_fields("org123", "Expenses")
        
        assert len(result) == 2
        assert result[0]['field_name'] == 'supplier'
        assert result[1]['field_name'] == 'amount'
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_get_field_type(self, mock_supabase):
        """Test getting field type"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': []},
            {'field_name': 'amount', 'field_type': 'numeric', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        result = SchemaIntrospection.get_field_type("org123", "Expenses", "amount")
        assert result == "numeric"
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_build_search_conditions(self, mock_supabase):
        """Test building search conditions"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'category', 'field_type': 'text', 'aliases': []},
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        result = SchemaIntrospection.build_search_conditions("org123", "Expenses", "fuel")
        
        assert len(result) >= 2
        assert any("category" in cond for cond in result)
        assert any("supplier" in cond for cond in result)
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_get_all_field_names(self, mock_supabase):
        """Test getting all field names"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'category', 'field_type': 'text', 'aliases': []},
            {'field_name': 'amount', 'field_type': 'numeric', 'aliases': []},
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        result = SchemaIntrospection.get_all_field_names("org123", "Expenses")
        
        assert len(result) == 3
        assert 'category' in result
        assert 'amount' in result
        assert 'supplier' in result
    
    @patch('app.services.schema_introspection.get_supabase_client')
    def test_field_exists(self, mock_supabase):
        """Test checking if field exists"""
        # Mock response
        mock_response = Mock()
        mock_response.data = [
            {'field_name': 'supplier', 'field_type': 'text', 'aliases': []}
        ]
        
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        result = SchemaIntrospection.field_exists("org123", "Expenses", "supplier")
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
