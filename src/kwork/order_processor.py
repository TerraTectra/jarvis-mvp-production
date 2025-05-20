"""Order processing service with LLM integration."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.llm import get_local_llm_service
from src.database.models import SystemLog
from src.database.session import SessionLocal

logger = logging.getLogger(__name__)

class OrderProcessor:
    """Service for processing and filtering Kwork orders."""
    
    def __init__(self):
        """Initialize the order processor with LLM service."""
        # Configure LLM with optimal parameters for order analysis
        self.llm_service = get_local_llm_service(
            temperature=0.2,  # Lower for more deterministic responses
            max_tokens=300,  # Enough for a concise analysis
            n_ctx=2048,      # Context window size
            n_threads=4      # Number of CPU threads to use
        )
        
    async def process_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Kwork order through the LLM filter.
        
        Args:
            order_data: Raw order data from Kwork
            
        Returns:
            Dict containing processing results
        """
        try:
            # Log the incoming order
            self._log_order_received(order_data)
            
            # Analyze the order with LLM
            analysis = await self.llm_service.analyze_order(order_data)
            
            # Log the analysis result
            self._log_analysis_result(order_data, analysis)
            
            # Prepare the result
            result = {
                "order_id": order_data.get("id"),
                "title": order_data.get("title"),
                "is_relevant": analysis.get("is_relevant", False),
                "reasoning": analysis.get("reasoning", "No reasoning provided"),
                "confidence": analysis.get("confidence_score", 0.5),
                "processed_at": datetime.utcnow().isoformat(),
                "source": "kwork",
                "raw_analysis": analysis
            }
            
            # If order is relevant, notify the user
            if result["is_relevant"]:
                await self._notify_relevant_order(result)
                
            return result
            
        except Exception as e:
            logger.error(f"Error processing order {order_data.get('id')}: {e}")
            # In case of error, default to relevant to not miss any orders
            return {
                "order_id": order_data.get("id"),
                "is_relevant": True,
                "error": str(e),
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def _log_order_received(self, order_data: Dict[str, Any]):
        """Log the received order to the database."""
        try:
            with SessionLocal() as session:
                log = SystemLog(
                    level="INFO",
                    message=f"Order received: {order_data.get('title')}",
                    source="order_processor",
                    details={
                        "order_id": order_data.get("id"),
                        "title": order_data.get("title"),
                        "price": order_data.get("price"),
                        "category": order_data.get("category")
                    }
                )
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log order: {e}")
    
    def _log_analysis_result(self, order_data: Dict[str, Any], analysis: Dict[str, Any]):
        """Log the analysis result to the database."""
        try:
            with SessionLocal() as session:
                log = SystemLog(
                    level="INFO",
                    message=f"Order analysis: {order_data.get('title')} - "
                           f"Relevant: {analysis.get('is_relevant')}",
                    source="order_processor",
                    details={
                        "order_id": order_data.get("id"),
                        "is_relevant": analysis.get("is_relevant"),
                        "confidence": analysis.get("confidence_score"),
                        "reasoning": analysis.get("reasoning"),
                        "error": analysis.get("error", False)
                    }
                )
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log analysis result: {e}")
    
    async def _notify_relevant_order(self, result: Dict[str, Any]):
        """Send notification about a relevant order."""
        try:
            # This would be implemented to send a notification via Telegram or another channel
            # For now, just log it
            logger.info(
                f"Relevant order found: {result['title']} "
                f"(Confidence: {result['confidence']:.2f})\n"
                f"Reasoning: {result['reasoning']}"
            )
            
            # Here you would add code to send a notification via Telegram
            # For example:
            # await telegram_service.send_message(
            #     f"🎯 *Relevant Order Found!*\n"
            #     f"*{result['title']}*\n"
            #     f"Confidence: {result['confidence']:.0%}\n\n"
            #     f"*Reasoning:*\n{result['reasoning']}\n\n"
            #     f"[View on Kwork](https://kwork.ru/order/{result['order_id']})"
            # )
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

# Singleton instance
_order_processor = None

def get_order_processor() -> OrderProcessor:
    """Get or create a singleton instance of OrderProcessor."""
    global _order_processor
    if _order_processor is None:
        _order_processor = OrderProcessor()
    return _order_processor
