import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from src.models.user import User, Role, user_roles

# Database URL - adjust if needed
DATABASE_URL = "sqlite+aiosqlite:///./kwork_scraper_staging.db"

async def check_users():
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Get all users with their roles
        result = await session.execute(
            select(User).options(selectinload(User.roles))
        )
        users = result.scalars().all()
        
        print("\nUsers in the database:")
        print("-" * 50)
        print(f"{'ID':<5} {'Username':<15} {'Email':<25} {'Active':<8} {'Verified':<8} {'Roles'}")
        print("-" * 50)
        
        for user in users:
            role_names = [role.name for role in user.roles]
            print(f"{user.id:<5} {user.username:<15} {user.email:<25} {user.is_active:<8} {user.is_verified:<8} {', '.join(role_names)}")

if __name__ == "__main__":
    from sqlalchemy.orm import selectinload
    asyncio.run(check_users())
