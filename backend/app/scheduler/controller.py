"""
Auto Trading Controller and State Machine
Coordinates 24/7 autonomous trading loop with APScheduler, Emergency Stop, and live WebSocket broadcasts.
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.config.settings import settings
from app.binance.client import BinanceSpotClient
from app.trading.decision_engine import DecisionEngine
from app.trading.position_manager import PositionManager
from app.trading.pair_manager import pair_manager
from app.database.session import AsyncSessionLocal, record_audit
from app.database.models import Position
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

    async def _get_open_position_symbols(self) -> List[str]:
        async with AsyncSessionLocal() as session:
            stmt = select(Position.symbol).where(
                Position.status == "OPEN",
                Position.mode == self.mode
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def _has_open_positions(self) -> bool:
        return bool(await self._get_open_position_symbols())

    async def resume_position_monitoring(self):
        """Restore exit monitoring for persisted positions after app restart."""
        if self.mode in ("LIVE", "TESTNET") and await self._has_open_positions():
            self.is_running = False
            self._ensure_monitor_scheduler()

    def _ensure_monitor_scheduler(self):
        if not self.scheduler:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.start()
        self.scheduler.add_job(
            self.run_position_monitor,
            "interval",
            seconds=(settings.SCALPING_POSITION_MONITOR_INTERVAL_SECONDS
                     if settings.SCALPING_MODE_ENABLED else 15),
            id="position_monitor_job",
            replace_existing=True
        )

    def refresh_schedule(self):
        """Apply scalping cadence changes after settings are saved."""
        if not self.scheduler:
            return
        self._ensure_monitor_scheduler()
        if self.is_running:
            self.scheduler.add_job(
                self.run_scheduled_cycle,
                "interval",
                seconds=(settings.SCALPING_EVALUATION_INTERVAL_SECONDS
                         if settings.SCALPING_MODE_ENABLED
                         else settings.EVALUATION_INTERVAL_SECONDS),
                id="trading_cycle_job",
                replace_existing=True
            )

    def _remove_job(self, job_id: str):
        if self.scheduler:
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass

    def _shutdown_scheduler(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

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

        # Keep exit monitoring independently scheduled from new trade entries.
        self._ensure_monitor_scheduler()
        self.scheduler.add_job(
            self.run_scheduled_cycle,
            "interval",
            seconds=(settings.SCALPING_EVALUATION_INTERVAL_SECONDS
                     if settings.SCALPING_MODE_ENABLED
                     else settings.EVALUATION_INTERVAL_SECONDS),
            id="trading_cycle_job",
            replace_existing=True
        )

        self.state = BotState.OBSERVING
        await self.broadcast_status()
        
        await notifier.notify("BOT_STARTED", "Bot Đã Khởi Động", f"Hệ thống bắt đầu tự động ở chế độ {self.mode}")

        # Trigger immediate first cycle
        asyncio.create_task(self.run_scheduled_cycle())

    async def stop(self):
        """Stop auto trading loop."""
        self.is_running = False
        self.state = BotState.STOPPED
        self._remove_job("trading_cycle_job")
        if self.mode in ("LIVE", "TESTNET") and await self._has_open_positions():
            self._ensure_monitor_scheduler()
        else:
            self._shutdown_scheduler()

        await self.broadcast_status()
        await notifier.notify("BOT_STOPPED", "Bot Đã Dừng", "Hệ thống đã dừng chu kỳ tự động giao dịch.")

    async def trigger_emergency_stop(self) -> Dict[str, Any]:
        """
        Emergency Stop:
        - Halts new orders immediately
        - Cancels pending open limit orders
        - Sets the runtime EMERGENCY_STOP state; LIVE is locked again on restart
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
                    if not str(o.get("clientOrderId", "")).startswith("ABTC_"):
                        continue
                    res = await self.binance_client.cancel_order(
                        symbol=o["symbol"],
                        order_id=o["orderId"]
                    )
                    canceled_orders.append(res)
            except Exception as e:
                canceled_orders.append({"error": str(e)})

        if self.mode in ("LIVE", "TESTNET") and await self._has_open_positions():
            self._ensure_monitor_scheduler()
        else:
            self._shutdown_scheduler()

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
        """Monitor existing live/testnet positions even when new entries are halted."""
        if not self.is_running and self.mode not in ("LIVE", "TESTNET"):
            return

        try:
            # Continue monitoring a held asset after its pair is disabled.
            open_symbols = await self._get_open_position_symbols()
            if not open_symbols:
                if not self.is_running:
                    self._shutdown_scheduler()
                return

            # Get prices for active pairs plus all symbols with open positions.
            prices = {}
            price_errors = {}
            symbols = set(pair_manager.get_active_symbols()) | set(open_symbols)
            for pair in symbols:
                try:
                    ticker = await self.binance_client.get_ticker_24hr(pair)
                    prices[pair] = float(ticker.get("lastPrice", 0.0))
                    if pair in open_symbols:
                        book = await self.binance_client.get_order_book(pair, limit=5)
                        bids = book.get("bids", [])
                        if bids:
                            # SL/TP exits are MARKET SELLs; use executable bid, not last trade.
                            prices[pair] = float(bids[0][0])
                except Exception as e:
                    price_errors[pair] = str(e)

            async with AsyncSessionLocal() as session:
                actions = await PositionManager.update_active_positions(
                    session=session,
                    current_prices=prices,
                    mode=self.mode,
                    execution_engine=self.decision_engine.execution if self.mode in ("LIVE", "TESTNET") else None
                )
                if actions:
                    for act in actions:
                        await notifier.notify(
                            "POSITION_CLOSED",
                            f"Đóng Vị Thế {act['symbol']}",
                            f"Lý do: {act['reason']} | PnL: {act['pnl']:.2f} USDT"
                        )
                    await self.broadcast_status({"position_actions": actions})
            remaining_symbols = await self._get_open_position_symbols()
            if price_errors:
                await self.broadcast_status({"position_price_errors": price_errors})
            if not self.is_running and not remaining_symbols:
                self._shutdown_scheduler()
        except Exception as e:
            self.state = BotState.ERROR
            await self.broadcast_status({"position_monitor_error": str(e)})

    async def run_scheduled_cycle(self):
        """Executes one evaluation cycle across active pairs."""
        if not self.is_running or settings.EMERGENCY_STOP_ACTIVE:
            return

        self.state = BotState.ANALYZING
        await self.broadcast_status()

        async with AsyncSessionLocal() as session:
            timeframe = (
                settings.SCALPING_TIMEFRAME
                if settings.SCALPING_MODE_ENABLED
                else settings.DEFAULT_TIMEFRAME
            )
            for pair in pair_manager.get_active_symbols():
                if not self.is_running or settings.EMERGENCY_STOP_ACTIVE or (self.mode == "LIVE" and settings.LIVE_SPOT_LOCKED):
                    break
                try:
                    result = await self.decision_engine.execute_cycle(
                        session=session,
                        symbol=pair,
                        timeframe=timeframe,
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
