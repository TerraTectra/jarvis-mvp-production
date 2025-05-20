"""Script to create a test Kwork order."""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime
from src.database.session import async_session
from src.kwork.models import KworkOrder

async def create_test_order():
    """Create a test Kwork order."""
    async with async_session() as session:
        order = KworkOrder(
            id='test_999999',
            title='Test Order',
            description='This is a test order for bot testing',
            price={"amount": 5000, "currency": "RUB"},
            category='Web Development',
            status='active',
            views=10,
            replies_count=5,
            published_at=datetime.utcnow(),
            raw_data={
                "id": "test_999999",
                "title": "Test Order",
                "description": "This is a test order for bot testing",
                "price": 5000,
                "currency": "RUB",
                "category": "Web Development"
            }
        )
        session.add(order)
        await session.commit()
        print('Test order created successfully!')

if __name__ == "__main__":
    asyncio.run(create_test_order())
