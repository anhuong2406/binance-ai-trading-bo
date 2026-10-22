"""
Trading Pairs Management API Routes
AI Binance Trading Company
Allows viewing, selecting, toggling, adding, and removing trading pairs.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from app.trading.pair_manager import pair_manager
from app.binance.client import BinanceSpotClient

router = APIRouter(prefix="/api/pairs", tags=["Trading Pairs"])

class TogglePairRequest(BaseModel):
    symbol: str
    enabled: bool

class AddPairRequest(BaseModel):
    symbol: str
    name: Optional[str] = None

@router.get("/list")
async def get_pairs_list():
    """Returns all configured pairs with live ticker prices and status."""
    pairs = pair_manager.get_all_pairs()
    active_symbols = pair_manager.get_active_symbols()

    # Try fetching real-time ticker prices for pairs
    client = BinanceSpotClient()
    enriched_pairs = []
    for p in pairs:
        pair_dict = dict(p)
        try:
            ticker = await client.get_ticker_24hr(p["symbol"])
            pair_dict["last_price"] = float(ticker.get("lastPrice", 0.0))
            pair_dict["price_change_percent"] = float(ticker.get("priceChangePercent", 0.0))
            pair_dict["high_price"] = float(ticker.get("highPrice", 0.0))
            pair_dict["low_price"] = float(ticker.get("lowPrice", 0.0))
            pair_dict["volume"] = float(ticker.get("volume", 0.0))
        except Exception:
            pair_dict["last_price"] = 0.0
            pair_dict["price_change_percent"] = 0.0

        enriched_pairs.append(pair_dict)

    return {
        "status": "SUCCESS",
        "pairs": enriched_pairs,
        "active_symbols": active_symbols,
        "total": len(pairs),
        "active_count": len(active_symbols)
    }

@router.post("/toggle")
async def toggle_pair(req: TogglePairRequest):
    """Enables or disables a trading pair for automated AI cycles."""
    symbol = req.symbol.upper().strip()
    try:
        success = pair_manager.toggle_pair(symbol, req.enabled)
        if not success:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy cặp {symbol} trong danh mục.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "SUCCESS",
        "symbol": symbol,
        "enabled": req.enabled,
        "active_symbols": pair_manager.get_active_symbols()
    }

@router.post("/add")
async def add_pair(req: AddPairRequest):
    """Validates against Binance Spot API and adds a new trading pair."""
    symbol = req.symbol.upper().strip()
    if not symbol.endswith("USDT"):
        symbol = f"{symbol}USDT"

    client = BinanceSpotClient()
    try:
        filters = await client.get_symbol_filters(symbol)
        if not filters:
            raise HTTPException(status_code=400, detail=f"Không tìm thấy cặp {symbol} trên sàn Binance Spot.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi kiểm tra cặp {symbol} trên Binance: {str(e)}")

    min_notional = float(filters.get("minNotional", 5.0))
    base_asset = symbol.replace("USDT", "")

    new_pair = pair_manager.add_pair(
        symbol=symbol,
        name=req.name or base_asset,
        min_notional=min_notional,
        base_asset=base_asset
    )

    return {
        "status": "SUCCESS",
        "message": f"Đã thêm thành công cặp {symbol} (Lệnh tối thiểu: {min_notional} USDT)",
        "pair": new_pair,
        "active_symbols": pair_manager.get_active_symbols()
    }

@router.delete("/{symbol}")
async def remove_pair(symbol: str):
    """Removes a trading pair from the catalog."""
    sym = symbol.upper().strip()
    try:
        success = pair_manager.remove_pair(sym)
        if not success:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy cặp {sym}.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "SUCCESS",
        "message": f"Đã xóa cặp {sym}",
        "active_symbols": pair_manager.get_active_symbols()
    }
