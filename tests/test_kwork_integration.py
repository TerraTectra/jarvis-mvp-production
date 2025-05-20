"""
Tests for Kwork integration.
"""
import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.kwork.api import KworkAPI, KworkAPIError
from src.kwork.models import KworkOrder, KworkReply, KworkFilter
from src.kwork.service import KworkService

# Test data
SAMPLE_ORDER = {
    "id": "12345",
    "name": "Test Order",
    "description": "This is a test order",
    "price": {"amount": 1000, "currency": "RUB"},
    "category": {"name": "Web Development"},
    "status": "active",
    "views": 10,
    "replies_count": 2,
    "published_at": int(datetime.now().timestamp())
}

@pytest.mark.asyncio
async def test_kwork_api_get_orders():
    """Test fetching orders from Kwork API."""
    with patch('httpx.AsyncClient.get') as mock_get:
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "list": [SAMPLE_ORDER]
            }
        }
        mock_get.return_value = mock_response
        
        async with KworkAPI("test_token") as api:
            result = await api.get_recent_orders()
            
            assert "data" in result
            assert len(result["data"]["list"]) == 1
            assert result["data"]["list"][0]["id"] == "12345"

@pytest.mark.asyncio
async def test_kwork_service_process_orders():
    """Test processing orders with the Kwork service."""
    # Create a mock API client
    mock_api = AsyncMock()
    mock_api.get_recent_orders.return_value = {
        "data": {
            "list": [SAMPLE_ORDER]
        }
    }
    
    # Initialize service with mock API
    service = KworkService(api=mock_api)
    
    # Test processing orders
    await service.process_new_orders()
    
    # Verify API was called
    mock_api.get_recent_orders.assert_called_once()
    
    # Verify database operations
    async with async_session() as session:
        # Verify order was created
        result = await session.execute(select(KworkOrder).where(KworkOrder.id == "12345"))
        order = result.scalar_one_or_none()
        assert order is not None
        assert order.title == "Test Order"

@pytest.mark.asyncio
async def test_kwork_filter_matching():
    """Test order filtering logic."""
    # Create a test filter
    test_filter = KworkFilter(
        name="Test Filter",
        keywords=["test", "python"],
        categories=[1, 2, 3],
        min_price=500,
        max_price=5000,
        is_active=True
    )
    
    # Create a test order that should match the filter
    order = KworkOrder(
        id="test_order_1",
        title="Test Python Project",
        description="We need a Python developer for testing",
        price={"amount": 1000, "currency": "RUB"},
        category="Web Development",
        status="active"
    )
    
    # Test matching
    service = KworkService()
    assert await service._matches_filter(order, test_filter) is True
    
    # Test non-matching price
    order.price = {"amount": 300, "currency": "RUB"}
    assert await service._matches_filter(order, test_filter) is False
    
    # Test non-matching keyword
    order.price = {"amount": 1000, "currency": "RUB"}
    order.title = "Java Project"
    order.description = "Need Java developer"
    assert await service._matches_filter(order, test_filter) is False

@pytest.mark.asyncio
async def test_kwork_poller():
    """Test the Kwork poller background task."""
    from src.kwork.tasks import KworkPoller
    
    # Create a mock service
    mock_service = AsyncMock()
    
    # Initialize poller with short interval for testing
    poller = KworkPoller(poll_interval=1)
    poller.service = mock_service
    
    # Start the poller
    task = asyncio.create_task(poller.start())
    
    # Let it run for a short time
    await asyncio.sleep(0.1)
    
    # Stop the poller
    await poller.stop()
    
    # Verify service was called
    mock_service.process_new_orders.assert_called()
    
    # Clean up
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
