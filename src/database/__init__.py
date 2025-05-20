"""
Database module for the application.
"""
from .session import (
    Base,
    engine,
    async_session,
    SQLALCHEMY_DATABASE_URL,
    get_db,
)

# Import models to ensure they are registered with Base
from . import models  # noqa

__all__ = [
    "Base",
    "engine",
    "async_session",
    "SQLALCHEMY_DATABASE_URL",
    "get_db",
    "models",
]

# For backward compatibility
SessionLocal = None  # Deprecated, use async_session instead
