"""
Test Suite: Quant Engine & Strategy Plugins
"""
import pytest
from app.trading.quant_engine import QuantEngine
from app.trading.strategies.trend_following import TrendFollowingStrategy
from app.trading.strategies.ema_crossover import EMACrossoverStrategy
from app.trading.strategies.rsi_reversion import RSIMeanReversionStrategy
from app.trading.strategies.macd_momentum import MACDMomentumStrategy
from app.trading.strategies.multi_timeframe import MultiTimeframeStrategy

def test_quant_engine_insufficient_data():
    """Verify Quant Engine raises error when candles are fewer than required threshold."""
    closes = [100.0] * 30
    highs = [105.0] * 30
    lows = [95.0] * 30
    volumes = [1000.0] * 30
    with pytest.raises(ValueError, match="Không đủ dữ liệu nến"):
        QuantEngine.compute_all_indicators(highs, lows, closes, volumes)

def test_quant_engine_calculation_correctness():
    """Verify indicators compute valid values with sufficient candles."""
    n = 100
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    volumes = [1000.0] * n

    indicators = QuantEngine.compute_all_indicators(highs, lows, closes, volumes)
    latest = indicators["latest"]

    assert latest["close"] == closes[-1]
    assert latest["ema9"] is not None
    assert latest["ema21"] is not None
    assert latest["ema50"] is not None
    assert latest["rsi14"] is not None
    assert latest["rsi14"] > 70  # Strong uptrend should show high RSI
    assert latest["stoch_rsi_k"] is not None
    assert latest["stoch_rsi_d"] is not None
    assert latest["market_session"] is not None
    assert "session" in latest["market_session"]
    assert latest["adx"] is not None
    assert latest["volume_ratio"] == 1.0

def test_strategy_plugins_evaluation():
    """Verify all 5 strategy plugins evaluate cleanly without crashes."""
    n = 100
    closes = [100.0 + i * 0.2 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [500.0] * n
    ind = QuantEngine.compute_all_indicators(highs, lows, closes, volumes)

    strategies = [
        TrendFollowingStrategy(),
        EMACrossoverStrategy(),
        RSIMeanReversionStrategy(),
        MACDMomentumStrategy(),
        MultiTimeframeStrategy(),
    ]

    for s in strategies:
        res = s.evaluate("BTCUSDT", closes, highs, lows, volumes, ind)
        assert res.action in ("BUY", "SELL", "HOLD")
        assert res.strategy_name == s.name

def test_quant_engine_mtf_alignment():
    """Verify Multi-Timeframe Alignment correctly distinguishes aligned vs diverging trends."""
    n = 60
    # Bullish series
    bull_closes = [100.0 + i * 1.0 for i in range(n)]
    bull_highs = [c + 1.0 for c in bull_closes]
    bull_lows = [c - 1.0 for c in bull_closes]
    bull_vols = [1000.0] * n

    # Bearish series
    bear_closes = [200.0 - i * 1.0 for i in range(n)]
    bear_highs = [c + 1.0 for c in bear_closes]
    bear_lows = [c - 1.0 for c in bear_closes]
    bear_vols = [1000.0] * n

    # Both Bullish -> ALIGNED_BULLISH
    res_bull = QuantEngine.compute_mtf_alignment(
        htf_highs=bull_highs, htf_lows=bull_lows, htf_closes=bull_closes, htf_volumes=bull_vols,
        ltf_highs=bull_highs, ltf_lows=bull_lows, ltf_closes=bull_closes, ltf_volumes=bull_vols
    )
    assert res_bull["alignment"] == "ALIGNED_BULLISH"
    assert res_bull["allow_buy"] is True

    # HTF Bearish + LTF Bullish -> COUNTER_TREND (Must NOT allow buy)
    res_counter = QuantEngine.compute_mtf_alignment(
        htf_highs=bear_highs, htf_lows=bear_lows, htf_closes=bear_closes, htf_volumes=bear_vols,
        ltf_highs=bull_highs, ltf_lows=bull_lows, ltf_closes=bull_closes, ltf_volumes=bull_vols
    )
    assert res_counter["allow_buy"] is False
    assert res_counter["alignment"] == "COUNTER_TREND"

def test_stoch_rsi_and_session_filter():
    from app.trading.quant_engine import calculate_stoch_rsi, detect_market_session
    from datetime import datetime, timezone

    # StochRSI on 50 candles
    closes = [100.0 + (i % 10) * 0.5 for i in range(50)]
    stoch = calculate_stoch_rsi(closes)
    assert len(stoch["k"]) == 50
    assert len(stoch["d"]) == 50
    valid_k = [x for x in stoch["k"] if x is not None]
    assert len(valid_k) > 0
    assert 0.0 <= valid_k[-1] <= 100.0

    # Dead zone session check (22:00 UTC = 05:00 VN)
    dead_time = datetime(2026, 10, 23, 22, 0, tzinfo=timezone.utc)
    res_dead = detect_market_session(dead_time)
    assert res_dead["is_dead_zone"] is True
    assert res_dead["liquidity"] == "LOW"

    # US Peak session check (15:00 UTC = 22:00 VN)
    us_time = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
    res_us = detect_market_session(us_time)
    assert res_us["is_dead_zone"] is False
    assert res_us["liquidity"] in ("HIGH", "PEAK")

@pytest.mark.asyncio
async def test_scalping_take_profit_and_stop_loss():
    from decimal import Decimal
    from app.config.settings import settings
    from app.trading.position_manager import PositionManager
    from app.database.session import AsyncSessionLocal
    from app.database.models import Position

    assert settings.SCALPING_MODE_ENABLED is True
    assert settings.TARGET_TAKE_PROFIT_PERCENT > 0
    assert settings.TARGET_STOP_LOSS_PERCENT > 0

    # Calculate scalping TP / SL on entry of 100
    entry_price = Decimal("100.0")
    tp = entry_price * (Decimal("1.0") + Decimal("0.012"))
    sl = entry_price * (Decimal("1.0") - Decimal("0.010"))

    assert tp == Decimal("101.2")
    assert sl == Decimal("99.0")

    # Test PositionManager triggers Take Profit when price reaches 101.25
    async with AsyncSessionLocal() as session:
        pos = await PositionManager.open_position(
            session=session,
            symbol="DOGEUSDT",
            amount=Decimal("10"),
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            fee=Decimal("0.01"),
            mode="PAPER"
        )
        assert pos.id is not None
        assert pos.status == "OPEN"

        # Market price below TP -> no action
        actions = await PositionManager.update_active_positions(
            session=session,
            current_prices={"DOGEUSDT": 100.5},
            mode="PAPER"
        )
        assert len(actions) == 0

        # Market price reaches or exceeds TP (101.25 >= 101.20) -> TAKE_PROFIT_TRIGGERED
        actions_tp = await PositionManager.update_active_positions(
            session=session,
            current_prices={"DOGEUSDT": 101.25},
            mode="PAPER"
        )
        assert len(actions_tp) == 1
        assert actions_tp[0]["action"] == "CLOSED"
        assert actions_tp[0]["reason"] == "TAKE_PROFIT_TRIGGERED"
        assert actions_tp[0]["pnl"] > 0

        # Now test Stop Loss trigger on a new position
        pos_sl = await PositionManager.open_position(
            session=session,
            symbol="BTCUSDT",
            amount=Decimal("0.05"),
            entry_price=entry_price,
            stop_loss=sl,
            take_profit=tp,
            fee=Decimal("0.01"),
            mode="PAPER"
        )
        assert pos_sl.status == "OPEN"

        # Market price drops below SL (98.90 <= 99.00) -> STOP_LOSS_TRIGGERED
        actions_sl = await PositionManager.update_active_positions(
            session=session,
            current_prices={"BTCUSDT": 98.90},
            mode="PAPER"
        )
        assert len(actions_sl) == 1
        assert actions_sl[0]["action"] == "CLOSED"
        assert actions_sl[0]["reason"] == "STOP_LOSS_TRIGGERED"
        assert actions_sl[0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_scalping_reversal_confirmation_with_oversold_bounce():
    from app.trading.quant_engine import QuantEngine
    from app.binance.market_data import Candle
    
    candles = [
        Candle(open_time=1, open_=100.0, high=101.0, low=98.0, close=98.5, volume=500.0, close_time=2),
        Candle(open_time=3, open_=98.5, high=99.5, low=98.0, close=99.2, volume=600.0, close_time=4)
    ]
    indicators = {
        "latest": {
            "close": 99.2,
            "ema9": 99.5,
            "ema21": 100.0,
            "volume_ratio": 0.6,
            "stoch_rsi_k": 22.0,
            "stoch_rsi_d": 18.0,
            "bb_lower": 98.2,
            "rsi14": 32.0
        },
        "series": {
            "stoch_rsi_k": [15.0, 22.0],
            "stoch_rsi_d": [14.0, 18.0],
            "macd": {"histogram": [-0.5, -0.2]}
        }
    }
    
    is_confirmed = QuantEngine.has_confirmed_scalping_reversal(indicators, candles)
    assert is_confirmed is True
