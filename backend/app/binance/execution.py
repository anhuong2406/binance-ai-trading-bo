"""
Execution Engine with Filter Validation & Idempotency Protection
Enforces LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL, and handles timeout recovery.
"""
import asyncio
import uuid
import time
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN
import httpx
from app.binance.client import BinanceSpotClient
from app.config.settings import settings

def round_step_size(quantity: Decimal, step_size: Decimal) -> Decimal:
    """Rounds down quantity strictly to the allowed stepSize."""
    precision = abs(step_size.as_tuple().exponent)
    # Quantize using step_size directly or decimal precision
    step_ratio = (quantity // step_size) * step_size
    return step_ratio.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

def round_tick_size(price: Decimal, tick_size: Decimal) -> Decimal:
    """Rounds down price strictly to allowed tickSize."""
    precision = abs(tick_size.as_tuple().exponent)
    price_ratio = (price // tick_size) * tick_size
    return price_ratio.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

class ExecutionEngine:
    def __init__(self, client: BinanceSpotClient):
        self.client = client

    def generate_client_order_id(self, prefix: str = "ABTC") -> str:
        """Generate unique idempotent clientOrderId."""
        unique_id = uuid.uuid4().hex[:12]
        ts = int(time.time() * 1000)
        return f"{prefix}_{ts}_{unique_id}"

    async def validate_and_format_order(
        self,
        symbol: str,
        side: str,
        raw_quantity: Decimal,
        raw_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Validates against Binance symbol filters."""
        filters = await self.client.get_symbol_filters(symbol)
        
        step_size = filters["stepSize"]
        min_qty = filters["minQty"]
        max_qty = filters["maxQty"]
        tick_size = filters["tickSize"]
        min_price = filters["minPrice"]
        max_price = filters["maxPrice"]
        min_notional = filters["minNotional"]

        qty = round_step_size(raw_quantity, step_size)
        if qty < min_qty:
            raise ValueError(
                f"Khối lượng {qty} nhỏ hơn mức tối thiểu cho phép {min_qty} của sàn ({symbol})"
            )
        if qty > max_qty:
            raise ValueError(
                f"Khối lượng {qty} vượt mức tối đa {max_qty} của sàn ({symbol})"
            )

        formatted_price = None
        if raw_price is not None:
            formatted_price = round_tick_size(raw_price, tick_size)
            if formatted_price < min_price or formatted_price > max_price:
                raise ValueError(
                    f"Giá {formatted_price} nằm ngoài khoảng cho phép [{min_price}, {max_price}] của sàn ({symbol})"
                )
            notional = qty * formatted_price
        else:
            # For MARKET orders, fetch latest ticker to estimate notional
            ticker = await self.client.get_ticker_24hr(symbol)
            est_price = Decimal(ticker.get("lastPrice", "0"))
            notional = qty * est_price

        if notional < min_notional:
            raise ValueError(
                f"Giá trị lệnh ({notional:.2f} USDT) nhỏ hơn yêu cầu tối thiểu MIN_NOTIONAL ({min_notional} USDT) của Binance ({symbol})"
            )

        return {
            "symbol": symbol,
            "side": side.upper(),
            "quantity": qty,
            "price": formatted_price,
            "notional": notional
        }

    async def execute_spot_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Executes order with timeout verification:
        If a timeout occurs during order placement, DO NOT blindly retry!
        Query by clientOrderId to check if order reached Binance.
        """
        validated = await self.validate_and_format_order(symbol, side, quantity, price)
        client_order_id = self.generate_client_order_id()

        try:
            resp = await self.client.create_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=validated["quantity"],
                price=validated["price"],
                new_client_order_id=client_order_id
            )
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            # A 4xx response is a definite exchange rejection. A timeout,
            # connection failure, or 5xx response can leave the order outcome
            # unknown, so reconcile by clientOrderId instead of replaying POST.
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise

            for _ in range(3):
                try:
                    reconciled = await self.client.query_order(
                        symbol=symbol,
                        orig_client_order_id=client_order_id
                    )
                    return reconciled
                except Exception:
                    await asyncio.sleep(1.5)

            # Still indeterminate: freeze any subsequent order placement.
            settings.EMERGENCY_STOP_ACTIVE = True
            raise RuntimeError(
                f"Không xác định được trạng thái lệnh {client_order_id} sau khi gửi tới Binance. "
                "Đã bật Emergency Stop để chặn lệnh mới; cần đối soát trên Binance trước khi mở lại."
            ) from exc
