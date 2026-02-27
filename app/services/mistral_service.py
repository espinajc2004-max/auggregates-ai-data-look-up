"""
Mistral Service - Hybrid 3-stage architecture (Mistral → T5 → Mistral).

Architecture:
  Mistral = Brain (understands user query, extracts intent, formats response)
  T5 = SQL Converter (sole SQL generator in Stage 2)
  Rule-based = Last resort fallback (ONLY fires when T5 errors out)

Pipeline:
  Stage 1: Mistral extracts structured intent JSON from user query
  Stage 2: T5 generates SQL (only method) → validated → executed via Supabase
  Stage 3: Mistral formats query results into natural language response

Fallback chain (Stage 2 only):
  T5 SQL → raise exception → process_query catches → rule-based QueryEngine (last resort)
"""

import re
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.config.mistral_config import MistralConfig
from app.config.prompt_templates import SYSTEM_IDENTITY, SCHEMA_CONTEXT, SAFETY_RULES, JSON_INTENT_EXAMPLES, build_stage1_prompt, build_stage3_prompt
from app.services.mistral_context_manager import MistralContextManager
from app.services.schema_registry import SchemaRegistry, get_schema_registry
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


# Spider format schema for T5-LM-Large-text2sql-spider model input
SPIDER_SCHEMA = (
    "tables: ai_documents ("
    "id, source_table, file_name, project_name, "
    "searchable_text, metadata, document_type"
    ") | query: "
)


class MistralService:
    """
    Hybrid 3-stage service: Mistral → T5 → Mistral.
    
    Mistral = Brain (understands query + formats response)
    T5 = SQL Converter (sole SQL generator in Stage 2)
    
    Stage 1 (Mistral): Extract structured intent JSON from user query
    Stage 2 (T5): T5 generates SQL (only method) → validate → execute
    Stage 3 (Mistral): Format query results into natural language response
    
    Fallback: Rule-based engine (ONLY when T5 errors out in Stage 2)
    """
    
    def __init__(
        self,
        config: Optional[MistralConfig] = None,
        prompt_builder=None,
        context_manager: Optional[MistralContextManager] = None,
        sql_validator: Optional[SQLValidator] = None,
        schema_registry: Optional[SchemaRegistry] = None
    ):
        """
        Initialize hybrid Mistral+T5 service.
        
        Args:
            config: Mistral configuration
            prompt_builder: System prompt builder
            context_manager: Conversation context manager
            sql_validator: SQL validator
            schema_registry: Schema registry for dynamic metadata key discovery
        """
        self.config = config or MistralConfig.from_env()
        self.prompt_builder = prompt_builder
        self.context_manager = context_manager
        self.sql_validator = sql_validator or SQLValidator()
        self.schema_registry = schema_registry or get_schema_registry()
        
        # Mistral 7B model (for understanding and response formatting)
        self.mistral_model = None
        self.mistral_tokenizer = None
        self._mistral_loaded = False
        self._mistral_enabled = True  # Enable Mistral 7B
        
        # T5 model (for SQL generation)
        self.t5_model = None
        self.t5_tokenizer = None
        self._t5_loaded = False
        self._t5_device = "cpu"  # Default device, updated in _load_t5()
    
    def _load_model(self) -> None:
        """
        Load both Mistral 7B and T5 models.
        
        Raises:
            ModelLoadError: If Mistral fails to load.
            T5 load failures are caught gracefully — the service continues
            with rule-based fallback only.
        """
        # Load Mistral 7B (mistralai/Mistral-7B-Instruct-v0.2 with 4-bit quantization)
        self._load_mistral()
        try:
            self._load_t5()
        except ModelLoadError as e:
            logger.warning(f"T5 model failed to load — continuing without T5: {e}")
            self._t5_loaded = False
    
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
            logger.error(f"Failed to load Mistral model: {str(e)}", exc_info=True)
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
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import torch
            import os
            
            # T5 model path from environment (pre-trained text-to-SQL model)
            t5_model_path = os.getenv("T5_MODEL_PATH", "gaussalgo/T5-LM-Large-text2sql-spider")
            
            # Detect local fine-tuned model vs HuggingFace identifier
            if os.path.isdir(t5_model_path):
                logger.info(f"Loading fine-tuned T5 from local: {t5_model_path}")
            else:
                logger.info(f"Loading base T5 from HuggingFace: {t5_model_path}")
            
            # Determine device: GPU if available, else CPU with warning
            if torch.cuda.is_available():
                device = "cuda"
            else:
                logger.warning("CUDA not available — loading T5 on CPU (slower inference)")
                device = "cpu"
            
            # Fix tokenizer_config.json if extra_special_tokens is a list (not dict)
            # This is a known issue with some T5 fine-tuned models saved with older transformers.
            # Works for both local paths AND HuggingFace cached downloads.
            import json as _json
            from pathlib import Path

            def _find_tokenizer_config(model_path: str):
                """Find tokenizer_config.json — local dir or HF cache."""
                # Case 1: local directory
                if os.path.isdir(model_path):
                    p = os.path.join(model_path, "tokenizer_config.json")
                    return p if os.path.exists(p) else None
                # Case 2: HuggingFace cache (models--org--repo/snapshots/*/tokenizer_config.json)
                hf_cache = Path(os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))) / "hub"
                # Convert "org/repo" → "models--org--repo"
                cache_name = "models--" + model_path.replace("/", "--")
                snapshots_dir = hf_cache / cache_name / "snapshots"
                if snapshots_dir.exists():
                    for snap in sorted(snapshots_dir.iterdir(), reverse=True):
                        tc = snap / "tokenizer_config.json"
                        if tc.exists():
                            return str(tc)
                return None

            _tc_path = _find_tokenizer_config(t5_model_path)
            if _tc_path:
                with open(_tc_path) as _f:
                    _tc = _json.load(_f)
                if isinstance(_tc.get("extra_special_tokens"), list):
                    logger.warning("Fixing tokenizer_config.json: extra_special_tokens is list, converting to dict")
                    _tc["extra_special_tokens"] = {}
                    with open(_tc_path, "w") as _f:
                        _json.dump(_tc, _f, indent=2)
                    logger.info(f"tokenizer_config.json fixed at: {_tc_path}")

            # Load T5 tokenizer and model
            self.t5_tokenizer = AutoTokenizer.from_pretrained(t5_model_path)
            self.t5_model = AutoModelForSeq2SeqLM.from_pretrained(t5_model_path)
            self.t5_model = self.t5_model.to(device)
            self.t5_model.eval()
            self._t5_device = device  # Store for inference use
            
            self._t5_loaded = True
            logger.info(f"T5 model loaded successfully on {device}")
        
        except Exception as e:
            logger.error(f"Failed to load T5 model: {str(e)}", exc_info=True)
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

            # Check for out-of-scope query
            if intent.get("intent_type") == "out_of_scope":
                message = intent.get("out_of_scope_message") or "I can only help with expense and cashflow data queries."
                return {
                    "response": message,
                    "out_of_scope": True,
                    "query": query,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }

            # STAGE 2: Generate SQL → validate → execute
            # Chain: T5 (from Mistral's structured intent) → rule-based (last resort)
            logger.info("Stage 2: Generating SQL with T5")
            stage2_start = time.time()
            data = []
            sql = ""
            execution_time = 0.0
            sql_source = "none"

            try:
                # T5 receives structured query from Mistral (not raw user input)
                logger.info("Stage 2: T5 SQL generation from Mistral's structured intent")
                sql, sql_source = await self._generate_sql_with_t5(query, intent)
                logger.info(f"Stage 2 generated SQL (source={sql_source}): {sql}")
                
                # Validate T5 SQL
                validation_result = self.sql_validator.validate(sql, role="user")
                if not validation_result.is_valid:
                    logger.warning(f"Stage 2 SQL REJECTED by validator (source={sql_source}): {validation_result.errors}")
                    raise ValidationError(f"SQL invalid: {', '.join(validation_result.errors or ['Invalid SQL'])}")
                
                logger.info(f"Stage 2 SQL passed validation (source={sql_source}), executing...")

                # Execute via Supabase RPC
                supabase = get_supabase_client()
                exec_start = time.time()
                result = supabase.rpc("execute_sql", {"query": sql})
                execution_time = (time.time() - exec_start) * 1000
                data = result if isinstance(result, list) else []
                logger.info(f"SQL executed in {execution_time:.0f}ms (source={sql_source}) | rows: {len(data)}")

            except (ValidationError, GenerationError, Exception) as t5_err:
                # T5 failed — no fallback, raise the error directly
                logger.error(f"Stage 2 T5 failed: {type(t5_err).__name__}: {t5_err}")
                raise GenerationError(f"T5 SQL generation failed: {t5_err}")

            stage2_time = (time.time() - stage2_start) * 1000
            logger.info(f"Stage 2 done in {stage2_time:.0f}ms | source: {sql_source} | rows: {len(data)}")

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
                "sql_source": sql_source,
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
                "response": f"Sorry, an error occurred: {str(e)}",
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
        system_msg = build_stage1_prompt()
        user_msg = (
            f"Extract intent from this query: \"{query}\"\n\n"
            "Return a JSON object with these exact fields:\n"
            "- intent_type: list_files | query_data | sum | count | average | compare | list_categories | date_filter | out_of_scope\n"
            "- source_table: 'Expenses' or 'CashFlow' (default 'Expenses' if unclear)\n"
            "- entities: list of key terms mentioned (file names, categories, project names)\n"
            "- filters: dict with any of: file_name, project_name, category, date, supplier\n"
            "- needs_clarification: true or false\n"
            "- clarification_question: string (only if needs_clarification is true)\n"
            "- out_of_scope_message: string (only if intent_type is \"out_of_scope\")\n\n"
            "Return ONLY the JSON object. No explanation."
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
        source_table = "CashFlow" if any(w in query_lower for w in ["cashflow", "cash flow", "inflow", "outflow"]) else "Expenses"
        return {
            "intent_type": rule.get("intent", "query_data"),
            "source_table": source_table,
            "entities": list(rule.get("slots", {}).values()),
            "filters": {**rule.get("slots", {}), "source_table": source_table},
            "needs_clarification": rule.get("needs_clarification", False),
            "clarification_question": rule.get("clarification_question", "")
        }
    
    async def _generate_sql_with_t5(self, query: str, intent: Dict[str, Any]) -> tuple:
        """
        STAGE 2: Generate SQL — T5 only, no rule-based fallback.

        Returns:
            Tuple of (sql_string, source_label) where source is always "t5"
        Raises:
            GenerationError: If T5 fails to generate SQL
            ValidationError: If T5 output fails SQL validation
        """
        t5_start = time.time()

        try:
            sql = await self._generate_sql_with_t5_model(query, intent)
        except Exception as e:
            t5_time_ms = (time.time() - t5_start) * 1000
            logger.warning(f"Stage 2 T5 attempt failed in {t5_time_ms:.0f}ms: {e}")
            raise GenerationError(f"T5 SQL generation failed: {e}")

        t5_time_ms = (time.time() - t5_start) * 1000

        # Validate T5 output
        validation_result = self.sql_validator.validate(sql, role="user")
        if not validation_result.is_valid:
            logger.warning(
                f"Stage 2 T5 SQL rejected by validator in {t5_time_ms:.0f}ms: "
                f"{validation_result.errors} | SQL: {sql}"
            )
            raise ValidationError(
                f"T5 SQL invalid: {', '.join(validation_result.errors or ['Invalid SQL'])}"
            )

        logger.info(f"Stage 2 T5 attempt: {t5_time_ms:.0f}ms")
        logger.info(f"Stage 2: T5 SQL generated and validated (source=t5): {sql}")
        return (sql, "t5")

    async def _generate_sql_with_t5_model(self, query: str, intent: Dict[str, Any]) -> str:
        """
        Use T5 model to generate SQL from natural language query.
        Uses Spider format input with the raw user query.
        """
        # Spider format: pass raw user query to the Spider-trained model
        t5_input = SPIDER_SCHEMA + query
        
        logger.info(f"T5 Spider format input: {t5_input}")
        
        try:
            import torch
            
            # Tokenize
            inputs = self.t5_tokenizer(
                t5_input,
                return_tensors="pt",
                max_length=512,
                truncation=True
            )
            # Move input tensors to the same device as the T5 model
            inputs = {k: v.to(self._t5_device) for k, v in inputs.items()}
            
            # Generate SQL
            with torch.no_grad():
                outputs = self.t5_model.generate(
                    inputs["input_ids"],
                    max_length=512,
                    num_beams=4,
                    early_stopping=True
                )
            
            sql = self.t5_tokenizer.decode(outputs[0], skip_special_tokens=True)
            logger.info(f"T5 raw output: {sql}")
            
            # Clean up SQL
            if not sql.strip().upper().startswith("SELECT"):
                sql = "SELECT " + sql
            # Strip trailing semicolons — Supabase RPC rejects them
            sql = sql.strip().rstrip(";")
            
            # Post-process: convert standard column refs to JSONB patterns
            # T5 generates things like WHERE category = 'fuel' but we need metadata->>'Category'
            sql = self._convert_to_jsonb_sql(sql, intent)
            
            logger.info(f"T5 post-processed SQL: {sql}")
            return sql
        
        except Exception as e:
            logger.error(f"T5 SQL generation error: {str(e)}")
            raise GenerationError(f"Failed to generate SQL: {str(e)}")
    
    def _convert_to_jsonb_sql(self, sql: str, intent: Dict[str, Any]) -> str:
        """
        Post-process T5 SQL to convert standard column references to JSONB patterns.
        T5 generates: WHERE category = 'fuel'
        We need:      WHERE metadata->>'Category' ILIKE '%fuel%'

        Uses SchemaRegistry for dynamic metadata key discovery instead of
        hardcoded column mappings.
        """
        # Build metadata_columns dynamically from SchemaRegistry
        schema = self.schema_registry.get_schema()
        source_table = intent.get("source_table")

        metadata_columns: Dict[str, str] = {}
        if source_table and source_table in schema:
            for key in schema[source_table]:
                metadata_columns[key.lower()] = key
        else:
            # Cross-table: merge all keys
            for keys in schema.values():
                for key in keys:
                    metadata_columns[key.lower()] = key

        numeric_keys = self.schema_registry.get_numeric_keys()

        result = sql

        # Replace known column references with JSONB accessor patterns
        for col_lower, col_proper in metadata_columns.items():
            # Escape special regex chars in key name
            col_escaped = re.escape(col_lower)

            # Pattern: column = 'value' or column = "value"
            pattern = re.compile(
                rf"\b{col_escaped}\b\s*=\s*['\"]([^'\"]+)['\"]",
                re.IGNORECASE
            )
            result = pattern.sub(
                f"metadata->>'{col_proper}' ILIKE '%\\1%'",
                result
            )

            # Pattern: column LIKE '%value%'
            pattern2 = re.compile(
                rf"\b{col_escaped}\b\s+LIKE\s+",
                re.IGNORECASE
            )
            result = pattern2.sub(f"metadata->>'{col_proper}' ILIKE ", result)

            # Pattern: SUM(column), COUNT(column), AVG(column), MIN(column), MAX(column)
            pattern3 = re.compile(
                rf"(SUM|COUNT|AVG|MIN|MAX)\s*\(\s*{col_escaped}\s*\)",
                re.IGNORECASE
            )
            if col_proper in numeric_keys:
                result = pattern3.sub(
                    f"\\1((metadata->>'{col_proper}')::numeric)",
                    result
                )
            else:
                result = pattern3.sub(
                    f"\\1(metadata->>'{col_proper}')",
                    result
                )

        # Passthrough: catch remaining column references not in known keys
        # Matches word = 'value' patterns that weren't already converted to metadata->>
        remaining_eq = re.compile(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b\s*=\s*['\"]([^'\"]+)['\"]"
        )
        for match in remaining_eq.finditer(result):
            col_name = match.group(1)
            # Skip already-converted, SQL keywords, and known non-metadata columns
            if (col_name.lower() in ('source_table', 'file_name', 'project_name',
                                      'document_type', 'metadata', 'select', 'from',
                                      'where', 'and', 'or', 'not', 'in', 'like',
                                      'ilike', 'order', 'group', 'by', 'limit',
                                      'offset', 'as', 'on', 'join')
                    or "metadata->>'" in match.group(0)):
                continue
            # Unknown key — use as-is in JSONB accessor
            value = match.group(2)
            old_fragment = match.group(0)
            new_fragment = f"metadata->>'{col_name}' ILIKE '%{value}%'"
            result = result.replace(old_fragment, new_fragment, 1)

        # Ensure table is ai_documents (T5 might generate wrong table name)
        result = re.sub(
            r'\bFROM\s+\w+',
            'FROM ai_documents',
            result,
            count=1,
            flags=re.IGNORECASE
        )

        # Convert exact match on file_name/project_name to ILIKE for fuzzy matching
        # T5 generates: file_name = 'francis gays' → file_name ILIKE '%francis gays%'
        for col in ['file_name', 'project_name']:
            pattern = re.compile(
                rf"\b{col}\b\s*=\s*['\"]([^'\"]+)['\"]",
                re.IGNORECASE
            )
            result = pattern.sub(f"{col} ILIKE '%\\1%'", result)

        # Add source_table filter if not present (only when source_table is specified)
        if source_table and "source_table" not in result.lower():
            if "WHERE" in result.upper():
                result = result.replace("WHERE", f"WHERE source_table = '{source_table}' AND", 1)
            else:
                # Insert before ORDER BY, GROUP BY, LIMIT, or semicolon
                insert_match = re.search(r'\s*(ORDER|GROUP|LIMIT|;)', result, re.IGNORECASE)
                if insert_match:
                    pos = insert_match.start()
                    result = result[:pos] + f" WHERE source_table = '{source_table}'" + result[pos:]
                else:
                    result = result.rstrip(';') + f" WHERE source_table = '{source_table}';"
        # When source_table is None, do NOT inject any source_table filter (cross-table search)

        return result

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
        elif len(data) <= 10:
            data_summary = f"EXACTLY {len(data)} rows returned:\n{json.dumps(data, default=str)}"
        else:
            data_summary = f"EXACTLY {len(data)} rows returned. Showing first 5:\n{json.dumps(data[:5], default=str)}"

        system_msg = build_stage3_prompt()
        user_msg = (
            f"User asked: \"{query}\"\n"
            f"Database returned: {data_summary}\n\n"
            f"Write a short, helpful response in ENGLISH ONLY that directly answers the question. "
            f"IMPORTANT RULES:\n"
            f"- The database returned EXACTLY {len(data)} row(s). State this exact count.\n"
            f"- If there are amounts, format them with ₱ sign (e.g., ₱12,500.00).\n"
            f"- Do NOT use Tagalog or Taglish. English only.\n"
            f"- Keep it under 3 sentences.\n"
            f"- Do NOT expose SQL or technical details to the user."
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
