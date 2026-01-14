"""SQLite database connection and session management."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import get_data_dir

Base = declarative_base()

# Database file location
DATABASE_PATH = get_data_dir() / "weather_trader.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_database() -> None:
    """Initialize the database, creating all tables."""
    from app.models.database_models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
