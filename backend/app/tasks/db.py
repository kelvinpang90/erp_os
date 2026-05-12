"""Celery-specific async DB engine.

Celery workers invoke each task in a fresh asyncio loop via ``asyncio.run``.
The web engine in ``app.core.database`` uses a connection pool that caches
connections against the loop they were created in — reusing one across loops
raises ``RuntimeError: ... attached to a different loop``. Using ``NullPool``
here disables caching so every task acquires (and releases) a fresh
connection scoped to its own loop.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

celery_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DATABASE_ECHO,
)

AsyncSessionLocal = async_sessionmaker(
    bind=celery_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
