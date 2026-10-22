"""
Risk Control API Routes
View risk status, limits, and audit logs of risk engine evaluations.
"""
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.database.session import get_db, record_audit
from app.database.models import RiskEvaluation
from app.trading.risk_engine import risk_engine

router = APIRouter(prefix="/api/risk", tags=["Risk"])

class RiskConfigUpdate(BaseModel):
    max_risk_per_trade_percent: Optional[float] = None
    max_position_size_percent: Optional[float] = None
    daily_max_loss_percent: Optional[float] = None
    max_drawdown_percent: Optional[float] = None
    max_concurrent_positions: Optional[int] = None
    max_daily_entries: Optional[int] = None
    cooldown_minutes: Optional[int] = None

@router.get("/status")
async def get_risk_status(db: AsyncSession = Depends(get_db)):
    """Fetch current risk metrics and thresholds."""
    stat = await risk_engine.get_or_create_daily_stat(db, settings.BOT_ALLOCATED_CAPITAL_USDT)
    return {
        "allocated_capital": settings.BOT_ALLOCATED_CAPITAL_USDT,
        "max_risk_per_trade_percent": settings.MAX_RISK_PER_TRADE_PERCENT,
        "max_position_size_percent": settings.MAX_POSITION_SIZE_PERCENT,
        "daily_max_loss_percent": settings.DAILY_MAX_LOSS_PERCENT,
        "max_drawdown_percent": settings.MAX_DRAWDOWN_PERCENT,
        "max_concurrent_positions": settings.MAX_CONCURRENT_POSITIONS,
        "max_daily_entries": settings.MAX_DAILY_ENTRIES,
        "cooldown_minutes": settings.COOLDOWN_MINUTES,
        "current_drawdown_percent": stat.max_drawdown_percent,
        "today_trade_count": stat.trade_count,
        "today_loss_percent": ((stat.start_equity - stat.current_equity) / stat.start_equity * 100) if stat.start_equity > 0 else 0.0,
        "emergency_stop_active": settings.EMERGENCY_STOP_ACTIVE,
        "live_locked": settings.LIVE_SPOT_LOCKED
    }

@router.post("/config")
async def update_risk_config(req: RiskConfigUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update risk rules:
    Users can tighten rules, but cannot exceed safety ceilings!
    """
    if req.max_risk_per_trade_percent is not None:
        if req.max_risk_per_trade_percent > 3.0:
            raise HTTPException(status_code=400, detail="Rủi ro mỗi lệnh không được vượt quá 3.0% vốn bot.")
        settings.MAX_RISK_PER_TRADE_PERCENT = req.max_risk_per_trade_percent

    if req.max_position_size_percent is not None:
        if req.max_position_size_percent > 50.0:
            raise HTTPException(status_code=400, detail="Quy mô vị thế không được vượt quá 50% vốn bot.")
        settings.MAX_POSITION_SIZE_PERCENT = req.max_position_size_percent

    if req.daily_max_loss_percent is not None:
        if req.daily_max_loss_percent > 5.0:
            raise HTTPException(status_code=400, detail="Giới hạn lỗ trong ngày không được vượt quá 5.0%.")
        settings.DAILY_MAX_LOSS_PERCENT = req.daily_max_loss_percent

    if req.max_drawdown_percent is not None:
        if req.max_drawdown_percent > 10.0:
            raise HTTPException(status_code=400, detail="Giới hạn Drawdown tối đa không được vượt quá 10.0%.")
        settings.MAX_DRAWDOWN_PERCENT = req.max_drawdown_percent

    if req.max_concurrent_positions is not None:
        if req.max_concurrent_positions > 5:
            raise HTTPException(status_code=400, detail="Tối đa 5 vị thế đồng thời.")
        settings.MAX_CONCURRENT_POSITIONS = req.max_concurrent_positions

    if req.max_daily_entries is not None:
        settings.MAX_DAILY_ENTRIES = req.max_daily_entries

    if req.cooldown_minutes is not None:
        settings.COOLDOWN_MINUTES = req.cooldown_minutes

    await record_audit(db, "RISK_RULES_UPDATED", "Cập nhật tham số quản trị rủi ro", "WARNING")
    return {"status": "SUCCESS", "message": "Đã lưu cài đặt quản trị rủi ro mới"}

@router.get("/evaluations")
async def get_risk_evaluations(limit: int = 30, db: AsyncSession = Depends(get_db)):
    stmt = select(RiskEvaluation).order_by(RiskEvaluation.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "action": r.action,
            "proposed_entry": r.proposed_entry,
            "proposed_sl": r.proposed_sl,
            "proposed_tp": r.proposed_tp,
            "passed": r.passed,
            "rejection_reasons": r.rejection_reasons,
            "calculated_risk_percent": r.calculated_risk_percent,
            "calculated_position_size": r.calculated_position_size,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in records
    ]
