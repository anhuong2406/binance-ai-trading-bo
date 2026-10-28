"""
AI Active Exit Sentinel - Intelligent Volatility Exit & Profit Protection Engine
AI Binance Trading Company

While holding a position, monitors price velocity (rapid surges or dumps).
When price spikes or drops rapidly before hitting hard TP/SL, triggers an emergency
AI analysis to determine whether to exit immediately (lock profit / cut loss early) or hold.
"""
import time
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import Position
from app.database.session import record_audit
from app.notifications.notifier import notifier
from app.ai.gateway import ai_gateway
from app.trading.trade_memory import TradeMemoryService

logger = logging.getLogger("ai_exit_sentinel")

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
# Compact, action-first. Chỉ nói cho AI biết đúng việc nó cần làm.
AI_EXIT_SYSTEM_PROMPT = """Bạn là AI Quản lý Thoát Vị Thế Spot Binance.
Nhiệm vụ: Phân tích vị thế đang mở khi giá biến động mạnh → quyết định EXIT_NOW hoặc HOLD.

KHI GIÁ TĂNG NHANH: EXIT_NOW nếu RSI>70 / nến râu trên / tường bán lớn (đà kiệt sức). HOLD nếu lực đẩy còn mạnh, khối lượng dồi dào.
KHI GIÁ GIẢM NHANH: EXIT_NOW nếu bán tháo ồ ạt / thủng hỗ trợ rõ (rủi ro tiếp tục rơi). HOLD nếu chỉ là liquidity sweep ngắn hạn (volume teo, nến rút chân).

ĐẦU RA: JSON thuần, không text ngoài JSON:
{"decision":"EXIT_NOW","action":"SELL","confidence":0.85,"urgency":"HIGH","suggested_action_name":"EARLY_PROFIT_TAKE","reason":"1–2 câu Tiếng Việt ngắn gọn"}
"""


class AIExitSentinel:
    def __init__(self):
        # Maps position_id -> list of {timestamp: float, price: float}
        self._price_history: Dict[int, List[Dict[str, float]]] = {}
        # Maps position_id -> {timestamp, price, decision, reason}
        self._last_consultation: Dict[int, Dict[str, Any]] = {}

    def record_price_tick(self, position_id: int, price: float):
        """Records price sample for tracking short-term velocity."""
        now = time.time()
        if position_id not in self._price_history:
            self._price_history[position_id] = []

        history = self._price_history[position_id]
        history.append({"timestamp": now, "price": price})

        # Keep ticks within the last 180 seconds (3 minutes), max 40 ticks
        cutoff = now - 180.0
        self._price_history[position_id] = [h for h in history if h["timestamp"] >= cutoff][-40:]

    def detect_volatility_event(
        self,
        position: Position,
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Determines if price has surged or dropped rapidly.
        Returns event metadata if condition is met, else None.
        """
        entry_price = float(position.entry_price or current_price)
        if entry_price <= 0:
            return None

        current_pnl_pct = (current_price - entry_price) / entry_price * 100.0

        history = self._price_history.get(position.id, [])
        velocity_1m = 0.0
        velocity_3m = 0.0

        now = time.time()
        if len(history) >= 2:
            # Find price 60s ago
            ticks_1m = [h for h in history if (now - h["timestamp"]) <= 65.0]
            if ticks_1m:
                oldest_1m = ticks_1m[0]["price"]
                velocity_1m = (current_price - oldest_1m) / oldest_1m * 100.0

            oldest_3m = history[0]["price"]
            velocity_3m = (current_price - oldest_3m) / oldest_3m * 100.0

        surge_thresh = getattr(settings, "AI_ACTIVE_EXIT_SURGE_PCT", 0.5)
        drop_thresh = getattr(settings, "AI_ACTIVE_EXIT_DROP_PCT", 0.4)

        # 1. Rapid Surge condition
        is_rapid_surge = (
            velocity_1m >= surge_thresh or
            velocity_3m >= (surge_thresh * 1.4) or
            (current_pnl_pct >= 0.65 and velocity_1m >= 0.25)
        )

        # 2. Rapid Drop condition
        is_rapid_drop = (
            velocity_1m <= -drop_thresh or
            velocity_3m <= -(drop_thresh * 1.4) or
            (current_pnl_pct <= -0.45 and velocity_1m <= -0.20)
        )

        if is_rapid_surge:
            return {
                "event_type": "RAPID_SURGE",
                "direction": "UP",
                "current_pnl_pct": round(current_pnl_pct, 2),
                "velocity_1m": round(velocity_1m, 2),
                "velocity_3m": round(velocity_3m, 2),
                "description": f"Giá tăng nhanh ({velocity_1m:+.2f}% trong 1m, PnL: {current_pnl_pct:+.2f}%)"
            }
        elif is_rapid_drop:
            return {
                "event_type": "RAPID_DROP",
                "direction": "DOWN",
                "current_pnl_pct": round(current_pnl_pct, 2),
                "velocity_1m": round(velocity_1m, 2),
                "velocity_3m": round(velocity_3m, 2),
                "description": f"Giá giảm nhanh ({velocity_1m:+.2f}% trong 1m, PnL: {current_pnl_pct:+.2f}%)"
            }

        return None

    def should_consult_ai(
        self,
        position_id: int,
        current_price: float,
        event: Dict[str, Any]
    ) -> bool:
        """Enforces cooldown to avoid spamming AI, while permitting critical moves."""
        last_info = self._last_consultation.get(position_id)
        if not last_info:
            return True

        now = time.time()
        elapsed = now - last_info["timestamp"]
        cooldown = getattr(settings, "AI_ACTIVE_EXIT_COOLDOWN_SECONDS", 60)

        # If cooldown expired, allow
        if elapsed >= cooldown:
            return True

        # If price moved significantly (>= 0.4%) since last consultation, allow early re-check
        last_price = last_info.get("price", current_price)
        if last_price > 0:
            price_delta_pct = abs(current_price - last_price) / last_price * 100.0
            if price_delta_pct >= 0.4:
                return True

        return False

    async def evaluate_open_position(
        self,
        session: AsyncSession,
        position: Position,
        current_price: Decimal,
        execution_engine: Any = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether an open position should be exited early by AI due to rapid price velocity.
        Returns closed action dict if position was exited, else None.
        """
        if not getattr(settings, "AI_ACTIVE_EXIT_ENABLED", True):
            return None

        pos_id = position.id
        cur_p = float(current_price)
        self.record_price_tick(pos_id, cur_p)

        event = self.detect_volatility_event(position, cur_p)
        if not event:
            return None

        if not self.should_consult_ai(pos_id, cur_p, event):
            return None

        logger.info(
            "Phát hiện biến động nhanh cho vị thế #%s (%s): %s. Kích hoạt AI Active Exit Sentinel...",
            pos_id, position.symbol, event["description"]
        )

        # 1. Gather Market Context
        context_data = await self._gather_market_context(
            session=session,
            position=position,
            current_price=cur_p,
            event=event,
            execution_engine=execution_engine
        )

        # 2. Consult AI
        ai_verdict = await self._query_ai_sentinel(context_data)
        if not ai_verdict:
            return None

        now = time.time()
        self._last_consultation[pos_id] = {
            "timestamp": now,
            "price": cur_p,
            "decision": ai_verdict.get("decision", "HOLD"),
            "reason": ai_verdict.get("reason", "")
        }

        decision = (ai_verdict.get("decision") or ai_verdict.get("action") or "HOLD").upper()
        reason_text = ai_verdict.get("reason", "Phân tích tự động của AI Sentinel")

        # 3. Handle Decision
        if decision in ("EXIT_NOW", "SELL"):
            logger.warning(
                "AI Sentinel KHUYẾN NGHỊ BÁN NGAY cho vị thế #%s (%s): %s",
                pos_id, position.symbol, reason_text
            )

            is_profit = event["current_pnl_pct"] > 0
            exit_reason = (
                "AI_SURGE_PROFIT_EXIT" if is_profit else "AI_RAPID_DROP_EXIT"
            )

            # Record audit log before exit
            await record_audit(
                session=session,
                event_type="AI_ACTIVE_EXIT_TRIGGERED",
                message=f"AI Quyết Định Bán Ngay vị thế #{pos_id} ({position.symbol}): {reason_text}",
                level="WARNING",
                details={
                    "position_id": pos_id,
                    "symbol": position.symbol,
                    "event": event,
                    "verdict": ai_verdict
                }
            )

            # Import here to avoid circular imports
            from app.trading.position_manager import PositionManager
            closed = await PositionManager._execute_exit(
                session=session,
                position=position,
                market_price=current_price,
                reason=exit_reason,
                execution_engine=execution_engine
            )

            if closed:
                # Clean up tracking
                self._price_history.pop(pos_id, None)
                self._last_consultation.pop(pos_id, None)

                pnl_val = float(closed.realized_pnl or 0.0)
                await notifier.notify(
                    "AI_VOLATILITY_EXIT",
                    f"AI Đã Chốt Vị Thế {position.symbol}",
                    f"Lý do: {reason_text} | PnL: {pnl_val:+.2f} USDT ({event['current_pnl_pct']:+.2f}%)"
                )

                return {
                    "action": "CLOSED",
                    "reason": exit_reason,
                    "position_id": closed.id,
                    "symbol": closed.symbol,
                    "ai_reason": reason_text,
                    "pnl": pnl_val
                }

        else:
            # AI recommends HOLD
            logger.info(
                "AI Sentinel khuyên TIẾP TỤC GIỮ (HOLD) cho vị thế #%s (%s): %s",
                pos_id, position.symbol, reason_text
            )
            await record_audit(
                session=session,
                event_type="AI_EXIT_SENTINEL_HOLD",
                message=f"AI Khuyên Tiếp Tục Giữ vị thế #{pos_id} ({position.symbol}): {reason_text}",
                level="INFO",
                details={
                    "position_id": pos_id,
                    "symbol": position.symbol,
                    "event": event,
                    "verdict": ai_verdict
                }
            )

        return None

    async def _gather_market_context(
        self,
        session: AsyncSession,
        position: Position,
        current_price: float,
        event: Dict[str, Any],
        execution_engine: Any = None
    ) -> Dict[str, Any]:
        """Collects fresh 1m klines, orderbook and trade memory for AI consultation."""
        symbol = position.symbol
        client = getattr(execution_engine, "binance_client", None) if execution_engine else None

        klines_summary = []
        rsi_1m = 50.0
        orderbook_ratio = 1.0

        if client:
            try:
                klines = await client.get_klines(symbol, interval="1m", limit=15)
                if klines and len(klines) >= 10:
                    for k in klines[-5:]:
                        klines_summary.append({
                            "o": float(k[1]),
                            "h": float(k[2]),
                            "l": float(k[3]),
                            "c": float(k[4]),
                            "v": float(k[5])
                        })

                    # Simple 1m RSI
                    closes = [float(k[4]) for k in klines]
                    gains = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
                    losses = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
                    avg_g = sum(gains) / len(gains) if gains else 0.0
                    avg_l = sum(losses) / len(losses) if losses else 0.0
                    if avg_l > 0:
                        rs = avg_g / avg_l
                        rsi_1m = round(100.0 - (100.0 / (1.0 + rs)), 1)
                    elif avg_g > 0:
                        rsi_1m = 100.0
            except Exception as e:
                logger.debug("Không thể lấy nến 1m cho %s: %s", symbol, e)

            try:
                book = await client.get_order_book(symbol, limit=5)
                bids_vol = sum(float(b[1]) for b in book.get("bids", []))
                asks_vol = sum(float(a[1]) for a in book.get("asks", []))
                if asks_vol > 0:
                    orderbook_ratio = round(bids_vol / asks_vol, 2)
            except Exception:
                pass

        # Past trade memory
        trade_lessons = ""
        try:
            trade_lessons = await TradeMemoryService.format_lessons_for_ai_prompt(
                session=session,
                symbol=symbol,
                mode=position.mode,
                limit=3
            )
        except Exception:
            pass

        return {
            "sym": symbol,
            "entry": float(position.entry_price),
            "price": current_price,
            "tp": float(position.take_profit) if position.take_profit else None,
            "sl": float(position.stop_loss) if position.stop_loss else None,
            "event": event,
            "rsi_1m": rsi_1m,
            "ob_ratio": orderbook_ratio,
            "candles_1m": klines_summary,
            "lessons": trade_lessons
        }

    async def _query_ai_sentinel(self, context_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sends emergency exit evaluation request to AI Gateway."""
        event = context_data["event"]
        # Compact JSON — no indent to save tokens
        prompt = (
            f"Vị thế cần phân tích:\n"
            f"{json.dumps(context_data, ensure_ascii=False, separators=(',', ':'))}\n"
            f"Sự kiện: {event['description']} | RSI_1m={context_data['rsi_1m']} | "
            f"OB_ratio={context_data['ob_ratio']}\n"
            f"Quyết định: EXIT_NOW hay HOLD?"
        )

        try:
            target_model = settings.GEMINI_MODEL_ID
            res, latency_ms, usage = await ai_gateway.complete_chat(
                model_id=target_model,
                system_prompt=AI_EXIT_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.1
            )
            logger.info("AI Sentinel phản hồi sau %dms: %s", latency_ms, res.get("decision"))
            return res
        except Exception as e:
            logger.error("Lỗi khi gọi AI Exit Sentinel: %s", e)
            return None

# Global singleton instance
ai_exit_sentinel = AIExitSentinel()
