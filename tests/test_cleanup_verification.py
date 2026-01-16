"""
Test to verify cleanup didn't break anything.
Tests that UniversalHandler is properly integrated.
"""

import pytest
from app.services.smart_query_builder import SmartQueryBuilder
from app.services.query_parser import ParsedQuery


class TestCleanupVerification:
    """Verify that cleanup changes work correctly."""
    
    def test_smart_query_builder_imports(self):
        """Test that SmartQueryBuilder imports correctly."""
        assert SmartQueryBuilder is not None
        assert hasattr(SmartQueryBuilder, 'execute')
    
    def test_universal_handler_import(self):
        """Test that UniversalHandler can be imported."""
        from app.services.query_handlers import UniversalHandler
        assert UniversalHandler is not None
    
    def test_no_old_handlers_imported(self):
        """Test that old handlers are not imported."""
        from app.services import query_handlers
        
        # These should NOT exist
        assert not hasattr(query_handlers, 'ExpensesHandler')
        assert not hasattr(query_handlers, 'CashFlowHandler')
        assert not hasattr(query_handlers, 'ProjectHandler')
        
        # This SHOULD exist
        assert hasattr(query_handlers, 'UniversalHandler')
    
    def test_smart_query_builder_has_no_handlers_dict(self):
        """Test that HANDLERS dictionary was removed."""
        assert not hasattr(SmartQueryBuilder, 'HANDLERS')
    
    def test_smart_query_builder_has_table_map(self):
        """Test that TABLE_MAP still exists (for compatibility)."""
        assert hasattr(SmartQueryBuilder, 'TABLE_MAP')
        assert 'expenses' in SmartQueryBuilder.TABLE_MAP
        assert 'cashflow' in SmartQueryBuilder.TABLE_MAP
    
    def test_execute_method_exists(self):
        """Test that execute method still exists."""
        assert hasattr(SmartQueryBuilder, 'execute')
        assert callable(SmartQueryBuilder.execute)
    
    def test_delegation_methods_exist(self):
        """Test that delegation methods still exist."""
        assert hasattr(SmartQueryBuilder, 'resolve_project_with_disambiguation')
        assert hasattr(SmartQueryBuilder, 'resolve_entity_cross_type')
        assert hasattr(SmartQueryBuilder, '_get_project_id')


class TestUniversalHandlerIntegration:
    """Test that UniversalHandler is properly integrated."""
    
    def test_universal_handler_has_search(self):
        """Test that UniversalHandler has search method."""
        from app.services.query_handlers import UniversalHandler
        assert hasattr(UniversalHandler, 'search')
        assert callable(UniversalHandler.search)
    
    def test_universal_handler_has_count(self):
        """Test that UniversalHandler has count method."""
        from app.services.query_handlers import UniversalHandler
        assert hasattr(UniversalHandler, 'count')
        assert callable(UniversalHandler.count)
    
    def test_universal_handler_has_list(self):
        """Test that UniversalHandler has list method."""
        from app.services.query_handlers import UniversalHandler
        assert hasattr(UniversalHandler, 'list')
        assert callable(UniversalHandler.list)
    
    def test_universal_handler_has_list_files(self):
        """Test that UniversalHandler has list_files method."""
        from app.services.query_handlers import UniversalHandler
        assert hasattr(UniversalHandler, 'list_files')
        assert callable(UniversalHandler.list_files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
