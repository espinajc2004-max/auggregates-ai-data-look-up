"""
Chat Hybrid - Full AI Pipeline (Mistral → T5 → Mistral)
Stage 1: Mistral extracts intent from natural language (Taglish-aware)
Stage 2: T5 generates SQL from structured intent
Stage 3: Mistral formats results into natural language response
Fallback: Rule-based engine if models not loaded
"""

import asyncio
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models.requests import ChatRequest
from app.models.responses import ChatResponse
from app.services.intent_parser import parse_intent
from app.services.query_engine import QueryEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Singletons
_query_engine: Optional[QueryEngine] = None
_mistral_service = None
_mistral_loading = False
_mistral_load_attempts = 0
_MAX_LOAD_ATTEMPTS = 3


def get_query_engine() -> QueryEngine:
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine


def get_mistral_service():
    """Get or initialize MistralService. Retries up to 3 times if loading fails."""
    global _mistral_service, _mistral_loading, _mistral_load_attempts

    if _mistral_service is not None:
        return _mistral_service

    if _mistral_load_attempts >= _MAX_LOAD_ATTEMPTS:
        return None  # Exhausted retries

    if _mistral_loading:
        return None  # Still loading

    try:
        _mistral_loading = True
        _mistral_load_attempts += 1
        logger.info(f"[HYBRID] Loading Mistral+T5 (attempt {_mistral_load_attempts}/{_MAX_LOAD_ATTEMPTS})")
        from app.services.mistral_service import MistralService
        svc = MistralService()
        svc._load_model()  # Pre-load both Mistral + T5
        _mistral_service = svc
        logger.info("[HYBRID] Mistral+T5 pipeline loaded successfully")
        return _mistral_service
    except Exception as e:
        logger.error(f"[HYBRID] Failed to load Mistral+T5 (attempt {_mistral_load_attempts}): {e}")
        return None
    finally:
        _mistral_loading = False


@router.on_event("startup")
async def preload_models():
    """Pre-load models on startup in background so first request isn't slow."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, get_mistral_service)
    logger.info("[HYBRID] Model pre-loading started in background")


@router.post("/chat/hybrid", response_model=ChatResponse)
async def chat_hybrid(request: ChatRequest):
    """
    Full AI Pipeline Endpoint

    Primary flow (Mistral+T5):
      Mistral → intent JSON → T5 → SQL → Supabase → Mistral → response

    Fallback flow (rule-based):
      intent_parser → query_engine → template response
    """
    try:
        user_id = getattr(request, "user_id", None) or "anonymous"
        session_id = getattr(request, "session_id", None)

        logger.info(f"[HYBRID] User: {user_id} | Query: {request.query}")

        # Try full AI pipeline first
        mistral = get_mistral_service()

        if mistral is not None:
            logger.info("[HYBRID] Using Mistral+T5 pipeline")
            result = await mistral.process_query(
                query=request.query,
                user_id=user_id,
                conversation_id=session_id
            )

            # Handle clarification response from Mistral
            if result.get("needs_clarification"):
                return ChatResponse(
                    query=request.query,
                    message=result.get("response", "Pwede mo bang i-clarify ang tanong mo?"),
                    data=[],
                    intent="clarification",
                    confidence=0.5,
                    session_id=session_id,
                    metadata={"pipeline": "mistral", "needs_clarification": True}
                )

            confidence = 0.95 if result.get("row_count", 0) > 0 else 0.6

            return ChatResponse(
                query=request.query,
                message=result.get("response", ""),
                data=result.get("data", []),
                intent=str(result.get("intent", {}).get("intent_type", "query_data")),
                confidence=confidence,
                session_id=session_id,
                metadata={
                    "pipeline": "mistral+t5",
                    "row_count": result.get("row_count", 0),
                    "sql": result.get("sql", ""),
                    "stage1_ms": result.get("stage1_time_ms"),
                    "stage2_ms": result.get("stage2_time_ms"),
                    "stage3_ms": result.get("stage3_time_ms"),
                    "total_ms": result.get("total_time_ms"),
                }
            )

        # Fallback: rule-based pipeline
        logger.warning("[HYBRID] Mistral not available, using rule-based fallback")
        return await _rule_based_fallback(request, session_id)

    except Exception as e:
        logger.error(f"[HYBRID] Error: {str(e)}", exc_info=True)
        return ChatResponse(
            query=request.query,
            message=f"Sorry, may error: {str(e)}",
            data=[],
            intent="error",
            confidence=0.0,
            error=str(e)
        )


async def _rule_based_fallback(request: ChatRequest, session_id: Optional[str]) -> ChatResponse:
    """Rule-based fallback when Mistral is not available."""
    intent = parse_intent(request.query)
    logger.info(f"[FALLBACK] Intent: {intent['intent']} | Slots: {intent.get('slots', {})}")

    if intent.get("needs_clarification") and intent["intent"] not in ("ambiguous",):
        return ChatResponse(
            query=request.query,
            message=intent.get("clarification_question", "Pwede mo bang i-clarify ang tanong mo?"),
            data=[],
            intent="clarification",
            confidence=0.5,
            session_id=session_id,
            metadata={"pipeline": "rule-based"}
        )

    engine = get_query_engine()
    result = engine.execute(intent)
    confidence = 0.9 if result.get("row_count", 0) > 0 else 0.4

    return ChatResponse(
        query=request.query,
        message=result.get("message", ""),
        data=result.get("data", []),
        intent=result.get("intent", intent["intent"]),
        confidence=confidence,
        session_id=session_id,
        metadata={
            "pipeline": "rule-based",
            "elapsed_ms": result.get("elapsed_ms"),
            "row_count": result.get("row_count", 0),
            "needs_clarification": result.get("needs_clarification", False),
            "clarification_options": result.get("clarification_options"),
            "slots": intent.get("slots", {})
        }
    )
