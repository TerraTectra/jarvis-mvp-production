import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the models for autogenerate support
from src.models.user import Base
from src.database.session import SQLALCHEMY_DATABASE_URL

# Set target_metadata for autogenerate support
target_metadata = Base.metadata

# Override the SQLAlchemy URL from the environment
config.set_main_option('sqlalchemy.url', str(SQLALCHEMY_DATABASE_URL))

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async SQLAlchemy."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    """Run migrations with proper event loop handling."""
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        # Always run in a new event loop to avoid conflicts
        try:
            import asyncio
            
            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run migrations in the new event loop
            print("Running migrations in a new event loop...")
            loop.run_until_complete(run_migrations_online())
            
        except Exception as e:
            print(f"❌ Error running migrations: {e}")
            raise
        finally:
            # Clean up the event loop
            if loop:
                loop.close()

if __name__ == "__main__":
    run_migrations()
else:
    run_migrations()
