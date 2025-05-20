"""Mock LLM service for testing."""
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class MockLLMService:
    """Mock LLM service for testing purposes."""
    
    def __init__(self, **kwargs):
        self.model_loaded = True
        self.temperature = kwargs.get('temperature', 0.2)
        self.max_tokens = kwargs.get('max_tokens', 300)
        self.n_ctx = kwargs.get('n_ctx', 2048)
        self.n_threads = kwargs.get('n_threads', 4)
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock response."""
        logger.debug(f"Generating response for prompt: {prompt[:100]}...")
        return """
        Здравствуйте! Я заинтересован в вашем заказе на разработку бота. 
        У меня есть опыт создания подобных решений и я готов приступить к работе. 
        Срок выполнения: 5-7 дней. Буду рад обсудить детали!""".strip()
    
    async def analyze_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze an order and determine if it's relevant."""
        logger.debug(f"Analyzing order: {order_data.get('id')} - {order_data.get('title')}")
        
        # Default to relevant for testing purposes
        is_relevant = True
        reasoning = "Order matches filter criteria"
        
        return {
            "is_relevant": is_relevant,
            "reasoning": reasoning,
            "confidence_score": 0.95,
            "order_id": order_data.get('id'),
            "source": "kwork"
        }

def get_mock_llm_service(**kwargs) -> MockLLMService:
    """Get a mock LLM service instance."""
    return MockLLMService(**kwargs)
