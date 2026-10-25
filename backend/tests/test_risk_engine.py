"""
Test Suite: Risk Engine & Safety Rules
Tests Cases 6, 7, 8, 16, 17 from the specification.
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from app.trading.risk_engine import risk_engine
from app.config.settings import settings
from app.database.models import Position, DailyStat

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@pytest.mark.asyncio
async def test_case_6_small_balance_mode_rejects_below_min_notional(test_db, mock_symbol_filters):
    """Case 6: Small Balance Mode rejects orders where calculated notional < MIN_NOTIONAL (5 USDT)."""
    # Allocated capital = 10 USDT, entry price = 65000, max position size = 25% (2.5 USDT < 5 USDT)
    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=10.0,
        available_usdt=10.0,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert res.passed is False
    assert any("MIN_NOTIONAL" in r or "minQty" in r or "Small Balance" in r for r in res.reasons)

@pytest.mark.asyncio
async def test_case_7_insufficient_available_balance(test_db, mock_symbol_filters):
    """Case 7: Rejects when available USDT is insufficient."""
    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=100.0,
        available_usdt=1.0,  # Only 1 USDT available!
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert res.passed is False
    assert any("không đủ" in r or "MIN_NOTIONAL" in r or "minQty" in r or "Small Balance" in r for r in res.reasons)

@pytest.mark.asyncio
async def test_case_8_max_concurrent_positions(test_db, mock_symbol_filters):
    """Case 8: Rejects opening new position when max concurrent positions is reached, and allows when 0 (unlimited)."""
    # Add 2 open positions
    p1 = Position(symbol="ETHUSDT", amount=Decimal("0.1"), entry_price=Decimal("3000"), current_price=Decimal("3000"), status="OPEN", mode="PAPER")
    p2 = Position(symbol="SOLUSDT", amount=Decimal("1.0"), entry_price=Decimal("150"), current_price=Decimal("150"), status="OPEN", mode="PAPER")
    test_db.add_all([p1, p2])
    await test_db.commit()

    # Part 1: Unlimited mode (MAX_CONCURRENT_POSITIONS = 0) -> does not block for position count
    settings.MAX_CONCURRENT_POSITIONS = 0
    res_unlimited = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert not any("tối đa cho bot" in r for r in res_unlimited.reasons)

    # Part 2: Limited mode (MAX_CONCURRENT_POSITIONS = 2) -> rejects
    settings.MAX_CONCURRENT_POSITIONS = 2
    try:
        res = await risk_engine.evaluate_trade(
            session=test_db,
            symbol="BTCUSDT",
            action="BUY",
            entry_price=65000.0,
            stop_loss=64500.0,
            take_profit=66500.0,
            allocated_capital=100.0,
            available_usdt=100.0,
            symbol_filters=mock_symbol_filters,
            mode="PAPER"
        )
        assert res.passed is False
        assert any("tối đa cho bot" in r for r in res.reasons)
    finally:
        settings.MAX_CONCURRENT_POSITIONS = 0

@pytest.mark.asyncio
async def test_case_8_no_martingale_adding(test_db, mock_symbol_filters):
    """Case 8: Prohibits opening a second position in the same symbol (Anti-Martingale)."""
    p1 = Position(symbol="BTCUSDT", amount=Decimal("0.001"), entry_price=Decimal("65000"), current_price=Decimal("64000"), status="OPEN", mode="PAPER")
    test_db.add(p1)
    await test_db.commit()

    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=64000.0,
        stop_loss=63500.0,
        take_profit=66000.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert res.passed is False
    assert any("Martingale" in r for r in res.reasons)

@pytest.mark.asyncio
async def test_case_8_daily_loss_limit_reached(test_db, mock_symbol_filters):
    """Case 8: Rejects when daily loss limit (2%) has been breached."""
    today_str = utc_now().strftime("%Y-%m-%d")
    # Start equity 100, current equity 97.5 (2.5% loss >= 2.0% limit)
    stat = DailyStat(
        date=today_str,
        start_equity=100.0,
        current_equity=97.5,
        peak_equity=100.0,
        daily_pnl=-2.5,
        max_drawdown_percent=2.5,
        trade_count=1
    )
    test_db.add(stat)
    await test_db.commit()

    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=97.5,
        available_usdt=97.5,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert res.passed is False
    assert any("ngưỡng lỗ trong ngày" in r for r in res.reasons)

@pytest.mark.asyncio
async def test_case_8_cooldown_period_enforced(test_db, mock_symbol_filters):
    """Case 8: When cooldown is 0 it is disabled; when > 0 it is enforced."""
    p_closed = Position(
        symbol="BTCUSDT",
        amount=Decimal("0.001"),
        entry_price=Decimal("65000"),
        current_price=Decimal("64800"),
        status="CLOSED",
        mode="PAPER",
        closed_at=utc_now() - timedelta(minutes=1)
    )
    test_db.add(p_closed)
    await test_db.commit()

    # Part 1: Default cooldown is 0 (Disabled) -> passes without cooldown rejection
    settings.COOLDOWN_MINUTES = 0
    settings.SCALPING_COOLDOWN_MINUTES = 0
    res_disabled = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="ETHUSDT",
        action="BUY",
        entry_price=3000.0,
        stop_loss=2950.0,
        take_profit=3150.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    assert not any("Cooldown" in r for r in res_disabled.reasons)

    # Part 2: Enforced when cooldown > 0
    settings.COOLDOWN_MINUTES = 20
    settings.SCALPING_COOLDOWN_MINUTES = 20
    try:
        res = await risk_engine.evaluate_trade(
            session=test_db,
            symbol="ETHUSDT",
            action="BUY",
            entry_price=3000.0,
            stop_loss=2950.0,
            take_profit=3150.0,
            allocated_capital=100.0,
            available_usdt=100.0,
            symbol_filters=mock_symbol_filters,
            mode="PAPER"
        )
        assert res.passed is False
        assert any("Cooldown" in r for r in res.reasons)
    finally:
        settings.COOLDOWN_MINUTES = 0
        settings.SCALPING_COOLDOWN_MINUTES = 0

@pytest.mark.asyncio
async def test_case_16_live_mode_locked_by_default(test_db, mock_symbol_filters):
    """Case 16: Orders in LIVE mode are rejected when LIVE_SPOT_LOCKED is True."""
    settings.LIVE_SPOT_LOCKED = True

    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters=mock_symbol_filters,
        mode="LIVE"
    )
    assert res.passed is False
    assert any("KHÓA (LOCKED)" in r for r in res.reasons)

@pytest.mark.asyncio
async def test_case_17_emergency_stop_freezes_orders(test_db, mock_symbol_filters):
    """Case 17: When Emergency Stop is active, ALL new orders are frozen."""
    settings.EMERGENCY_STOP_ACTIVE = True

    res = await risk_engine.evaluate_trade(
        session=test_db,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=65000.0,
        stop_loss=64500.0,
        take_profit=66500.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters=mock_symbol_filters,
        mode="PAPER"
    )
    # Reset flag
    settings.EMERGENCY_STOP_ACTIVE = False
    assert res.passed is False
    assert any("EMERGENCY STOP" in r for r in res.reasons)
