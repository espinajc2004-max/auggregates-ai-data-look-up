"""
Chat Hybrid - Full AI Pipeline (Phi-3 → T5 → Phi-3)
Stage 1: Phi-3 extracts intent from natural language (Taglish-aware)
Stage 2: T5 generates SQL from structured intent
Stage 3: Phi-3 formats results into natural language response
Returns HTTP 503 if AI pipeline is unavailable.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from typing import Optional
from app.models.requests import ChatRequest
from app.models.responses import ChatResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Singletons
_phi3_service = None
_phi3_loading = False
_phi3_load_attempts = 0
_MAX_LOAD_ATTEMPTS = 3


def get_phi3_service():
    """Get or initialize Phi3Service. Retries up to 3 times if loading fails."""
    global _phi3_service, _phi3_loading, _phi3_load_attempts

    if _phi3_service is not None:
        return _phi3_service

    if _phi3_load_attempts >= _MAX_LOAD_ATTEMPTS:
        logger.warning(f"[HYBRID] Phi-3 load exhausted all {_MAX_LOAD_ATTEMPTS} attempts, returning None")
        return None  # Exhausted retries

    if _phi3_loading:
        logger.info("[HYBRID] Phi-3 is currently loading in another thread, returning None for now")
        return None  # Still loading

    try:
        _phi3_loading = True
        _phi3_load_attempts += 1
        logger.info(f"[HYBRID] Loading Phi-3+T5 (attempt {_phi3_load_attempts}/{_MAX_LOAD_ATTEMPTS})")
        from app.services.phi3_service import Phi3Service
        svc = Phi3Service()
        svc._load_model()  # Pre-load both Phi-3 + T5
        _phi3_service = svc
        logger.info("[HYBRID] Phi-3+T5 pipeline loaded successfully")
        return _phi3_service
    except Exception as e:
        logger.error(f"[HYBRID] Failed to load Phi-3+T5 (attempt {_phi3_load_attempts}): {e}", exc_info=True)
        return None
    finally:
        _phi3_loading = False


@router.on_event("startup")
async def preload_models():
    """Pre-load models on startup in background so first request isn't slow."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, get_phi3_service)
    logger.info("[HYBRID] Model pre-loading started in background")


@router.post("/chat/hybrid", response_model=ChatResponse)
async def chat_hybrid(request: ChatRequest):
    """
    Full AI Pipeline Endpoint (Phi-3 + T5)

    Flow: Phi-3 → intent JSON → T5 → SQL → Supabase → Phi-3 → response

    Returns HTTP 503 if AI pipeline is unavailable.
    """
    try:
        user_id = getattr(request, "user_id", None) or "anonymous"
        session_id = getattr(request, "session_id", None)

        logger.info(f"[HYBRID] User: {user_id} | Query: {request.query}")

        # Wait for background model loading if still in progress (up to 120s)
        import time as _time
        wait_start = _time.time()
        while _phi3_loading and (_time.time() - wait_start) < 120:
            logger.info("[HYBRID] Waiting for background model loading to finish...")
            await asyncio.sleep(2)

        # Try full AI pipeline
        phi3 = get_phi3_service()

        if phi3 is not None:
            logger.info("[HYBRID] Using Phi-3+T5 pipeline")
            result = await phi3.process_query(
                query=request.query,
                user_id=user_id,
                conversation_id=session_id
            )

            # Handle clarification response
            if result.get("needs_clarification"):
                return ChatResponse(
                    query=request.query,
                    message=result.get("response", "Could you please clarify your question?"),
                    data=[],
                    intent="clarification",
                    confidence=0.5,
                    session_id=session_id,
                    metadata={"pipeline": "phi3", "needs_clarification": True}
                )

            # Handle out-of-scope response
            if result.get("out_of_scope"):
                return ChatResponse(
                    query=request.query,
                    message=result.get("response", "I can only help with expense and cashflow data queries."),
                    data=[],
                    intent="out_of_scope",
                    confidence=1.0,
                    session_id=session_id,
                    metadata={"pipeline": "phi3", "out_of_scope": True}
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
                    "pipeline": "phi3+t5",
                    "sql_source": result.get("sql_source", "unknown"),
                    "row_count": result.get("row_count", 0),
                    "sql": result.get("sql", ""),
                    "stage1_ms": result.get("stage1_time_ms"),
                    "stage2_ms": result.get("stage2_time_ms"),
                    "stage3_ms": result.get("stage3_time_ms"),
                    "total_ms": result.get("total_time_ms"),
                }
            )

        # No fallback — AI pipeline required
        logger.error("[HYBRID] AI pipeline unavailable after all retry attempts")
        raise HTTPException(
            status_code=503,
            detail="AI pipeline unavailable. Models failed to load after all retry attempts."
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like 503) without wrapping
    except Exception as e:
        logger.error(f"[HYBRID] Error: {str(e)}", exc_info=True)
        return ChatResponse(
            query=request.query,
            message=f"Sorry, an error occurred: {str(e)}",
            data=[],
            intent="error",
            confidence=0.0,
            error=str(e)
        )


@router.get("/chat/hybrid/status")
async def model_status():
    """Check model loading status — useful for debugging on Colab."""
    return {
        "phi3_loaded": _phi3_service is not None,
        "loading_in_progress": _phi3_loading,
        "load_attempts": _phi3_load_attempts,
        "max_attempts": _MAX_LOAD_ATTEMPTS,
        "pipeline": "phi3+t5" if _phi3_service is not None else "unavailable"
    }
