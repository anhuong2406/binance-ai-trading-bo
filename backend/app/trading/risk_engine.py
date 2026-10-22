"""
Independent Risk Engine
Written in pure Python, isolated from AI prompts and models.
AI has zero permission to override or alter any rule in this engine.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
        calculated_risk_percent: float = 0.0
    ):
        self.passed = passed
        self.reasons = reasons
        self.allowed_quantity = allowed_quantity
        self.notional_value = notional_value
        self.calculated_risk_percent = calculated_risk_percent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "allowed_quantity": float(self.allowed_quantity),
            "notional_value": float(self.notional_value),
            "calculated_risk_percent": self.calculated_risk_percent
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
        mode: str
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

        # 5. Daily stats and Drawdown check
        stat = await self.get_or_create_daily_stat(session, allocated_capital)
        
        # Check Daily Loss Limit (2%)
        start_eq = stat.start_equity if stat.start_equity > 0 else allocated_capital
        daily_loss_pct = ((start_eq - allocated_capital) / start_eq) * 100.0 if start_eq > 0 else 0.0
        if daily_loss_pct >= settings.DAILY_MAX_LOSS_PERCENT:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Đã chạm ngưỡng lỗ trong ngày ({daily_loss_pct:.2f}% >= {settings.DAILY_MAX_LOSS_PERCENT}%). Khóa mở vị thế mới hôm nay!"]
            )

        # Check Max Drawdown from peak (5%)
        peak_eq = max(stat.peak_equity, allocated_capital)
        current_dd_pct = ((peak_eq - allocated_capital) / peak_eq) * 100.0 if peak_eq > 0 else 0.0
        if current_dd_pct >= settings.MAX_DRAWDOWN_PERCENT:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Đã chạm ngưỡng Drawdown tối đa ({current_dd_pct:.2f}% >= {settings.MAX_DRAWDOWN_PERCENT}%). Khóa giao dịch bảo vệ tài sản!"]
            )

        # 6. Max concurrent positions check (Max 2)
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

        # Check if already holding this symbol
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

        # 7. Max daily entries check (Max 5)
        if stat.trade_count >= settings.MAX_DAILY_ENTRIES:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Đã đạt giới hạn số lệnh mở trong ngày ({stat.trade_count}/{settings.MAX_DAILY_ENTRIES})."]
            )

        # 8. Cooldown check (20 mins after last closed position)
        last_closed_stmt = select(Position).where(
            Position.status == "CLOSED",
            Position.mode == mode
        ).order_by(Position.closed_at.desc()).limit(1)
        last_closed_res = await session.execute(last_closed_stmt)
        last_closed_pos = last_closed_res.scalar_one_or_none()

        if last_closed_pos and last_closed_pos.closed_at:
            cooldown_delta = utc_now() - last_closed_pos.closed_at
            if cooldown_delta < timedelta(minutes=settings.COOLDOWN_MINUTES):
                remaining_mins = settings.COOLDOWN_MINUTES - int(cooldown_delta.total_seconds() / 60)
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
        qty_by_avail = avail_dec / Decimal(str(entry_price))
        target_qty = min(raw_qty, qty_by_avail)

        # Check against Binance Filters: stepSize, minQty, minNotional
        step_size = symbol_filters.get("stepSize", Decimal("0.00001"))
        min_qty = symbol_filters.get("minQty", Decimal("0.00001"))
        min_notional = symbol_filters.get("minNotional", Decimal("5.0"))

        precision = abs(step_size.as_tuple().exponent)
        rounded_qty = (target_qty // step_size) * step_size
        rounded_notional = rounded_qty * Decimal(str(entry_price))

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

        if rounded_notional > avail_dec:
            return RiskCheckResult(
                passed=False,
                reasons=[f"Số dư USDT khả dụng ({avail_dec:.2f} USDT) không đủ cho giá trị lệnh ({rounded_notional:.2f} USDT)."]
            )

        calculated_risk_pct = float((risk_per_unit * rounded_qty) / Decimal(str(allocated_capital)) * 100)

        return RiskCheckResult(
            passed=True,
            reasons=["Toàn bộ kiểm tra Risk Engine: PASS."],
            allowed_quantity=rounded_qty,
            notional_value=rounded_notional,
            calculated_risk_percent=round(calculated_risk_pct, 2)
        )

risk_engine = RiskEngine()
