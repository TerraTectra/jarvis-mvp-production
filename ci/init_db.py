"""Initialize the database for the code review system."""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ci.review_storage import Base, storage

def init_db():
    """Initialize the database by creating all tables."""
    print("Initializing database...")
    
    # Create all tables
    Base.metadata.create_all(bind=storage.engine)
    
    print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()
