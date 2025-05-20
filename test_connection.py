import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def test_connection():
    try:
        # Try to connect with common default credentials
        credentials = [
            {"user": "postgres", "password": "postgres"},
            {"user": "postgres", "password": ""},
            {"user": "postgres", "password": "admin"},
            {"user": "postgres", "password": "password"}
        ]
        
        for cred in credentials:
            try:
                print(f"Trying with user: {cred['user']}")
                conn = psycopg2.connect(
                    host="localhost",
                    user=cred['user'],
                    password=cred['password'],
                    dbname="postgres"
                )
                print(f"Successfully connected with user: {cred['user']}")
                conn.close()
                return cred
            except Exception as e:
                print(f"Failed with user {cred['user']}: {str(e)}")
        
        print("\nCould not connect with default credentials.")
        print("Please provide the PostgreSQL superuser username and password.")
        user = input("Username (default: postgres): ") or "postgres"
        password = input("Password: ")
        
        conn = psycopg2.connect(
            host="localhost",
            user=user,
            password=password,
            dbname="postgres"
        )
        print("Successfully connected with provided credentials!")
        return {"user": user, "password": password}
        
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def create_database(credentials):
    try:
        conn = psycopg2.connect(
            host="localhost",
            user=credentials['user'],
            password=credentials['password'],
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'jarvis_staging'")
        if not cursor.fetchone():
            print("Creating database 'jarvis_staging'...")
            cursor.execute("CREATE DATABASE jarvis_staging")
            print("Database created successfully.")
        else:
            print("Database 'jarvis_staging' already exists.")
        
        # Create user if not exists
        cursor.execute("SELECT 1 FROM pg_user WHERE usename = 'terratectra'")
        if not cursor.fetchone():
            print("Creating user 'TerraTectra'...")
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier('TerraTectra')
                ),
                ('272829Dr',)
            )
            print("User created successfully.")
        else:
            print("User 'TerraTectra' already exists.")
        
        # Grant privileges
        print("Granting privileges...")
        cursor.execute("GRANT ALL PRIVILEGES ON DATABASE jarvis_staging TO TerraTectra")
        
        # Connect to the new database to set schema permissions
        conn_db = psycopg2.connect(
            host="localhost",
            user=credentials['user'],
            password=credentials['password'],
            dbname="jarvis_staging"
        )
        conn_db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor_db = conn_db.cursor()
        cursor_db.execute("GRANT ALL ON SCHEMA public TO TerraTectra")
        
        print("\n✅ Database setup completed successfully!")
        print("\nYou can now use these credentials in your .env file:")
        print("DATABASE_URL=postgresql://TerraTectra:272829Dr@localhost:5432/jarvis_staging")
        
    except Exception as e:
        print(f"\n❌ Error during database setup: {e}")
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
    print("=== Testing PostgreSQL Connection ===\n")
    creds = test_connection()
    if creds:
        print("\n=== Setting Up Database ===\n")
        create_database(creds)
    else:
        print("\n❌ Failed to connect to PostgreSQL. Please check your PostgreSQL service and credentials.")
        print("1. Make sure PostgreSQL service is running")
        print("2. Check your PostgreSQL username and password")
        print("3. Verify that your pg_hba.conf file allows password authentication")
