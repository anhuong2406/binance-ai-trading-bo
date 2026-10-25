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

        # Record trade experience and actionable lessons learned for AI
        if fully_closed:
            try:
                from app.trading.trade_memory import TradeMemoryService
                await TradeMemoryService.record_trade_experience(
                    session=session,
                    position=pos,
                    exit_price=exit_price,
                    reason=reason
                )
            except Exception as e:
                logger.error("Không thể ghi kinh nghiệm giao dịch cho #%s: %s", pos.id, e)

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
        """
        Close position via Spot and/or Binance Convert.
        Guarantees execution even with taker fee deduction, LOT_SIZE stepSize, or sub-5 USDT minNotional.
        """
        quantity = Decimal(position.amount)
        exit_price = market_price
        exit_fee = Decimal("0.0")

        if position.mode in ("LIVE", "TESTNET"):
            if execution_engine is None:
                logger.error("Thiếu execution engine khi đóng vị thế %s ở %s", position.symbol, position.mode)
                return None

            client = getattr(execution_engine, "client", None)
            base_asset = position.symbol[:-4] if position.symbol.endswith("USDT") else position.symbol

            # 1. Fetch exact free balance on Binance
            sell_qty = quantity
            if client:
                try:
                    acc = await client.get_account_information()
                    for b in acc.get("balances", []):
                        if b.get("asset") == base_asset:
                            free_bal = Decimal(str(b.get("free", "0")))
                            if free_bal > 0:
                                sell_qty = min(quantity, free_bal)
                            break
                except Exception as err:
                    logger.warning("Không thể lấy số dư %s trên Binance: %s", base_asset, err)

            total_quote_received = Decimal("0.0")
            total_qty_sold = Decimal("0.0")

            # 2. Check filters for spot order
            if client:
                try:
                    filters = await client.get_symbol_filters(position.symbol)
                    step_size = filters.get("stepSize", Decimal("0.0001"))
                    min_notional = filters.get("minNotional", Decimal("5.0"))
                    spot_qty = (sell_qty // step_size) * step_size

                    # Check if spot order is feasible
                    if spot_qty > 0 and (spot_qty * market_price) >= min_notional:
                        resp = await execution_engine.execute_spot_order(
                            symbol=position.symbol,
                            side="SELL",
                            order_type="MARKET",
                            quantity=spot_qty
                        )
                        exec_q = Decimal(str(resp.get("executedQty", "0")))
                        q_quote = Decimal(str(resp.get("cummulativeQuoteQty", "0")))
                        if exec_q > 0:
                            total_qty_sold += exec_q
                            total_quote_received += q_quote
                            exit_fee += q_quote * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
                except Exception as spot_err:
                    logger.warning("Lệnh Spot SELL tự động %s thất bại (%s): %s. Thử Binance Convert...", reason, position.symbol, spot_err)

            # 3. If spot failed or if there is remaining dust: use Binance Convert
            remaining_qty = sell_qty - total_qty_sold
            if remaining_qty > 0 and client:
                try:
                    conv_res = await client.convert_asset(
                        from_asset=base_asset,
                        to_asset="USDT",
                        from_amount=remaining_qty
                    )
                    conv_from = Decimal(str(conv_res.get("fromAmount", str(remaining_qty))))
                    conv_to = Decimal(str(conv_res.get("toAmount", "0")))
                    total_qty_sold += conv_from
                    total_quote_received += conv_to
                except Exception as conv_err:
                    logger.error("Binance Convert cũng thất bại (%s): %s", position.symbol, conv_err)

            if total_qty_sold <= 0:
                logger.error("Không thể đóng vị thế %s qua cả Spot và Convert.", position.symbol)
                return None

            exit_price = total_quote_received / total_qty_sold if total_qty_sold > 0 else market_price
        else:
            exit_fee = quantity * exit_price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))

        return await cls.close_position(
            session=session,
            position_id=position.id,
            exit_price=exit_price,
            exit_fee=exit_fee,
            reason=reason,
            quantity=Decimal(position.amount)
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

            # 3. AI Volatility Sentinel: Active Exit Analysis when price surges or drops rapidly
            if execution_engine:
                try:
                    from app.trading.ai_exit_sentinel import ai_exit_sentinel
                    ai_action = await ai_exit_sentinel.evaluate_open_position(
                        session=session,
                        position=pos,
                        current_price=dec_price,
                        execution_engine=execution_engine
                    )
                    if ai_action and ai_action.get("action") == "CLOSED":
                        actions_taken.append(ai_action)
                        continue
                except Exception as ai_err:
                    logger.warning("Lỗi AI Exit Sentinel cho vị thế #%s: %s", pos.id, ai_err)

        await session.commit()
        return actions_taken
