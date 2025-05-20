"""
Initialize the database with required tables.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent))

# Set environment variable to use async driver
os.environ["DATABASE_URL"] = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

from src.database.session import engine, Base, init_db

async def create_tables():
    """Create all database tables."""
    print("🔄 Creating database tables...")
    try:
        await init_db()
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False

async def main():
    """Initialize database tables."""
    print("🚀 Starting database initialization...")
    
    # Create all tables
    success = await create_tables()
    
    if success:
        print("✨ Database initialization completed successfully!")
    else:
        print("❌ Database initialization failed!")

if __name__ == "__main__":
    asyncio.run(main())
