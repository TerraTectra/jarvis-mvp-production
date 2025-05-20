import sqlite3

def print_table(conn, table_name, limit=3):
    """Print table contents."""
    cursor = conn.cursor()
    try:
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        
        print(f"\n=== Table: {table_name} ({count} rows) ===")
        print("Columns:", ", ".join(columns))
        
        if count > 0:
            # Get first few rows
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
            rows = cursor.fetchall()
            
            print("\nSample data:")
            for row in rows:
                print("  " + str(row)[:200] + ("..." if len(str(row)) > 200 else ""))
    except sqlite3.Error as e:
        print(f"Error reading table {table_name}: {e}")

def main():
    db_path = "kwork_scraper.db"
    print(f"Checking database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("No tables found in the database.")
            return
        
        print("\n=== Tables in database ===")
        for table in tables:
            print(f"- {table}")
        
        # Check important tables
        for table in ['kwork_orders', 'kwork_replies', 'kwork_filters']:
            if table in tables:
                print_table(conn, table)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
