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
        model_path=os.getenv("T5_MODEL_PATH", "gaussalgo/T5-LM-Large-text2sql-spider"),
        supabase_connected=bool(os.getenv("SUPABASE_URL"))
    )
