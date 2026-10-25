"""
Trading Operations API Routes
Start/Stop automated trading, positions list, manual close position, daily PnL stats.
"""
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.database.session import get_db, record_audit
from app.database.models import Position, Order, DailyStat
from app.trading.position_manager import PositionManager
from app.trading.trade_memory import TradeMemoryService
from app.trading.simulator import paper_simulator
from app.scheduler.controller import trading_controller

router = APIRouter(prefix="/api/trading", tags=["Trading"])

@router.post("/start")
async def start_auto_trading():
    """Start autonomous 24/7 trading."""
    try:
        await trading_controller.start()
        return {
            "status": "RUNNING",
            "mode": trading_controller.mode,
            "state": trading_controller.state
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stop")
async def stop_auto_trading():
    """Stop autonomous trading."""
    try:
        await trading_controller.stop()
        return {
            "status": "STOPPED",
            "state": trading_controller.state
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/positions")
async def get_positions(
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """List positions (open / closed)."""
    stmt = select(Position).where(Position.mode == trading_controller.mode)
    if status:
        stmt = stmt.where(Position.status == status.upper())
    stmt = stmt.order_by(Position.opened_at.desc())

    res = await db.execute(stmt)
    positions = res.scalars().all()
    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "side": p.side,
            "amount": float(p.amount),
            "entry_price": float(p.entry_price),
            "current_price": float(p.current_price),
            "stop_loss": float(p.stop_loss) if p.stop_loss else None,
            "take_profit": float(p.take_profit) if p.take_profit else None,
            "status": p.status,
            "realized_pnl": float(p.realized_pnl),
            "realized_pnl_percent": p.realized_pnl_percent,
            "unrealized_pnl": float(p.unrealized_pnl),
            "total_fee": float(p.total_fee),
            "mode": p.mode,
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            "close_reason": p.close_reason
        }
        for p in positions
    ]

@router.post("/positions/{position_id}/close")
async def close_position_manually(position_id: int, db: AsyncSession = Depends(get_db)):
    """User manually triggers market close of a specific position."""
    stmt = select(Position).where(Position.id == position_id)
    res = await db.execute(stmt)
    pos = res.scalar_one_or_none()
    if not pos or pos.status != "OPEN":
        raise HTTPException(status_code=404, detail="Vị thế không tồn tại hoặc đã đóng.")

    if pos.mode == "PAPER":
        try:
            ticker = await trading_controller.binance_client.get_ticker_24hr(pos.symbol)
            price = Decimal(ticker.get("lastPrice", str(pos.current_price)))
        except Exception:
            price = Decimal(pos.current_price)

        result = await paper_simulator.execute_paper_order(
            session=db,
            symbol=pos.symbol,
            side="SELL",
            quantity=Decimal(pos.amount),
            market_price=price
        )
        if result.get("status") != "FILLED":
            raise HTTPException(status_code=502, detail="Không thể đóng vị thế Paper.")
        price = Decimal(str(result["fill_price"]))
        await db.refresh(pos)
    elif pos.mode in ("LIVE", "TESTNET"):
        base_asset = pos.symbol[:-4] if pos.symbol.endswith("USDT") else pos.symbol
        try:
            free_bal = await trading_controller.decision_engine.account_manager.get_free_balance(base_asset)
            qty_to_sell = min(Decimal(pos.amount), free_bal) if free_bal > 0 else Decimal(pos.amount)
        except Exception:
            qty_to_sell = Decimal(pos.amount)

        used_convert = False
        try:
            result = await trading_controller.decision_engine.execution.execute_spot_order(
                symbol=pos.symbol,
                side="SELL",
                order_type="MARKET",
                quantity=qty_to_sell
            )
        except Exception as spot_err:
            # Fallback to Binance Convert when spot order fails (e.g. MIN_NOTIONAL < 5 USDT or LOT_SIZE)
            try:
                convert_res = await trading_controller.binance_client.convert_asset(
                    from_asset=base_asset,
                    to_asset="USDT",
                    from_amount=qty_to_sell
                )
                used_convert = True
                result = {
                    "orderId": convert_res.get("orderId"),
                    "clientOrderId": f"CONVERT_{convert_res.get('quoteId', pos.id)}",
                    "executedQty": str(convert_res.get("fromAmount", qty_to_sell)),
                    "cummulativeQuoteQty": str(convert_res.get("toAmount", "0")),
                    "status": "FILLED"
                }
            except Exception as conv_err:
                raise HTTPException(
                    status_code=502,
                    detail=f"Binance chưa xác nhận lệnh SELL (Spot: {spot_err} | Convert: {conv_err})"
                )

        executed_qty = Decimal(str(result.get("executedQty", "0")))
        quote_qty = Decimal(str(result.get("cummulativeQuoteQty", "0")))
        client_order_id = str(result.get("clientOrderId") or f"BINANCE_{result.get('orderId', pos.id)}")
        db.add(Order(
            client_order_id=client_order_id,
            exchange_order_id=str(result["orderId"]) if result.get("orderId") is not None else None,
            symbol=pos.symbol,
            side="SELL",
            order_type="MARKET",
            quantity=qty_to_sell,
            executed_qty=executed_qty,
            cummulative_quote_qty=quote_qty,
            status=str(result.get("status", "UNKNOWN")).upper(),
            mode=pos.mode
        ))
        if executed_qty <= 0:
            await db.commit()
            raise HTTPException(status_code=502, detail="Lệnh SELL chưa khớp; vị thế vẫn được giữ để tiếp tục theo dõi.")

        price = quote_qty / executed_qty if quote_qty > 0 else Decimal(pos.current_price)
        quantity_to_close = min(executed_qty, Decimal(pos.amount))
        quote_for_closed = quote_qty * quantity_to_close / executed_qty if quote_qty > 0 else price * quantity_to_close
        exit_fee = Decimal("0.0") if used_convert else quote_for_closed * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
        close_reason = "MANUAL_USER_CLOSE (Binance Convert)" if used_convert else "MANUAL_USER_CLOSE"
        closed = await PositionManager.close_position(
            session=db,
            position_id=pos.id,
            exit_price=price,
            exit_fee=exit_fee,
            reason=close_reason,
            quantity=quantity_to_close
        )
    else:
        raise HTTPException(status_code=400, detail=f"Chế độ giao dịch không hợp lệ: {pos.mode}")

    if pos.mode == "PAPER":
        closed = pos

    await record_audit(
        db,
        "MANUAL_POSITION_CLOSE",
        f"Người dùng đã chủ động đóng vị thế #{pos.id} ({pos.symbol}) tại giá {price} USDT",
        "INFO"
    )

    return {
        "status": "SUCCESS",
        "position_id": closed.id,
        "realized_pnl": float(closed.realized_pnl),
        "realized_pnl_percent": closed.realized_pnl_percent
    }

@router.get("/stats")
async def get_trading_stats(db: AsyncSession = Depends(get_db)):
    """Fetch daily and aggregate PnL stats."""
    stmt = select(DailyStat).order_by(DailyStat.date.desc()).limit(30)
    res = await db.execute(stmt)
    daily_stats = res.scalars().all()

    # Aggregate open positions unrealized PnL (Filtered by active Mode)
    open_stmt = select(Position).where(
        Position.status == "OPEN",
        Position.mode == trading_controller.mode
    )
    open_res = await db.execute(open_stmt)
    open_positions = open_res.scalars().all()

    # Aggregate closed positions realized PnL (Filtered by active Mode)
    closed_stmt = select(Position).where(
        Position.status == "CLOSED",
        Position.mode == trading_controller.mode
    )
    closed_res = await db.execute(closed_stmt)
    closed_positions = closed_res.scalars().all()

    total_unrealized_pnl = sum(float(p.unrealized_pnl or 0.0) for p in open_positions)
    total_realized_pnl = sum(float(p.realized_pnl or 0.0) for p in closed_positions)
    total_trades = len(closed_positions)
    total_wins = sum(1 for p in closed_positions if (p.realized_pnl or 0) > 0)
    total_losses = sum(1 for p in closed_positions if (p.realized_pnl or 0) <= 0)
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "open_positions_count": len(open_positions),
        "daily_history": [
            {
                "date": d.date,
                "daily_pnl": round(d.daily_pnl, 2),
                "peak_equity": round(d.peak_equity, 2),
                "current_equity": round(d.current_equity, 2),
                "max_drawdown_percent": round(d.max_drawdown_percent, 2),
                "trade_count": d.trade_count,
                "win_count": d.win_count,
                "loss_count": d.loss_count,
                "total_fees": round(d.total_fees, 2)
            }
            for d in daily_stats
        ]
    }


@router.get("/memories")
async def get_trade_memories(
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch structured trade memory and lessons learned for AI adaptive learning.
    """
    memories = await TradeMemoryService.get_recent_memories(
        session=db,
        symbol=symbol,
        mode=trading_controller.mode,
        limit=limit
    )
    win_count = sum(1 for m in memories if m.outcome == "WIN")
    loss_count = sum(1 for m in memories if m.outcome == "LOSS")
    total = len(memories)
    win_rate = (win_count / total * 100) if total > 0 else 0.0

    return {
        "status": "SUCCESS",
        "total_memories": total,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "memories": [
            {
                "id": m.id,
                "position_id": m.position_id,
                "symbol": m.symbol,
                "mode": m.mode,
                "outcome": m.outcome,
                "entry_price": float(m.entry_price),
                "exit_price": float(m.exit_price),
                "pnl_usd": float(m.pnl_usd),
                "pnl_percent": round(m.pnl_percent, 2),
                "hold_duration_minutes": m.hold_duration_minutes,
                "close_reason": m.close_reason,
                "strategy_tag": m.strategy_tag,
                "market_state": m.market_state,
                "lesson_learned": m.lesson_learned,
                "recommendation": m.recommendation,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in memories
        ]
    }

@router.post("/memories/sync")
async def sync_historical_trade_memories(db: AsyncSession = Depends(get_db)):
    """
    Backfills trade memory records for any existing closed positions.
    """
    count = await TradeMemoryService.seed_historical_positions(db)
    return {
        "status": "SUCCESS",
        "synced_count": count,
        "message": f"Đã đồng bộ {count} bài học kinh nghiệm từ lịch sử giao dịch."
    }

@router.get("/screener")
async def get_market_screener(
    force_refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns 2-stage market screening results and the #1 Best Pick suitable for available capital.
    """
    try:
        from app.trading.market_screener import market_screener
        capital = float(settings.BOT_ALLOCATED_CAPITAL_USDT)
        if trading_controller.mode in ("TESTNET", "LIVE"):
            try:
                acc = await trading_controller.decision_engine.account_manager.get_spot_balances()
                capital = float(acc.get("usdtFree", capital))
            except Exception:
                pass
        res = await market_screener.scan_market(
            capital_usdt=capital,
            session=db,
            force_refresh=force_refresh
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/screener/scan")
async def trigger_market_scan(db: AsyncSession = Depends(get_db)):
    """
    Forces an immediate fresh market screening cycle and returns ranked candidates.
    """
    try:
        from app.trading.market_screener import market_screener
        capital = float(settings.BOT_ALLOCATED_CAPITAL_USDT)
        if trading_controller.mode in ("TESTNET", "LIVE"):
            try:
                acc = await trading_controller.decision_engine.account_manager.get_spot_balances()
                capital = float(acc.get("usdtFree", capital))
            except Exception:
                pass
        res = await market_screener.scan_market(
            capital_usdt=capital,
            session=db,
            force_refresh=True
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

