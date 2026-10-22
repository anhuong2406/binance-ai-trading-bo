"""
Binance Spot REST API Client
Fully typed, robust error handling, rate limiting, HMAC-SHA256 signing,
server time synchronization, and exchangeInfo filter caching.
"""
import hmac
import hashlib
import time
import asyncio
import urllib.parse
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN
import httpx
from app.config.settings import settings

class BinanceSpotClient:
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        use_testnet: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.use_testnet = use_testnet
        self.base_url = (
            settings.BINANCE_TESTNET_URL if use_testnet else settings.BINANCE_BASE_URL
        )
        self.time_offset_ms = 0
        self._exchange_info_cache: Dict[str, Any] = {}
        self._cache_time = 0

    def set_credentials(self, api_key: str, api_secret: str, use_testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.use_testnet = use_testnet
        self.base_url = (
            settings.BINANCE_TESTNET_URL if use_testnet else settings.BINANCE_BASE_URL
        )

    def _get_timestamp_ms(self) -> int:
        return int(time.time() * 1000) + self.time_offset_ms

    def _sign_query(self, params: Dict[str, Any]) -> str:
        """Sign request params with HMAC-SHA256 according to Binance API spec, returning query string."""
        if not self.api_secret:
            raise ValueError("Binance API Secret is required for signed endpoints.")
        
        params["timestamp"] = self._get_timestamp_ms()
        params["recvWindow"] = 5000
        
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.strip().encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    async def sync_server_time(self) -> int:
        """Synchronize local clock with Binance server time."""
        url = f"{self.base_url}/api/v3/time"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            server_time = data["serverTime"]
            local_time = int(time.time() * 1000)
            self.time_offset_ms = server_time - local_time
            return self.time_offset_ms

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        retries: int = 2
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        headers = {}
        params_dict = params.copy() if params else {}

        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key.strip()

        req_params = None
        if signed:
            signed_query = self._sign_query(params_dict)
            url = f"{url}?{signed_query}"
        else:
            req_params = params_dict if params_dict else None

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    if method.upper() == "GET":
                        resp = await client.get(url, params=req_params, headers=headers)
                    elif method.upper() == "POST":
                        resp = await client.post(url, params=req_params, headers=headers)
                    elif method.upper() == "DELETE":
                        resp = await client.delete(url, params=req_params, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method {method}")

                    # Detect rate limits
                    if resp.status_code in (429, 418):
                        retry_after = int(resp.headers.get("Retry-After", 10))
                        await asyncio.sleep(retry_after)
                        continue

                    # Server timestamp mismatch (-1021)
                    if resp.status_code == 400:
                        err_data = resp.json()
                        if err_data.get("code") == -1021 and attempt < retries:
                            await self.sync_server_time()
                            if signed:
                                signed_query = self._sign_query(params_dict)
                                url = f"{self.base_url}{endpoint}?{signed_query}"
                            continue

                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                if attempt == retries:
                    raise e
                await asyncio.sleep(1.0 * (2 ** attempt))
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries:
                    raise e
                await asyncio.sleep(1.0 * (2 ** attempt))

    async def test_connectivity(self) -> Dict[str, Any]:
        """Test ping and server time."""
        await self.sync_server_time()
        res = await self._request("GET", "/api/v3/ping")
        return {"status": "connected", "time_offset_ms": self.time_offset_ms}

    async def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch and cache exchange info including LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER."""
        now = time.time()
        if not self._exchange_info_cache or (now - self._cache_time) > 3600:
            params = {"symbol": symbol} if symbol else {}
            data = await self._request("GET", "/api/v3/exchangeInfo", params=params)
            self._exchange_info_cache = {s["symbol"]: s for s in data.get("symbols", [])}
            self._cache_time = now
        
        if symbol:
            return self._exchange_info_cache.get(symbol, {})
        return self._exchange_info_cache

    async def get_symbol_filters(self, symbol: str) -> Dict[str, Any]:
        """Extract exact filter criteria: minQty, maxQty, stepSize, minPrice, tickSize, minNotional."""
        info = await self.get_exchange_info(symbol)
        if not info:
            # Fallback direct query
            data = await self._request("GET", "/api/v3/exchangeInfo", params={"symbol": symbol})
            symbols = data.get("symbols", [])
            info = symbols[0] if symbols else {}
            if info:
                self._exchange_info_cache[symbol] = info

        filters = {f["filterType"]: f for f in info.get("filters", [])}
        
        lot_size = filters.get("LOT_SIZE", {})
        price_filter = filters.get("PRICE_FILTER", {})
        min_notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))

        return {
            "symbol": symbol,
            "status": info.get("status", "TRADING"),
            "baseAsset": info.get("baseAsset", ""),
            "quoteAsset": info.get("quoteAsset", ""),
            "minQty": Decimal(lot_size.get("minQty", "0.00001")),
            "maxQty": Decimal(lot_size.get("maxQty", "9000000")),
            "stepSize": Decimal(lot_size.get("stepSize", "0.00001")),
            "minPrice": Decimal(price_filter.get("minPrice", "0.01")),
            "maxPrice": Decimal(price_filter.get("maxPrice", "1000000")),
            "tickSize": Decimal(price_filter.get("tickSize", "0.01")),
            "minNotional": Decimal(min_notional.get("minNotional", min_notional.get("notional", "5.0"))),
        }

    async def get_account_information(self) -> Dict[str, Any]:
        """Fetch Spot account details (balances, permissions). Signed."""
        return await self._request("GET", "/api/v3/account", signed=True)

    async def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 100
    ) -> List[List[Any]]:
        """Fetch OHLCV candlestick data."""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return await self._request("GET", "/api/v3/klines", params=params)

    async def get_ticker_24hr(self, symbol: str) -> Dict[str, Any]:
        """Fetch 24hr ticker price change statistics."""
        return await self._request("GET", "/api/v3/ticker/24hr", params={"symbol": symbol})

    async def get_order_book(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """Fetch current order book depth."""
        return await self._request("GET", "/api/v3/depth", params={"symbol": symbol, "limit": limit})

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open orders."""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/api/v3/openOrders", params=params, signed=True)

    async def query_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query specific order by orderId or origClientOrderId."""
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return await self._request("GET", "/api/v3/order", params=params, signed=True)

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        new_client_order_id: Optional[str] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place SPOT order with strict clientOrderId tracking."""
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity),
        }
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id

        if order_type.upper() == "LIMIT":
            if not price:
                raise ValueError("Price is required for LIMIT order.")
            params["price"] = str(price)
            params["timeInForce"] = time_in_force

        return await self._request("POST", "/api/v3/order", params=params, signed=True)

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel an active order."""
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return await self._request("DELETE", "/api/v3/order", params=params, signed=True)
