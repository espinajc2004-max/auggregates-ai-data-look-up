"""
Pydantic request models for the AI API.
"""

from typing import Optional
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Request model for /predict endpoint."""
    query: str = Field(..., description="The user's natural language query")
    role: str = Field(default="ENCODER", description="User role for RBAC")


class ChatRequest(BaseModel):
    """Request model for /chat endpoint."""
    query: str = Field(..., description="The user's natural language query")
    role: str = Field(default="ENCODER", description="User role for RBAC")
    user_id: str = Field(default="anonymous", description="User identifier for conversation tracking")
    session_id: Optional[str] = Field(default=None, description="Session identifier for conversation continuity")
    org_id: Optional[int] = Field(default=1, description="Organization ID for multi-tenancy and security guardrails")
