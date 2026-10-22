"""
Multi-timeframe Confirmation Strategy
Aligns higher-timeframe trend with lower-timeframe entry pullbacks.
"""
from typing import Dict, Any, List
from .base import BaseStrategy, SignalResult

class MultiTimeframeStrategy(BaseStrategy):
    name = "Multi-Timeframe Confirmation"
    description = "Đồng thuận đa khung thời gian: Xu hướng khung lớn hỗ trợ điểm vào lệnh khung nhỏ."

    def evaluate(
        self,
        symbol: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        indicators: Dict[str, Any]
    ) -> SignalResult:
        latest = indicators.get("latest", {})
        close = latest.get("close")
        ema21 = latest.get("ema21")
        ema50 = latest.get("ema50")
        ema200 = latest.get("ema200")
        rsi = latest.get("rsi14")
        adx = latest.get("adx")
        atr = latest.get("atr14") or (close * 0.015)

        if not (close and ema21 and ema50 and rsi and atr):
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Thiếu chỉ báo cho chiến lược đa khung", confidence=0.0
            )

        # Macro trend condition: Price > EMA50 (and > EMA200 if available)
        macro_bullish = close > ema50 and (ema200 is None or close > ema200)

        # Micro pullback: Price pulls back near EMA21 with RSI resetting to 42-55
        micro_pullback = abs(close - ema21) / close <= 0.008 and 40 <= rsi <= 55

        if macro_bullish and micro_pullback:
            stop_loss = round(min(close - (1.5 * atr), ema50 * 0.995), 4)
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
                reason=f"Đồng thuận đa khung: Xu hướng tăng vĩ mô (trên EMA50) + Điểm kéo ngược vi mô gần EMA21 (RSI={rsi:.1f})",
                confidence=0.88
            )

        # Invalidation
        if close < ema50 * 0.985:
            return SignalResult(
                strategy_name=self.name,
                action="SELL",
                symbol=symbol,
                entry_price=round(close, 4),
                reason=f"Phá vỡ cấu trúc đa khung: Giá thủng sâu dưới EMA50 ({ema50:.2f})",
                confidence=0.82
            )

        return SignalResult(
            strategy_name=self.name,
            action="HOLD",
            symbol=symbol,
            reason="Chưa đồng bộ giữa xu hướng lớn và nhịp kéo ngược khung nhỏ",
            confidence=0.5
        )
