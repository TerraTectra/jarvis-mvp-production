"""
Initialize the database with required tables and initial data.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent))

# Set environment variable to use async driver
os.environ["DATABASE_URL"] = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

from src.database.session import engine, Base, init_db
from src.models.user import User, Role, Permission, user_roles
from src.database.models import Order, Reply, SystemLog
from src.database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from src.kwork.models import KworkOrder, KworkReply, KworkFilter
from sqlalchemy import insert

async def create_initial_data():
    """Create initial roles and permissions."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    
    async with AsyncSession(engine) as session:
        try:
            # Check if roles already exist
            result = await session.execute(select(Role).where(Role.name.in_(["admin", "user"])))
            existing_roles = {role.name: role for role in result.scalars()}
            
            # Create admin role if it doesn't exist
            if "admin" not in existing_roles:
                admin_role = Role(
                    name="admin",
                    description="Administrator with full access"
                )
                session.add(admin_role)
                await session.flush()  # Get the ID
                
                # Add admin permissions
                admin_permissions = [
                    Permission(name="users:read", description="Read users", role_id=admin_role.id),
                    Permission(name="users:write", description="Create/update users", role_id=admin_role.id),
                    Permission(name="users:delete", description="Delete users", role_id=admin_role.id),
                    Permission(name="settings:manage", description="Manage system settings", role_id=admin_role.id),
                ]
                session.add_all(admin_permissions)
                
                # Create default user role if it doesn't exist
                if "user" not in existing_roles:
                    user_role = Role(
                        name="user",
                        description="Regular user with basic access"
                    )
                    session.add(user_role)
                    await session.flush()
                    
                    # Add user permissions
                    user_permissions = [
                        Permission(name="profile:read", description="Read own profile", role_id=user_role.id),
                        Permission(name="profile:update", description="Update own profile", role_id=user_role.id),
                    ]
                    session.add_all(user_permissions)
                
                await session.commit()
                print("✅ Initial roles and permissions created successfully!")
            else:
                print("ℹ️  Roles already exist, skipping creation.")
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating initial data: {e}")
            raise

async def main():
    """Initialize database and create initial data."""
    print("🚀 Starting database initialization...")
    
    # Create all tables
    print("🔄 Creating database tables...")
    await init_db()
    
    # Create initial data
    print("📝 Creating initial roles and permissions...")
    await create_initial_data()
    
    print("✨ Database initialization completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
