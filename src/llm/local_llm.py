"""Local LLM service for order filtering and analysis."""
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import os

# Import llama-cpp-python only when needed
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logging.warning("llama-cpp-python not installed. Install with: pip install llama-cpp-python")

logger = logging.getLogger(__name__)

class LocalLLMService:
    """Service for local LLM-based order filtering and analysis."""
    
    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 2048, 
                 temperature: float = 0.3, max_tokens: int = 500):
        """
        Initialize Local LLM service.
        
        Args:
            model_path: Path to the GGUF model file
            n_ctx: Context window size
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("llama-cpp-python is required for local LLM inference")
            
        if model_path is None:
            # Default model path
            model_path = "models/mistral/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
            
        self.model_path = Path(model_path)
        self.model_loaded = False
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.temperature = max(0.1, min(1.0, temperature))  # Clamp between 0.1 and 1.0
        self.max_tokens = max(100, min(1000, max_tokens))  # Clamp between 100 and 1000
        self.llm = None
        
        try:
            self._load_model()
            self.model_loaded = True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model_loaded = False
            # Don't raise here to allow fallback behavior
    
    def _load_model(self):
        """Load the LLM model with GPU acceleration."""
        logger.info(f"Loading model from {self.model_path}...")
        try:
            self.llm = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_batch=512,
                n_gpu_layers=-1,  # Use all layers on GPU
                verbose=False
            )
            logger.info("Model loaded successfully with GPU acceleration")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            # Try fallback to CPU if GPU fails
            try:
                logger.warning("Falling back to CPU mode...")
                self.llm = Llama(
                    model_path=str(self.model_path),
                    n_ctx=self.n_ctx,
                    n_batch=512,
                    n_gpu_layers=0,  # CPU mode
                    verbose=False
                )
                logger.info("Model loaded in CPU mode")
            except Exception as e2:
                logger.error(f"Failed to load model in CPU mode: {e2}")
                raise
    
    async def analyze_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze order using local LLM to determine if it's a good fit.
        
        Args:
            order_data: Dictionary containing order details
            
        Returns:
            Dict with analysis results including 'is_relevant' and 'reasoning'
        """
        # Fallback response if model is not loaded
        if not self.model_loaded or not self.llm:
            logger.warning("LLM model not loaded, using fallback analysis")
            return self._fallback_analysis(order_data)
            
        try:
            # Prepare the prompt
            prompt = self._prepare_prompt(order_data)
            
            # Generate response with configurable parameters
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": "You are an expert order analyzer. "
                                               "Your task is to determine if an order is relevant "
                                               "based on the provided criteria. Be concise and professional."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=["</s>"]
            )
            
            # Parse the response
            analysis = self._parse_llm_response(response['choices'][0]['message']['content'])
            
            # Log analysis result
            decision = "✅ APPROVED" if analysis.get('is_relevant') else "❌ REJECTED"
            logger.info(f"Order analysis complete. Decision: {decision}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing order with local LLM: {e}")
            return self._fallback_analysis(order_data, str(e))
    
    def _fallback_analysis(self, order_data: Dict[str, Any], error: str = None) -> Dict[str, Any]:
        """Fallback analysis when LLM is not available."""
        fallback_reason = ""
        if error:
            fallback_reason = f"LLM Error ({error}). Using fallback analysis. "
        
        # Simple keyword-based fallback
        title = order_data.get('title', '').lower()
        description = order_data.get('description', '').lower()
        
        # Keywords that indicate relevance
        design_keywords = ['дизайн', 'логотип', 'баннер', 'обложк', 'афиш', 'лого', 'бренд']
        
        # Check for design-related keywords
        is_relevant = any(keyword in title or keyword in description 
                         for keyword in design_keywords)
        
        status = "relevant" if is_relevant else "not relevant"
        reason = f"{fallback_reason}Fallback analysis: {status} based on keywords"
        
        return {
            "is_relevant": is_relevant,
            "reasoning": reason,
            "confidence": 0.7 if is_relevant else 0.3,
            "used_fallback": True
        }
    
    def _prepare_prompt(self, order_data: Dict[str, Any]) -> str:
        """Prepare the prompt for order analysis."""
        # Extract relevant fields with fallbacks
        title = order_data.get('title', 'No title')
        description = order_data.get('description', 'No description')
        price = order_data.get('price', 0)
        
        prompt = (
            "Analyze this order and determine if it's a good fit based on the following criteria:\n"
            "1. Clear requirements\n"
            "2. Reasonable budget\n"
            "3. Relevant to our expertise\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Price: {price} RUB\n\n"
            "Provide a JSON response with 'is_relevant' (true/false) and 'reasoning' (string)."
        )
        return prompt
    
    async def generate_response(self, prompt: str, max_new_tokens: int = 50, 
                            temperature: float = 0.7, top_p: float = 0.9) -> str:
        """
        Generate a response using the local LLM.
        
        Args:
            prompt: The input prompt
            max_new_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated text response
        """
        if not self.model_loaded or not self.llm:
            logger.warning("LLM model not loaded, cannot generate response")
            return "Извините, сервис генерации временно недоступен."
            
        try:
            # Prepare the prompt with system message
            full_prompt = f"Ты — помощник Министра. {prompt}"
            
            # Generate response
            response = self.llm(
                full_prompt,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=["\n\n", "###"],
                echo=False
            )
            
            # Extract the generated text
            if isinstance(response, dict) and 'choices' in response and len(response['choices']) > 0:
                return response['choices'][0]['text'].strip()
            return "Не удалось сгенерировать ответ."
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return f"Произошла ошибка при генерации ответа: {str(e)}"
    
    @staticmethod
    def _parse_llm_response(response_text: str) -> Dict[str, Any]:
        """Parse the LLM response into a structured format."""
        try:
            # Simple JSON extraction (can be improved with regex or proper JSON parsing)
            import json
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            json_str = response_text[start:end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {
                "is_relevant": True,  # Default to relevant to not miss orders
                "reasoning": f"Error parsing response: {str(e)}",
                "error": True
            }

# Singleton instance
_local_llm_service = None

def get_local_llm_service(temperature: float = 0.3, max_tokens: int = 500, 
                       n_ctx: int = 2048) -> LocalLLMService:
    """
    Get or create a singleton instance of LocalLLMService.
    
    Args:
        temperature: Controls randomness (0.0 to 1.0)
        max_tokens: Maximum number of tokens to generate
        n_ctx: Context window size
        
    Returns:
        LocalLLMService instance
    """
    global _local_llm_service
    if _local_llm_service is None:
        _local_llm_service = LocalLLMService(
            temperature=temperature,
            max_tokens=max_tokens,
            n_ctx=n_ctx
        )
    return _local_llm_service
