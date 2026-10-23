"""
Position Manager
Tracks open spot positions, triggers Stop Loss & Take Profit, updates PnL and daily stats.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Position, DailyStat
from app.config.settings import settings

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
        reason: str
    ) -> Position:
        stmt = select(Position).where(Position.id == position_id)
        result = await session.execute(stmt)
        pos = result.scalar_one_or_none()
        if not pos or pos.status != "OPEN":
            raise ValueError(f"Vị thế #{position_id} không tồn tại hoặc đã đóng.")

        existing_fee = pos.total_fee or Decimal("0.0")
        gross_pnl = (exit_price - pos.entry_price) * pos.amount
        net_pnl = gross_pnl - existing_fee - exit_fee
        invested = pos.entry_price * pos.amount
        pnl_pct = float(net_pnl / invested * 100) if invested > 0 else 0.0

        pos.current_price = exit_price
        pos.realized_pnl = net_pnl
        pos.realized_pnl_percent = pnl_pct
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
            stat.trade_count += 1
            if net_pnl > 0:
                stat.win_count += 1
            else:
                stat.loss_count += 1
            stat.daily_pnl += float(net_pnl)
            stat.total_fees += float(pos.total_fee)
            stat.current_equity += float(net_pnl)
            if stat.current_equity > stat.peak_equity:
                stat.peak_equity = stat.current_equity
            
            # Recalculate drawdown
            if stat.peak_equity > 0:
                dd = ((stat.peak_equity - stat.current_equity) / stat.peak_equity) * 100.0
                if dd > stat.max_drawdown_percent:
                    stat.max_drawdown_percent = dd

        await session.commit()
        await session.refresh(pos)
        return pos

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
                # In LIVE mode, execute real market sell on Binance
                if execution_engine and pos.mode == "LIVE":
                    try:
                        await execution_engine.execute_spot_order(
                            symbol=pos.symbol,
                            side="SELL",
                            order_type="MARKET",
                            quantity=pos.amount
                        )
                    except Exception:
                        pass

                # Trigger Stop Loss
                exit_fee = pos.amount * dec_price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
                closed = await cls.close_position(
                    session=session,
                    position_id=pos.id,
                    exit_price=dec_price,
                    exit_fee=exit_fee,
                    reason="STOP_LOSS_TRIGGERED"
                )
                actions_taken.append({
                    "action": "CLOSED",
                    "reason": "STOP_LOSS_TRIGGERED",
                    "position_id": closed.id,
                    "symbol": closed.symbol,
                    "pnl": float(closed.realized_pnl)
                })
                continue

            # Check Take Profit
            if pos.take_profit and dec_price >= pos.take_profit:
                # In LIVE mode, execute real market sell on Binance
                if execution_engine and pos.mode == "LIVE":
                    try:
                        await execution_engine.execute_spot_order(
                            symbol=pos.symbol,
                            side="SELL",
                            order_type="MARKET",
                            quantity=pos.amount
                        )
                    except Exception:
                        pass

                # Trigger Take Profit
                exit_fee = pos.amount * dec_price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
                closed = await cls.close_position(
                    session=session,
                    position_id=pos.id,
                    exit_price=dec_price,
                    exit_fee=exit_fee,
                    reason="TAKE_PROFIT_TRIGGERED"
                )
                actions_taken.append({
                    "action": "CLOSED",
                    "reason": "TAKE_PROFIT_TRIGGERED",
                    "position_id": closed.id,
                    "symbol": closed.symbol,
                    "pnl": float(closed.realized_pnl)
                })
                continue

        await session.commit()
        return actions_taken
