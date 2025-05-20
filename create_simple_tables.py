"""
Create simple tables without complex relationships.
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

# Database URL
DATABASE_URL = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

# Create engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()

# Simple model for testing
class SimpleOrder(Base):
    __tablename__ = "simple_orders"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

async def create_tables():
    """Create all tables."""
    print("🔄 Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully!")

async def main():
    """Run the table creation process."""
    try:
        await create_tables()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
