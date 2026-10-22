"""
EMA Crossover Strategy with Trend Filter
Detects EMA 9 crossing above EMA 21 with price confirmed above EMA 50.
"""
from typing import Dict, Any, List
from .base import BaseStrategy, SignalResult

class EMACrossoverStrategy(BaseStrategy):
    name = "EMA Crossover"
    description = "Giao cắt EMA 9 và EMA 21 có xác nhận bởi xu hướng EMA 50."

    def evaluate(
        self,
        symbol: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        indicators: Dict[str, Any]
    ) -> SignalResult:
        series = indicators.get("series", {})
        latest = indicators.get("latest", {})
        ema9_series = series.get("ema9", [])
        ema21_series = series.get("ema21", [])

        if len(ema9_series) < 2 or len(ema21_series) < 2:
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Không đủ nến lịch sử cho tín hiệu giao cắt", confidence=0.0
            )

        prev_ema9 = ema9_series[-2]
        cur_ema9 = ema9_series[-1]
        prev_ema21 = ema21_series[-2]
        cur_ema21 = ema21_series[-1]
        close = latest.get("close")
        ema50 = latest.get("ema50")
        atr = latest.get("atr14") or (close * 0.015)

        if not (prev_ema9 and cur_ema9 and prev_ema21 and cur_ema21 and close and ema50):
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Dữ liệu chỉ báo EMA chưa sẵn sàng", confidence=0.0
            )

        # Bullish Golden Cross: EMA9 crossed above EMA21, and Price > EMA50
        if prev_ema9 <= prev_ema21 and cur_ema9 > cur_ema21 and close > ema50:
            stop_loss = round(close - (1.5 * atr), 4)
            take_profit = round(close + (3.0 * atr), 4)
            rr = (take_profit - close) / (close - stop_loss) if (close - stop_loss) > 0 else 2.0
            return SignalResult(
                strategy_name=self.name,
                action="BUY",
                symbol=symbol,
                entry_price=round(close, 4),
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(rr, 2),
                reason=f"Giao cắt vàng EMA 9/21 được xác nhận: EMA9 ({cur_ema9:.2f}) vượt EMA21 ({cur_ema21:.2f}) trên nền EMA50",
                confidence=0.82
            )

        # Bearish Death Cross: EMA9 crosses below EMA21
        if prev_ema9 >= prev_ema21 and cur_ema9 < cur_ema21:
            return SignalResult(
                strategy_name=self.name,
                action="SELL",
                symbol=symbol,
                entry_price=round(close, 4),
                reason=f"Giao cắt tử thần EMA 9/21: EMA9 ({cur_ema9:.2f}) cắt xuống dưới EMA21 ({cur_ema21:.2f})",
                confidence=0.78
            )

        return SignalResult(
            strategy_name=self.name,
            action="HOLD",
            symbol=symbol,
            reason="Không có tín hiệu giao cắt mới",
            confidence=0.4
        )
