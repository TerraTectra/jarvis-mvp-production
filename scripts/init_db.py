"""
Initialize the database and run migrations.
This script handles both the initial database creation and running migrations.
"""
import asyncio
import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from src.database.session import SQLALCHEMY_DATABASE_URL, Base, async_session
from src.models.user import User, Role, Permission, user_roles
from src.core.security import get_password_hash


async def init_models():
    """Initialize database models."""
    async with async_session() as session:
        try:
            # Create default roles if they don't exist
            result = await session.execute(
                Role.__table__.select().where(Role.name == "admin")
            )
            admin_role = result.scalar_one_or_none()
            
            if not admin_role:
                logger.info("Creating default roles...")
                # Create admin role
                admin_role = Role(
                    name="admin",
                    description="Administrator with full access",
                    is_default=False,
                )
                session.add(admin_role)
                
                # Create user role
                user_role = Role(
                    name="user",
                    description="Regular user",
                    is_default=True,
                )
                session.add(user_role)
                
                # Create review roles
                review_read_role = Role(
                    name="review:read",
                    description="Can read reviews",
                    is_default=False,
                )
                session.add(review_read_role)
                
                review_write_role = Role(
                    name="review:write",
                    description="Can create and update reviews",
                    is_default=False,
                )
                session.add(review_write_role)
                
                await session.commit()
                logger.info("✅ Created default roles")
            
            # Create default admin user if it doesn't exist
            result = await session.execute(
                User.__table__.select().where(User.username == "admin")
            )
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                logger.info("Creating admin user...")
                admin_user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Admin User",
                    is_active=True,
                    is_verified=True,
                )
                session.add(admin_user)
                await session.commit()
                
                # Add admin role to admin user
                admin_user.roles.append(admin_role)
                await session.commit()
                
                logger.info("✅ Created admin user with username: admin, password: admin123")
            else:
                logger.info("ℹ️ Admin user already exists")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error initializing models: {e}")
            raise


def run_migrations() -> None:
    """Run database migrations using subprocess."""
    logger.info("Running database migrations...")
    
    # Get the base directory
    base_dir = Path(__file__).resolve().parent.parent
    
    try:
        # Run migrations using the alembic command line
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(base_dir),
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Migration error: {result.stderr}")
            raise RuntimeError(f"Migration failed: {result.stderr}")
            
        logger.info("✅ Database migrations completed")
        if result.stdout:
            logger.debug(f"Migration output: {result.stdout}")
            
    except Exception as e:
        logger.error(f"❌ Error running migrations: {e}")
        raise


def create_tables() -> None:
    """Create database tables synchronously."""
    logger.info("Creating database tables...")
    
    # Create a synchronous engine
    sync_db_url = SQLALCHEMY_DATABASE_URL.replace("+aiosqlite", "")
    engine = create_engine(sync_db_url)
    
    try:
        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise
    finally:
        engine.dispose()

async def init_database():
    """Initialize the database."""
    try:
        # Create tables synchronously first
        create_tables()
        
        # Run migrations
        run_migrations()
        
        # Initialize default data
        await init_models()
        
        logger.info("✅ Database initialization completed")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        raise 1


if __name__ == "__main__":
    try:
        logger.info("Starting database initialization...")
        asyncio.run(init_database())
        logger.info("✅ Database initialization completed successfully")
    except Exception as e:
        logger.error(f"❌ Fatal error during database initialization: {e}")
        sys.exit(1)
