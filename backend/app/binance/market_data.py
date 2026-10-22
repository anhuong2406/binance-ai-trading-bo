"""
Market Data Engine
Processes OHLCV candles, checks timestamp freshness, validates spread and order book depth.
"""
import time
from typing import List, Dict, Any, Optional
from decimal import Decimal
from app.binance.client import BinanceSpotClient

class Candle:
    def __init__(
        self,
        open_time: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        close_time: int
    ):
        self.open_time = open_time
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.close_time = close_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": int(self.open_time / 1000),  # Seconds for lightweight-charts
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }

class MarketDataEngine:
    def __init__(self, client: BinanceSpotClient):
        self.client = client

    async def get_validated_candles(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 100
    ) -> List[Candle]:
        """Fetch and validate candlestick data."""
        raw_klines = await self.client.get_klines(symbol, interval=interval, limit=limit)
        if not raw_klines:
            raise ValueError(f"No candlestick data returned for {symbol}")

        candles: List[Candle] = []
        for k in raw_klines:
            candles.append(
                Candle(
                    open_time=int(k[0]),
                    open_=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                    close_time=int(k[6]),
                )
            )

        # Check freshness of latest candle
        latest_candle = candles[-1]
        now_ms = int(time.time() * 1000)
        # Parse interval in minutes
        interval_mins = 15
        if interval.endswith("m"):
            interval_mins = int(interval[:-1])
        elif interval.endswith("h"):
            interval_mins = int(interval[:-1]) * 60
        elif interval.endswith("d"):
            interval_mins = int(interval[:-1]) * 1440

        max_allowed_lag_ms = (interval_mins * 60 * 1000) * 3
        if now_ms - latest_candle.close_time > max_allowed_lag_ms:
            # Stale market data
            raise ValueError(
                f"Market data for {symbol} is stale. Last close time {latest_candle.close_time}, current {now_ms}"
            )

        return candles

    async def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get complete snapshot including bid/ask spread and 24h stats."""
        ticker = await self.client.get_ticker_24hr(symbol)
        order_book = await self.client.get_order_book(symbol, limit=5)

        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        best_bid = float(bids[0][0]) if bids else float(ticker.get("bidPrice", 0.0))
        best_ask = float(asks[0][0]) if asks else float(ticker.get("askPrice", 0.0))
        spread = best_ask - best_bid if best_ask and best_bid else 0.0
        spread_pct = (spread / best_ask * 100) if best_ask > 0 else 0.0

        return {
            "symbol": symbol,
            "lastPrice": float(ticker.get("lastPrice", 0.0)),
            "priceChangePercent": float(ticker.get("priceChangePercent", 0.0)),
            "highPrice": float(ticker.get("highPrice", 0.0)),
            "lowPrice": float(ticker.get("lowPrice", 0.0)),
            "volume": float(ticker.get("volume", 0.0)),
            "quoteVolume": float(ticker.get("quoteVolume", 0.0)),
            "bestBid": best_bid,
            "bestAsk": best_ask,
            "spread": spread,
            "spreadPercent": spread_pct,
            "timestamp": int(time.time() * 1000)
        }
