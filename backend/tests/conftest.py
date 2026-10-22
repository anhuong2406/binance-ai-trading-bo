"""
Pytest Fixtures for AI Binance Trading Company Test Suite
Uses SQLite in-memory database and mock clients to test all 18 failure and edge cases safely offline.
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base
from app.config.settings import settings

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
def mock_symbol_filters():
    return {
        "symbol": "BTCUSDT",
        "stepSize": Decimal("0.0001"),
        "minQty": Decimal("0.0001"),
        "maxQty": Decimal("1000.0"),
        "tickSize": Decimal("0.01"),
        "minPrice": Decimal("100.0"),
        "maxPrice": Decimal("1000000.0"),
        "minNotional": Decimal("5.0"),
    }
