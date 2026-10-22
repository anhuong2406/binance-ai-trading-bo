"""
RSI Mean Reversion Strategy with Ranging Market Filter
Enters on oversold RSI (<32) in sideways/ranging conditions (ADX < 25) with Bollinger Bands bounce.
"""
from typing import Dict, Any, List
from .base import BaseStrategy, SignalResult

class RSIMeanReversionStrategy(BaseStrategy):
    name = "RSI Mean Reversion"
    description = "Chiến lược hồi quy về trung bình RSI trong thị trường đi ngang (Ranging)."

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
        rsi = latest.get("rsi14")
        adx = latest.get("adx")
        bb_lower = latest.get("bb_lower")
        bb_middle = latest.get("bb_middle")
        bb_upper = latest.get("bb_upper")
        atr = latest.get("atr14") or (close * 0.015)

        if not (close and rsi and adx and bb_lower and bb_middle and bb_upper):
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Dữ liệu chỉ báo RSI/Bollinger Bands chưa đủ", confidence=0.0
            )

        # Ranging filter: ADX < 25 (market is not in a strong directional trend)
        is_ranging = adx < 25.0

        # Oversold bounce: RSI < 32 and close near or below lower band
        if is_ranging and rsi <= 32.0 and close <= (bb_lower * 1.01):
            stop_loss = round(close - (1.2 * atr), 4)
            take_profit = round(bb_middle, 4)  # Target is mean reversion to middle band
            rr = (take_profit - close) / (close - stop_loss) if (close - stop_loss) > 0 else 1.5
            return SignalResult(
                strategy_name=self.name,
                action="BUY",
                symbol=symbol,
                entry_price=round(close, 4),
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(rr, 2),
                reason=f"Quá bán trong thị trường đi ngang: RSI={rsi:.1f} <= 32, giá chạm dải dưới Bollinger ({bb_lower:.2f}), ADX={adx:.1f}",
                confidence=0.80
            )

        # Overbought exit: RSI > 70 or close near upper band
        if rsi >= 70.0 or close >= (bb_upper * 0.99):
            return SignalResult(
                strategy_name=self.name,
                action="SELL",
                symbol=symbol,
                entry_price=round(close, 4),
                reason=f"Chốt lời hồi quy: RSI chạm vùng quá mua ({rsi:.1f}) hoặc dải trên Bollinger ({bb_upper:.2f})",
                confidence=0.80
            )

        return SignalResult(
            strategy_name=self.name,
            action="HOLD",
            symbol=symbol,
            reason=f"Chưa có điều kiện quá mua/quá bán trong vùng đi ngang (RSI={rsi:.1f})",
            confidence=0.5
        )
