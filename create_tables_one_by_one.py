"""
Create database tables one by one to identify any issues.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent))

# Set environment variable to use async driver
os.environ["DATABASE_URL"] = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import MetaData, Table, Column, String, Integer, Text, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects import sqlite

# Use JSONB for PostgreSQL, JSON for SQLite
JSON_COLUMN = JSONB().with_variant(JSON(), sqlite.dialect.name)

# Create async engine
engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=True,
    future=True,
)

metadata = MetaData()

# Define tables
orders = Table(
    "orders",
    metadata,
    Column("id", String, primary_key=True, index=True),
    Column("title", String, nullable=False),
    Column("category", String, nullable=True),
    Column("budget", String, nullable=True),
    Column("description", Text, nullable=True),
    Column("source", String, nullable=False, default="kwork"),
    Column("url", String, nullable=True),
    Column("created_at", DateTime, default="now()"),
    Column("updated_at", DateTime, default="now()", onupdate="now()"),
)

replies = Table(
    "replies",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("order_id", String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    Column("message", Text, nullable=False),
    Column("sent", Boolean, default=False, nullable=False),
    Column("status", String(50), default="pending", nullable=False),
    Column("error_message", Text, nullable=True),
    Column("created_at", DateTime, default="now()"),
)

system_logs = Table(
    "system_logs",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("level", String(20), nullable=False),
    Column("message", Text, nullable=False),
    Column("source", String(50), nullable=True),
    Column("details", Text, nullable=True),
    Column("created_at", DateTime, default="now()"),
)

kwork_orders = Table(
    "kwork_orders",
    metadata,
    Column("id", String, primary_key=True, index=True),
    Column("title", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("price", JSON_COLUMN, nullable=True),
    Column("category", String, nullable=True),
    Column("status", String, nullable=True),
    Column("views", Integer, default=0),
    Column("replies_count", Integer, default=0),
    Column("published_at", DateTime, nullable=True),
    Column("raw_data", JSON_COLUMN, nullable=True),
    Column("created_at", DateTime, default="now()"),
    Column("updated_at", DateTime, default="now()", onupdate="now()"),
)

kwork_replies = Table(
    "kwork_replies",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("order_id", String, ForeignKey("kwork_orders.id", ondelete="CASCADE"), nullable=False),
    Column("message", Text, nullable=False),
    Column("price", Float, nullable=True),
    Column("days", Integer, nullable=True),
    Column("status", String, default="pending"),
    Column("error_message", Text, nullable=True),
    Column("created_at", DateTime, default="now()"),
    Column("updated_at", DateTime, default="now()", onupdate="now()"),
)

kwork_filters = Table(
    "kwork_filters",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("name", String, nullable=False),
    Column("keywords", JSON_COLUMN, nullable=True),
    Column("categories", JSON_COLUMN, nullable=True),
    Column("min_price", Float, nullable=True),
    Column("max_price", Float, nullable=True),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime, default="now()"),
    Column("updated_at", DateTime, default="now()", onupdate="now()"),
)

async def create_tables():
    """Create all tables one by one."""
    print("🔄 Starting to create tables...")
    
    async with engine.begin() as conn:
        # Drop all tables first (be careful with this in production!)
        print("\n🔨 Dropping existing tables...")
        await conn.run_sync(metadata.drop_all)
        
        # Create tables one by one
        print("\n🛠️  Creating tables...")
        for table in metadata.sorted_tables:
            try:
                print(f"\nCreating table: {table.name}")
                await conn.run_sync(table.create)
                print(f"✅ Successfully created table: {table.name}")
            except Exception as e:
                print(f"❌ Error creating table {table.name}: {e}")
                raise
    
    print("\n✨ All tables created successfully!")

async def main():
    """Run the table creation process."""
    try:
        await create_tables()
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
