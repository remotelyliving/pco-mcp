from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pco_mcp.config import Settings


def create_engine(settings: Settings):
    """Create async SQLAlchemy engine from settings."""
    return create_async_engine(settings.database_url, echo=settings.debug)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)
