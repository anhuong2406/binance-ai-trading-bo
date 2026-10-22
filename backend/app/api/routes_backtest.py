"""
Backtesting API Routes
Execute historical strategy backtests and retrieve performance reports.
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query
from app.trading.backtest import BacktestEngine
from app.trading.strategies import STRATEGY_MAP, ALL_STRATEGIES
from app.scheduler.controller import trading_controller

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])

class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    candle_limit: int = 500
    initial_capital: float = 1000.0

@router.get("/strategies")
async def list_available_strategies():
    """List all registered trading strategies."""
    return [
        {
            "name": s.name,
            "description": s.description
        }
        for s in ALL_STRATEGIES
    ]

@router.post("/run")
async def run_backtest(req: BacktestRequest):
    """Run historical backtest for a strategy on real candlestick data."""
    strategy = STRATEGY_MAP.get(req.strategy_name)
    if not strategy:
        raise HTTPException(status_code=400, detail=f"Không tìm thấy chiến lược '{req.strategy_name}'")

    # Fetch historical candles
    try:
        raw_candles = await trading_controller.decision_engine.market_data.get_validated_candles(
            symbol=req.symbol,
            interval=req.timeframe,
            limit=req.candle_limit
        )
        formatted_candles = [c.to_dict() for c in raw_candles]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tải dữ liệu nến: {str(e)}")

    engine = BacktestEngine(initial_capital=req.initial_capital)
    try:
        results = engine.run_backtest(strategy, req.symbol, formatted_candles)
        return {"status": "SUCCESS", "report": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi backtest: {str(e)}")
