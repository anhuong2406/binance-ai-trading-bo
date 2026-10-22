"""
Binance Spot Data & Account API Routes
Read-only Spot balance fetching, 24hr tickers, candlestick data, and connection testing.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.scheduler.controller import trading_controller

router = APIRouter(prefix="/api/binance", tags=["Binance"])

@router.get("/test")
async def test_binance_connection():
    """Test ping and server time synchronization with Binance."""
    try:
        res = await trading_controller.binance_client.test_connectivity()
        return {"status": "SUCCESS", "details": res}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@router.get("/account")
async def get_spot_account():
    """Fetch Spot balances and portfolio summary."""
    try:
        acc = await trading_controller.decision_engine.account_manager.get_spot_balances()
        return {"status": "SUCCESS", "account": acc}
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Không thể lấy thông tin tài khoản: {str(e)}",
            "account": {
                "canTrade": False,
                "permissions": ["SPOT"],
                "totalEquityUsdt": 0.0,
                "usdtFree": 0.0,
                "usdtLocked": 0.0,
                "balances": []
            }
        }

@router.get("/klines")
async def get_klines(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="15m"),
    limit: int = Query(default=100)
):
    """Fetch OHLCV candlestick data formatted for lightweight-charts."""
    try:
        candles = await trading_controller.decision_engine.market_data.get_validated_candles(
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        return {"status": "SUCCESS", "candles": [c.to_dict() for c in candles]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi lấy dữ liệu nến: {str(e)}")

@router.get("/snapshot")
async def get_market_snapshot(symbol: str = Query(default="BTCUSDT")):
    """Get market snapshot including spread, bid, ask, and 24h stats."""
    try:
        snap = await trading_controller.decision_engine.market_data.get_market_snapshot(symbol)
        return {"status": "SUCCESS", "snapshot": snap}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/open-orders")
async def get_open_orders(symbol: Optional[str] = None):
    """Fetch open orders from Binance."""
    try:
        orders = await trading_controller.binance_client.get_open_orders(symbol)
        return {"status": "SUCCESS", "orders": orders}
    except Exception as e:
        return {"status": "ERROR", "message": str(e), "orders": []}
