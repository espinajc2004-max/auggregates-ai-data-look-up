"""
Pydantic response models for the AI API.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class PredictResponse(BaseModel):
    """Response model for /predict endpoint."""
    query: str
    intent: str
    confidence: float
    top_3: dict


class ChatResponse(BaseModel):
    """Response model for /chat endpoint."""
    query: str
    intent: str
    confidence: float
    message: str
    data: Optional[list] = []
    error: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[dict] = None

    class Config:
        # Ensure None data becomes [] for frontend safety
        json_encoders = {}


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""
    status: str
    timestamp: str
    model_path: str
    supabase_connected: bool
