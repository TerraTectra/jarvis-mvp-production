import sqlite3
import os
from pprint import pprint

def check_database(db_path):
    """Check SQLite database contents."""
    if not os.path.exists(db_path):
        print(f"Database file {db_path} does not exist!")
        return
    
    print(f"\n=== Checking database: {db_path} ===\n")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("No tables found in the database.")
            return
        
        for table in tables:
            table_name = table[0]
            print(f"\n=== Table: {table_name} ===")
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print("\nColumns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"\nRow count: {count}")
            
            if count > 0:
                # Get first few rows
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                rows = cursor.fetchall()
                
                print("\nSample data:")
                for row in rows:
                    print("  " + str(row)[:200] + ("..." if len(str(row)) > 200 else ""))
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

if __name__ == "__main__":
    # Check all SQLite databases in the current directory
    for db_file in ["jarvis.db", "kwork_scraper.db", "kwork_scraper_staging.db"]:
        check_database(db_file)
