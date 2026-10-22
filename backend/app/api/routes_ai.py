"""
AI Multi-Agent API Routes
Test AI Gateway connection, view debate logs, and trigger manual multi-agent analysis.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.ai.gateway import ai_gateway
from app.database.session import get_db
from app.database.models import AIAnalysisLog
from app.scheduler.controller import trading_controller

router = APIRouter(prefix="/api/ai", tags=["AI"])

@router.get("/test")
async def test_ai_connection():
    """Test both Gemini Analyst and GPT-6 Luna models via the single Gateway."""
    try:
        results = await ai_gateway.test_connection(
            gemini_model_id=settings.GEMINI_MODEL_ID,
            gpt_model_id=settings.GPT_MODEL_ID
        )
        return {"status": "COMPLETED", "results": results}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@router.get("/logs")
async def get_ai_analysis_logs(
    limit: int = Query(default=20),
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve structured debate and analysis logs between the two AI models."""
    stmt = select(AIAnalysisLog)
    if symbol:
        stmt = stmt.where(AIAnalysisLog.symbol == symbol)
    stmt = stmt.order_by(AIAnalysisLog.created_at.desc()).limit(limit)

    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "symbol": l.symbol,
            "timeframe": l.timeframe,
            "gemini_output": l.gemini_output,
            "gpt_output": l.gpt_output,
            "consensus_action": l.consensus_action,
            "execution_approved": l.execution_approved,
            "rejection_reason": l.rejection_reason,
            "gemini_latency_ms": l.gemini_latency_ms,
            "gpt_latency_ms": l.gpt_latency_ms,
            "total_tokens": l.total_tokens,
            "created_at": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]

@router.post("/analyze-now")
async def trigger_manual_analysis(
    symbol: str = Query(default="BTCUSDT"),
    db: AsyncSession = Depends(get_db)
):
    """Trigger an on-demand multi-agent decision cycle for a specific pair."""
    try:
        result = await trading_controller.decision_engine.execute_cycle(
            session=db,
            symbol=symbol,
            timeframe=settings.DEFAULT_TIMEFRAME,
            mode=trading_controller.mode
        )
        return {"status": "SUCCESS", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích đa tác nhân: {str(e)}")
