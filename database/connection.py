"""
Database connection management.

Purpose: Creates and manages the async SQLAlchemy engine and session factory.
Provides a `get_session` dependency for FastAPI and helper functions for
table creation / teardown.

Clean architecture: This is a gateway — core logic depends on the
database interface (repositories), not on SQLAlchemy directly.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base all ORM models inherit from."""
    pass


async def init_database():
    """Create all tables. Call once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    """Dispose of the engine. Call once at shutdown."""
    await engine.dispose()


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a session for the request lifecycle."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
