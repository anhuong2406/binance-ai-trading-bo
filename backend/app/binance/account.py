"""
Binance Spot Account Manager
Read-only queries of available and locked Spot balances, calculating total portfolio equity.
"""
from typing import Dict, Any, List
from decimal import Decimal
from app.binance.client import BinanceSpotClient

class AccountManager:
    def __init__(self, client: BinanceSpotClient):
        self.client = client

    async def get_spot_balances(self) -> Dict[str, Any]:
        """Fetch Spot balances and calculate total USDT equivalent."""
        account_info = await self.client.get_account_information()
        raw_balances = account_info.get("balances", [])

        balances: List[Dict[str, Any]] = []
        total_usdt_value = Decimal("0.0")

        # Filter balances > 0
        non_zero = [
            b for b in raw_balances
            if Decimal(b.get("free", "0")) > 0 or Decimal(b.get("locked", "0")) > 0
        ]

        usdt_free = Decimal("0.0")
        usdt_locked = Decimal("0.0")

        for b in non_zero:
            asset = b["asset"]
            free = Decimal(b.get("free", "0"))
            locked = Decimal(b.get("locked", "0"))
            total = free + locked

            usdt_val = Decimal("0.0")
            if asset in ("USDT", "BUSD", "FDUSD", "USDC"):
                usdt_val = total
                if asset == "USDT":
                    usdt_free = free
                    usdt_locked = locked
            else:
                # Estimate USDT value using ticker price
                try:
                    ticker = await self.client.get_ticker_24hr(f"{asset}USDT")
                    price = Decimal(ticker.get("lastPrice", "0"))
                    usdt_val = total * price
                except Exception:
                    usdt_val = Decimal("0.0")

            total_usdt_value += usdt_val
            balances.append({
                "asset": asset,
                "free": float(free),
                "locked": float(locked),
                "total": float(total),
                "estimatedUsdt": float(usdt_val)
            })

        can_trade = account_info.get("canTrade", False)
        permissions = account_info.get("permissions", [])

        return {
            "canTrade": can_trade,
            "permissions": permissions,
            "totalEquityUsdt": float(total_usdt_value),
            "usdtFree": float(usdt_free),
            "usdtLocked": float(usdt_locked),
            "balances": balances
        }
