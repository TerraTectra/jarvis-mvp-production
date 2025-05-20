"""Script to check if test order exists in the database."""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy import select
from src.database.session import async_session, init_db
from src.kwork.models import KworkOrder

async def check_test_order():
    """Check if test order exists in the database."""
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(KworkOrder).where(KworkOrder.id == 'test_999999'))
        order = result.scalar_one_or_none()
        if order:
            print(f"✅ Test order found in database:")
            print(f"  ID: {order.id}")
            print(f"  Title: {order.title}")
            print(f"  Status: {order.status}")
            print(f"  Created at: {order.created_at}")
            return True
        else:
            print("❌ Test order not found in database")
            return False

if __name__ == "__main__":
    asyncio.run(check_test_order())
