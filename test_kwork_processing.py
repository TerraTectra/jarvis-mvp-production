"""Test Kwork order processing with a mock LLM service."""
import asyncio
import os
import sys
import logging
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_kwork_processing.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Mock LLM service
class MockLLMService:
    """Mock LLM service for testing purposes."""
    
    def __init__(self):
        self.model_loaded = True
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock response."""
        logger.info("Generating mock response...")
        return """
        Здравствуйте! Я заинтересован в вашем заказе на разработку бота. 
        У меня есть опыт создания подобных решений и я готов приступить к работе. 
        Срок выполнения: 5-7 дней. Буду рад обсудить детали!""".strip()

# Patch the LLM service
sys.modules['src.llm.local_llm'] = type(sys)('src.llm.local_llm')
sys.modules['src.llm.local_llm'].get_local_llm_service = MockLLMService

# Now import the KworkService
from src.kwork.service import KworkService
from src.kwork.models import KworkOrder, KworkFilter, KworkReply
from src.database.session import Base, async_session, engine

# Test data
test_order_data = {
    "id": "test_order_123",
    "title": "Тестовый заказ на разработку бота",
    "description": "Требуется разработать телеграм-бота для автоматизации ответов на заказы. Бот должен уметь анализировать заказы и генерировать персонализированные ответы.",
    "price": {
        "amount": 5000,
        "currency": "RUB"
    },
    "category": "Программирование",
    "subcategory": "Боты",
    "status": "active",
    "views": 10,
    "replies_count": 3,
    "published_at": "2025-05-20T10:00:00Z",
    "is_remote": True,
    "is_premium": False,
    "is_safe_deal": True,
    "is_urgent": False,
    "is_budget_flexible": True,
    "raw_data": {
        "id": "test_order_123",
        "title": "Тестовый заказ на разработку бота",
        "description": "Требуется разработать телеграм-бота для автоматизации ответов на заказы.",
        "price": {
            "amount": 5000,
            "currency": "RUB"
        },
        "category": "Программирование",
        "subcategory": "Боты",
        "status": "active",
        "views": 10,
        "replies_count": 3,
        "published_at": "2025-05-20T10:00:00Z"
    }
}

async def init_db():
    """Initialize the database with test data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        # Create test filter
        test_filter = KworkFilter(
            name="Test Bot Filter",
            keywords=["бот", "телеграм", "автоматизация"],
            categories=[1, 2, 3],
            min_price=1000,
            max_price=10000,
            is_active=True
        )
        session.add(test_filter)
        
        # Create test order
        order = KworkOrder(
            id=test_order_data["id"],  # Используем id вместо order_id
            title=test_order_data["title"],
            description=test_order_data["description"],
            price=test_order_data["price"],  # Передаем словарь с ценой
            category=test_order_data["category"],
            status="active",  # Добавляем обязательное поле status
            views=test_order_data["views"],
            replies_count=test_order_data["replies_count"],
            published_at=test_order_data["published_at"],
            raw_data=test_order_data  # Сохраняем все исходные данные
        )
        session.add(order)
        
        await session.commit()
        return test_filter.id

async def test_order_processing():
    """Test the order processing pipeline."""
    print("\n=== [TEST] Starting order processing test ===\n")
    
    try:
        # Initialize database
        print("[INIT] Initializing database...")
        filter_id = await init_db()
        print(f"[OK] Database initialized with test data. Filter ID: {filter_id}")
        
        # Create service instance
        print("\n[INFO] Creating KworkService instance...")
        service = KworkService()
        
        # Process the filter
        print("\n[PROCESS] Processing filter...")
        async with async_session() as session:
            # Get the test filter
            print(f"[INFO] Fetching test filter with ID: {filter_id}")
            result = await session.execute(
                select(KworkFilter).where(KworkFilter.id == filter_id)
            )
            test_filter = result.scalars().first()
            
            if not test_filter:
                print("[ERROR] Test filter not found!")
                return
            
            print(f"[INFO] Processing filter: {test_filter.name}")
            print(f"[INFO] Filter criteria: {test_filter.keywords} in categories {test_filter.categories}")
            
            # Process the filter
            print("\n[INFO] Calling _process_filter...")
            await service._process_filter(session, test_filter)
            print("[OK] _process_filter completed")
            
            # Commit the transaction to ensure all changes are saved
            await session.commit()
            
            # Start a new transaction for reading
            await session.begin()
            
            # Check if reply was created
            print("\n[INFO] Checking for generated replies...")
            result = await session.execute(
                select(KworkOrder)
                .where(KworkOrder.id == test_order_data["id"])
                .options(selectinload(KworkOrder.replies))
            )
            order = result.scalars().first()
            
            if not order:
                print("[ERROR] Test order not found after processing!")
                return
                
            print(f"[INFO] Order status: {order.status}, Replies count: {len(order.replies) if order.replies else 0}")
            
            if order.replies:
                print("\n[SUCCESS] Test passed: Reply was generated successfully!")
                print(f"[REPLY] Text: {order.replies[0].message}")
                print(f"[INFO] Created at: {order.replies[0].created_at}")
            else:
                print("\n[ERROR] Test failed: No reply was generated!")
                # Check if there are any orders in the database
                all_orders = await session.execute(select(KworkOrder))
                orders = all_orders.scalars().all()
                print(f"Total orders in database: {len(orders)}")
                if orders:
                    print(f"First order ID: {orders[0].id}")
                    print(f"First order replies: {orders[0].replies}")
                
            # Print summary
            print("\n=== [SUMMARY] Test Summary ===")
            print(f"- Orders processed: 1")
            print(f"- Replies generated: {len(order.replies) if order.replies else 0}")
            print(f"- Errors: {'None' if order.replies else 'Reply not generated'}")
            
            # Log the complete order data for debugging
            print("\n=== [ORDER] Order data ===")
            print(f"ID: {order.id}")
            print(f"Title: {order.title}")
            print(f"Description: {order.description[:100]}..." if order.description else "No description")
            print(f"Price: {order.price}")
            print(f"Status: {order.status}")
            if order.replies:
                for i, reply in enumerate(order.replies, 1):
                    print(f"\n[REPLY] #{i}:")
                    print(f"   Message: {reply.message[:100]}..." if len(reply.message) > 100 else f"   Message: {reply.message}")
                    print(f"   Created at: {reply.created_at}")
            else:
                print("No replies found for this order")
    
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n=== [DONE] Test completed ===\n")

if __name__ == "__main__":
    # Set environment variables
    os.environ["DRY_RUN"] = "true"
    os.environ["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN", "test_token")
    os.environ["TELEGRAM_ADMIN_ID"] = os.getenv("TELEGRAM_ADMIN_ID", "123456789")
    
    # Run the test
    asyncio.run(test_order_processing())
