import sqlite3
import json
from pprint import pprint

def print_table_schema(conn, table_name):
    """Print the schema of a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    print(f"\n=== Schema for {table_name} ===")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

def print_table_data(conn, table_name, limit=3):
    """Print data from a table."""
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    
    print(f"\n=== Data in {table_name} ({count} rows) ===")
    
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
        rows = cursor.fetchall()
        
        for row in rows:
            print("\nRow:")
            for col_name, value in zip(columns, row):
                # Truncate long values for better readability
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                print(f"  {col_name}: {value_str}")
    else:
        print("  No data found.")

def main():
    db_path = "kwork_scraper.db"
    print(f"Checking database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        
        # Get list of tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("\n=== Tables in database ===")
        for table in tables:
            print(f"- {table}")
        
        # Check important tables
        for table in ['kwork_orders', 'kwork_replies', 'kwork_filters']:
            if table in tables:
                print_table_schema(conn, table)
                print_table_data(conn, table)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
