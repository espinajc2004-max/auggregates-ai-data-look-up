"""
Configuration module for Mistral 7B service.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MistralConfig:
    """Configuration for Mistral 7B service."""
    
    # Model Configuration
    model_name: str = "mistralai/Mistral-7B-Instruct-v0.2"
    quantization: str = "4bit"
    device: str = "cpu"
    device_map: str = "auto"
    
    # Generation Parameters
    temperature: float = 0.1  # Low for deterministic SQL
    max_new_tokens: int = 512
    top_p: float = 0.95
    top_k: int = 50
    do_sample: bool = True
    
    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Context Configuration
    max_conversation_history: int = 5
    max_context_tokens: int = 2000
    
    # Performance Configuration
    batch_size: int = 1
    max_concurrent_requests: int = 3
    
    # Timeout Configuration
    generation_timeout: int = 300  # seconds (5 min for CPU inference)
    
    @classmethod
    def from_env(cls) -> "MistralConfig":
        """Load configuration from environment variables."""
        return cls(
            model_name=os.getenv("MISTRAL_MODEL", cls.model_name),
            quantization=os.getenv("MISTRAL_QUANTIZATION", cls.quantization),
            temperature=float(os.getenv("MISTRAL_TEMPERATURE", str(cls.temperature))),
            max_new_tokens=int(os.getenv("MISTRAL_MAX_TOKENS", str(cls.max_new_tokens))),
            max_retries=int(os.getenv("MISTRAL_MAX_RETRIES", str(cls.max_retries))),
            generation_timeout=int(os.getenv("MISTRAL_TIMEOUT", str(cls.generation_timeout))),
        )


@dataclass
class ModelLoadConfig:
    """Configuration for loading Mistral model."""
    
    model_name: str
    quantization: str
    device: str
    device_map: str
    torch_dtype: str = "auto"
    trust_remote_code: bool = False
    
    def to_transformers_kwargs(self) -> dict:
        """Convert to kwargs for transformers.AutoModelForCausalLM.from_pretrained()."""
        kwargs = {
            "device_map": self.device_map,
            "torch_dtype": self.torch_dtype,
            "trust_remote_code": self.trust_remote_code,
        }
        
        if self.quantization == "8bit":
            kwargs["load_in_8bit"] = True
        elif self.quantization == "4bit":
            kwargs["load_in_4bit"] = True
        
        return kwargs
