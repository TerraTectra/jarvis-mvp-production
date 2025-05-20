import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host="localhost",
            user="postgres",
            password="postgres",  # Default password, change if different
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Create database
        print("Creating database 'jarvis_staging'...")
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='jarvis_staging'")
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("CREATE DATABASE jarvis_staging")
            print("Database created successfully.")
        else:
            print("Database already exists.")

        # Create user and grant privileges
        print("Creating user 'TerraTectra'...")
        cursor.execute("SELECT 1 FROM pg_user WHERE usename = 'terratectra'")
        user_exists = cursor.fetchone()
        
        if not user_exists:
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier('TerraTectra')
                ),
                ('272829Dr',)
            )
            print("User created successfully.")
        else:
            print("User already exists.")

        # Grant privileges
        print("Granting privileges...")
        cursor.execute("GRANT ALL PRIVILEGES ON DATABASE jarvis_staging TO TerraTectra")
        
        # Connect to the new database to set schema permissions
        conn_db = psycopg2.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            dbname="jarvis_staging"
        )
        conn_db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor_db = conn_db.cursor()
        cursor_db.execute("GRANT ALL ON SCHEMA public TO TerraTectra")
        
        print("Database setup completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        if 'cursor_db' in locals():
            cursor_db.close()
        if 'conn_db' in locals():
            conn_db.close()

if __name__ == "__main__":
    setup_database()
