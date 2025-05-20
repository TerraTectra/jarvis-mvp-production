"""
Test script for Kwork API integration.
"""
import os
import asyncio
import logging
from dotenv import load_dotenv
from src.kwork.api import KworkAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Test Kwork API integration."""
    # Load environment variables
    load_dotenv()
    
    # Check if token is set
    token = os.getenv("KWORK_TOKEN")
    if not token or token == "your_kwork_token_here":
        logger.error("KWORK_TOKEN is not set in .env file")
        return
    
    # Initialize API client
    try:
        async with KworkAPI(token) as api:
            logger.info("Fetching recent orders...")
            
            # Test fetching recent orders
            try:
                orders_data = await api.get_recent_orders(per_page=5)
                orders = orders_data.get("data", {}).get("list", [])
                
                if not orders:
                    logger.warning("No orders found")
                    return
                
                logger.info(f"Found {len(orders)} orders")
                
                # Display basic info about each order
                for order in orders:
                    order_id = order.get("id")
                    logger.info(
                        f"Order ID: {order_id}, "
                        f"Title: {order.get('name', 'N/A')}, "
                        f"Price: {order.get('price', {}).get('amount', 'N/A')} {order.get('price', {}).get('currency', '')}"
                    )
                    
                    # Test getting order details
                    try:
                        details = await api.get_order_details(order_id)
                        if details:
                            logger.info(f"  Description: {details.get('description', 'N/A')[:100]}...")
                    except Exception as e:
                        logger.error(f"  Error getting details: {e}")
                
                # Test sending a reply (commented out to prevent accidental replies)
                # reply = await api.send_reply(
                #     order_id=orders[0]["id"],
                #     message="Тестовый отклик от Jarvis MVP",
                #     price=1000,
                #     days=3
                # )
                # logger.info(f"Reply sent: {reply}")
                
            except Exception as e:
                logger.error(f"Error during API calls: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"Failed to initialize Kwork API: {e}", exc_info=True)

if __name__ == "__main__":
    ashto.run(main())
