"""Test script for LLM integration with Kwork orders."""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.kwork.service import KworkService
from src.kwork.order_processor import get_order_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_llm_integration.log')
    ]
)
logger = logging.getLogger(__name__)

async def process_test_orders():
    """Process test orders through the LLM processor."""
    # Load test orders
    test_orders_path = os.path.join(project_root, 'tests', 'test_orders.json')
    with open(test_orders_path, 'r', encoding='utf-8') as f:
        test_orders = json.load(f)
    
    logger.info(f"Loaded {len(test_orders)} test orders")
    
    # Initialize order processor
    order_processor = get_order_processor()
    
    # Process each test order
    for order_data in test_orders:
        try:
            logger.info("=" * 80)
            logger.info(f"Processing order: {order_data['name']}")
            logger.info(f"Description: {order_data['description'][:100]}...")
            
            # Prepare order info
            order_info = {
                "id": str(order_data["id"]),
                "title": order_data["name"],
                "description": order_data["description"],
                "price": order_data["price"],
                "category": order_data["category"]["name"],
                "filter_id": "test_filter_123"
            }
            
            # Process with LLM
            result = await order_processor.process_order(order_info)
            
            # Log results
            logger.info(f"✅ LLM Decision: {'APPROVED' if result.get('is_relevant') else 'REJECTED'}")
            logger.info(f"🤖 Reasoning: {result.get('reasoning', 'No reasoning provided')}")
            logger.info(f"🔍 Confidence: {result.get('confidence', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error processing order {order_data.get('id')}: {e}", exc_info=True)
        finally:
            logger.info("-" * 80)
            await asyncio.sleep(1)  # Small delay between orders

async def main():
    """Main test function."""
    logger.info("Starting LLM integration test...")
    
    try:
        await process_test_orders()
        logger.info("✅ Test completed successfully!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
    finally:
        logger.info("Exiting...")

if __name__ == "__main__":
    asyncio.run(main())
