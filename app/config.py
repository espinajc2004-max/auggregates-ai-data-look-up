"""
Configuration module for AU-Ggregates AI API.
Loads environment variables and provides centralized configuration.
"""

import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Config:
    """Application configuration loaded from environment variables."""
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Model Configuration
    MODEL_PATH: str = os.getenv("MODEL_PATH", "./ml/model/final")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    
    
    # Sentry Configuration (optional - for error tracking)
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Thresholds
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.10"))
    
    # Multi-Query Settings
    MULTI_QUERY_ENABLED: bool = True  # Feature flag
    MULTI_QUERY_MAX_SUBQUERIES: int = 5  # Max sub-queries allowed
    MULTI_QUERY_RESULTS_PER_QUERY: int = 10  # Results per sub-query
    
    # URL Navigation Settings (Dynamic URL Generation)
    # DISABLED: System displays data in table columns only, no detail pages to navigate to
    URL_NAVIGATION_ENABLED: bool = False  # Enable/disable URL generation
    URL_VALIDATION_ENABLED: bool = False  # Validate URLs before returning (slower but safer)
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "")  # e.g., "https://app.auggregates.com"
    
    # URL Patterns (customize to match your frontend routes)
    URL_PATTERNS: dict = {
        "Expenses": "/expenses/view/{id}",
        "CashFlow": "/cashflow/view/{id}",
        "Project": "/projects/view/{id}",
        "Quotation": "/quotations/view/{id}",
        "QuotationItem": "/quotations/{quotation_id}/items/{id}",
    }
    
    # Semantic Search Settings (Phase 1)
    # DISABLED: Heavy embedding model causes crashes on Windows
    # System will use keyword-only search which still handles complex queries
    SEMANTIC_SEARCH_ENABLED: bool = False  # Enable/disable semantic search
    SEMANTIC_WEIGHT: float = 0.7  # 70% semantic, 30% keyword
    EMBEDDINGS_MODEL: str = "intfloat/multilingual-e5-base"
    EMBEDDINGS_BATCH_SIZE: int = 100
    
    # Text-to-SQL Settings (Phase 2)
    TEXT_TO_SQL_ENABLED: bool = os.getenv("TEXT_TO_SQL_ENABLED", "false").lower() == "true"
    TEXT_TO_SQL_LOCAL: bool = os.getenv("TEXT_TO_SQL_LOCAL", "true").lower() == "true"
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-coder:6.7b")
    MODAL_API_URL: str = os.getenv("MODAL_API_URL", "")
    MODAL_API_KEY: str = os.getenv("MODAL_API_KEY", "")
    TEXT_TO_SQL_TIMEOUT: int = int(os.getenv("TEXT_TO_SQL_TIMEOUT", "60"))  # Local models need more time
    TEXT_TO_SQL_MAX_RETRIES: int = int(os.getenv("TEXT_TO_SQL_MAX_RETRIES", "3"))
    
    # T5 Text-to-SQL Settings (ChatGPT-Style 3-Stage Architecture)
    TEXT_TO_SQL_USE_T5: bool = os.getenv("TEXT_TO_SQL_USE_T5", "true").lower() == "true"
    T5_MODEL_PATH: str = os.getenv("T5_MODEL_PATH", "./ml/models/t5_text_to_sql")
    T5_CONFIDENCE_THRESHOLD: float = float(os.getenv("T5_CONFIDENCE_THRESHOLD", "0.7"))
    ALLOWED_TABLES: List[str] = os.getenv("ALLOWED_TABLES", "ai_documents,projects,conversations").split(",")
    
    # Stage 1: DistilBERT Orchestrator Settings
    ORCHESTRATOR_ENABLED: bool = os.getenv("ORCHESTRATOR_ENABLED", "true").lower() == "true"
    ORCHESTRATOR_MODEL_PATH: str = os.getenv("ORCHESTRATOR_MODEL_PATH", "./ml/models/enhanced_orchestrator_model")
    
    # Stage 1.5: DB Clarification Settings
    DB_CLARIFICATION_ENABLED: bool = os.getenv("DB_CLARIFICATION_ENABLED", "true").lower() == "true"
    DB_CLARIFICATION_MAX_OPTIONS: int = int(os.getenv("DB_CLARIFICATION_MAX_OPTIONS", "10"))
    
    # Stage 3: LoRA Composers Settings
    STAGE3_ENABLED: bool = os.getenv("STAGE3_ENABLED", "true").lower() == "true"
    LORA_ANSWER_COMPOSER_PATH: str = os.getenv("LORA_ANSWER_COMPOSER_PATH", "./ml/models/lora_answer_composer")
    LORA_CLARIFICATION_COMPOSER_PATH: str = os.getenv("LORA_CLARIFICATION_COMPOSER_PATH", "./ml/models/lora_clarification_composer")
    
    @classmethod
    def get_supabase_headers(cls) -> dict:
        """Get headers for Supabase REST API requests."""
        return {
            "apikey": cls.SUPABASE_KEY,
            "Authorization": f"Bearer {cls.SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return True
