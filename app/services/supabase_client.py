"""
Centralized Supabase Client with Robust Connection Handling.
Features:
- Connection pooling via requests.Session
- Retry logic with exponential backoff
- Timeout handling
- Health monitoring
"""

import time
import json
import requests
from typing import Any, Dict, Optional, Callable
from functools import wraps
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Minimal config for Supabase client."""
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    @classmethod
    def get_supabase_headers(cls) -> dict:
        """Get headers for Supabase REST API requests."""
        return {
            "apikey": cls.SUPABASE_KEY,
            "Authorization": f"Bearer {cls.SUPABASE_KEY}",
            "Content-Type": "application/json",
        }


class SupabaseError(Exception):
    """Custom exception for Supabase-related errors."""
    pass


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, 
                        requests.exceptions.ConnectionError,
                        SupabaseError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        print(f"   ⚠️ Retry {attempt + 1}/{max_retries} after {delay}s: {str(e)[:50]}")
                        time.sleep(delay)
                    else:
                        print(f"   ❌ All {max_retries} retries failed")
            
            raise last_exception
        return wrapper
    return decorator


class SupabaseClient:
    """
    Centralized Supabase client with connection pooling and retry logic.
    Singleton pattern to reuse connections.
    """
    
    _instance = None
    _session: Optional[requests.Session] = None
    _is_healthy: bool = True
    _last_health_check: float = 0
    _health_check_interval: float = 60.0  # seconds
    
    # Default timeout for all requests (connect, read)
    DEFAULT_TIMEOUT = (5, 10)  # (connect timeout, read timeout)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_session()
        return cls._instance
    
    def _init_session(self):
        """Initialize requests session with connection pooling."""
        self._session = requests.Session()
        self._session.headers.update(Config.get_supabase_headers())
        
        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # We handle retries ourselves
        )
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)
    
    @property
    def base_url(self) -> str:
        return f"{Config.SUPABASE_URL}/rest/v1"
    
    @property
    def is_healthy(self) -> bool:
        """Check if Supabase connection is healthy."""
        current_time = time.time()
        if current_time - self._last_health_check > self._health_check_interval:
            self._check_health()
        return self._is_healthy
    
    def _check_health(self):
        """Perform a lightweight health check."""
        try:
            response = self._session.get(
                f"{self.base_url}/Project?select=id&limit=1",
                timeout=(2, 5)
            )
            self._is_healthy = response.status_code == 200
        except Exception:
            self._is_healthy = False
        self._last_health_check = time.time()
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        GET request to Supabase REST API.
        
        Args:
            endpoint: Table name or full endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
        """
        url = f"{self.base_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        
        response = self._session.get(
            url,
            params=params,
            timeout=self.DEFAULT_TIMEOUT
        )
        
        if response.status_code != 200:
            raise SupabaseError(f"GET {endpoint} failed: {response.status_code}")
        
        return response.json()
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def rpc(self, function_name: str, params: Optional[Dict] = None) -> Any:
        """
        Call a Supabase RPC function.
        
        Args:
            function_name: Name of the RPC function
            params: Parameters to pass to the function
            
        Returns:
            JSON response data
        """
        url = f"{self.base_url}/rpc/{function_name}"
        
        response = self._session.post(
            url,
            json=params or {},
            timeout=self.DEFAULT_TIMEOUT
        )
        
        if response.status_code != 200:
            # Try to get error details from response
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = f" - {error_data.get('message', error_data)}"
            except:
                error_detail = f" - {response.text[:200]}"
            
            raise SupabaseError(f"RPC {function_name} failed: {response.status_code}{error_detail}")
        
        return response.json()
    
    def get_safe(self, endpoint: str, params: Optional[Dict] = None, 
                 default: Any = None) -> Any:
        """
        GET request that returns default value on failure instead of raising.
        Use for non-critical operations.
        """
        try:
            return self.get(endpoint, params)
        except Exception as e:
            print(f"   ⚠️ Safe GET failed for {endpoint}: {str(e)[:30]}")
            return default
    
    def rpc_safe(self, function_name: str, params: Optional[Dict] = None,
                 default: Any = None) -> Any:
        """
        RPC call that returns default value on failure instead of raising.
        Use for non-critical operations.
        """
        try:
            return self.rpc(function_name, params)
        except Exception as e:
            print(f"   ⚠️ Safe RPC failed for {function_name}: {str(e)[:30]}")
            return default
    
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def update(self, table: str, record_id: Any, data: Dict) -> Any:
        """
        UPDATE request to Supabase REST API.
        
        Args:
            table: Table name
            record_id: ID of the record to update
            data: Data to update
            
        Returns:
            JSON response data
        """
        url = f"{self.base_url}/{table}?id=eq.{record_id}"
        
        response = self._session.patch(
            url,
            json=data,
            timeout=self.DEFAULT_TIMEOUT
        )
        
        if response.status_code not in (200, 204):
            raise SupabaseError(f"UPDATE {table} failed: {response.status_code}")
        
        return response.json() if response.content else None
    
    def update_safe(self, table: str, record_id: Any, data: Dict, 
                    default: Any = None) -> Any:
        """
        UPDATE request that returns default value on failure instead of raising.
        Use for non-critical operations.
        """
        try:
            return self.update(table, record_id, data)
        except Exception as e:
            print(f"   ⚠️ Safe UPDATE failed for {table}/{record_id}: {str(e)[:30]}")
            return default
    
    def execute_sql(self, sql: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Execute raw SQL query using Supabase RPC.

        Args:
            sql: SQL query to execute
            timeout: Query timeout in seconds

        Returns:
            Dictionary with 'data' key containing query results
        """
        try:
            # Strip trailing semicolons — Supabase RPC rejects them
            sql = sql.strip().rstrip(";").strip()
            
            # Use the rpc() method which already handles retries and errors
            result = self.rpc("execute_sql", {"query": sql})
            
            # Supabase RPC returns the result directly
            return {"data": result if isinstance(result, list) else [result]}

        except Exception as e:
            raise SupabaseError(f"SQL execution failed: {str(e)}")



# Singleton instance
supabase = SupabaseClient()


def get_supabase_client() -> SupabaseClient:
    """Get the Supabase client instance."""
    return supabase


# Backward compatibility alias
def get_supabase() -> SupabaseClient:
    """
    Backward compatibility alias for get_supabase_client().
    DEPRECATED: Use get_supabase_client() instead.
    """
    return supabase
