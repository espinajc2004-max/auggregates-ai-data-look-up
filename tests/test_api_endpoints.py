"""
API Endpoint Tests
==================
Tests the FastAPI endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
class TestAPIEndpoints:
    """Test API endpoints."""
    
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
    
    async def test_predict_endpoint(self):
        """Test predict endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/predict",
                json={"query": "find fuel"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "intent" in data
            assert "table_hint" in data
    
    async def test_predict_endpoint_empty_query(self):
        """Test predict endpoint with empty query."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/predict",
                json={"query": ""}
            )
            # Should handle gracefully
            assert response.status_code in [200, 400, 422]
    
    async def test_predict_endpoint_invalid_json(self):
        """Test predict endpoint with invalid JSON."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/predict",
                json={}
            )
            # Should return validation error
            assert response.status_code in [400, 422]


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API."""
    
    @pytest.mark.asyncio
    async def test_full_prediction_flow(self):
        """Test full prediction flow."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Test multiple queries
            queries = [
                "find fuel",
                "how many car",
                "total of salary",
            ]
            
            for query in queries:
                response = await client.post(
                    "/predict",
                    json={"query": query}
                )
                assert response.status_code == 200
                data = response.json()
                assert "intent" in data
                assert "overall_confidence" in data
