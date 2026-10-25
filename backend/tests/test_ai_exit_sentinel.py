import pytest
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.trading.ai_exit_sentinel import AIExitSentinel
from app.database.models import Position


def test_detect_rapid_surge():
    sentinel = AIExitSentinel()
    pos = Position(
        id=101,
        symbol="DOGEUSDT",
        amount=Decimal("100"),
        entry_price=Decimal("0.0760"),
        current_price=Decimal("0.0768"),
        status="OPEN"
    )

    now = time.time()
    # Mock price history: 50s ago it was 0.0760, now it is 0.0768 (+1.05% in < 1m)
    sentinel._price_history[101] = [
        {"timestamp": now - 50, "price": 0.0760},
        {"timestamp": now - 10, "price": 0.0764},
    ]

    event = sentinel.detect_volatility_event(pos, current_price=0.0768)
    assert event is not None
    assert event["event_type"] == "RAPID_SURGE"
    assert event["current_pnl_pct"] > 0.8
    assert event["velocity_1m"] > 0.5


def test_detect_rapid_drop():
    sentinel = AIExitSentinel()
    pos = Position(
        id=102,
        symbol="BTCUSDT",
        amount=Decimal("0.01"),
        entry_price=Decimal("65000"),
        current_price=Decimal("64600"),
        status="OPEN"
    )

    now = time.time()
    # Mock price history: dropped from 65000 to 64600 (-0.61% in 40s)
    sentinel._price_history[102] = [
        {"timestamp": now - 40, "price": 65000.0},
        {"timestamp": now - 10, "price": 64800.0},
    ]

    event = sentinel.detect_volatility_event(pos, current_price=64600.0)
    assert event is not None
    assert event["event_type"] == "RAPID_DROP"
    assert event["current_pnl_pct"] < -0.4
    assert event["velocity_1m"] < -0.4


def test_cooldown_prevents_spam():
    sentinel = AIExitSentinel()
    now = time.time()
    sentinel._last_consultation[201] = {
        "timestamp": now - 20,  # 20 seconds ago (< 60s cooldown)
        "price": 0.0765,
        "decision": "HOLD"
    }

    event = {"event_type": "RAPID_SURGE", "velocity_1m": 0.6}
    # Price barely moved: 0.0765 -> 0.07652
    should_run = sentinel.should_consult_ai(201, current_price=0.07652, event=event)
    assert should_run is False

    # Price moved significantly: 0.0765 -> 0.0772 (+0.91%) -> bypass cooldown
    should_run_jump = sentinel.should_consult_ai(201, current_price=0.0772, event=event)
    assert should_run_jump is True


@pytest.mark.asyncio
async def test_evaluate_open_position_ai_recommends_exit(test_db):
    sentinel = AIExitSentinel()

    pos = Position(
        symbol="DOGEUSDT",
        amount=Decimal("100"),
        entry_price=Decimal("0.0760"),
        current_price=Decimal("0.0768"),
        status="OPEN",
        mode="PAPER"
    )
    test_db.add(pos)
    await test_db.commit()
    await test_db.refresh(pos)

    # Mock historical ticks
    now = time.time()
    sentinel._price_history[pos.id] = [
        {"timestamp": now - 45, "price": 0.0760}
    ]

    mock_ai_response = {
        "decision": "EXIT_NOW",
        "action": "SELL",
        "confidence": 0.9,
        "reason": "Áp lực bán lớn tại kháng cự ngắn hạn, chốt lời sớm +1.0%."
    }

    with patch.object(sentinel, "_query_ai_sentinel", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_ai_response

        action = await sentinel.evaluate_open_position(
            session=test_db,
            position=pos,
            current_price=Decimal("0.0768"),
            execution_engine=None  # Paper mode
        )

        assert action is not None
        assert action["action"] == "CLOSED"
        assert action["reason"] == "AI_SURGE_PROFIT_EXIT"
        assert "chốt lời sớm" in action["ai_reason"]

        await test_db.refresh(pos)
        assert pos.status == "CLOSED"
        assert pos.close_reason == "AI_SURGE_PROFIT_EXIT"
