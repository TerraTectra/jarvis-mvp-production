"""LLM module for local language model integration."""
# Use mock implementation for testing
from .local_llm_mock import LocalLLMService, get_local_llm_service

__all__ = ["LocalLLMService", "get_local_llm_service"]
