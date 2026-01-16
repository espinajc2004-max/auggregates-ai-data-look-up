"""
Context Manager for Mistral queries.
Manages conversation history and context across queries.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from app.services.conversation_db import ConversationDatabaseService as ConversationDB


class MistralContextManager:
    """Manages conversation context for Mistral queries."""
    
    def __init__(
        self,
        conversation_db: ConversationDB,
        max_history_length: int = 5,
        max_tokens: int = 2000
    ):
        """
        Initialize context manager.
        
        Args:
            conversation_db: Database for storing conversations
            max_history_length: Maximum number of exchanges to keep
            max_tokens: Maximum tokens for context (approximate)
        """
        self.conversation_db = conversation_db
        self.max_history_length = max_history_length
        self.max_tokens = max_tokens
    
    async def get_context(
        self,
        conversation_id: str,
        current_query: str
    ) -> List[Dict]:
        """
        Get relevant conversation context.
        
        Args:
            conversation_id: Conversation identifier
            current_query: Current user query
            
        Returns:
            List of previous exchanges with queries and results
        """
        # Get conversation history from database
        conversation = await self.conversation_db.get_conversation(conversation_id)
        
        if not conversation or not conversation.get("exchanges"):
            return []
        
        exchanges = conversation["exchanges"]
        
        # Get recent exchanges
        recent_exchanges = exchanges[-self.max_history_length:]
        
        # Format exchanges for context
        context = []
        for exchange in recent_exchanges:
            context.append({
                "query": exchange.get("query", ""),
                "sql": exchange.get("sql", ""),
                "result_summary": self._summarize_results(exchange.get("results", []))
            })
        
        # Truncate if needed to fit token limit
        context = self._truncate_context(context, self.max_tokens)
        
        return context
    
    async def add_exchange(
        self,
        conversation_id: str,
        query: str,
        sql: str,
        results: Any
    ) -> None:
        """
        Add query exchange to conversation history.
        
        Args:
            conversation_id: Conversation identifier
            query: User's natural language query
            sql: Generated SQL query
            results: Query execution results
        """
        exchange = {
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "sql": sql,
            "results": results,
            "result_summary": self._summarize_results(results)
        }
        
        await self.conversation_db.add_exchange(conversation_id, exchange)
    
    def _summarize_results(self, results: Any) -> str:
        """
        Create a summary of query results.
        
        Args:
            results: Query execution results
            
        Returns:
            Summary string
        """
        if not results:
            return "No results found"
        
        if isinstance(results, list):
            count = len(results)
            if count == 0:
                return "No results found"
            elif count == 1:
                return "Found 1 result"
            else:
                return f"Found {count} results"
        
        return "Results returned"
    
    def _truncate_context(
        self,
        context: List[Dict],
        max_tokens: int
    ) -> List[Dict]:
        """
        Truncate context to fit within token limit.
        Uses rough approximation: 1 token ≈ 4 characters.
        
        Args:
            context: List of exchanges
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated context list
        """
        max_chars = max_tokens * 4
        total_chars = 0
        truncated = []
        
        # Add exchanges from most recent backwards
        for exchange in reversed(context):
            exchange_text = (
                exchange.get("query", "") +
                exchange.get("sql", "") +
                exchange.get("result_summary", "")
            )
            exchange_chars = len(exchange_text)
            
            if total_chars + exchange_chars > max_chars:
                break
            
            truncated.insert(0, exchange)
            total_chars += exchange_chars
        
        return truncated
    
    async def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            conversation_id: Conversation identifier
        """
        await self.conversation_db.clear_conversation(conversation_id)
