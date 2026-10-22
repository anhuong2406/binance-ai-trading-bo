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

    # Get market price
    try:
        ticker = await trading_controller.binance_client.get_ticker_24hr(pos.symbol)
        price = Decimal(ticker.get("lastPrice", str(pos.current_price)))
    except Exception:
        price = pos.current_price

    exit_fee = pos.amount * price * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))

    closed = await PositionManager.close_position(
        session=db,
        position_id=pos.id,
        exit_price=price,
        exit_fee=exit_fee,
        reason="MANUAL_USER_CLOSE"
    )

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

    # Aggregate open positions unrealized PnL
    open_stmt = select(Position).where(
        Position.status == "OPEN",
        Position.mode == trading_controller.mode
    )
    open_res = await db.execute(open_stmt)
    open_positions = open_res.scalars().all()

    total_unrealized_pnl = sum(float(p.unrealized_pnl) for p in open_positions)
    total_realized_pnl = sum(d.daily_pnl for d in daily_stats)
    total_trades = sum(d.trade_count for d in daily_stats)
    total_wins = sum(d.win_count for d in daily_stats)
    total_losses = sum(d.loss_count for d in daily_stats)
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
