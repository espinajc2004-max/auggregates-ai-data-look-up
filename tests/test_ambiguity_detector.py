"""
Unit tests for Ambiguity Detector service.
Tests ambiguity detection across multiple dimensions (source_table, file_name, project).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.ambiguity_detector import AmbiguityDetector


class TestAmbiguityDetector:
    """Test suite for AmbiguityDetector."""
    
    def test_init_default_threshold(self):
        """Test initialization with default threshold."""
        detector = AmbiguityDetector()
        assert detector.threshold == 2
    
    def test_init_custom_threshold(self):
        """Test initialization with custom threshold."""
        detector = AmbiguityDetector(threshold=3)
        assert detector.threshold == 3
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_multiple_tables(self, mock_supabase):
        """Test ambiguity detection when search term exists in multiple tables."""
        # Mock Supabase response - fuel in both Expenses and CashFlow
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"source_table": "Expenses", "count": 5, "total_amount": 10000},
            {"source_table": "CashFlow", "count": 3, "total_amount": 7500}
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector(threshold=2)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table"]
        )
        
        assert result["is_ambiguous"] is True
        assert result["ambiguous_dimension"] == "source_table"
        assert len(result["options"]) == 2
        assert "fuel" in result["message"].lower()
        assert "Expenses" in result["message"]
        assert "CashFlow" in result["message"]
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_multiple_files(self, mock_supabase):
        """Test ambiguity detection when search term exists in multiple files."""
        # Mock Supabase response - fuel in multiple files
        mock_client = Mock()
        
        # First call returns single table (no ambiguity)
        mock_response_table = Mock()
        mock_response_table.data = [
            {"source_table": "Expenses", "count": 10, "total_amount": 20000}
        ]
        
        # Second call returns multiple files (ambiguous)
        mock_response_file = Mock()
        mock_response_file.data = [
            {"file_name": "francis gays", "count": 5, "total_amount": 10000},
            {"file_name": "JC", "count": 5, "total_amount": 10000}
        ]
        
        mock_client.rpc.return_value.execute.side_effect = [
            mock_response_table,
            mock_response_file
        ]
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector(threshold=2)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table", "file_name"]
        )
        
        assert result["is_ambiguous"] is True
        assert result["ambiguous_dimension"] == "file_name"
        assert len(result["options"]) == 2
        assert "francis gays" in result["message"]
        assert "JC" in result["message"]
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_multiple_projects(self, mock_supabase):
        """Test ambiguity detection when search term exists in multiple projects."""
        # Mock Supabase response - fuel in multiple projects
        mock_client = Mock()
        
        # First two calls return single result (no ambiguity)
        mock_response_single = Mock()
        mock_response_single.data = [{"source_table": "Expenses", "count": 10}]
        
        # Third call returns multiple projects (ambiguous)
        mock_response_project = Mock()
        mock_response_project.data = [
            {"project": "SJDM", "count": 6, "total_amount": 12000},
            {"project": "TEST", "count": 4, "total_amount": 8000}
        ]
        
        mock_client.rpc.return_value.execute.side_effect = [
            mock_response_single,
            mock_response_single,
            mock_response_project
        ]
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector(threshold=2)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table", "file_name", "project"]
        )
        
        assert result["is_ambiguous"] is True
        assert result["ambiguous_dimension"] == "project"
        assert len(result["options"]) == 2
        assert "SJDM" in result["message"]
        assert "TEST" in result["message"]
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_not_ambiguous(self, mock_supabase):
        """Test when search term is NOT ambiguous (single location)."""
        # Mock Supabase response - fuel only in one table
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"source_table": "Expenses", "count": 5, "total_amount": 10000}
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector(threshold=2)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table"]
        )
        
        assert result["is_ambiguous"] is False
        assert result["ambiguous_dimension"] is None
        assert len(result["options"]) == 0
        assert result["message"] is None
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_below_threshold(self, mock_supabase):
        """Test when results are below threshold (not ambiguous)."""
        # Mock Supabase response - only 1 result (below threshold of 2)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"source_table": "Expenses", "count": 5, "total_amount": 10000}
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector(threshold=2)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1"
        )
        
        assert result["is_ambiguous"] is False
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_custom_threshold(self, mock_supabase):
        """Test ambiguity detection with custom threshold."""
        # Mock Supabase response - 2 tables
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"source_table": "Expenses", "count": 5, "total_amount": 10000},
            {"source_table": "CashFlow", "count": 3, "total_amount": 7500}
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        # With threshold=3, 2 results should NOT be ambiguous
        detector = AmbiguityDetector(threshold=3)
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table"]
        )
        
        assert result["is_ambiguous"] is False
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_error_handling(self, mock_supabase):
        """Test error handling when database query fails."""
        # Mock Supabase to raise exception
        mock_client = Mock()
        mock_client.rpc.side_effect = Exception("Database connection failed")
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector()
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1"
        )
        
        # Should fail open (not ambiguous) on error
        assert result["is_ambiguous"] is False
        assert result["ambiguous_dimension"] is None
        assert len(result["options"]) == 0
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_build_ambiguity_result_source_table(self, mock_supabase):
        """Test clarification message building for source_table dimension."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"source_table": "Expenses", "count": 5, "total_amount": 10000},
            {"source_table": "CashFlow", "count": 3, "total_amount": 7500}
        ]
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector()
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table"]
        )
        
        message = result["message"]
        assert "fuel" in message.lower()
        assert "multiple tables" in message.lower()
        assert "1. Expenses (5 entries)" in message
        assert "2. CashFlow (3 entries)" in message
        assert "Which one would you like to see?" in message
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_build_ambiguity_result_file_name(self, mock_supabase):
        """Test clarification message building for file_name dimension."""
        mock_client = Mock()
        
        # First call returns single table
        mock_response_table = Mock()
        mock_response_table.data = [{"source_table": "Expenses", "count": 10}]
        
        # Second call returns multiple files
        mock_response_file = Mock()
        mock_response_file.data = [
            {"file_name": "francis gays", "count": 5, "total_amount": 10000},
            {"file_name": "JC", "count": 5, "total_amount": 10000}
        ]
        
        mock_client.rpc.return_value.execute.side_effect = [
            mock_response_table,
            mock_response_file
        ]
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector()
        result = detector.check_ambiguity(
            search_term="fuel",
            org_id="1",
            check_dimensions=["source_table", "file_name"]
        )
        
        message = result["message"]
        assert "fuel" in message.lower()
        assert "multiple files" in message.lower()
        assert "1. francis gays (5 entries)" in message
        assert "2. JC (5 entries)" in message
        assert "Which file?" in message
    
    @patch('app.services.ambiguity_detector.get_supabase_client')
    def test_check_ambiguity_empty_results(self, mock_supabase):
        """Test when database returns empty results."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_client.rpc.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        
        detector = AmbiguityDetector()
        result = detector.check_ambiguity(
            search_term="nonexistent",
            org_id="1"
        )
        
        assert result["is_ambiguous"] is False
        assert result["ambiguous_dimension"] is None
        assert len(result["options"]) == 0
