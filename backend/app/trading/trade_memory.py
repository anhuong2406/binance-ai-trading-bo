"""
Trade Memory & Adaptive Learning Engine
Records profit/loss outcomes of every closed trade, extracts systematic lessons learned,
and injects relevant historical insights into future AI prompts so the bot adapts and improves.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.models import Position, TradeMemory

logger = logging.getLogger("trade_memory")

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class TradeMemoryService:
    @classmethod
    def synthesize_lesson(
        cls,
        symbol: str,
        outcome: str,
        pnl_pct: float,
        close_reason: str,
        hold_minutes: int,
        entry_price: Decimal,
        exit_price: Decimal
    ) -> Dict[str, str]:
        """
        Synthesizes an actionable quantitative lesson and forward-looking recommendation
        based on the trade's outcome and exit circumstances.
        """
        reason_upper = (close_reason or "").upper()

        if outcome == "WIN":
            if "AI_SURGE_PROFIT" in reason_upper:
                lesson = (
                    f"Chốt lời chủ động theo AI +{pnl_pct:.2f}% khi giá tăng nhanh. "
                    f"AI phát hiện đà tăng suy kiệt và khóa lợi nhuận kịp thời trước khi thị trường đảo chiều."
                )
                recommendation = (
                    f"Chiến lược chốt lời chủ động khi giá tăng nhanh hoạt động rất hiệu quả cho {symbol}. "
                    f"Tiếp tục bảo toàn lợi nhuận sớm khi nến xuất hiện râu trên dài hoặc lực mua cạn kiệt."
                )
                tag = "ai-volatility-profit"
            elif "TAKE_PROFIT" in reason_upper:
                lesson = (
                    f"Chốt lời thành công +{pnl_pct:.2f}% sau {hold_minutes} phút. "
                    f"Điểm vào tại {entry_price} khớp nhịp hồi kỹ thuật và chạm mục tiêu TP {exit_price} đúng kế hoạch."
                )
                recommendation = (
                    f"Setup này hoạt động rất hiệu quả cho {symbol}. Khi phát hiện cấu trúc nến tương tự "
                    f"(quá bán/phân kỳ/chạm hỗ trợ), ưu tiên giữ nguyên tỷ lệ R:R và kiên nhẫn để lệnh chạm TP tự động."
                )
                tag = "take-profit-win"
            else:
                lesson = (
                    f"Đóng vị thế có lãi +{pnl_pct:.2f}% ({close_reason}). "
                    f"Thanh lý thành công và chốt lợi nhuận kịp thời trước khi thị trường đảo chiều."
                )
                recommendation = (
                    f"Bảo toàn vốn tốt cho {symbol}. Đối với các vị thế có lãi sớm, cân nhắc nâng Stop Loss về Entry "
                    f"(Breakeven) để vừa gồng lãi vừa loại trừ rủi ro quay đầu."
                )
                tag = "manual-win"
        elif outcome == "LOSS":
            if "AI_RAPID_DROP" in reason_upper:
                lesson = (
                    f"Cắt lỗ sớm chủ động theo AI {pnl_pct:.2f}% khi giá giảm nhanh. "
                    f"AI phát hiện áp lực bán tháo bất thường và thoát lệnh trước khi chạm Stop Loss sâu hơn."
                )
                recommendation = (
                    f"Thoát hiểm bảo vệ vốn tốt cho {symbol}. Tiếp tục giữ kỷ luật cắt lỗ sớm khi AI cảnh báo rủi ro xả mạnh."
                )
                tag = "ai-rapid-drop-cut"
            elif "STOP_LOSS" in reason_upper:
                lesson = (
                    f"Cắt lỗ chuẩn kỷ luật {pnl_pct:.2f}% tại giá {exit_price}. "
                    f"Thị trường phá vỡ đáy hỗ trợ gần nhất, Stop Loss đã kích hoạt kịp thời để chặn đà lỗ sâu."
                )
                recommendation = (
                    f"Khi {symbol} đang chịu áp lực bán lớn, tránh bắt đáy quá sớm ngay cả khi RSI quá bán. "
                    f"Bắt buộc đợi có nến 5m đảo chiều xanh xác nhận (rút chân/pinbar) hoặc MACD cắt lên trước khi mở BUY."
                )
                tag = "disciplined-stoploss"
            else:
                lesson = (
                    f"Thoát lệnh lỗ nhẹ {pnl_pct:.2f}% do {close_reason}. "
                    f"Cắt giảm rủi ro sớm khi thị trường suy yếu hoặc cấu trúc sóng mất hiệu lực."
                )
                recommendation = (
                    f"Kiểm tra kỹ khối lượng giao dịch và xu hướng khung 1h của {symbol} trước khi vào lệnh. "
                    f"Nếu khung lớn đang giảm mạnh, chỉ vào lệnh khi biên độ phục hồi tiềm năng đủ bù đắp phí sàn 0.2%."
                )
                tag = "risk-mitigation-loss"
        else:
            lesson = f"Lệnh hòa vốn ({pnl_pct:.2f}%). Thoát vị thế an toàn tại {exit_price}."
            recommendation = f"Kiên nhẫn chờ đợi tín hiệu rõ nét hơn từ thị trường."
            tag = "breakeven"

        return {
            "lesson": lesson,
            "recommendation": recommendation,
            "strategy_tag": tag
        }

    @classmethod
    async def record_trade_experience(
        cls,
        session: AsyncSession,
        position: Position,
        exit_price: Decimal,
        reason: str,
        market_state: Optional[str] = None
    ) -> Optional[TradeMemory]:
        """
        Records a newly closed position into the trade memory database.
        """
        try:
            pnl_pct = float(position.realized_pnl_percent or 0.0)
            pnl_usd = Decimal(str(position.realized_pnl or 0.0))

            if pnl_pct > 0.1:
                outcome = "WIN"
            elif pnl_pct < -0.1:
                outcome = "LOSS"
            else:
                outcome = "BREAKEVEN"

            hold_minutes = 0
            if position.opened_at and position.closed_at:
                hold_minutes = max(1, int((position.closed_at - position.opened_at).total_seconds() / 60))

            synthesis = cls.synthesize_lesson(
                symbol=position.symbol,
                outcome=outcome,
                pnl_pct=pnl_pct,
                close_reason=reason or position.close_reason,
                hold_minutes=hold_minutes,
                entry_price=position.entry_price,
                exit_price=exit_price
            )

            memory = TradeMemory(
                position_id=position.id,
                symbol=position.symbol,
                side=position.side or "BUY",
                mode=position.mode or "LIVE",
                outcome=outcome,
                entry_price=position.entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                pnl_percent=pnl_pct,
                hold_duration_minutes=hold_minutes,
                close_reason=reason or position.close_reason,
                strategy_tag=synthesis["strategy_tag"],
                market_state=market_state or ("OVERSOLD_BOUNCE" if outcome == "WIN" else "TRENDING_DOWN"),
                lesson_learned=synthesis["lesson"],
                recommendation=synthesis["recommendation"],
                created_at=utc_now()
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            logger.info("Đã ghi lại kinh nghiệm giao dịch cho vị thế #%s (%s: %s %.2f%%)", position.id, position.symbol, outcome, pnl_pct)
            return memory
        except Exception as e:
            logger.error("Lỗi ghi nhận kinh nghiệm giao dịch cho vị thế #%s: %s", getattr(position, "id", "?"), e)
            return None

    @classmethod
    async def get_recent_memories(
        cls,
        session: AsyncSession,
        symbol: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 10
    ) -> List[TradeMemory]:
        """Query recent trade memories."""
        stmt = select(TradeMemory)
        if symbol:
            stmt = stmt.where(TradeMemory.symbol == symbol)
        if mode:
            stmt = stmt.where(TradeMemory.mode == mode)
        stmt = stmt.order_by(desc(TradeMemory.created_at)).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def format_lessons_for_ai_prompt(
        cls,
        session: AsyncSession,
        symbol: str,
        mode: str = "LIVE"
    ) -> str:
        """
        Formats past trading lessons into a structured instruction block
        to be injected into Gemini / GPT analysis prompts.
        """
        # 1. Fetch past trades for this specific symbol
        symbol_stmt = select(TradeMemory).where(
            TradeMemory.symbol == symbol,
            TradeMemory.mode == mode
        ).order_by(desc(TradeMemory.created_at)).limit(3)
        res_sym = await session.execute(symbol_stmt)
        symbol_memories = list(res_sym.scalars().all())

        # 2. Fetch other recent trades across all symbols
        recent_stmt = select(TradeMemory).where(
            TradeMemory.mode == mode
        ).order_by(desc(TradeMemory.created_at)).limit(3)
        res_recent = await session.execute(recent_stmt)
        recent_memories = [m for m in res_recent.scalars().all() if m not in symbol_memories]

        all_memories = (symbol_memories + recent_memories)[:4]
        if not all_memories:
            return ""

        lines = [
            f"[BÀI HỌC KINH NGHIỆM THỰC CHIẾN TỪ CÁC LỆNH TRƯỚC (TRADE MEMORY & LEARNING)]:"
        ]
        for idx, m in enumerate(all_memories, 1):
            badge = "THẮNG" if m.outcome == "WIN" else ("THUA" if m.outcome == "LOSS" else "HÒA")
            lines.append(
                f"{idx}. {m.symbol} ({badge} {m.pnl_percent:+.2f}% | Vào: {m.entry_price} -> Thoát: {m.exit_price}):\n"
                f"   - Bài học: {m.lesson_learned}\n"
                f"   - Khuyến nghị ứng dụng: {m.recommendation}"
            )

        lines.append(
            "\n-> YÊU CẦU ĐỐI VỚI BẠN:\n"
            "   Hãy vận dụng các bài học kinh nghiệm trên vào tình huống thị trường hiện tại. "
            "   Nếu phát hiện các dấu hiệu từng dẫn đến thua lỗ (như nến chưa xác nhận, ngược xu hướng 1h), HÃY CHỌN 'HOLD'. "
            "   Chỉ đề xuất 'BUY' khi cấu trúc thị trường khớp với các bài học chiến thắng hoặc có tỷ lệ R:R ròng vượt trội."
        )
        return "\n".join(lines)

    @classmethod
    async def seed_historical_positions(cls, session: AsyncSession) -> int:
        """
        One-time backfill of lessons for all existing closed positions.
        """
        stmt = select(Position).where(Position.status == "CLOSED").order_by(Position.id.asc())
        res = await session.execute(stmt)
        closed_positions = res.scalars().all()

        seeded_count = 0
        for pos in closed_positions:
            # Check if memory already exists
            check_stmt = select(TradeMemory).where(TradeMemory.position_id == pos.id)
            check_res = await session.execute(check_stmt)
            if check_res.scalar_one_or_none():
                continue

            exit_price = pos.current_price or pos.entry_price
            await cls.record_trade_experience(
                session=session,
                position=pos,
                exit_price=exit_price,
                reason=pos.close_reason or "MANUAL_OR_SYSTEM_EXIT"
            )
            seeded_count += 1

        return seeded_count
