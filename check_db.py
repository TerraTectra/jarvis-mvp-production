"""Simple script to check database contents."""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.session import async_session
from src.kwork.models import KworkOrder, KworkFilter, KworkReply

async def check_database():
    """Check database contents."""
    print("\n=== Checking database contents ===\n")
    
    async with async_session() as session:
        # Check orders
        print("=== Orders ===")
        result = await session.execute(select(KworkOrder).options(selectinload(KworkOrder.replies)))
        orders = result.scalars().all()
        
        if not orders:
            print("No orders found in the database.")
        else:
            for order in orders:
                print(f"\nOrder ID: {order.id}")
                print(f"Title: {order.title}")
                print(f"Status: {order.status}")
                print(f"Replies count: {len(order.replies) if order.replies else 0}")
                
                if order.replies:
                    print("\nReplies:")
                    for i, reply in enumerate(order.replies, 1):
                        print(f"  {i}. {reply.message[:100]}..." if len(reply.message) > 100 else f"  {i}. {reply.message}")
                        print(f"     Created at: {reply.created_at}")
        
        # Check filters
        print("\n=== Filters ===")
        result = await session.execute(select(KworkFilter))
        filters = result.scalars().all()
        
        if not filters:
            print("No filters found in the database.")
        else:
            for f in filters:
                print(f"\nFilter ID: {f.id}")
                print(f"Name: {f.name}")
                print(f"Keywords: {f.keywords}")
                print(f"Categories: {f.categories}")
                print(f"Active: {f.is_active}")
    
    print("\n=== Database check completed ===\n")

if __name__ == "__main__":
    asyncio.run(check_database())
