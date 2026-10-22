"""
Database session management and lifecycle hooks using SQLAlchemy AsyncIO
"""
import json
from typing import AsyncGenerator, Optional, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import settings
from app.database.models import Base, AuditEvent

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Create all database tables on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for injecting async database session into FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def record_audit(
    session: AsyncSession,
    event_type: str,
    message: str,
    level: str = "INFO",
    details: Optional[Any] = None
):
    """Utility function to persist audit events safely without leaking secrets."""
    details_str = None
    if details is not None:
        if isinstance(details, str):
            details_str = details
        else:
            try:
                details_str = json.dumps(details, default=str)
            except Exception:
                details_str = str(details)
    
    event = AuditEvent(
        event_type=event_type,
        level=level,
        message=message,
        details_json=details_str
    )
    session.add(event)
    await session.commit()
