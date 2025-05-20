"""
Create tables using raw SQL.
"""
import asyncio
import asyncpg
from datetime import datetime

# Database connection settings
DB_CONFIG = {
    "user": "TerraTectra",
    "password": "272829Dr",
    "database": "jarvis_staging",
    "host": "localhost",
    "port": 5432
}

# SQL to create tables
CREATE_TABLES_SQL = """
-- Drop tables if they exist
DROP TABLE IF EXISTS replies CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS kwork_replies CASCADE;
DROP TABLE IF EXISTS kwork_orders CASCADE;
DROP TABLE IF EXISTS kwork_filters CASCADE;

-- Create orders table
CREATE TABLE orders (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    category VARCHAR,
    budget VARCHAR,
    description TEXT,
    source VARCHAR NOT NULL DEFAULT 'kwork',
    url VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create replies table
CREATE TABLE replies (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    sent BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create kwork_orders table
CREATE TABLE kwork_orders (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    description TEXT,
    price JSONB,
    category VARCHAR,
    status VARCHAR,
    views INTEGER DEFAULT 0,
    replies_count INTEGER DEFAULT 0,
    published_at TIMESTAMP WITH TIME ZONE,
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create kwork_replies table
CREATE TABLE kwork_replies (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR NOT NULL REFERENCES kwork_orders(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    price FLOAT,
    days INTEGER,
    status VARCHAR DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create kwork_filters table
CREATE TABLE kwork_filters (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    keywords JSONB,
    categories JSONB,
    min_price FLOAT,
    max_price FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

async def create_tables():
    """Create all tables using raw SQL."""
    print("🔄 Connecting to the database...")
    conn = await asyncpg.connect(**DB_CONFIG)
    
    try:
        print("🚀 Creating tables...")
        await conn.execute(CREATE_TABLES_SQL)
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise
    finally:
        await conn.close()
        print("🔌 Database connection closed.")

async def main():
    """Run the table creation process."""
    try:
        await create_tables()
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
