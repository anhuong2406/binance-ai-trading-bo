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
