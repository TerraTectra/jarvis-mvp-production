"""
List all tables in the database.
"""
import asyncio
import asyncpg

async def list_tables():
    """List all tables in the database."""
    print("🔄 Connecting to the database...")
    conn = await asyncpg.connect(
        user="TerraTectra",
        password="272829Dr",
        database="jarvis_staging",
        host="localhost",
        port=5432
    )
    
    try:
        print("📋 Listing all tables in the database:")
        
        # Get all tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        
        if tables:
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table['table_name']}")
                
                # Get table columns
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1;
                """, table['table_name'])
                
                for col in columns:
                    print(f"   - {col['column_name']} ({col['data_type']}) {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
                print()
        else:
            print("No tables found in the database.")
            
    except Exception as e:
        print(f"❌ Error listing tables: {e}")
    finally:
        await conn.close()
        print("🔌 Database connection closed.")

if __name__ == "__main__":
    asyncio.run(list_tables())
