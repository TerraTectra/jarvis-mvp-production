"""Test script for order processing."""
import asyncio
import os
import sys
import logging
from datetime import datetime
from unittest.mock import patch
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_order_processing.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database.session import Base, get_db
from src.kwork.models import KworkOrder, KworkFilter, KworkReply
from .test_data import test_order
from .mock_llm import get_mock_llm_service
from .mock_kwork_api import MockKworkAPI

# Patch the LLM service to use our mock
with patch('src.llm.local_llm.get_local_llm_service', get_mock_llm_service):
    from src.kwork.service import KworkService

# Test database URL (use in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine and session
engine = create_async_engine(
    TEST_DATABASE_URL, 
    echo=True,
    future=True  # Enable SQLAlchemy 2.0 style
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
    "min_price": 1000,
    "max_price": 10000,
    "is_active": True
}

async def init_test_db():
    """Initialize test database with tables."""
    async with engine.begin() as conn:
        # Drop all tables first to ensure a clean state
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    # Explicitly dispose the engine to close all connections
    await engine.dispose()

async def create_test_data():
    """Create test data in the database."""
    async with TestingSessionLocal() as session:
        # Create test filter
        test_filter = KworkFilter(**test_filter_data)
        session.add(test_filter)
        await session.commit()
        
        # Create test order
        order = KworkOrder(
            id=test_order["id"],  # Changed from order_id to id
            title=test_order["title"],
            description=test_order["description"],
            price={"amount": test_order["price"]["amount"], "currency": test_order["price"]["currency"]},
            category=test_order["category"],
            status="active",  # Add required status field
            views=test_order["views"],
            replies_count=test_order["replies_count"],
            published_at=datetime.fromisoformat(test_order["published_at"].replace('Z', '+00:00')),
            raw_data=test_order  # Store the raw data as required by the model
        )
        session.add(order)
        await session.commit()

async def test_order_processing():
    """Test order processing with a test order."""
    print("\n=== Starting test_order_processing ===")
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_order_processing.log', mode='w', encoding='utf-8')
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Python version: %s", sys.version)
    logger.info("Current working directory: %s", os.getcwd())
    logger.info("Test database URL: %s", TEST_DATABASE_URL)
    
    # Initialize test database
    logger.info("Initializing test database...")
    await init_test_db()
    logger.info("Test database initialized successfully")
    
    # Initialize KworkService with mock API
    logger.info("Initializing KworkService with mock API...")
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
        # Begin a transaction
        async with session.begin():
            try:
                # Create test filter
                logger.info("\nCreating test filter...")
                test_filter = KworkFilter(**test_filter_data)
                session.add(test_filter)
                await session.commit()
                logger.info("✅ Created test filter with ID: %s", test_filter.id)
                logger.debug("Test filter data: %s", test_filter.__dict__)
            except Exception as e:
                logger.error("Failed to create test filter: %s", e, exc_info=True)
                raise
            
            # Create a new async session for the test
            async with TestingSessionLocal() as session:
                # Begin a transaction
                async with session.begin():
                    try:
                        # Create test filter
                        logger.info("\nCreating test filter...")
                        test_filter = KworkFilter(**test_filter_data)
                        session.add(test_filter)
                        await session.commit()
                        logger.info("✅ Created test filter with ID: %s", test_filter.id)
                        logger.debug("Test filter data: %s", test_filter.__dict__)
                except Exception as e:
                    logger.error("Failed to create test filter: %s", e, exc_info=True)
                    raise
                
                # Verify the test order data
                logger.info("\nTest order data:")
                logger.info("ID: %s", test_order.get('id'))
                logger.info("Title: %s", test_order.get('title', 'No title'))
                logger.info("Description: %s", 
                            test_order.get('description', 'No description')[:100] + '...' 
                            if test_order.get('description') else "No description")
                
                # Log price information if available
                if 'price' in test_order and isinstance(test_order['price'], dict):
                    price = test_order['price']
                    logger.info("Price: %s %s", 
                                price.get('amount', 'N/A'), 
                                price.get('currency', ''))
                else:
                    logger.warning("No valid price information in test order data")
                
                # Mock the get_orders method to return our test order
                logger.info("\nSetting up mock for get_orders...")
                with patch.object(mock_api, 'get_orders', return_value=[test_order]) as mock_get_orders:
                    logger.info("✅ Successfully patched get_orders")
                    logger.info("\nCalling _process_filter...")
                    # Process the filter - this should fetch the test order and process it
                    try:
                        await service._process_filter(session, test_filter)
                        logger.info("✅ _process_filter completed successfully")
                    except Exception as e:
                        logger.error(f"❌ Error in _process_filter: {e}", exc_info=True)
                        raise
                    
                    # Verify the mock was called as expected
                    logger.info("\nVerifying mock API calls...")
                    try:
                        mock_get_orders.assert_called_once()
                        logger.info("✅ get_orders was called as expected")
                    except AssertionError as e:
                        logger.error(f"❌ get_orders was not called as expected: {e}")
                        raise
                    
                    # Commit the transaction to save changes
                    logger.info("Committing transaction...")
                    await session.commit()
                    logger.info("✅ Transaction committed successfully")
            
                    # Check if order was created
                    logger.info("\nChecking if order was created in the database...")
                    try:
                        result = await session.execute(
                            select(KworkOrder)
                            .where(KworkOrder.id == test_order["id"])
                            .options(selectinload(KworkOrder.replies))  # Eager load the replies
                        )
                        order = result.scalars().first()
                        
                        if order:
                            logger.info(f"✅ Found order with ID: {order.id}")
                            logger.info(f"Order status: {getattr(order, 'status', 'N/A')}")
                            logger.info(f"Order replies count: {len(order.replies) if hasattr(order, 'replies') else 0}")
                            
                            # Log order details for debugging
                            logger.debug(f"Order details: {order.__dict__}")
                        else:
                            logger.error("❌ Order not found in database")
                            
                            # Check if there are any orders in the database
                            all_orders = await session.execute(select(KworkOrder))
                            orders = all_orders.scalars().all()
                            logger.info(f"Total orders in database: {len(orders)}")
                            for i, o in enumerate(orders, 1):
                                logger.info(f"  Order {i}: ID={o.id}, Title={getattr(o, 'title', 'N/A')}")
                    except Exception as e:
                        logger.error(f"❌ Error checking for order: {e}", exc_info=True)
                        raise
            
                    # Also check the replies table directly
                    logger.info("\nChecking replies table directly...")
                    replies_result = await session.execute(select(KworkReply))
                    all_replies = replies_result.scalars().all()
                    
                    logger.info("\n=== Test Results ===")
                    logger.info(f"Order found: {'✅' if order else '❌'}")
                    
                    if order:
                        logger.info(f"Order ID: {order.id}")
                        logger.info(f"Order status: {getattr(order, 'status', 'N/A')}")
                        logger.info(f"Order replies (from relationship): {len(order.replies) if hasattr(order, 'replies') else 0}")
                    else:
                        logger.warning("Order ID: N/A")
                            
                    logger.info(f"Total replies in database: {len(all_replies)}")
                    
                    if all_replies:
                        logger.info("\n=== Reply Details ===")
                        for i, reply in enumerate(all_replies, 1):
                            logger.info(f"Reply {i}:")
                            logger.info(f"  ID: {reply.id}")
                            logger.info(f"  Order ID: {reply.order_id}")
                            logger.info(f"  Status: {getattr(reply, 'status', 'N/A')}")
                            logger.info(f"  Message: {reply.message[:100]}..." if hasattr(reply, 'message') and reply.message else "  No message")
                    
                    if order and hasattr(order, 'replies') and order.replies:
                        logger.info("\n✅ Test passed: Reply was generated successfully!")
                        logger.info(f"📝 Reply text: {order.replies[0].message[:200]}...")
                    else:
                        logger.error("\n❌ Test failed: No reply was generated!")
                        
                        # Additional debug info
                        if not order:
                            logger.error("  - Order was not created in the database")
                        elif not hasattr(order, 'replies') or not order.replies:
                            logger.error(f"  - Order exists but has no replies (replies attribute: {hasattr(order, 'replies')})")
                            
                            # Check if there are any replies in the database that might not be linked
                            all_replies = await session.execute(select(KworkReply))
                            replies = all_replies.scalars().all()
                            if replies:
                                logger.error(f"  - Found {len(replies)} replies in the database, but they're not linked to the order")
                                for i, reply in enumerate(replies, 1):
                                    logger.error(f"    Reply {i}: Order ID: {reply.order_id}, Status: {getattr(reply, 'status', 'N/A')}")
                
                # Clean up test data
                logger.info("\nCleaning up test data...")
                try:
                    # Rollback any pending transactions
                    await session.rollback()
                    
                    # Delete test data
                    await session.execute(delete(KworkReply))
                    await session.execute(delete(KworkOrder))
                    await session.execute(delete(KworkFilter))
                    await session.commit()
                    logger.info("✅ Test data cleaned up successfully")
                except Exception as e:
                    logger.error(f"❌ Error cleaning up test data: {e}", exc_info=True)
                    await session.rollback()
                    raise
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error in test execution: {e}", exc_info=True)
                raise
        
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["DRY_RUN"] = "true"
    os.environ["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN", "test_token")
    os.environ["TELEGRAM_ADMIN_ID"] = os.getenv("TELEGRAM_ADMIN_ID", "123456789")
    
    # Run the test
    asyncio.run(test_order_processing())
