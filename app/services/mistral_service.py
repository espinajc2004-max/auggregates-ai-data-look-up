"""
Mistral Service - Hybrid 3-stage architecture (Mistral → T5 → Mistral).
Stage 1: Mistral understands query and extracts intent
Stage 2: T5 generates SQL from structured intent
Stage 3: Mistral formats results into natural language response
"""

import re
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.config.mistral_config import MistralConfig, ModelLoadConfig
from app.config.prompt_templates import build_system_prompt, SYSTEM_IDENTITY, SCHEMA_CONTEXT, SAFETY_RULES
from app.services.mistral_context_manager import MistralContextManager
from app.services.sql_validator import SQLValidator
from app.services.supabase_client import get_supabase_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ModelLoadError(Exception):
    """Raised when model fails to load."""
    pass


class GenerationError(Exception):
    """Raised when model fails to generate valid output."""
    pass


class ValidationError(Exception):
    """Raised when generated SQL is invalid."""
    pass


class MistralService:
    """
    Hybrid 3-stage service: Mistral → T5 → Mistral.
    
    Stage 1 (Mistral): Intent understanding and extraction
    Stage 2 (T5): SQL generation from structured intent
    Stage 3 (Mistral): Natural language response formatting
    """
    
    def __init__(
        self,
        config: Optional[MistralConfig] = None,
        prompt_builder=None,
        context_manager: Optional[MistralContextManager] = None,
        sql_validator: Optional[SQLValidator] = None
    ):
        """
        Initialize hybrid Mistral+T5 service.
        
        Args:
            config: Mistral configuration
            prompt_builder: System prompt builder
            context_manager: Conversation context manager
            sql_validator: SQL validator
        """
        self.config = config or MistralConfig.from_env()
        self.prompt_builder = prompt_builder
        self.context_manager = context_manager
        self.sql_validator = sql_validator or SQLValidator()
        
        # Mistral 7B model (for understanding and response formatting)
        self.mistral_model = None
        self.mistral_tokenizer = None
        self._mistral_loaded = False
        self._mistral_enabled = True  # Enable Mistral 7B
        
        # T5 model (for SQL generation)
        self.t5_model = None
        self.t5_tokenizer = None
        self._t5_loaded = False
    
    def _load_model(self) -> None:
        """
        Load both Mistral 7B and T5 models.
        
        Raises:
            ModelLoadError: If models fail to load
        """
        # Load Mistral 7B (mistralai/Mistral-7B-Instruct-v0.2 with 4-bit quantization)
        self._load_mistral()
        self._load_t5()
    
    def _load_mistral(self) -> None:
        """
        Load Mistral 7B model for intent understanding and response formatting.
        
        Raises:
            ModelLoadError: If model fails to load
        """
        if self._mistral_loaded:
            return
        
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            logger.info(f"Loading Mistral model: {self.config.model_name}")
            logger.info(f"Device: {self.config.device}")
            
            # Check GPU availability
            cuda_available = hasattr(torch, 'cuda') and torch.cuda.is_available()
            if self.config.device == "cuda" and not cuda_available:
                logger.warning("CUDA not available, using CPU")
                self.config.device = "cpu"
            
            # Load tokenizer
            self.mistral_tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True
            )
            
            # Load Mistral model with 4-bit quantization to reduce memory usage
            load_kwargs = {
                "device_map": self.config.device_map,
                "trust_remote_code": True,
            }
            if self.config.quantization == "4bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
            elif self.config.quantization == "8bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            else:
                load_kwargs["torch_dtype"] = torch.float32
            
            self.mistral_model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                **load_kwargs
            )
            
            self._mistral_loaded = True
            logger.info("Mistral model loaded successfully")
            
            # Log GPU memory if available
            if hasattr(torch, 'cuda') and torch.cuda.is_available():
                memory_allocated = torch.cuda.memory_allocated() / 1024**3
                memory_reserved = torch.cuda.memory_reserved() / 1024**3
                logger.info(f"GPU Memory - Allocated: {memory_allocated:.2f}GB, Reserved: {memory_reserved:.2f}GB")
        
        except Exception as e:
            logger.error(f"Failed to load Mistral model: {str(e)}")
            raise ModelLoadError(f"Failed to load Mistral: {str(e)}")
    
    def _load_t5(self) -> None:
        """
        Load T5 model for SQL generation.
        
        Raises:
            ModelLoadError: If model fails to load
        """
        if self._t5_loaded:
            return
        
        try:
            from transformers import T5ForConditionalGeneration, T5Tokenizer
            import os
            
            # T5 model path from environment (pre-trained text-to-SQL model)
            t5_model_path = os.getenv("T5_MODEL_PATH", "cssupport/t5-small-awesome-text-to-sql")
            
            logger.info(f"Loading T5 text-to-SQL model from: {t5_model_path}")
            
            # Load T5 tokenizer and model
            self.t5_tokenizer = T5Tokenizer.from_pretrained(t5_model_path)
            self.t5_model = T5ForConditionalGeneration.from_pretrained(t5_model_path)
            
            # Move to CPU (T5 is small enough to run on CPU)
            self.t5_model = self.t5_model.to("cpu")
            self.t5_model.eval()
            
            self._t5_loaded = True
            logger.info("T5 model loaded successfully")
        
        except Exception as e:
            logger.error(f"Failed to load T5 model: {str(e)}")
            raise ModelLoadError(f"Failed to load T5: {str(e)}")
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process query using 3-stage hybrid architecture:
        Stage 1: Mistral extracts structured intent (JSON)
        Stage 2: T5 generates SQL from intent → validated → executed via Supabase
        Stage 3: Mistral formats results into natural language (Taglish)

        Falls back to rule-based query_engine if T5 SQL is invalid.
        """
        start_time = time.time()

        try:
            # Load models if not already loaded
            self._load_model()

            # Get conversation context
            context = []
            if conversation_id and self.context_manager:
                context = await self.context_manager.get_context(conversation_id, query)

            # STAGE 1: Mistral extracts structured intent
            logger.info("Stage 1: Extracting intent with Mistral")
            stage1_start = time.time()
            intent = await self._extract_intent(query, context)
            stage1_time = (time.time() - stage1_start) * 1000
            logger.info(f"Stage 1 done in {stage1_time:.0f}ms | intent: {intent}")

            # Check if clarification is needed
            if intent.get("needs_clarification"):
                return {
                    "response": intent.get("clarification_question", "Could you please clarify your question?"),
                    "needs_clarification": True,
                    "query": query,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }

            # STAGE 2: T5 generates SQL → validate → execute
            logger.info("Stage 2: Generating SQL with T5")
            stage2_start = time.time()
            data = []
            sql = ""
            execution_time = 0.0

            try:
                sql = await self._generate_sql_with_t5(intent)
                stage2_time = (time.time() - stage2_start) * 1000
                logger.info(f"Stage 2 done in {stage2_time:.0f}ms | SQL: {sql}")

                # Validate SQL
                validation_result = self.sql_validator.validate(sql, role="user")
                if not validation_result.is_valid:
                    raise ValidationError(", ".join(validation_result.errors or ["Invalid SQL"]))

                # Execute via Supabase RPC
                supabase = get_supabase_client()
                exec_start = time.time()
                result = supabase.rpc("execute_sql", {"query": sql})
                execution_time = (time.time() - exec_start) * 1000
                data = result if isinstance(result, list) else []
                logger.info(f"SQL executed in {execution_time:.0f}ms | rows: {len(data)}")

            except (ValidationError, GenerationError, Exception) as sql_err:
                # T5 SQL failed — fall back to rule-based query_engine
                logger.warning(f"Stage 2 SQL failed ({sql_err}), falling back to query_engine")
                stage2_time = (time.time() - stage2_start) * 1000

                from app.services.intent_parser import parse_intent
                from app.services.query_engine import QueryEngine
                rule_intent = parse_intent(query)
                engine = QueryEngine()
                rule_result = engine.execute(rule_intent)
                data = rule_result.get("data", [])
                sql = f"-- rule-based fallback: {rule_intent.get('intent')}"

            # STAGE 3: Mistral formats natural language response
            logger.info("Stage 3: Formatting response with Mistral")
            stage3_start = time.time()
            formatted_response = await self._format_response(query, intent, sql, data, context)
            stage3_time = (time.time() - stage3_start) * 1000
            logger.info(f"Stage 3 done in {stage3_time:.0f}ms")

            # Save to conversation context
            if conversation_id and self.context_manager:
                await self.context_manager.add_exchange(
                    conversation_id=conversation_id,
                    query=query,
                    sql=sql,
                    results=data
                )

            total_time = (time.time() - start_time) * 1000

            return {
                "response": formatted_response,
                "query": query,
                "intent": intent,
                "sql": sql,
                "sql_valid": True,
                "data": data,
                "row_count": len(data),
                "execution_time_ms": execution_time,
                "stage1_time_ms": stage1_time,
                "stage2_time_ms": stage2_time,
                "stage3_time_ms": stage3_time,
                "total_time_ms": total_time,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "context_used": len(context) > 0,
                "context_length": len(context)
            }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            total_time = (time.time() - start_time) * 1000

            return {
                "response": f"Sorry, may error: {str(e)}",
                "query": query,
                "sql": "",
                "sql_valid": False,
                "data": [],
                "row_count": 0,
                "execution_time_ms": 0,
                "total_time_ms": total_time,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def _extract_intent(self, query: str, context: list) -> Dict[str, Any]:
        """
        STAGE 1: Use Mistral to extract structured intent from natural language (Taglish).

        Returns JSON with intent_type, entities, filters, needs_clarification.
        Falls back to rule-based parser if Mistral output is unparseable.
        """
        import torch

        # Mistral-7B-Instruct uses [INST]...[/INST] format
        system_msg = (
            "You are an AI assistant for a construction company expense management system. "
            "Extract structured intent from user queries. "
            "Return ONLY a valid JSON object, no explanation.\n\n"
            f"DATABASE SCHEMA:\n{SCHEMA_CONTEXT}\n\n"
            f"{SAFETY_RULES}"
        )
        user_msg = (
            f"Extract intent from: \"{query}\"\n\n"
            "Return JSON with these fields:\n"
            "- intent_type: one of [query_data, sum, count, compare, list_categories, date_filter, clarification_needed]\n"
            "- source_table: 'Expenses' or 'CashFlow' (based on query context)\n"
            "- entities: list of mentioned items (file names, project names, categories like fuel/food/labor)\n"
            "- filters: dict with optional keys: source_table, category, file_name, date, project_name, metadata_key, metadata_value\n"
            "- needs_clarification: true/false\n"
            "- clarification_question: string (only if needs_clarification is true)\n\n"
            "Example: {\"intent_type\": \"query_data\", \"source_table\": \"Expenses\", "
            "\"entities\": [\"fuel\"], "
            "\"filters\": {\"source_table\": \"Expenses\", \"metadata_key\": \"Category\", \"metadata_value\": \"fuel\", \"project_name\": \"project alpha\"}, "
            "\"needs_clarification\": false}"
        )

        prompt = f"<s>[INST] {system_msg}\n\n{user_msg} [/INST]"

        try:
            inputs = self.mistral_tokenizer(prompt, return_tensors="pt")
            cuda_available = hasattr(torch, 'cuda') and torch.cuda.is_available()
            if cuda_available:
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.mistral_model.generate(
                    **inputs,
                    max_new_tokens=300,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=self.mistral_tokenizer.eos_token_id
                )

            # Decode only the new tokens (skip the prompt)
            new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            response = self.mistral_tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            logger.info(f"Mistral Stage1 raw output: {response[:300]}")

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group())
                # Ensure required fields exist
                intent.setdefault("intent_type", "query_data")
                intent.setdefault("entities", [])
                intent.setdefault("filters", {})
                intent.setdefault("needs_clarification", False)
                return intent

            logger.warning("Mistral Stage1: no JSON found in output, using rule-based fallback")

        except Exception as e:
            logger.error(f"Mistral Stage1 error: {str(e)}")

        # Fallback: use rule-based intent parser
        from app.services.intent_parser import parse_intent
        rule = parse_intent(query)
        # Detect source_table from query
        query_lower = query.lower()
        source_table = "CashFlow" if any(w in query_lower for w in ["cashflow", "cash flow", "daloy", "inflow", "outflow"]) else "Expenses"
        return {
            "intent_type": rule.get("intent", "query_data"),
            "source_table": source_table,
            "entities": list(rule.get("slots", {}).values()),
            "filters": {**rule.get("slots", {}), "source_table": source_table},
            "needs_clarification": rule.get("needs_clarification", False),
            "clarification_question": rule.get("clarification_question", "")
        }
    
    async def _generate_sql_with_t5(self, intent: Dict[str, Any]) -> str:
        """
        STAGE 2: Use T5 to generate SQL from structured intent.
        
        Args:
            intent: Structured intent from Stage 1
            
        Returns:
            Generated SQL query
        """
        # Format intent as T5 input — include schema so T5 knows the correct table/columns
        intent_text = json.dumps(intent)
        t5_input = (
            f"tables: ai_documents (source_table, source_id, file_id, file_name, "
            f"project_id, project_name, searchable_text, metadata) | "
            f"query: {intent_text}"
        )
        
        logger.info(f"T5 input: {t5_input}")
        
        try:
            import torch
            
            # Tokenize
            inputs = self.t5_tokenizer(
                t5_input,
                return_tensors="pt",
                max_length=512,
                truncation=True
            )
            
            # Generate SQL
            with torch.no_grad():
                outputs = self.t5_model.generate(
                    inputs.input_ids,
                    max_length=256,
                    num_beams=4,
                    early_stopping=True
                )
            
            sql = self.t5_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            logger.info(f"T5 raw output: {sql}")
            
            # Clean up SQL
            if not sql.strip().upper().startswith("SELECT"):
                sql = "SELECT " + sql
            if not sql.strip().endswith(";"):
                sql = sql.strip() + ";"
            
            logger.info(f"T5 cleaned SQL: {sql}")
            
            return sql
        
        except Exception as e:
            logger.error(f"T5 SQL generation error: {str(e)}")
            raise GenerationError(f"Failed to generate SQL: {str(e)}")
    
    async def _format_response(
        self,
        query: str,
        intent: Dict[str, Any],
        sql: str,
        data: list,
        context: list
    ) -> str:
        """
        STAGE 3: Use Mistral to format results into natural Taglish response.
        Falls back to template if Mistral fails.
        """
        import torch

        # Summarize data for prompt (avoid huge context)
        if not data:
            data_summary = "No results found."
        elif len(data) <= 3:
            data_summary = f"{len(data)} results: {json.dumps(data, default=str)}"
        else:
            data_summary = f"{len(data)} results. First 3: {json.dumps(data[:3], default=str)}"

        system_msg = SYSTEM_IDENTITY.strip()
        user_msg = (
            f"User asked: \"{query}\"\n"
            f"Database returned: {data_summary}\n\n"
            "Write a short, helpful response in English that directly answers the question. "
            "If there are amounts, format them with ₱ sign. Keep it under 3 sentences."
        )

        prompt = f"<s>[INST] {system_msg}\n\n{user_msg} [/INST]"

        try:
            inputs = self.mistral_tokenizer(prompt, return_tensors="pt")
            cuda_available = hasattr(torch, 'cuda') and torch.cuda.is_available()
            if cuda_available:
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.mistral_model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.mistral_tokenizer.eos_token_id
                )

            new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            response = self.mistral_tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            logger.info(f"Mistral Stage3 response: {response[:200]}")

            if response:
                return response

        except Exception as e:
            logger.error(f"Mistral Stage3 error: {str(e)}")

        # Fallback: template response
        if not data:
            return "No results found for your query."
        total_key = next((k for k in ["total", "Expenses", "Amount"] if data[0].get(k)), None)
        if total_key and len(data) == 1:
            return f"Found: {data[0].get(total_key)} ({len(data)} result)."
        return f"Found {len(data)} results for your query."
