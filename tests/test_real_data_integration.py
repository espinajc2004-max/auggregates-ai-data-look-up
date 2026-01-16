"""
Integration tests using REAL data from Supabase.
Tests the complete pipeline with actual database data.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestRealDataIntegration:
    """Test with actual data from Supabase database."""
    
    # ========================================
    # SEARCH TESTS (Using Real Data)
    # ========================================
    
    def test_search_fuel_in_expenses(self):
        """
        Test: Search for 'fuel' in expenses
        Expected: S