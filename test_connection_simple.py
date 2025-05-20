"""
Simple script to test PostgreSQL connection.
"""
import asyncio
import asyncpg

async def test_connection():
    """Test database connection."""
    print("🔄 Testing database connection...")
    try:
        conn = await asyncpg.connect(
            user="TerraTectra",
            password="272829Dr",
            database="jarvis_staging",
            host="localhost",
            port=5432
        )
        print("✅ Successfully connected to the database!")
        
        # Get database version
        version = await conn.fetchval('SELECT version();')
        print(f"📊 Database version: {version}")
        
        # Get current user
        current_user = await conn.fetchval('SELECT current_user;')
        print(f"👤 Current user: {current_user}")
        
        # Get current database
        current_db = await conn.fetchval('SELECT current_database();')
        print(f"💾 Current database: {current_db}")
        
        # Get current schema
        current_schema = await conn.fetchval('SHOW search_path;')
        print(f"📂 Current schema: {current_schema}")
        
        # List all schemas
        print("\n📋 Available schemas:")
        schemas = await conn.fetch('SELECT schema_name FROM information_schema.schemata;')
        for row in schemas:
            print(f"- {row['schema_name']}")
        
        # List all tables in public schema
        print("\n📋 Tables in public schema:")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        
        if tables:
            for table in tables:
                print(f"- {table['table_name']}")
        else:
            print("No tables found in public schema.")
            
        # Try to create a simple table
        print("\n🛠️  Creating a test table...")
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Test table created successfully!")
            
            # Insert test data
            await conn.execute(
                "INSERT INTO test_table (name) VALUES ($1)",
                "test_record"
            )
            print("✅ Test data inserted successfully!")
            
            # Query test data
            records = await conn.fetch("SELECT * FROM test_table;")
            print("\n📝 Test data in test_table:")
            for record in records:
                print(f"- ID: {record['id']}, Name: {record['name']}, Created: {record['created_at']}")
                
        except Exception as e:
            print(f"❌ Error creating test table: {e}")
        
    except Exception as e:
        print(f"❌ Error connecting to the database: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    asyncio.run(test_connection())
