import sqlite3

def print_table_data(db_path, table_name, limit=5):
    """Print data from a table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        
        print(f"\n=== {table_name} ({count} rows) ===")
        print("Columns:", ", ".join(columns))
        
        if count > 0:
            # Get data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
            rows = cursor.fetchall()
            
            print("\nData:")
            for i, row in enumerate(rows, 1):
                print(f"\nRow {i}:")
                for col, value in zip(columns, row):
                    print(f"  {col}: {value}")
        else:
            print("No data found.")
            
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error reading table {table_name}: {e}")

def main():
    db_path = "kwork_scraper.db"
    print(f"Checking database: {db_path}")
    
    # Check kwork_orders
    print_table_data(db_path, "kwork_orders")
    
    # Check kwork_replies
    print_table_data(db_path, "kwork_replies")
    
    # Check kwork_filters
    print_table_data(db_path, "kwork_filters")

if __name__ == "__main__":
    main()
