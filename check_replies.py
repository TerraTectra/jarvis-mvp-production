import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.session import Base
from src.kwork.models import KworkReply, KworkOrder

# Database URL - adjust as needed
DATABASE_URL = "sqlite+aiosqlite:///kwork_scraper.db"

# Create engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def check_replies():
    """Check the contents of the kwork_replies table."""
    async with TestingSessionLocal() as session:
        # Check kwork_replies table
        result = await session.execute(select(KworkReply))
        replies = result.scalars().all()
        
        print(f"\n=== Found {len(replies)} replies in kwork_replies table ===")
        for i, reply in enumerate(replies, 1):
            print(f"\nReply {i}:")
            print(f"  ID: {reply.id}")
            print(f"  Order ID: {reply.order_id}")
            print(f"  Status: {reply.status}")
            print(f"  Created At: {reply.created_at}")
            print(f"  Message Preview: {reply.message[:100]}..." if reply.message else "  No message")
        
        # Also check the kwork_orders table
        result = await session.execute(select(KworkOrder))
        orders = result.scalars().all()
        
        print(f"\n=== Found {len(orders)} orders in kwork_orders table ===")
        for order in orders:
            print(f"\nOrder ID: {order.id}")
            print(f"  Title: {order.title}")
            print(f"  Status: {order.status}")
            print(f"  Replies Count: {order.replies_count}")
            print(f"  Created At: {order.created_at}")

if __name__ == "__main__":
    asyncio.run(check_replies())
