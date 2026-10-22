"""
Auto Trading Controller and State Machine
Coordinates 24/7 autonomous trading loop with APScheduler, Emergency Stop, and live WebSocket broadcasts.
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config.settings import settings
from app.binance.client import BinanceSpotClient
from app.trading.decision_engine import DecisionEngine
from app.trading.position_manager import PositionManager
from app.trading.pair_manager import pair_manager
from app.database.session import AsyncSessionLocal, record_audit
from app.notifications.notifier import notifier

class BotState:
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    OBSERVING = "OBSERVING"
    ANALYZING = "ANALYZING"
    WAITING_FOR_CONSENSUS = "WAITING_FOR_CONSENSUS"
    RISK_CHECK = "RISK_CHECK"
    EXECUTING = "EXECUTING"
    MONITORING_POSITION = "MONITORING_POSITION"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"

class AutoTradingController:
    def __init__(self):
        self.state: str = BotState.STOPPED
        self.mode: str = settings.TRADING_MODE  # PAPER, TESTNET, LIVE
        self.is_running: bool = False
        self.last_cycle_time: float = 0.0
        self.last_pipeline_report: Optional[Dict[str, Any]] = None
        self.scheduler: Optional[AsyncIOScheduler] = None
        
        # Binance client instance
        self.binance_client = BinanceSpotClient(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            use_testnet=(self.mode == "TESTNET")
        )
        self.decision_engine = DecisionEngine(self.binance_client)
        self._ws_broadcast_callback = None

    def set_ws_broadcast(self, callback):
        self._ws_broadcast_callback = callback

    async def broadcast_status(self, extra: Optional[Dict[str, Any]] = None):
        """Emit live status update to connected frontend WebSockets."""
        if self._ws_broadcast_callback:
            payload = {
                "type": "BOT_STATE_UPDATE",
                "state": self.state,
                "mode": self.mode,
                "is_running": self.is_running,
                "emergency_stop": settings.EMERGENCY_STOP_ACTIVE,
                "live_locked": settings.LIVE_SPOT_LOCKED,
                "timestamp": int(time.time() * 1000)
            }
            if extra:
                payload.update(extra)
            await self._ws_broadcast_callback(payload)

    async def start(self, mode: Optional[str] = None):
        """Start auto trading loop."""
        if settings.EMERGENCY_STOP_ACTIVE:
            raise ValueError("Không thể khởi động bot khi EMERGENCY STOP đang bật!")

        if mode:
            if mode == "LIVE" and settings.LIVE_SPOT_LOCKED:
                raise ValueError("Không thể khởi động chế độ LIVE SPOT khi chưa mở khóa xác thực an toàn!")
            self.mode = mode
            self.binance_client.set_credentials(
                api_key=settings.BINANCE_TESTNET_API_KEY if mode == "TESTNET" else settings.BINANCE_API_KEY,
                api_secret=settings.BINANCE_TESTNET_API_SECRET if mode == "TESTNET" else settings.BINANCE_API_SECRET,
                use_testnet=(mode == "TESTNET")
            )

        self.state = BotState.STARTING
        self.is_running = True
        await self.broadcast_status()

        # Initialize Scheduler
        if not self.scheduler:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.add_job(
                self.run_scheduled_cycle,
                "interval",
                seconds=settings.EVALUATION_INTERVAL_SECONDS,
                id="trading_cycle_job",
                replace_existing=True
            )
            # Add high-frequency position monitor job (every 15 seconds)
            self.scheduler.add_job(
                self.run_position_monitor,
                "interval",
                seconds=15,
                id="position_monitor_job",
                replace_existing=True
            )
            self.scheduler.start()

        self.state = BotState.OBSERVING
        await self.broadcast_status()
        
        await notifier.notify("BOT_STARTED", "Bot Đã Khởi Động", f"Hệ thống bắt đầu tự động ở chế độ {self.mode}")

        # Trigger immediate first cycle
        asyncio.create_task(self.run_scheduled_cycle())

    async def stop(self):
        """Stop auto trading loop."""
        self.is_running = False
        self.state = BotState.STOPPED
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

        await self.broadcast_status()
        await notifier.notify("BOT_STOPPED", "Bot Đã Dừng", "Hệ thống đã dừng chu kỳ tự động giao dịch.")

    async def trigger_emergency_stop(self) -> Dict[str, Any]:
        """
        Emergency Stop:
        - Halts new orders immediately
        - Cancels pending open limit orders
        - Sets durable EMERGENCY_STOP state
        - DOES NOT panic dump spot positions unless explicitly confirmed.
        """
        settings.EMERGENCY_STOP_ACTIVE = True
        self.is_running = False
        self.state = BotState.EMERGENCY_STOP

        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

        # Cancel pending orders if testnet or live
        canceled_orders = []
        if self.mode in ("TESTNET", "LIVE"):
            try:
                open_orders = await self.binance_client.get_open_orders()
                for o in open_orders:
                    res = await self.binance_client.cancel_order(
                        symbol=o["symbol"],
                        order_id=o["orderId"]
                    )
                    canceled_orders.append(res)
            except Exception as e:
                canceled_orders.append({"error": str(e)})

        async with AsyncSessionLocal() as session:
            await record_audit(
                session=session,
                event_type="EMERGENCY_STOP_TRIGGERED",
                message="KÍCH HOẠT NÚT DỪNG KHẨN CẤP (EMERGENCY STOP)",
                level="CRITICAL",
                details={"canceled_orders": canceled_orders}
            )

        await self.broadcast_status({"emergency_stop": True})
        await notifier.notify(
            "EMERGENCY_STOP",
            "DỪNG KHẨN CẤP ĐÃ BẬT!",
            "Tất cả tác vụ đặt lệnh mới đã bị phong tỏa ngay lập tức!"
        )

        return {
            "status": "EMERGENCY_STOP_ACTIVE",
            "canceled_orders_count": len(canceled_orders),
            "details": canceled_orders
        }

    async def reset_emergency_stop(self):
        """Reset emergency stop lock."""
        settings.EMERGENCY_STOP_ACTIVE = False
        self.state = BotState.STOPPED
        await self.broadcast_status({"emergency_stop": False})

    async def run_position_monitor(self):
        """Monitors open positions for SL/TP hits."""
        if not self.is_running or settings.EMERGENCY_STOP_ACTIVE:
            return

        try:
            # Get latest prices for active pairs
            prices = {}
            for pair in pair_manager.get_active_symbols():
                ticker = await self.binance_client.get_ticker_24hr(pair)
                prices[pair] = float(ticker.get("lastPrice", 0.0))

            async with AsyncSessionLocal() as session:
                actions = await PositionManager.update_active_positions(
                    session=session,
                    current_prices=prices,
                    mode=self.mode
                )
                if actions:
                    for act in actions:
                        await notifier.notify(
                            "POSITION_CLOSED",
                            f"Đóng Vị Thế {act['symbol']}",
                            f"Lý do: {act['reason']} | PnL: {act['pnl']:.2f} USDT"
                        )
                    await self.broadcast_status({"position_actions": actions})
        except Exception:
            pass

    async def run_scheduled_cycle(self):
        """Executes one evaluation cycle across active pairs."""
        if not self.is_running or settings.EMERGENCY_STOP_ACTIVE:
            return

        self.state = BotState.ANALYZING
        await self.broadcast_status()

        async with AsyncSessionLocal() as session:
            for pair in pair_manager.get_active_symbols():
                try:
                    result = await self.decision_engine.execute_cycle(
                        session=session,
                        symbol=pair,
                        timeframe=settings.DEFAULT_TIMEFRAME,
                        mode=self.mode
                    )
                    self.last_pipeline_report = result.get("pipeline")
                    await self.broadcast_status({"last_report": self.last_pipeline_report})
                except Exception as e:
                    self.state = BotState.ERROR
                    await self.broadcast_status({"error": str(e)})

        self.state = BotState.OBSERVING
        self.last_cycle_time = time.time()
        await self.broadcast_status()

trading_controller = AutoTradingController()
