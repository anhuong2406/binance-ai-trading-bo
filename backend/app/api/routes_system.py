"""
System & Safety API Routes
Emergency Stop, LIVE Mode Unlock, Mode Switching, Auditing, and App Configuration.
"""
from typing import Dict, Any, Optional
import math
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.database.session import get_db, record_audit
from app.database.models import AuditEvent, TradingSession, Position
from app.security.credentials import mask_secret
from app.scheduler.controller import trading_controller
from app.trading.pair_manager import pair_manager
from app.ai.gateway import ai_gateway

router = APIRouter(prefix="/api/system", tags=["System"])

class LiveUnlockRequest(BaseModel):
    confirmation_phrase: str
    allocated_capital: float

class ModeChangeRequest(BaseModel):
    mode: str  # PAPER, TESTNET, LIVE

class SettingsUpdateRequest(BaseModel):
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    gpt_model_id: Optional[str] = None
    gemini_model_id: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet_api_key: Optional[str] = None
    binance_testnet_api_secret: Optional[str] = None
    bot_allocated_capital: Optional[float] = None
    evaluation_interval_seconds: Optional[int] = None
    target_take_profit_percent: Optional[float] = None
    target_stop_loss_percent: Optional[float] = None
    scalping_mode_enabled: Optional[bool] = None
    ai_single_model_mode: Optional[bool] = None

@router.get("/status")
async def get_system_status():
    scalping = settings.SCALPING_MODE_ENABLED
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mode": trading_controller.mode,
        "bot_state": trading_controller.state,
        "is_running": trading_controller.is_running,
        "emergency_stop": settings.EMERGENCY_STOP_ACTIVE,
        "live_locked": settings.LIVE_SPOT_LOCKED,
        "allocated_capital": settings.BOT_ALLOCATED_CAPITAL_USDT,
        "active_pairs": pair_manager.get_active_symbols(),
        "timeframe": settings.SCALPING_TIMEFRAME if scalping else settings.DEFAULT_TIMEFRAME,
        "interval_seconds": settings.SCALPING_EVALUATION_INTERVAL_SECONDS if scalping else settings.EVALUATION_INTERVAL_SECONDS,
        "position_monitor_interval_seconds": settings.SCALPING_POSITION_MONITOR_INTERVAL_SECONDS if scalping else 15,
        "ai_single_model_mode": settings.AI_SINGLE_MODEL_MODE
    }

@router.post("/emergency-stop")
async def trigger_emergency_stop():
    result = await trading_controller.trigger_emergency_stop()
    return result

@router.post("/emergency-stop/reset")
async def reset_emergency_stop(db: AsyncSession = Depends(get_db)):
    await trading_controller.reset_emergency_stop()
    await record_audit(db, "EMERGENCY_STOP_RESET", "Đã mở khóa an toàn sau Emergency Stop", "WARNING")
    return {"status": "SUCCESS", "emergency_stop": False}

@router.post("/unlock-live")
async def unlock_live_mode(req: LiveUnlockRequest, db: AsyncSession = Depends(get_db)):
    """
    Unlocks LIVE SPOT mode safely:
    - User must explicitly type 'ENABLE LIVE SPOT'
    - Confirms capital allocated to bot
    """
    if req.confirmation_phrase != settings.LIVE_SPOT_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Cụm từ xác nhận không chính xác! Yêu cầu nhập đúng '{settings.LIVE_SPOT_CONFIRMATION_PHRASE}'"
        )

    if req.allocated_capital <= 0:
        raise HTTPException(status_code=400, detail="Vốn cấp cho bot phải lớn hơn 0 USDT.")

    settings.LIVE_SPOT_LOCKED = False
    settings.BOT_ALLOCATED_CAPITAL_USDT = req.allocated_capital

    await record_audit(
        db,
        "LIVE_MODE_UNLOCKED",
        f"Người dùng đã chủ động mở khóa LIVE SPOT với mức vốn bot {req.allocated_capital} USDT",
        "WARNING"
    )

    return {
        "status": "UNLOCKED",
        "live_locked": False,
        "allocated_capital": settings.BOT_ALLOCATED_CAPITAL_USDT
    }

@router.post("/lock-live")
async def lock_live_mode(db: AsyncSession = Depends(get_db)):
    settings.LIVE_SPOT_LOCKED = True
    if trading_controller.mode == "LIVE" and trading_controller.is_running:
        await trading_controller.stop()

    await record_audit(db, "LIVE_MODE_LOCKED", "Đã khóa an toàn chế độ LIVE SPOT", "INFO")
    return {"status": "LOCKED", "live_locked": True}

@router.post("/mode")
async def switch_trading_mode(req: ModeChangeRequest, db: AsyncSession = Depends(get_db)):
    target_mode = req.mode.upper()
    if target_mode not in ("PAPER", "TESTNET", "LIVE"):
        raise HTTPException(status_code=400, detail="Chế độ không hợp lệ (PAPER, TESTNET, LIVE)")

    if target_mode == "LIVE" and settings.LIVE_SPOT_LOCKED:
        raise HTTPException(
            status_code=403,
            detail="LIVE SPOT đang bị khóa. Bạn phải xác nhận mở khóa trước khi chuyển sang LIVE."
        )

    if target_mode != trading_controller.mode:
        open_position_stmt = select(Position.id).where(Position.status == "OPEN")
        open_position_id = (await db.execute(open_position_stmt)).scalars().first()
        if open_position_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Hãy đóng các vị thế đang mở trước khi chuyển chế độ giao dịch."
            )

    # Stop current bot if running before mode change
    if trading_controller.is_running:
        await trading_controller.stop()

    backend_dir = Path(__file__).resolve().parents[2]
    for env_path in (backend_dir / ".env", backend_dir.parent / ".env"):
        if env_path.is_file():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            updated_lines = []
            mode_written = False
            for line in lines:
                if line.startswith("TRADING_MODE=") or line.startswith("#TRADING_MODE="):
                    if not mode_written:
                        updated_lines.append(f"TRADING_MODE={target_mode}")
                        mode_written = True
                else:
                    updated_lines.append(line)
            if not mode_written:
                updated_lines.append(f"TRADING_MODE={target_mode}")
            env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    trading_controller.mode = target_mode
    settings.TRADING_MODE = target_mode
    trading_controller.binance_client.set_credentials(
        api_key=settings.BINANCE_TESTNET_API_KEY if target_mode == "TESTNET" else settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_TESTNET_API_SECRET if target_mode == "TESTNET" else settings.BINANCE_API_SECRET,
        use_testnet=(target_mode == "TESTNET")
    )

    await record_audit(db, "MODE_CHANGED", f"Chuyển chế độ giao dịch sang {target_mode}", "INFO")
    return {"status": "SUCCESS", "current_mode": target_mode}

@router.get("/settings")
async def get_settings():
    return {
        "ai_base_url": settings.AI_BASE_URL,
        "ai_api_key_masked": mask_secret(settings.AI_API_KEY),
        "gpt_model_id": settings.GPT_MODEL_ID,
        "gemini_model_id": settings.GEMINI_MODEL_ID,
        "binance_api_key_masked": mask_secret(settings.BINANCE_API_KEY),
        "binance_api_secret_masked": mask_secret(settings.BINANCE_API_SECRET),
        "binance_testnet_key_masked": mask_secret(settings.BINANCE_TESTNET_API_KEY),
        "bot_allocated_capital": settings.BOT_ALLOCATED_CAPITAL_USDT,
        "evaluation_interval_seconds": settings.EVALUATION_INTERVAL_SECONDS,
        "scalping_mode_enabled": settings.SCALPING_MODE_ENABLED,
        "scalping_timeframe": settings.SCALPING_TIMEFRAME,
        "scalping_evaluation_interval_seconds": settings.SCALPING_EVALUATION_INTERVAL_SECONDS,
        "scalping_position_monitor_interval_seconds": settings.SCALPING_POSITION_MONITOR_INTERVAL_SECONDS,
        "scalping_min_net_risk_reward": settings.SCALPING_MIN_NET_RISK_REWARD,
        "target_take_profit_percent": settings.TARGET_TAKE_PROFIT_PERCENT,
        "target_stop_loss_percent": settings.TARGET_STOP_LOSS_PERCENT,
        "ai_single_model_mode": settings.AI_SINGLE_MODEL_MODE,
        "max_risk_per_trade_percent": settings.MAX_RISK_PER_TRADE_PERCENT,
        "max_position_size_percent": settings.MAX_POSITION_SIZE_PERCENT,
        "daily_max_loss_percent": settings.DAILY_MAX_LOSS_PERCENT,
        "max_drawdown_percent": settings.MAX_DRAWDOWN_PERCENT
    }

@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest, db: AsyncSession = Depends(get_db)):
    for field_name, value in (
        ("Take Profit", req.target_take_profit_percent),
        ("Stop Loss", req.target_stop_loss_percent),
    ):
        if value is not None and (not math.isfinite(value) or value < 0.05 or value > 20):
            raise HTTPException(status_code=400, detail=f"{field_name} phải nằm trong khoảng 0.05% đến 20%.")

    if req.ai_base_url is not None:
        settings.AI_BASE_URL = req.ai_base_url
    if req.ai_api_key:
        settings.AI_API_KEY = req.ai_api_key
    if req.gpt_model_id is not None:
        settings.GPT_MODEL_ID = req.gpt_model_id
    if req.gemini_model_id is not None:
        settings.GEMINI_MODEL_ID = req.gemini_model_id
    if req.binance_api_key:
        settings.BINANCE_API_KEY = req.binance_api_key
    if req.binance_api_secret:
        settings.BINANCE_API_SECRET = req.binance_api_secret
    if req.binance_testnet_api_key:
        settings.BINANCE_TESTNET_API_KEY = req.binance_testnet_api_key
    if req.binance_testnet_api_secret:
        settings.BINANCE_TESTNET_API_SECRET = req.binance_testnet_api_secret
    if req.bot_allocated_capital is not None and req.bot_allocated_capital > 0:
        settings.BOT_ALLOCATED_CAPITAL_USDT = req.bot_allocated_capital
    if req.evaluation_interval_seconds is not None and req.evaluation_interval_seconds >= 30:
        settings.EVALUATION_INTERVAL_SECONDS = req.evaluation_interval_seconds
    if req.scalping_mode_enabled is not None:
        settings.SCALPING_MODE_ENABLED = req.scalping_mode_enabled
    if req.target_take_profit_percent is not None:
        settings.TARGET_TAKE_PROFIT_PERCENT = round(req.target_take_profit_percent, 2)
    if req.target_stop_loss_percent is not None:
        settings.TARGET_STOP_LOSS_PERCENT = round(req.target_stop_loss_percent, 2)
    if req.ai_single_model_mode is not None:
        settings.AI_SINGLE_MODEL_MODE = req.ai_single_model_mode

    # Update active client instances
    trading_controller.binance_client.set_credentials(
        api_key=settings.BINANCE_TESTNET_API_KEY if trading_controller.mode == "TESTNET" else settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_TESTNET_API_SECRET if trading_controller.mode == "TESTNET" else settings.BINANCE_API_SECRET,
        use_testnet=(trading_controller.mode == "TESTNET")
    )
    ai_gateway.update_config(base_url=settings.AI_BASE_URL, api_key=settings.AI_API_KEY)
    trading_controller.decision_engine.gemini_analyst.gateway.update_config(
        base_url=settings.AI_BASE_URL,
        api_key=settings.AI_API_KEY
    )
    trading_controller.decision_engine.gpt_reviewer.gateway.update_config(
        base_url=settings.AI_BASE_URL,
        api_key=settings.AI_API_KEY
    )

    # Persist updated values to .env files
    from pathlib import Path
    for p in [Path(".env"), Path("backend/.env"), Path("../.env")]:
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8")
                updates = {
                    "AI_BASE_URL": settings.AI_BASE_URL,
                    "AI_API_KEY": settings.AI_API_KEY,
                    "GPT_MODEL_ID": settings.GPT_MODEL_ID,
                    "GEMINI_MODEL_ID": settings.GEMINI_MODEL_ID,
                    "SCALPING_MODE_ENABLED": str(settings.SCALPING_MODE_ENABLED),
                    "TARGET_TAKE_PROFIT_PERCENT": str(settings.TARGET_TAKE_PROFIT_PERCENT),
                    "TARGET_STOP_LOSS_PERCENT": str(settings.TARGET_STOP_LOSS_PERCENT),
                    "AI_SINGLE_MODEL_MODE": str(settings.AI_SINGLE_MODEL_MODE).lower(),
                }
                lines = text.splitlines()
                new_lines = []
                handled = set()
                for line in lines:
                    replaced = False
                    for k, v in updates.items():
                        if line.startswith(f"{k}=") or line.startswith(f"#{k}="):
                            new_lines.append(f"{k}={v}")
                            handled.add(k)
                            replaced = True
                            break
                    if not replaced:
                        new_lines.append(line)
                p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception:
                pass

    trading_controller.refresh_schedule()
    await record_audit(db, "SETTINGS_UPDATED", "Cấu hình hệ thống đã được cập nhật thành công", "INFO")
    return {"status": "SUCCESS", "message": "Đã lưu cài đặt mới"}

@router.get("/audit-logs")
async def get_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "event_type": l.event_type,
            "level": l.level,
            "message": l.message,
            "details": l.details_json,
            "created_at": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]
