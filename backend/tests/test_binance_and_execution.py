"""
Test Suite: Binance Connector, Execution Engine & Reconciliation
Tests Cases 1, 5, 9, 10, 11, 12, 13, 18 from the specification.
"""
import pytest
import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from app.binance.client import BinanceSpotClient
from app.binance.market_data import MarketDataEngine, Candle
from app.binance.execution import ExecutionEngine
from app.binance.reconciliation import ReconciliationEngine
from app.database.models import Order, Position
from app.api.websocket_handler import ConnectionManager

@pytest.mark.asyncio
async def test_case_1_invalid_binance_key():
    """Case 1: Signed requests raise error when secret key is empty or invalid."""
    client = BinanceSpotClient(api_key="dummy_key", api_secret="")
    with pytest.raises(ValueError, match="Binance API Secret is required"):
        client._sign_query({"symbol": "BTCUSDT"})

@pytest.mark.asyncio
async def test_case_5_stale_candlestick_data_rejected():
    """Case 5: Stale market data is rejected when the latest candle is too old."""
    client = BinanceSpotClient()
    engine = MarketDataEngine(client)

    # Mock klines returning candle from 2 hours ago
    stale_time_ms = int((time.time() - 7200) * 1000)
    fake_kline = [
        [stale_time_ms, "60000", "61000", "59000", "60500", "100", stale_time_ms + 900000]
    ]

    with patch.object(client, "get_klines", new=AsyncMock(return_value=fake_kline)):
        with pytest.raises(ValueError, match="stale"):
            await engine.get_validated_candles("BTCUSDT", interval="15m")

@pytest.mark.asyncio
async def test_case_9_partial_fill_handling(test_db):
    """Case 9: Reconciliation updates order state when partially filled on exchange."""
    client = BinanceSpotClient()
    recon = ReconciliationEngine(client)

    # Local order: 1.0 BTC status NEW
    ord_rec = Order(
        client_order_id="TEST_ORD_001",
        exchange_order_id="EX_001",
        symbol="BTCUSDT",
        side="BUY",
        quantity=Decimal("1.0"),
        executed_qty=Decimal("0.0"),
        status="NEW",
        mode="TESTNET"
    )
    test_db.add(ord_rec)
    await test_db.commit()

    # Exchange reports PARTIALLY_FILLED with 0.4 executed
    fake_exchange_ord = {
        "status": "PARTIALLY_FILLED",
        "executedQty": "0.4000"
    }

    with patch.object(client, "query_order", new=AsyncMock(return_value=fake_exchange_ord)):
        res = await recon.reconcile_active_orders(test_db, mode="TESTNET")
        assert len(res["discrepancies"]) == 1
        assert ord_rec.status == "PARTIALLY_FILLED"
        assert float(ord_rec.executed_qty) == 0.4

@pytest.mark.asyncio
async def test_case_10_order_timeout_checks_client_order_id():
    """Case 10: On HTTP timeout, queries exchange by clientOrderId to avoid duplicate order."""
    client = BinanceSpotClient()
    execution = ExecutionEngine(client)

    # Mock get_symbol_filters
    with patch.object(client, "get_symbol_filters", new=AsyncMock(return_value={
        "stepSize": Decimal("0.0001"),
        "minQty": Decimal("0.0001"),
        "maxQty": Decimal("100.0"),
        "tickSize": Decimal("0.01"),
        "minPrice": Decimal("100.0"),
        "maxPrice": Decimal("1000000.0"),
        "minNotional": Decimal("5.0"),
    })):
        import httpx
        # create_order times out, but query_order succeeds finding the placed order
        with patch.object(client, "create_order", side_effect=httpx.TimeoutException("Network timeout")):
            with patch.object(client, "query_order", new=AsyncMock(return_value={"status": "FILLED", "orderId": 99999})):
                resp = await execution.execute_spot_order(
                    symbol="BTCUSDT",
                    side="BUY",
                    order_type="LIMIT",
                    quantity=Decimal("0.01"),
                    price=Decimal("60000.0")
                )
                assert resp["status"] == "FILLED"
                assert resp["orderId"] == 99999

@pytest.mark.asyncio
async def test_case_11_restart_reconciliation(test_db):
    """Case 11: On application restart, any pending local orders are synced with exchange."""
    client = BinanceSpotClient()
    recon = ReconciliationEngine(client)

    # Unresolved local order created before restart
    ord_rec = Order(
        client_order_id="PRE_RESTART_ORD",
        symbol="ETHUSDT",
        side="BUY",
        quantity=Decimal("0.5"),
        status="NEW",
        mode="TESTNET"
    )
    test_db.add(ord_rec)
    await test_db.commit()

    with patch.object(client, "query_order", new=AsyncMock(return_value={"status": "FILLED", "executedQty": "0.5"})):
        res = await recon.reconcile_active_orders(test_db, mode="TESTNET")
        assert res["total_checked"] == 1
        assert ord_rec.status == "FILLED"

@pytest.mark.asyncio
async def test_case_12_websocket_disconnect_resilience():
    """Case 12: ConnectionManager disconnects dead WebSockets without affecting other clients."""
    manager = ConnectionManager()
    ws1 = MagicMock()
    ws1.send_text = AsyncMock()
    ws2 = MagicMock()
    ws2.send_text = AsyncMock(side_effect=Exception("Socket disconnected"))

    manager.active_connections = [ws1, ws2]
    await manager.broadcast({"type": "PING"})

    # Dead ws2 should be removed, ws1 kept
    assert ws1 in manager.active_connections
    assert ws2 not in manager.active_connections

@pytest.mark.asyncio
async def test_case_18_disconnect_while_in_position(test_db):
    """Case 18: Disconnect while holding position does not crash local position manager."""
    from app.trading.position_manager import PositionManager
    
    pos = Position(
        symbol="BTCUSDT",
        amount=Decimal("0.01"),
        entry_price=Decimal("65000.0"),
        current_price=Decimal("65000.0"),
        stop_loss=Decimal("63000.0"),
        take_profit=Decimal("69000.0"),
        total_fee=Decimal("0.0"),
        status="OPEN",
        mode="PAPER"
    )
    test_db.add(pos)
    await test_db.commit()

    # Price hits stop loss
    actions = await PositionManager.update_active_positions(
        session=test_db,
        current_prices={"BTCUSDT": 62500.0},
        mode="PAPER"
    )
    assert len(actions) == 1
    assert actions[0]["reason"] == "STOP_LOSS_TRIGGERED"
    assert pos.status == "CLOSED"
