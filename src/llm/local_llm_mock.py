"""Mock LLM service for testing."""
from typing import Optional, Dict, Any

class LocalLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self, model_path: Optional[str] = None, **kwargs):
        self.model_loaded = True
        self.model_path = model_path or "mock_model"
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock response."""
        return """
        Здравствуйте! Я заинтересован в вашем заказе на разработку бота. 
        У меня есть опыт создания подобных решений и я готов приступить к работе. 
        Срок выполнения: 5-7 дней. Буду рад обсудить детали!""".strip()

def get_local_llm_service(**kwargs) -> LocalLLMService:
    """Get a mock LLM service instance.
    
    Args:
        **kwargs: Additional arguments (ignored in mock)
        
    Returns:
        LocalLLMService: Mock LLM service instance
    """
    return LocalLLMService()
