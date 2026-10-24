"""
Position Manager
Tracks open spot positions, triggers Stop Loss & Take Profit, updates PnL and daily stats.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Position, DailyStat
from app.config.settings import settings

logger = logging.getLogger("position_manager")

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class PositionManager:
    @classmethod
    async def open_position(
        cls,
        session: AsyncSession,
        symbol: str,
        amount: Decimal,
        entry_price: Decimal,
        stop_loss: Optional[Decimal],
        take_profit: Optional[Decimal],
        fee: Decimal,
        mode: str
    ) -> Position:
        pos = Position(
            symbol=symbol,
            side="BUY",
            amount=amount,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="OPEN",
            realized_pnl=Decimal("0.0"),
            realized_pnl_percent=0.0,
            unrealized_pnl=Decimal("0.0"),
            total_fee=fee,
            mode=mode,
            opened_at=utc_now()
        )
        session.add(pos)
        await session.commit()
        await session.refresh(pos)
        return pos

    @classmethod
    async def close_position(
        cls,
        session: AsyncSession,
        position_id: int,
        exit_price: Decimal,
        exit_fee: Decimal,
        reason: str,
        quantity: Optional[Decimal] = None
    ) -> Position:
        stmt = select(Position).where(Position.id == position_id)
        result = await session.execute(stmt)
        pos = result.scalar_one_or_none()
        if not pos or pos.status != "OPEN":
            raise ValueError(f"Vị thế #{position_id} không tồn tại hoặc đã đóng.")

        existing_amount = Decimal(pos.amount)
        amount_to_close = existing_amount if quantity is None else Decimal(quantity)
        if amount_to_close <= 0 or amount_to_close > existing_amount:
            raise ValueError("Khối lượng đóng vị thế không hợp lệ.")

        existing_fee = Decimal(pos.total_fee or 0)
        entry_fee_allocated = existing_fee * amount_to_close / existing_amount
        gross_pnl = (exit_price - pos.entry_price) * amount_to_close
        net_pnl = gross_pnl - entry_fee_allocated - exit_fee
        pnl_pct = float(net_pnl / (pos.entry_price * amount_to_close) * 100) if amount_to_close > 0 else 0.0

        pos.current_price = exit_price
        pos.realized_pnl = Decimal(pos.realized_pnl or 0) + net_pnl
        pos.realized_pnl_percent = pnl_pct
        pos.amount = existing_amount - amount_to_close
        pos.unrealized_pnl = (exit_price - pos.entry_price) * pos.amount
        pos.total_fee = existing_fee - entry_fee_allocated
        fully_closed = pos.amount == 0
        if fully_closed:
            pos.unrealized_pnl = Decimal("0.0")
            pos.total_fee = existing_fee + exit_fee
            pos.status = "CLOSED"
            pos.closed_at = utc_now()
        pos.close_reason = reason

        # Update daily stats
        today_str = utc_now().strftime("%Y-%m-%d")
        daily_stmt = select(DailyStat).where(DailyStat.date == today_str)
        daily_res = await session.execute(daily_stmt)
        stat = daily_res.scalar_one_or_none()

        if stat:
            stat.daily_pnl += float(net_pnl)
            stat.total_fees += float(entry_fee_allocated + exit_fee)
            stat.current_equity += float(net_pnl)
            if stat.current_equity > stat.peak_equity:
                stat.peak_equity = stat.current_equity

            if fully_closed:
                stat.trade_count += 1
                if pos.realized_pnl > 0:
                    stat.win_count += 1
                else:
                    stat.loss_count += 1
            
            # Recalculate drawdown
            if stat.peak_equity > 0:
                dd = ((stat.peak_equity - stat.current_equity) / stat.peak_equity) * 100.0
                if dd > stat.max_drawdown_percent:
                    stat.max_drawdown_percent = dd

        await session.commit()
        await session.refresh(pos)
        return pos

    @classmethod
    async def _execute_exit(
        cls,
        session: AsyncSession,
        position: Position,
        market_price: Decimal,
        reason: str,
        execution_engine: Any = None
    ) -> Optional[Position]:
        """Close only the quantity actually sold; keep the position open on failure."""
        quantity = Decimal(position.amount)
        exit_price = market_price

        if position.mode in ("LIVE", "TESTNET"):
            if execution_engine is None:
                logger.error("Thiếu execution engine khi đóng vị thế %s ở %s", position.symbol, position.mode)
                return None
            try:
                response = await execution_engine.execute_spot_order(
                    symbol=position.symbol,
                    side="SELL",
                    order_type="MARKET",
                    quantity=quantity
                )
            except Exception as e:
                logger.error("Lỗi gửi lệnh SELL %s trên Binance (%s): %s", reason, position.symbol, e)
                return None

            executed_qty = Decimal(str(response.get("executedQty", "0")))
            quote_qty = Decimal(str(response.get("cummulativeQuoteQty", "0")))
            if executed_qty <= 0:
                logger.error("Lệnh SELL %s chưa khớp (%s): %s", reason, position.symbol, response.get("status"))
                return None

            quantity = min(executed_qty, quantity)
            if quote_qty > 0:
                exit_price = quote_qty / executed_qty
                closed_quote = quote_qty * quantity / executed_qty
                exit_fee = closed_quote * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
            else:
                exit_fee = quantity * exit_price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
        else:
            exit_fee = quantity * exit_price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))

        return await cls.close_position(
            session=session,
            position_id=position.id,
            exit_price=exit_price,
            exit_fee=exit_fee,
            reason=reason,
            quantity=quantity
        )

    @classmethod
    async def update_active_positions(
        cls,
        session: AsyncSession,
        current_prices: Dict[str, float],
        mode: str,
        execution_engine: Any = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all open positions against latest market prices.
        Triggers SL / TP if breached. In LIVE mode, sends MARKET SELL to Binance.
        """
        stmt = select(Position).where(
            Position.status == "OPEN",
            Position.mode == mode
        )
        res = await session.execute(stmt)
        open_positions = res.scalars().all()

        actions_taken = []

        for pos in open_positions:
            price = current_prices.get(pos.symbol)
            if not price:
                continue

            dec_price = Decimal(str(price))
            pos.current_price = dec_price
            
            # Unrealized PnL
            unrealized = (dec_price - pos.entry_price) * pos.amount
            pos.unrealized_pnl = unrealized

            # Check Stop Loss
            if pos.stop_loss and dec_price <= pos.stop_loss:
                closed = await cls._execute_exit(
                    session=session,
                    position=pos,
                    market_price=dec_price,
                    reason="STOP_LOSS_TRIGGERED",
                    execution_engine=execution_engine
                )
                if closed is None:
                    continue
                actions_taken.append({
                    "action": "CLOSED" if closed.status == "CLOSED" else "PARTIALLY_CLOSED",
                    "reason": "STOP_LOSS_TRIGGERED",
                    "position_id": closed.id,
                    "symbol": closed.symbol,
                    "pnl": float(closed.realized_pnl)
                })
                continue

            # Check Take Profit
            if pos.take_profit and dec_price >= pos.take_profit:
                closed = await cls._execute_exit(
                    session=session,
                    position=pos,
                    market_price=dec_price,
                    reason="TAKE_PROFIT_TRIGGERED",
                    execution_engine=execution_engine
                )
                if closed is None:
                    continue
                actions_taken.append({
                    "action": "CLOSED" if closed.status == "CLOSED" else "PARTIALLY_CLOSED",
                    "reason": "TAKE_PROFIT_TRIGGERED",
                    "position_id": closed.id,
                    "symbol": closed.symbol,
                    "pnl": float(closed.realized_pnl)
                })
                continue

        await session.commit()
        return actions_taken
