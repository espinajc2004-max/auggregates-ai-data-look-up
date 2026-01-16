"""
Health check endpoint.
"""

from datetime import datetime
from fastapi import APIRouter
import os

from app.models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint to verify API status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        model_path=os.getenv("MODEL_PATH", "ml/models/t5-base-temp"),
        supabase_connected=bool(os.getenv("SUPABASE_URL"))
    )
