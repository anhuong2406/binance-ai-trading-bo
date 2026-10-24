"""
AI Multi-Agent API Routes
Test AI Gateway connection, view debate logs, and trigger manual multi-agent analysis.
"""
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.ai.gateway import ai_gateway, AIGateway
from app.database.session import get_db
from app.database.models import AIAnalysisLog
from app.scheduler.controller import trading_controller

router = APIRouter(prefix="/api/ai", tags=["AI"])

class AITestRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    gpt_model_id: Optional[str] = None
    gemini_model_id: Optional[str] = None

@router.post("/test")
async def test_ai_connection_post(req: AITestRequest):
    """Test AI models directly with credentials passed from form or saved settings."""
    test_key = req.api_key or settings.AI_API_KEY
    test_base = req.base_url or settings.AI_BASE_URL
    gemini_id = req.gemini_model_id or settings.GEMINI_MODEL_ID
    gpt_id = req.gpt_model_id or settings.GPT_MODEL_ID

    if not test_key:
        return {
            "status": "ERROR",
            "results": {
                "gemini": {"status": "error", "error": "Chưa nhập AI API Key!"},
                "gpt": {"status": "error", "error": "Chưa nhập AI API Key!"}
            }
        }

    tester = AIGateway(base_url=test_base, api_key=test_key)
    try:
        results = await tester.test_connection(
            gemini_model_id=gemini_id,
            gpt_model_id=gpt_id
        )
        return {"status": "COMPLETED", "results": results}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@router.get("/test")
async def test_ai_connection():
    """Test both Gemini Analyst and GPT-6 Luna models via the saved Gateway settings."""
    if not settings.AI_API_KEY:
        return {
            "status": "ERROR",
            "results": {
                "gemini": {"status": "error", "error": "Chưa cấu hình AI API Key!"},
                "gpt": {"status": "error", "error": "Chưa cấu hình AI API Key!"}
            }
        }
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
            timeframe=(settings.SCALPING_TIMEFRAME if settings.SCALPING_MODE_ENABLED else settings.DEFAULT_TIMEFRAME),
            mode=trading_controller.mode
        )
        return {"status": "SUCCESS", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích đa tác nhân: {str(e)}")
