"""
Paper Trading Simulator
Simulates order fills, slippage (0.05%), Binance taker fee (0.1%), and updates database.
Strictly isolated from real trading credentials.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import settings
from app.database.models import Order, Position
from app.trading.position_manager import PositionManager

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class PaperSimulator:
    def __init__(self, initial_capital: float = 100.0):
        self.capital = initial_capital
        self.slippage = Decimal(str(settings.SLIPPAGE_ESTIMATE_PERCENT / 100.0))
        self.fee_rate = Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))

    def simulate_fill_price(self, target_price: Decimal, side: str) -> Decimal:
        """Add slippage to target price (higher for BUY, lower for SELL)."""
        if side.upper() == "BUY":
            return target_price * (Decimal("1.0") + self.slippage)
        else:
            return target_price * (Decimal("1.0") - self.slippage)

    async def execute_paper_order(
        self,
        session: AsyncSession,
        symbol: str,
        side: str,
        quantity: Decimal,
        market_price: Decimal,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Executes simulated paper order."""
        fill_price = self.simulate_fill_price(market_price, side)
        notional = fill_price * quantity
        fee = notional * self.fee_rate

        client_order_id = f"PAPER_{int(utc_now().timestamp()*1000)}"

        # Record Order
        ord_rec = Order(
            client_order_id=client_order_id,
            exchange_order_id=f"SIM_{client_order_id}",
            symbol=symbol,
            side=side.upper(),
            order_type="MARKET",
            price=fill_price,
            quantity=quantity,
            executed_qty=quantity,
            cummulative_quote_qty=notional,
            status="FILLED",
            mode="PAPER"
        )
        session.add(ord_rec)

        position = None
        if side.upper() == "BUY":
            position = await PositionManager.open_position(
                session=session,
                symbol=symbol,
                amount=quantity,
                entry_price=fill_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                fee=fee,
                mode="PAPER"
            )

        await session.commit()

        return {
            "status": "FILLED",
            "client_order_id": client_order_id,
            "fill_price": float(fill_price),
            "quantity": float(quantity),
            "fee": float(fee),
            "position_id": position.id if position else None
        }

paper_simulator = PaperSimulator()
