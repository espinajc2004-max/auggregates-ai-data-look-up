"""
================================================================================
AU-GGREGATES AI API SERVER
================================================================================
Main entry point for the FastAPI application.
Run with: python -m app.main
================================================================================
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.api.routes import health, chat_hybrid
from app.utils.logger import logger

# Import Config directly from the file (app/config.py) to avoid folder conflict
import importlib.util, os as _os
_spec = importlib.util.spec_from_file_location("app_config_module", _os.path.join(_os.path.dirname(__file__), "config.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Config = _mod.Config

# ==============================================================================
# APP INITIALIZATION
# ==============================================================================

# Initialize Sentry (Error Tracking) - optional
SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv('ENVIRONMENT', 'development'),
        traces_sample_rate=1.0,
    )
    logger.info("Sentry error tracking initialized")

app = FastAPI(
    title="AU-Ggregates AI API",
    description="AI-powered data lookup for AU-Ggregates CRM",
    version="2.0.0"
)

# ==============================================================================
# CORS MIDDLEWARE
# ==============================================================================
# On Colab/ngrok, set CORS_ALLOW_ALL=true so any origin can reach the API
_cors_allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"
_origins = ["*"] if _cors_allow_all else [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://localhost:5173",   # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:4000",
    os.getenv("FRONTEND_URL", ""),  # Production frontend URL from .env
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=not _cors_allow_all,  # Can't use credentials with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# REGISTER ROUTES
# ==============================================================================
app.include_router(health.router, prefix="/api", tags=["Health"])
# app.include_router(predict.router, prefix="/api", tags=["AI Prediction"])  # Commented out - missing dependencies
# app.include_router(chat.router, prefix="/api", tags=["Chat - Unified V1+V2"])  # Commented out - missing dependencies
app.include_router(chat_hybrid.router, prefix="/api", tags=["Chat - Hybrid Phi-3+T5"])



# ==============================================================================
# STARTUP EVENT
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AU-Ggregates AI API Server...")
    

    # Start conversation memory cleanup service
    try:
        from app.services.cleanup_service import start_cleanup_service
        start_cleanup_service()
        logger.success("Conversation memory cleanup service started")
    except Exception as e:
        logger.error(f"Cleanup service initialization failed: {e}")
        logger.warning("Conversation memory cleanup will not run automatically")
    
    logger.success("Server startup complete")


# ==============================================================================
# SHUTDOWN EVENT
# ==============================================================================
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    logger.info("Shutting down AU-Ggregates AI API Server...")
    
    # Stop conversation memory cleanup service
    try:
        from app.services.cleanup_service import stop_cleanup_service
        stop_cleanup_service()
        logger.success("Conversation memory cleanup service stopped")
    except Exception as e:
        logger.error(f"Error stopping cleanup service: {e}")
    
    logger.success("Server shutdown complete")


# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "7860"))
    host = os.getenv("API_HOST", "0.0.0.0")
    logger.info("=" * 60)
    logger.info("AU-GGREGATES AI API SERVER v2.0")
    logger.info(f"Starting on http://{host}:{port}")
    logger.info("=" * 60)

    uvicorn.run("app.main:app", host=host, port=port, reload=False)
