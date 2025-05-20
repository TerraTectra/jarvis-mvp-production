"""Service initialization and management."""
from typing import Optional, Dict, Any
from src.llm import get_local_llm_service, LocalLLMService
from src.kwork.order_processor import get_order_processor

# Initialize services
llm_service = get_local_llm_service()
order_processor = get_order_processor()

# Flag to track if local LLM is ready for use
local_llm_ready = llm_service is not None and hasattr(llm_service, 'model_loaded') and llm_service.model_loaded

async def generate_response(prompt: str, **kwargs) -> str:
    """
    Generate a response using the local LLM if available.
    
    Args:
        prompt: The input prompt
        **kwargs: Additional arguments to pass to the LLM (max_new_tokens, temperature, top_p)
        
    Returns:
        Generated text response or error message
    """
    if not local_llm_ready or not llm_service:
        return "Извините, сервис генерации временно недоступен."
        
    try:
        # Set default values if not provided
        kwargs.setdefault('max_new_tokens', 50)
        kwargs.setdefault('temperature', 0.7)
        kwargs.setdefault('top_p', 0.9)
        
        return await llm_service.generate_response(prompt, **kwargs)
    except Exception as e:
        return f"Произошла ошибка при генерации ответа: {str(e)}"

def init_services():
    """Initialize all services."""
    # Services are initialized on import, but this function provides
    # a clear entry point for explicit initialization if needed
    pass
