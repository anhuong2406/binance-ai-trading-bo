"""
Auto Trading Controller and State Machine
Coordinates 24/7 autonomous trading loop with APScheduler, Emergency Stop, and live WebSocket broadcasts.
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func
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
        self.standby_reason: Optional[str] = None
        self._ws_broadcast_callback = None
        self._cycle_lock = asyncio.Lock()

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
            self.scheduler = AsyncIOScheduler(timezone="UTC")
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
                "standby_reason": self.standby_reason,
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

            # Get prices for active pairs plus all symbols with open positions concurrently.
            prices = {}
            price_errors = {}
            symbols = set(pair_manager.get_active_symbols()) | set(open_symbols)

            async def _fetch_price_for_symbol(pair: str):
                try:
                    if pair in open_symbols:
                        # For held positions, executable top bid is best for accurate SL/TP exits
                        book = await self.binance_client.get_order_book(pair, limit=5)
                        bids = book.get("bids", [])
                        if bids:
                            return pair, float(bids[0][0]), None
                    ticker = await self.binance_client.get_ticker_24hr(pair)
                    return pair, float(ticker.get("lastPrice", 0.0)), None
                except Exception as exc:
                    return pair, None, str(exc)

            pair_results = await asyncio.gather(*[_fetch_price_for_symbol(s) for s in symbols], return_exceptions=True)
            for res in pair_results:
                if isinstance(res, Exception):
                    continue
                sym, p_val, err_val = res
                if p_val is not None:
                    prices[sym] = p_val
                if err_val:
                    price_errors[sym] = err_val

            async with AsyncSessionLocal() as session:
                actions = await PositionManager.update_active_positions(
                    session=session,
                    current_prices=prices,
                    mode=self.mode,
                    execution_engine=self.decision_engine.execution if self.mode in ("LIVE", "TESTNET") else None
                )
                if actions:
                    self.standby_reason = None
                    for act in actions:
                        await notifier.notify(
                            "POSITION_CLOSED",
                            f"Đóng Vị Thế {act['symbol']}",
                            f"Lý do: {act['reason']} | PnL: {act['pnl']:.2f} USDT"
                        )
                    await self.broadcast_status({"position_actions": actions, "standby_reason": None})

                    # ⚡ ĐỘ TRỄ BẰNG 0: Ngay khi vừa chốt vị thế, lập tức kích hoạt chu kỳ quét mới!
                    # Không cần chờ hết 60s/20s giúp vào lệnh kịp thời, tránh trễ giá.
                    if self.is_running and not settings.EMERGENCY_STOP_ACTIVE:
                        logger.info("⚡ Vị thế vừa đóng. Lập tức kích hoạt quét tìm cơ hội mới sau 1.5s...")
                        asyncio.create_task(self._trigger_immediate_evaluation())
            remaining_symbols = await self._get_open_position_symbols()
            if price_errors:
                await self.broadcast_status({"position_price_errors": price_errors})
            if not self.is_running and not remaining_symbols:
                self._shutdown_scheduler()
        except Exception as e:
            self.state = BotState.ERROR
            await self.broadcast_status({"position_monitor_error": str(e)})

    async def _trigger_immediate_evaluation(self):
        """Executes an immediate evaluation cycle after an exit without waiting for timer."""
        await asyncio.sleep(1.5)  # 1.5s buffer for Binance balances to settle
        if self.is_running and not settings.EMERGENCY_STOP_ACTIVE:
            await self.run_scheduled_cycle(force_screener_refresh=True)

    async def run_scheduled_cycle(self, force_screener_refresh: bool = False):
        """Executes one evaluation cycle across active pairs."""
        if not self.is_running or settings.EMERGENCY_STOP_ACTIVE:
            return

        if self._cycle_lock.locked():
            logger.debug("Chu kỳ đánh giá đang chạy, bỏ qua gọi trùng lặp.")
            return

        async with self._cycle_lock:
            await self._run_scheduled_cycle_internal(force_screener_refresh=force_screener_refresh)

    async def _run_scheduled_cycle_internal(self, force_screener_refresh: bool = False):

        async with AsyncSessionLocal() as session:
            # Check open positions count
            stmt = select(func.count(Position.id)).where(
                Position.status == "OPEN",
                Position.mode == self.mode
            )
            count_res = await session.execute(stmt)
            open_count = count_res.scalar() or 0

            # 1. Max concurrent positions reached (only when > 0, 0 = Unlimited)
            if settings.MAX_CONCURRENT_POSITIONS and settings.MAX_CONCURRENT_POSITIONS > 0 and open_count >= settings.MAX_CONCURRENT_POSITIONS:
                self.standby_reason = (
                    f"Đang nắm giữ {open_count}/{settings.MAX_CONCURRENT_POSITIONS} vị thế. "
                    "Tạm dừng quét AI để tiết kiệm 100% token, tập trung theo dõi chốt lời/cắt lỗ."
                )
                self.state = BotState.MONITORING_POSITION
                await self.broadcast_status({"standby_reason": self.standby_reason})
                return

            # 2. Check available buying power
            avail_usdt = settings.BOT_ALLOCATED_CAPITAL_USDT
            if self.mode in ("TESTNET", "LIVE"):
                try:
                    acc_info = await self.decision_engine.account_manager.get_spot_balances()
                    avail_usdt = float(acc_info.get("usdtFree", 0.0))
                except Exception:
                    pass

            # Minimum Binance spot order requirement:
            # Standard pairs (BTC, ETH, SOL, BNB, XRP...): 5.0 USDT minimum notional.
            # Micro-notional pairs (DOGE, SHIB): 1.0 USDT minimum notional.
            active_pairs = pair_manager.get_active_symbols()
            has_micro_pairs = any(p in ("DOGEUSDT", "SHIBUSDT") for p in active_pairs)
            min_required_capital = 1.0 if has_micro_pairs else 5.0

            if avail_usdt < min_required_capital:
                if open_count > 0:
                    self.standby_reason = (
                        f"Đang nắm giữ {open_count} vị thế. Số dư khả dụng ({avail_usdt:.2f} USDT) < {min_required_capital:.1f} USDT (không đủ mua bất kỳ mã nào). "
                        "ĐÃ DỪNG TOÀN BỘ QUÉT THỊ TRƯỜNG & AI để tiết kiệm 100% token, tập trung theo dõi chốt lời/cắt lỗ."
                    )
                    self.state = BotState.MONITORING_POSITION
                else:
                    self.standby_reason = (
                        f"Số dư khả dụng ({avail_usdt:.2f} USDT) < {min_required_capital:.1f} USDT (không đủ mở bất kỳ lệnh nào trên sàn Binance). "
                        "ĐÃ DỪNG TOÀN BỘ QUÉT THỊ TRƯỜNG & AI để tiết kiệm token. Vui lòng nạp thêm USDT."
                    )
                    self.state = BotState.OBSERVING
                await self.broadcast_status({"standby_reason": self.standby_reason})
                return

            # Buying power is available: clear standby and proceed with AI analysis
            self.standby_reason = None
            self.state = BotState.ANALYZING
            await self.broadcast_status({"standby_reason": None})

            # 3. Market Screener & Best Pick Identification (Top-down Capital Allocation)
            symbols_to_evaluate = []
            try:
                from app.trading.market_screener import market_screener
                screener_result = await market_screener.scan_market(
                    capital_usdt=avail_usdt,
                    session=session,
                    force_refresh=force_screener_refresh
                )
                if screener_result.get("status") == "INSUFFICIENT_CAPITAL":
                    self.standby_reason = screener_result.get("message")
                    self.state = BotState.OBSERVING
                    await self.broadcast_status({"standby_reason": self.standby_reason})
                    return

                await self.broadcast_status({"market_radar": screener_result})
                # Prioritize Top candidates from Screener (#1 Best Pick first)
                radar_symbols = [c["symbol"] for c in screener_result.get("candidates", [])]
                for s in radar_symbols:
                    if s not in symbols_to_evaluate:
                        symbols_to_evaluate.append(s)
            except Exception as e:
                pass

            # Also ensure active watched symbols from pair_manager are evaluated
            for s in pair_manager.get_active_symbols():
                if s not in symbols_to_evaluate:
                    symbols_to_evaluate.append(s)

            timeframe = (
                settings.SCALPING_TIMEFRAME
                if settings.SCALPING_MODE_ENABLED
                else settings.DEFAULT_TIMEFRAME
            )
            for pair in symbols_to_evaluate:
                if not self.is_running or settings.EMERGENCY_STOP_ACTIVE or (self.mode == "LIVE" and settings.LIVE_SPOT_LOCKED):
                    break

                # Token optimization: if available balance is under 5.0 USDT,
                # skip pairs requiring 5.0 USDT (BTC, ETH, SOL) to save AI tokens,
                # and focus scanning strictly on 1-USDT pairs (DOGE, SHIB)!
                if avail_usdt < 5.0 and pair not in ("DOGEUSDT", "SHIBUSDT"):
                    continue

                # If capital was consumed by an earlier execution in this cycle, stop opening new positions
                if self.mode in ("TESTNET", "LIVE"):
                    try:
                        acc_check = await self.decision_engine.account_manager.get_spot_balances()
                        if float(acc_check.get("usdtFree", 0.0)) < 1.0:
                            break
                    except Exception:
                        pass

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
