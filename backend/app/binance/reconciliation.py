"""
State Reconciliation Engine
Cross-checks local database positions and orders against Binance exchange state.
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.binance.client import BinanceSpotClient
from app.database.models import Position, Order, AuditEvent
from app.database.session import record_audit

class ReconciliationEngine:
    def __init__(self, client: BinanceSpotClient):
        self.client = client

    async def reconcile_active_orders(self, session: AsyncSession, mode: str) -> Dict[str, Any]:
        """
        Check pending orders in database against Binance open orders.
        """
        if mode == "PAPER":
            return {"status": "skipped_in_paper_mode", "discrepancies": []}

        # Query all open/unfilled orders in database
        stmt = select(Order).where(
            Order.mode == mode,
            Order.status.in_(["NEW", "PARTIALLY_FILLED"])
        )
        result = await session.execute(stmt)
        local_orders = result.scalars().all()

        discrepancies: List[Dict[str, Any]] = []

        for ord_record in local_orders:
            try:
                exchange_order = await self.client.query_order(
                    symbol=ord_record.symbol,
                    orig_client_order_id=ord_record.client_order_id
                )
                ex_status = exchange_order.get("status")
                ex_exec_qty = exchange_order.get("executedQty")

                if ex_status and ex_status != ord_record.status:
                    discrepancies.append({
                        "client_order_id": ord_record.client_order_id,
                        "old_status": ord_record.status,
                        "new_status": ex_status,
                        "executed_qty": ex_exec_qty
                    })
                    ord_record.status = ex_status
                    if ex_exec_qty:
                        ord_record.executed_qty = float(ex_exec_qty)
            except Exception as e:
                discrepancies.append({
                    "client_order_id": ord_record.client_order_id,
                    "error": str(e)
                })

        if discrepancies:
            await session.commit()
            await record_audit(
                session=session,
                event_type="RECONCILIATION_SYNC",
                message=f"Đã đối soát {len(local_orders)} lệnh với sàn Binance ({len(discrepancies)} cập nhật).",
                level="INFO",
                details=discrepancies
            )

        return {
            "total_checked": len(local_orders),
            "discrepancies": discrepancies
        }
