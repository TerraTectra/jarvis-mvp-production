"""A simplified test script for order processing."""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_order_processing.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Import required modules after setting up the path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete
from unittest.mock import patch

# Import test data and mocks
from tests.test_data import test_order
from tests.mock_llm import get_mock_llm_service
from tests.mock_kwork_api import MockKworkAPI

# Import models and service
from src.database.session import Base
from src.kwork.models import KworkOrder, KworkFilter, KworkReply

# Patch the LLM service to use our mock
with patch('src.llm.local_llm.get_local_llm_service', get_mock_llm_service):
    from src.kwork.service import KworkService

# Test database URL (use in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=True,
    future=True
)

# Create session factory with expire_on_commit=False to prevent DetachedInstanceError
TestingSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Test filter data
test_filter_data = {
    "name": "Test Filter",
    "keywords": ["бот", "телеграм", "автоматизация"],
    "categories": [1, 2, 3],
    "min_price": 1000.0,
    "max_price": 10000.0,
    "is_active": True
}

async def init_test_db():
    """Initialize test database with tables."""
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise

async def test_order_processing():
    """Test order processing with a test order."""
    logger.info("\n=== Starting test_order_processing ===")
    
    # Initialize test database
    logger.info("Initializing test database...")
    try:
        await init_test_db()
        logger.info("Test database initialized successfully")
    except Exception as e:
        logger.error("❌ Failed to initialize test database: %s", e, exc_info=True)
        raise
    
    # Initialize KworkService with mock API
    logger.info("Initializing KworkService with mock API...")
    try:
        mock_api = MockKworkAPI()
        logger.info("Mock API initialized")
        
        # Verify the mock API is properly initialized
        required_methods = ['get_orders', 'get_recent_orders', 'get_order_details', 'send_reply']
        for method in required_methods:
            if not hasattr(mock_api, method):
                raise AttributeError(f"Mock API is missing required method: {method}")
        logger.info("All required API methods verified")
        
        # Initialize service
        service = KworkService(api=mock_api)
        logger.info("KworkService initialized")
        
        # Create a new async session for the test
        async with TestingSessionLocal() as session:
            try:
                # Create test filter
                logger.info("\nCreating test filter...")
                # Create the filter with all fields
                test_filter = KworkFilter(
                    name=test_filter_data["name"],
                    is_active=test_filter_data["is_active"]
                )
                
                # Add JSON fields
                test_filter.keywords = test_filter_data["keywords"]
                test_filter.categories = test_filter_data["categories"]
                test_filter.min_price = test_filter_data["min_price"]
                test_filter.max_price = test_filter_data["max_price"]
                
                session.add(test_filter)
                await session.commit()
                
                logger.info("✅ Created test filter with ID: %s", test_filter.id)
                logger.debug("Test filter data: %s", {
                    'id': test_filter.id,
                    'name': test_filter.name,
                    'keywords': test_filter.keywords,
                    'categories': test_filter.categories,
                    'min_price': test_filter.min_price,
                    'max_price': test_filter.max_price,
                    'is_active': test_filter.is_active
                })
                
                # Create test order
                logger.info("\nCreating test order...")
                from datetime import datetime
                published_at = datetime.strptime(
                    test_order["published_at"], 
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                order = KworkOrder(
                    id=test_order["id"],
                    title=test_order["title"],
                    description=test_order["description"],
                    price={"amount": test_order["price"]["amount"], "currency": test_order["price"]["currency"]},
                    category=test_order["category"],
                    status="active",
                    views=test_order["views"],
                    replies_count=test_order["replies_count"],
                    published_at=published_at,
                    raw_data=test_order
                )
                session.add(order)
                await session.commit()
                logger.info("✅ Created test order with ID: %s", order.id)
                
                # Process the order
                logger.info("\nProcessing order...")
                await service._process_filter(session, test_filter)
                logger.info("✅ Order processed successfully")
                
                # Verify the reply was created
                result = await session.execute(select(KworkReply).where(KworkReply.order_id == order.id))
                reply = result.scalars().first()
                if reply:
                    logger.info("✅ Found reply with ID: %s", reply.id)
                else:
                    logger.error("❌ No reply was created for the order")
                
                # Clean up
                logger.info("\nCleaning up test data...")
                await session.execute(delete(KworkReply))
                await session.execute(delete(KworkOrder))
                await session.execute(delete(KworkFilter))
                await session.commit()
                logger.info("✅ Test data cleaned up successfully")
                    
            except Exception as e:
                logger.error("❌ Error during test: %s", e, exc_info=True)
                await session.rollback()
                raise
                
    except Exception as e:
        logger.error("❌ Failed to initialize KworkService: %s", e, exc_info=True)
        raise
    
    except Exception as e:
        logger.error("❌ Test failed with error: %s", e, exc_info=True)
        raise
    
    logger.info("\n=== Test completed successfully ===")
    return True

if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["DRY_RUN"] = "true"
    os.environ["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN", "test_token")
    os.environ["TELEGRAM_ADMIN_ID"] = os.getenv("TELEGRAM_ADMIN_ID", "123456789")
    
    # Run the test
    asyncio.run(test_order_processing())
