import pytest
from decimal import Decimal
from app.trading.trade_memory import TradeMemoryService
from app.database.session import AsyncSessionLocal
from app.database.models import Position, TradeMemory


def test_synthesize_lesson_win():
    memory_dict = TradeMemoryService.synthesize_lesson(
        symbol="BTCUSDT",
        outcome="WIN",
        pnl_pct=2.0,
        close_reason="TAKE_PROFIT_TRIGGERED",
        hold_minutes=45,
        entry_price=Decimal("50000"),
        exit_price=Decimal("51000")
    )
    assert memory_dict["strategy_tag"] == "take-profit-win"
    assert "Chốt lời thành công" in memory_dict["lesson"]
    assert "R:R" in memory_dict["recommendation"] or "kiên nhẫn" in memory_dict["recommendation"]


def test_synthesize_lesson_loss():
    memory_dict = TradeMemoryService.synthesize_lesson(
        symbol="ETHUSDT",
        outcome="LOSS",
        pnl_pct=-2.0,
        close_reason="STOP_LOSS_TRIGGERED",
        hold_minutes=120,
        entry_price=Decimal("2500"),
        exit_price=Decimal("2450")
    )
    assert memory_dict["strategy_tag"] == "disciplined-stoploss"
    assert "Cắt lỗ chuẩn kỷ luật" in memory_dict["lesson"]
    assert len(memory_dict["recommendation"]) > 10


@pytest.mark.asyncio
async def test_record_and_query_memory():
    async with AsyncSessionLocal() as session:
        # Create a mock position
        pos = Position(
            symbol="SOLUSDT",
            side="BUY",
            amount=Decimal("1.0"),
            entry_price=Decimal("150.0"),
            current_price=Decimal("155.0"),
            status="CLOSED",
            realized_pnl=Decimal("5.0"),
            realized_pnl_percent=3.33,
            total_fee=Decimal("0.1"),
            mode="PAPER",
            close_reason="TAKE_PROFIT_TRIGGERED"
        )
        session.add(pos)
        await session.commit()
        await session.refresh(pos)

        # Record trade experience
        mem = await TradeMemoryService.record_trade_experience(
            session=session,
            position=pos,
            exit_price=Decimal("155.0"),
            reason="TAKE_PROFIT_TRIGGERED"
        )
        assert mem is not None
        assert mem.outcome == "WIN"
        assert mem.symbol == "SOLUSDT"

        # Check prompt formatting
        prompt_snippet = await TradeMemoryService.format_lessons_for_ai_prompt(
            session=session,
            symbol="SOLUSDT",
            mode="PAPER"
        )
        assert "BÀI HỌC KINH NGHIỆM THỰC CHIẾN" in prompt_snippet
        assert "SOLUSDT" in prompt_snippet
