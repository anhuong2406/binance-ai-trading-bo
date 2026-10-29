"""
Independent Risk Engine
Written in pure Python, isolated from AI prompts and models.
AI has zero permission to override or alter any rule in this engine.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, ROUND_UP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.config.settings import settings
from app.database.models import Position, DailyStat, TradingSession

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class RiskCheckResult:
    def __init__(
        self,
        passed: bool,
        reasons: List[str],
        allowed_quantity: Decimal = Decimal("0"),
        notional_value: Decimal = Decimal("0"),
        calculated_risk_percent: float = 0.0,
        small_balance_exception_used: bool = False
    ):
        self.passed = passed
        self.reasons = reasons
        self.allowed_quantity = allowed_quantity
        self.notional_value = notional_value
        self.calculated_risk_percent = calculated_risk_percent
        self.small_balance_exception_used = small_balance_exception_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "allowed_quantity": float(self.allowed_quantity),
            "notional_value": float(self.notional_value),
            "calculated_risk_percent": self.calculated_risk_percent,
            "small_balance_exception_used": self.small_balance_exception_used
        }

class RiskEngine:
    def __init__(self):
        pass

    async def get_or_create_daily_stat(self, session: AsyncSession, current_equity: float) -> DailyStat:
        today_str = utc_now().strftime("%Y-%m-%d")
        stmt = select(DailyStat).where(DailyStat.date == today_str)
        result = await session.execute(stmt)
        stat = result.scalar_one_or_none()

        if not stat:
            # Look up previous peak
            peak_stmt = select(func.max(DailyStat.peak_equity))
            peak_res = await session.execute(peak_stmt)
            prev_peak = peak_res.scalar() or current_equity

            stat = DailyStat(
                date=today_str,
                start_equity=current_equity,
                current_equity=current_equity,
                peak_equity=max(prev_peak, current_equity),
                daily_pnl=0.0,
                daily_pnl_percent=0.0,
                max_drawdown_percent=0.0,
                trade_count=0,
                win_count=0,
                loss_count=0,
                total_fees=0.0
            )
            session.add(stat)
            await session.commit()
            await session.refresh(stat)

        return stat

    async def get_current_equity(self, session: AsyncSession, stat: DailyStat, mode: str) -> float:
        """Rebuild today's equity from positions for this mode only."""
        return (await self.get_mode_daily_metrics(session, stat, mode))["current_equity"]

    async def get_mode_daily_metrics(
        self, session: AsyncSession, stat: DailyStat, mode: str
    ) -> Dict[str, float]:
        """Calculate mode-scoped PnL and drawdown, excluding PAPER/LIVE cross-talk."""
        today_start = datetime.combine(utc_now().date(), datetime.min.time())
        stmt = select(Position).where(
            Position.mode == mode,
            or_(Position.status == "OPEN", Position.closed_at >= today_start)
        )
        result = await session.execute(stmt)
        positions = result.scalars().all()
        closed_today = sorted(
            (p for p in positions if p.status == "CLOSED" and p.closed_at and p.closed_at >= today_start),
            key=lambda p: p.closed_at
        )
        open_positions = [p for p in positions if p.status == "OPEN"]
        start_equity = float(stat.start_equity if stat.start_equity > 0 else settings.BOT_ALLOCATED_CAPITAL_USDT)
        realized_today = sum(float(p.realized_pnl or 0.0) for p in closed_today)
        # Partial closes keep the position OPEN; their realized PnL belongs to
        # today's result when the position itself was opened today.
        realized_today += sum(
            float(p.realized_pnl or 0.0)
            for p in open_positions
            if p.opened_at and p.opened_at >= today_start
        )
        fee_rate = settings.BINANCE_TAKER_FEE_PERCENT / 100.0
        unrealized_net = sum(
            float(position.unrealized_pnl or 0.0)
            - float(position.total_fee or 0.0)
            - float(position.current_price * position.amount) * fee_rate
            for position in open_positions
        )
        current_equity = start_equity + realized_today + unrealized_net
        if not positions and stat and stat.current_equity > 0:
            current_equity = float(stat.current_equity)

        running_equity = start_equity
        peak_equity = start_equity
        for position in closed_today:
            running_equity += float(position.realized_pnl or 0.0)
            peak_equity = max(peak_equity, running_equity)
        peak_equity = max(peak_equity, current_equity)
        daily_loss_percent = (
            max(0.0, (start_equity - current_equity) / start_equity * 100.0)
            if start_equity > 0 else 0.0
        )
        drawdown_percent = (
            max(0.0, (peak_equity - current_equity) / peak_equity * 100.0)
            if peak_equity > 0 else 0.0
        )
        return {
            "start_equity": start_equity,
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "daily_loss_percent": daily_loss_percent,
            "drawdown_percent": drawdown_percent,
            "daily_pnl_percent": ((current_equity - start_equity) / start_equity * 100.0) if start_equity > 0 else 0.0,
        }

    async def get_today_entry_count(self, session: AsyncSession, mode: str) -> int:
        today_start = datetime.combine(utc_now().date(), datetime.min.time())
        stmt = select(func.count(Position.id)).where(
            Position.mode == mode,
            Position.opened_at >= today_start
        )
        result = await session.execute(stmt)
        return int(result.scalar() or 0)

    async def evaluate_trade(
        self,
        session: AsyncSession,
        symbol: str,
        action: str,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        allocated_capital: float,
        available_usdt: float,
        symbol_filters: Dict[str, Any],
        mode: str,
        spread_percent: float = 0.0
    ) -> RiskCheckResult:
        """
        Independent Risk Assessment:
        - Must be BUY or SELL
        - Emergency Stop check
        - Live lock check
        - Daily loss limit check
        - Max drawdown check
        - Max concurrent positions check
        - Daily trade count limit check
        - Cooldown period check
        - Small Balance Mode & Min Notional check
        - Position size cap (25% of bot capital)
        - Max risk cap (1% of bot capital)
        """
        reasons: List[str] = []

        # 1. Emergency stop check
        if settings.EMERGENCY_STOP_ACTIVE:
            return RiskCheckResult(
                passed=False,
                reasons=["EMERGENCY STOP đang kích hoạt! Mọi hoạt động mở lệnh mới bị đóng băng tuyệt đối."]
            )

        # 2. Live locked check
        if mode == "LIVE" and settings.LIVE_SPOT_LOCKED:
            return RiskCheckResult(
                passed=False,
                reasons=["Chế độ LIVE SPOT đang ở trạng thái KHÓA (LOCKED). Yêu cầu người dùng mở khóa thủ công trên giao diện."]
            )

        # 3. Action SELL is permitted to close positions, bypasses buy size checks
        if action == "SELL":
            return RiskCheckResult(passed=True, reasons=["Lệnh SELL thoát vị thế được chấp thuận."])

        if action != "BUY":
            return RiskCheckResult(passed=False, reasons=[f"Hành động '{action}' không phải BUY."])

        # 4. Stop loss validation
        if not stop_loss or stop_loss >= entry_price:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Bắt buộc phải có Stop Loss hợp lệ và nhỏ hơn Entry Price (Entry: {entry_price}, SL: {stop_loss})"]
            )

        round_trip_cost_percent = 2 * (
            settings.BINANCE_TAKER_FEE_PERCENT + settings.SLIPPAGE_ESTIMATE_PERCENT
        ) + max(float(spread_percent or 0.0), 0.0)

        if settings.SCALPING_MODE_ENABLED:
            if not take_profit or take_profit <= entry_price:
                return RiskCheckResult(
                    passed=False,
                    reasons=["Scalping yêu cầu Take Profit cao hơn giá vào lệnh để kiểm tra tỷ lệ lời/lỗ sau chi phí."]
                )

            gross_reward_percent = (take_profit - entry_price) / entry_price * 100.0
            gross_risk_percent = (entry_price - stop_loss) / entry_price * 100.0
            net_reward_percent = gross_reward_percent - round_trip_cost_percent
            net_risk_percent = gross_risk_percent + round_trip_cost_percent
            net_risk_reward = net_reward_percent / net_risk_percent if net_risk_percent > 0 else 0.0
            if net_risk_reward < settings.SCALPING_MIN_NET_RISK_REWARD:
                return RiskCheckResult(
                    passed=False,
                    reasons=[
                        f"Scalping bị từ chối: tỷ lệ lời/lỗ ròng ước tính {net_risk_reward:.2f}:1 "
                        f"thấp hơn mức tối thiểu {settings.SCALPING_MIN_NET_RISK_REWARD:.2f}:1 "
                        f"sau phí, spread và trượt giá dự kiến ({round_trip_cost_percent:.3f}% mỗi vòng)."
                    ]
                )

        # 5. Daily stats and Drawdown check
        stat = await self.get_or_create_daily_stat(session, allocated_capital)
        
        # Check Daily Loss Limit (2%)
        mode_metrics = await self.get_mode_daily_metrics(session, stat, mode)
        daily_loss_pct = mode_metrics["daily_loss_percent"]
        if daily_loss_pct >= settings.DAILY_MAX_LOSS_PERCENT:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Đã chạm ngưỡng lỗ trong ngày ({daily_loss_pct:.2f}% >= {settings.DAILY_MAX_LOSS_PERCENT}%). Khóa mở vị thế mới hôm nay!"]
            )

        # Check Max Drawdown from peak (5%)
        current_dd_pct = mode_metrics["drawdown_percent"]
        if current_dd_pct >= settings.MAX_DRAWDOWN_PERCENT:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Đã chạm ngưỡng Drawdown tối đa ({current_dd_pct:.2f}% >= {settings.MAX_DRAWDOWN_PERCENT}%). Khóa giao dịch bảo vệ tài sản!"]
            )

        # 6. Max concurrent positions check (0 or <= 0 means Unlimited)
        if settings.MAX_CONCURRENT_POSITIONS and settings.MAX_CONCURRENT_POSITIONS > 0:
            pos_stmt = select(func.count(Position.id)).where(
                Position.status == "OPEN",
                Position.mode == mode
            )
            pos_res = await session.execute(pos_stmt)
            open_positions_count = pos_res.scalar() or 0
            if open_positions_count >= settings.MAX_CONCURRENT_POSITIONS:
                return RiskCheckResult(
                    passed=False,
                    reasons=[f"Đã đạt số lượng vị thế mở tối đa cho bot ({open_positions_count}/{settings.MAX_CONCURRENT_POSITIONS})."]
                )

        # Check if already holding this symbol (bypassed when ALLOW_SAME_SYMBOL_ENTRIES is True)
        if not getattr(settings, "ALLOW_SAME_SYMBOL_ENTRIES", True):
            sym_stmt = select(func.count(Position.id)).where(
                Position.status == "OPEN",
                Position.symbol == symbol,
                Position.mode == mode
            )
            sym_res = await session.execute(sym_stmt)
            if (sym_res.scalar() or 0) > 0:
                return RiskCheckResult(
                    passed=False,
                    reasons=[f"Đang có vị thế mở cho {symbol}. Không thực hiện mua thêm (Chống nhồi lệnh Martingale)."]
                )

        # 7. Max daily entries check (0 or <= 0 means Unlimited)
        effective_max_entries = settings.SCALPING_MAX_DAILY_ENTRIES if settings.SCALPING_MODE_ENABLED else settings.MAX_DAILY_ENTRIES
        if effective_max_entries and effective_max_entries > 0:
            today_entry_count = await self.get_today_entry_count(session, mode)
            if today_entry_count >= effective_max_entries:
                return RiskCheckResult(
                    passed=False,
                    reasons=[f"Đã đạt giới hạn số lệnh mở trong ngày ({today_entry_count}/{effective_max_entries})."]
                )

        # 7b. Anti-Chasing Guard (Chống mua đuổi giá cao hơn lúc vừa chốt lời)
        if getattr(settings, "ANTI_CHASING_GUARD_ENABLED", True):
            anti_chase_mins = getattr(settings, "ANTI_CHASING_WINDOW_MINUTES", 5)
            last_win_stmt = (
                select(Position)
                .where(
                    Position.symbol == symbol,
                    Position.status == "CLOSED",
                    Position.mode == mode,
                    Position.realized_pnl > 0
                )
                .order_by(Position.closed_at.desc())
                .limit(1)
            )
            last_win_res = await session.execute(last_win_stmt)
            last_win_pos = last_win_res.scalar_one_or_none()

            if last_win_pos and last_win_pos.closed_at and last_win_pos.current_price:
                delta_mins = (utc_now() - last_win_pos.closed_at).total_seconds() / 60.0
                if delta_mins <= anti_chase_mins:
                    exit_p = float(last_win_pos.current_price)
                    cur_p = float(entry_price)
                    # Nếu giá hiện tại cao hơn giá vừa chốt lời > 0.3%: Chặn mua đuổi đỉnh!
                    if cur_p > exit_p * 1.003:
                        diff_pct = ((cur_p - exit_p) / exit_p) * 100.0
                        return RiskCheckResult(
                            passed=False,
                            reasons=[
                                f"Cảnh báo Chống Mua Đuổi: {symbol} vừa chốt lời {delta_mins:.1f}p trước ở giá {exit_p:.4f}. "
                                f"Giá hiện tại ({cur_p:.4f}, +{diff_pct:.2f}%) cao hơn lúc chốt. "
                                "Chờ giá thoái lui (pullback) về vùng an toàn hoặc để Radar chọn mã khác ở chân sóng."
                            ]
                        )

        # 8. Cooldown check (Dynamic: 0 or <= 0 means Disabled / No cooldown)
        effective_cooldown = settings.SCALPING_COOLDOWN_MINUTES if settings.SCALPING_MODE_ENABLED else settings.COOLDOWN_MINUTES
        if effective_cooldown and effective_cooldown > 0:
            last_closed_stmt = select(Position).where(
                Position.status == "CLOSED",
                Position.mode == mode
            ).order_by(Position.closed_at.desc()).limit(1)
            last_closed_res = await session.execute(last_closed_stmt)
            last_closed_pos = last_closed_res.scalar_one_or_none()

            if last_closed_pos and last_closed_pos.closed_at:
                cooldown_delta = utc_now() - last_closed_pos.closed_at
                if cooldown_delta < timedelta(minutes=effective_cooldown):
                    remaining_mins = effective_cooldown - int(cooldown_delta.total_seconds() / 60)
                    return RiskCheckResult(
                        passed=False,
                        reasons=[f"Đang trong thời gian nghỉ Cooldown (còn {remaining_mins} phút sau lệnh đóng gần nhất)."]
                    )

        # 9. Small Balance Mode & Position Sizing
        # Max position value = 25% of allocated capital
        max_position_usdt = Decimal(str(allocated_capital)) * Decimal(str(settings.MAX_POSITION_SIZE_PERCENT / 100.0))
        
        # Max risk amount = 1% of allocated capital
        max_risk_amount = Decimal(str(allocated_capital)) * Decimal(str(settings.MAX_RISK_PER_TRADE_PERCENT / 100.0))
        
        # Risk per unit = entry - stop_loss
        risk_per_unit = Decimal(str(entry_price)) - Decimal(str(stop_loss))
        if settings.SCALPING_MODE_ENABLED:
            risk_per_unit += Decimal(str(entry_price)) * Decimal(str(round_trip_cost_percent / 100.0))
        if risk_per_unit <= 0:
            return RiskCheckResult(passed=False, reasons=["Khoảng cách Stop Loss không hợp lệ."])

        # Quantity based on risk cap: qty = max_risk / risk_per_unit
        qty_by_risk = max_risk_amount / risk_per_unit
        # Quantity based on position value cap: qty = max_position_usdt / entry_price
        qty_by_pos_size = max_position_usdt / Decimal(str(entry_price))
        
        # Take the more conservative quantity
        raw_qty = min(qty_by_risk, qty_by_pos_size)

        # Also cannot exceed available spot balance
        avail_dec = Decimal(str(available_usdt))
        entry_cost_multiplier = Decimal("1") + Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
        qty_by_avail = avail_dec / (Decimal(str(entry_price)) * entry_cost_multiplier)
        target_qty = min(raw_qty, qty_by_avail)

        # Check against Binance Filters: stepSize, minQty, minNotional
        step_size = symbol_filters.get("stepSize", Decimal("0.00001"))
        min_qty = symbol_filters.get("minQty", Decimal("0.00001"))
        min_notional = symbol_filters.get("minNotional", Decimal("5.0"))

        precision = abs(step_size.as_tuple().exponent)
        rounded_qty = (target_qty // step_size) * step_size
        rounded_notional = rounded_qty * Decimal(str(entry_price))
        exception_used = False

        # Lift only the position-size cap to the exchange minimum for tiny accounts.
        # The risk budget and fee-inclusive available balance remain hard limits.
        if rounded_notional < min_notional and min_notional > max_position_usdt:
            exception_cap = Decimal(str(settings.SMALL_BALANCE_MIN_NOTIONAL_EXCEPTION_USDT))
            min_order_qty = (min_notional / Decimal(str(entry_price)) / step_size).to_integral_value(
                rounding=ROUND_UP
            ) * step_size
            if min_order_qty < min_qty:
                min_order_qty = (min_qty / step_size).to_integral_value(rounding=ROUND_UP) * step_size
            min_order_notional = min_order_qty * Decimal(str(entry_price))
            min_order_cost = min_order_notional * entry_cost_multiplier
            if (
                min_notional <= exception_cap
                and min_order_notional <= exception_cap
                and (min_order_qty <= qty_by_risk or min_order_qty * risk_per_unit <= Decimal("0.10"))
                and min_order_cost <= avail_dec
            ):
                rounded_qty = min_order_qty
                rounded_notional = min_order_notional
                exception_used = True

        if rounded_qty < min_qty:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Small Balance Mode: Khối lượng tính toán ({rounded_qty}) nhỏ hơn mức tối thiểu minQty ({min_qty}) hoặc MIN_NOTIONAL của sàn ({symbol}). Bot tiếp tục quan sát."]
            )

        if rounded_notional < min_notional:
            return RiskCheckResult(
                passed=False,
                reasons=[
                    f"Small Balance Mode: Giá trị lệnh tính toán ({rounded_notional:.2f} USDT) nhỏ hơn yêu cầu tối thiểu MIN_NOTIONAL ({min_notional} USDT) của Binance. Bot tiếp tục quan sát thị trường."
                ]
            )

        if rounded_notional * entry_cost_multiplier > avail_dec:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Số dư USDT khả dụng ({avail_dec:.2f} USDT) không đủ cho giá trị lệnh và phí ({(rounded_notional * entry_cost_multiplier):.2f} USDT)."]
            )

        calculated_risk_pct = float((risk_per_unit * rounded_qty) / Decimal(str(allocated_capital)) * 100)

        return RiskCheckResult(
            passed=True,
            reasons=[
                f"Toàn bộ kiểm tra Risk Engine: PASS. Ngoại lệ min-notional {rounded_notional:.2f} USDT được dùng trong giới hạn rủi ro hiện tại."
                if exception_used else "Toàn bộ kiểm tra Risk Engine: PASS."
            ],
            allowed_quantity=rounded_qty,
            notional_value=rounded_notional,
            calculated_risk_percent=round(calculated_risk_pct, 4),
            small_balance_exception_used=exception_used
        )

risk_engine = RiskEngine()
