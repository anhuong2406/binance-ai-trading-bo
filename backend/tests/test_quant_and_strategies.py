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
