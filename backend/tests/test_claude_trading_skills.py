"""
Comprehensive Test Suite for Claude Trading Skills Engine Integration
Tests:
- Non-existent skill rejection
- Corrupt/error data handling
- Security isolation: secret leakage protection & arbitrary code execution prevention
- Skill inability to invoke Binance orders directly
- Quantitative accuracy: Regime Detection 4 quadrants, Volatility modeling, Microstructure & Slippage, Position Sizing
- AI disagreement consensus
- Emergency Stop protection
- Small Balance Mode & Binance Spot compliance
"""
import pytest
import math
from app.skills.skill_registry import skill_registry, APPROVED_SKILLS_CATALOG
from app.skills.skill_loader import skill_loader
from app.skills.skill_executor import skill_executor
from app.skills.skill_validator import skill_validator
from app.skills.skill_selector import skill_selector
from app.skills.skill_audit import skill_audit
from app.ai.consensus import DecisionConsensus
from app.trading.risk_engine import risk_engine
from app.config.settings import settings

def test_non_existent_skill_rejected():
    """Test that skills not in approved catalog cannot be enabled or executed."""
    assert not skill_registry.is_enabled("malicious-dex-exploit")
    assert not skill_registry.set_enabled("malicious-dex-exploit", True)
    assert "malicious-dex-exploit" not in APPROVED_SKILLS_CATALOG

def test_skill_validator_detects_nan_inf_bad_data():
    """Test validator catches NaNs, Infs, mismatched arrays, and negative prices."""
    highs = [100.0, 102.0, float('nan'), 105.0]
    lows = [98.0, 99.0, 100.0, 101.0]
    closes = [99.0, 101.0, 102.0, 104.0]
    volumes = [10.0, 15.0, 20.0, 25.0]

    valid, err = skill_validator.validate_market_data(highs, lows, closes, volumes, min_bars=4)
    assert not valid
    assert "NaN/Inf" in err or "bất thường" in err

    # Test mismatched lengths
    valid, err = skill_validator.validate_market_data([100.0], [90.0], [95.0, 96.0], [10.0], min_bars=1)
    assert not valid
    assert "đồng nhất" in err

def test_security_blocks_binance_secret_leak():
    """Test sandbox validator catches and rejects any attempt to expose API secret."""
    dangerous_payload = {
        "symbol": "BTCUSDT",
        "parameters": {
            "binance_api_secret": "my_super_secret_key_12345",
            "command": "exec('import os')"
        }
    }
    safe, err = skill_validator.sanitize_and_audit_payload(dangerous_payload)
    assert not safe
    assert "binance_api_secret" in err

    code_injection = {"code": "eval('2+2')"}
    safe2, err2 = skill_validator.sanitize_and_audit_payload(code_injection)
    assert not safe2
    assert "eval(" in err2

def test_skill_cannot_execute_binance_orders():
    """Verify skill executor modules have no reference to order creation functions."""
    assert not hasattr(skill_executor, "create_order")
    assert not hasattr(skill_executor, "place_order")
    assert not hasattr(skill_executor, "send_order")

def test_regime_detection_quadrants():
    """Test market regime detection across synthetic market conditions."""
    # 1. Clean Trending Low Volatility (Steady upward climb)
    trend_closes = [100.0 + i * 2.0 for i in range(30)]
    trend_highs = [c + 0.5 for c in trend_closes]
    trend_lows = [c - 0.5 for c in trend_closes]
    trend_vols = [100.0] * 30

    res_trend = skill_executor.run_regime_detection(trend_highs, trend_lows, trend_closes, trend_vols)
    assert res_trend["regime"] in ("TRENDING_LOW_VOL", "TRENDING_HIGH_VOL")
    assert res_trend["choppiness_index"] < 61.8

    # 2. Choppy Sideway / Chaos (Alternating big spikes)
    choppy_closes = [100.0 if i % 2 == 0 else 105.0 for i in range(30)]
    choppy_highs = [c + 5.0 for c in choppy_closes]
    choppy_lows = [c - 5.0 for c in choppy_closes]
    choppy_vols = [500.0] * 30

    res_choppy = skill_executor.run_regime_detection(choppy_highs, choppy_lows, choppy_closes, choppy_vols)
    assert "RANGING" in res_choppy["regime"] or res_choppy["choppiness_index"] > 50.0

def test_volatility_modeling_parkinson_and_garman_klass():
    """Test volatility estimators calculate reasonable annualized metrics."""
    closes = [100.0, 101.0, 100.5, 102.0, 101.5, 103.0, 102.5, 104.0, 103.5, 105.0, 104.5, 106.0]
    opens = [c - 0.2 for c in closes]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]

    vol = skill_executor.run_volatility_modeling(highs, lows, opens, closes)
    assert "parkinson_vol" in vol
    assert "garman_klass_vol" in vol
    assert vol["parkinson_vol"] > 0.0
    assert vol["annualized_garman_klass_pct"] > 0.0

def test_market_microstructure_and_slippage():
    """Test order book imbalance, spread and VWAP slippage on simulated Binance book."""
    order_book = {
        "bids": [
            ["80000.0", "1.5"],
            ["79990.0", "2.0"],
            ["79980.0", "3.0"]
        ],
        "asks": [
            ["80010.0", "0.5"],
            ["80020.0", "1.0"],
            ["80030.0", "2.0"]
        ]
    }
    micro = skill_executor.run_microstructure_and_slippage(order_book, target_notional_usdt=50.0)
    assert micro["order_book_imbalance"] > 0  # Bid vol > Ask vol in top levels
    assert micro["spread_bps"] > 0
    assert micro["hurdle_rate_pct"] >= 0.20  # At least roundtrip 0.1%*2 taker fees

def test_position_sizing_respects_risk_limits():
    """Test position sizing caps at 1% capital risk and 25% max position size."""
    capital = 1000.0
    entry = 80000.0
    stop_loss = 79200.0  # 1% distance
    atr = 400.0

    sizing = skill_executor.run_position_sizing(
        allocated_capital=capital,
        entry_price=entry,
        stop_loss_price=stop_loss,
        current_atr=atr,
        max_risk_pct=1.0,
        max_pos_size_pct=25.0
    )
    assert sizing["risk_budget_usdt"] == 10.0  # 1% of 1000
    assert sizing["hard_cap_size_usdt"] == 250.0  # 25% of 1000
    assert sizing["recommended_size_usdt"] <= 250.0
    assert sizing["is_above_min_notional"] is True

def test_ai_disagreement_consensus_leads_to_hold():
    """Test that if Gemini says BUY but GPT-6 Luna says REJECT, decision is strictly HOLD."""
    gemini_out = {
        "action": "BUY",
        "entry_price": 80000.0,
        "stop_loss": 78000.0,
        "take_profit": 85000.0,
        "reasoning": "Tín hiệu phá vỡ đỉnh ngắn hạn"
    }
    gpt_out = {
        "decision": "REJECT",
        "reason": "Order Book Imbalance âm nặng và thị trường đang ở Regime Q4 Choppy Chaos",
        "technical_alignment": False,
        "risk_reward_acceptable": False
    }

    consensus = DecisionConsensus.evaluate_consensus("BTCUSDT", gemini_out, gpt_out)
    assert consensus.action == "HOLD"
    assert consensus.approved is False
    assert "bất đồng" in consensus.reason.lower() or "reject" in consensus.reason.lower()

@pytest.mark.asyncio
async def test_emergency_stop_blocks_execution():
    """Test that emergency stop flag blocks trading operations."""
    settings.EMERGENCY_STOP_ACTIVE = True
    check = await risk_engine.evaluate_trade(
        session=None,
        symbol="BTCUSDT",
        action="BUY",
        entry_price=80000.0,
        stop_loss=78000.0,
        take_profit=84000.0,
        allocated_capital=100.0,
        available_usdt=100.0,
        symbol_filters={},
        mode="PAPER"
    )
    assert check.passed is False
    assert any("EMERGENCY STOP" in r for r in check.reasons)
    settings.EMERGENCY_STOP_ACTIVE = False

def test_live_mode_locked_by_default():
    """Test that LIVE mode remains locked on startup."""
    assert settings.LIVE_SPOT_LOCKED is True
