"""
Mistral Service - Hybrid 3-stage architecture (Mistral → T5 → Mistral).

Architecture:
  Mistral = Brain (understands user query, extracts intent, formats response)
  T5 = SQL Converter (receives structured instruction from Mistral, generates SQL)
  Rule-based = Last resort fallback (ONLY fires when T5 errors out)

Pipeline:
  Stage 1: Mistral extracts structured intent JSON from user query
  Stage 2: T5 generates SQL from Mistral's structured intent → validate → execute
  Stage 3: Mistral formats query results into natural language response

Fallback chain (Stage 2 only):
  T5 SQL → rule-based (triggers on ValidationError, GenerationError, or execution error)
"""

import re
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.config.mistral_config import MistralConfig
from app.config.prompt_templates import SYSTEM_IDENTITY, SCHEMA_CONTEXT, SAFETY_RULES
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
    
    Mistral = Brain (understands query + formats response)
    T5 = SQL Converter (receives structured intent from Mistral, not raw user query)
    
    Stage 1 (Mistral): Extract structured intent JSON from user query
    Stage 2 (T5): Generate SQL from Mistral's structured intent → validate → execute
    Stage 3 (Mistral): Format query results into natural language response
    
    Fallback: Rule-based engine (ONLY when T5 errors out in Stage 2)
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
                # T5 failed — fall back to rule-based
                logger.warning(f"Stage 2 T5 failed: {type(t5_err).__name__}: {t5_err}, falling back to rule-based")

                from app.services.intent_parser import parse_intent
                from app.services.query_engine import QueryEngine
                rule_intent = parse_intent(query)
                engine = QueryEngine()
                rule_result = engine.execute(rule_intent)
                data = rule_result.get("data", [])
                sql = f"-- rule-based fallback: {rule_intent.get('intent')}"
                sql_source = "rule-based"

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
            "- intent_type: one of [query_data, sum, count, average, min, max, compare, list_categories, date_filter, clarification_needed]\n"
            "  Use 'sum' for total/sum queries (e.g., 'total expenses', 'how much total')\n"
            "  Use 'count' for counting queries (e.g., 'how many', 'count of')\n"
            "  Use 'average' for average queries (e.g., 'average expense', 'mean cost')\n"
            "  Use 'compare' for comparison queries (e.g., 'fuel vs labor', 'compare categories')\n"
            "  Use 'query_data' for listing/showing data\n"
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
        STAGE 2: Generate SQL from Mistral's structured intent.
        
        Strategy: Build SQL directly from intent (reliable) → fall back to T5 if needed.
        
        Returns:
            Tuple of (sql_string, source_label) where source is "direct" or "t5"
        """
        # Try direct SQL builder first (reliable, uses Mistral's structured intent)
        try:
            sql = self._build_direct_sql(intent)
            if sql:
                logger.info(f"Stage 2: Direct SQL from intent: {sql}")
                return (sql, "direct")
        except Exception as e:
            logger.warning(f"Stage 2: Direct SQL builder failed: {e}")
        
        # Fallback: use T5 model
        logger.info("Stage 2: Falling back to T5 model for SQL generation")
        sql = await self._generate_sql_with_t5_model(query, intent)
        return (sql, "t5")
    
    def _build_direct_sql(self, intent: Dict[str, Any]) -> Optional[str]:
        """
        Build SQL directly from Mistral's structured intent.
        No T5 needed — we construct the query from the extracted fields.
        
        Returns SQL string or None if we can't build it directly.
        """
        source_table = intent.get("source_table", "Expenses")
        intent_type = intent.get("intent_type", "query_data")
        filters = intent.get("filters", {})
        entities = intent.get("entities", [])
        
        # Build SELECT clause based on intent type
        if intent_type == "sum":
            select = "SELECT SUM((metadata->>'Expenses')::numeric) as total, COUNT(*) as count"
        elif intent_type == "count":
            select = "SELECT COUNT(*) as count"
        elif intent_type == "average":
            select = "SELECT AVG((metadata->>'Expenses')::numeric) as average, COUNT(*) as count"
        elif intent_type == "min":
            select = "SELECT MIN((metadata->>'Expenses')::numeric) as minimum"
        elif intent_type == "max":
            select = "SELECT MAX((metadata->>'Expenses')::numeric) as maximum"
        elif intent_type == "list_categories":
            select = "SELECT DISTINCT metadata->>'Category' as category"
        else:
            # query_data, date_filter, etc. — return all columns
            select = "SELECT id, file_name, project_name, source_table, searchable_text, metadata"
        
        # Build WHERE clause
        where_parts = [f"source_table = '{source_table}'"]
        
        # File name filter
        file_name = filters.get("file_name")
        if file_name:
            where_parts.append(f"file_name ILIKE '%{file_name}%'")
        
        # Project name filter
        project_name = filters.get("project_name")
        if project_name:
            where_parts.append(f"project_name ILIKE '%{project_name}%'")
        
        # Category filter (metadata JSONB)
        category = filters.get("category") or filters.get("metadata_value")
        if category:
            where_parts.append(f"metadata->>'Category' ILIKE '%{category}%'")
        
        # Supplier filter
        supplier = filters.get("supplier")
        if supplier:
            where_parts.append(f"metadata->>'Supplier' ILIKE '%{supplier}%'")
        
        # Date filter
        date_val = filters.get("date")
        if date_val:
            where_parts.append(f"metadata->>'Date' ILIKE '%{date_val}%'")
        
        # Determine if this is a "file lookup" vs "data query"
        # File lookup: user wants the parent file record (e.g., "show me francis gays file")
        # Data query: user wants rows inside a file (e.g., "show fuel expenses in francis gays")
        has_row_filter = any(filters.get(k) for k in ["category", "metadata_value", "supplier", "date"])
        is_file_lookup = file_name and not has_row_filter and intent_type == "query_data"
        
        if is_file_lookup:
            # Only return the parent file record, not individual rows
            where_parts.append("document_type = 'file'")
        elif has_row_filter:
            # Only return row-level data, not the file record
            where_parts.append("document_type = 'row'")
        
        # If no specific filters but we have entities, use searchable_text
        has_specific_filter = any(filters.get(k) for k in ["file_name", "project_name", "category", "metadata_value", "supplier", "date"])
        if not has_specific_filter and entities:
            for entity in entities:
                if entity and isinstance(entity, str):
                    where_parts.append(f"searchable_text ILIKE '%{entity}%'")
        
        where_clause = " AND ".join(where_parts)
        
        # Build full SQL
        sql = f"{select} FROM ai_documents WHERE {where_clause}"
        
        # Add GROUP BY for compare
        if intent_type == "compare":
            sql = f"SELECT metadata->>'Category' as category, SUM((metadata->>'Expenses')::numeric) as total, COUNT(*) as count FROM ai_documents WHERE {where_clause} GROUP BY metadata->>'Category'"
        
        # Add LIMIT for data queries
        if intent_type in ("query_data", "date_filter"):
            sql += " LIMIT 50"
        
        sql += ";"
        
        logger.info(f"Direct SQL built: {sql}")
        return sql
    
    async def _generate_sql_with_t5_model(self, query: str, intent: Dict[str, Any]) -> str:
        """
        Use T5 model to generate SQL (fallback when direct builder can't handle it).
        """
        source_table = intent.get("source_table", "Expenses")
        intent_type = intent.get("intent_type", "query_data")
        filters = intent.get("filters", {})
        entities = intent.get("entities", [])
        
        # Build a STRUCTURED query instruction for T5 based on Mistral's understanding
        # This is the key handoff: Mistral brain → T5 SQL converter
        structured_parts = []
        
        # What operation? Mistral tells T5 exactly what computation to do
        if intent_type == "sum":
            structured_parts.append("select sum of expenses")
        elif intent_type == "count":
            structured_parts.append("select count")
        elif intent_type == "average":
            structured_parts.append("select avg of expenses")
        elif intent_type == "min":
            structured_parts.append("select min of expenses")
        elif intent_type == "max":
            structured_parts.append("select max of expenses")
        elif intent_type == "compare":
            structured_parts.append("select category, sum of expenses")
        elif intent_type == "list_categories":
            structured_parts.append("select distinct category")
        elif intent_type == "date_filter":
            structured_parts.append("select all columns")
        else:
            structured_parts.append("select all columns")
        
        structured_parts.append(f"from ai_documents where source_table = '{source_table}'")
        
        # Add filters from Mistral's understanding
        if filters.get("file_name"):
            structured_parts.append(f"and file_name like '%{filters['file_name']}%'")
        if filters.get("project_name"):
            structured_parts.append(f"and project_name like '%{filters['project_name']}%'")
        if filters.get("category") or filters.get("metadata_value"):
            cat = filters.get("category") or filters.get("metadata_value")
            structured_parts.append(f"and category = '{cat}'")
        if filters.get("supplier"):
            structured_parts.append(f"and supplier = '{filters['supplier']}'")
        if filters.get("date"):
            structured_parts.append(f"and date like '%{filters['date']}%'")
        
        # If no specific filters but we have entities, use them
        if not any(filters.get(k) for k in ["file_name", "project_name", "category", "metadata_value", "supplier", "date"]):
            for entity in entities:
                if entity:
                    structured_parts.append(f"and searchable_text like '%{entity}%'")
        
        structured_query = " ".join(structured_parts)
        
        # T5 input format: tables + structured query from Mistral
        t5_input = (
            f"tables: ai_documents (source_table, source_id, file_id, file_name, "
            f"project_id, project_name, searchable_text, metadata, category, expenses, date, description, supplier) | "
            f"query: {structured_query}"
        )
        
        logger.info(f"T5 structured query from Mistral: {structured_query}")
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
        """
        # Known metadata keys that T5 might reference as columns
        metadata_columns = {
            "category": "Category",
            "amount": "Amount",
            "expenses": "Expenses",
            "date": "Date",
            "description": "Description",
            "supplier": "Supplier",
            "method": "Method",
            "name": "Name",
            "remarks": "Remarks",
            "inflow": "Inflow",
            "outflow": "Outflow",
            "balance": "Balance",
        }
        
        result = sql
        
        # Replace column = 'value' with metadata->>'Column' ILIKE '%value%'
        for col_lower, col_proper in metadata_columns.items():
            # Pattern: column = 'value' or column = "value"
            pattern = re.compile(
                rf"\b{col_lower}\b\s*=\s*['\"]([^'\"]+)['\"]",
                re.IGNORECASE
            )
            result = pattern.sub(
                f"metadata->>'{col_proper}' ILIKE '%\\1%'",
                result
            )
            
            # Pattern: column LIKE '%value%'
            pattern2 = re.compile(
                rf"\b{col_lower}\b\s+LIKE\s+",
                re.IGNORECASE
            )
            result = pattern2.sub(f"metadata->>'{col_proper}' ILIKE ", result)
            
            # Pattern: SUM(column) or COUNT(column)
            pattern3 = re.compile(
                rf"(SUM|COUNT|AVG|MIN|MAX)\s*\(\s*{col_lower}\s*\)",
                re.IGNORECASE
            )
            if col_lower in ("amount", "expenses", "inflow", "outflow", "balance"):
                result = pattern3.sub(
                    f"\\1((metadata->>'{col_proper}')::numeric)",
                    result
                )
            else:
                result = pattern3.sub(
                    f"\\1(metadata->>'{col_proper}')",
                    result
                )
        
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
        
        # Add source_table filter if not present
        source_table = intent.get("source_table", "Expenses")
        if "source_table" not in result.lower():
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

        system_msg = SYSTEM_IDENTITY.strip()
        user_msg = (
            f"User asked: \"{query}\"\n"
            f"Database returned: {data_summary}\n\n"
            f"Write a short, helpful response in English that directly answers the question. "
            f"IMPORTANT: The database returned EXACTLY {len(data)} row(s). State this exact count. "
            f"If there are amounts, format them with ₱ sign. Keep it under 3 sentences."
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
