"""
Trend Following Strategy
Requires ADX > 22 indicating strong trend, EMA alignment (EMA 21 > EMA 50), and RSI healthy.
"""
from typing import Dict, Any, List
from .base import BaseStrategy, SignalResult

class TrendFollowingStrategy(BaseStrategy):
    name = "Trend Following"
    description = "Bám sát xu hướng với bộ lọc EMA 21/50, ADX sức mạnh xu hướng và RSI."

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
        adx = latest.get("adx")
        plus_di = latest.get("plus_di")
        minus_di = latest.get("minus_di")
        atr = latest.get("atr14") or (close * 0.015)
        rsi = latest.get("rsi14")

        if not (close and ema21 and ema50 and adx and plus_di and minus_di and rsi):
            return SignalResult(
                strategy_name=self.name,
                action="HOLD",
                symbol=symbol,
                reason="Chưa đủ chỉ báo kỹ thuật cần thiết",
                confidence=0.0
            )

        # Bullish trend condition:
        # EMA21 > EMA50, Close > EMA21, ADX > 22, +DI > -DI, RSI between 45 and 68
        if (
            ema21 > ema50
            and close > ema21
            and adx >= 22
            and plus_di > minus_di
            and 45 <= rsi <= 68
        ):
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
                reason=f"Xu hướng tăng mạnh: EMA21 ({ema21:.2f}) > EMA50 ({ema50:.2f}), ADX={adx:.1f}, +DI > -DI, RSI={rsi:.1f}",
                confidence=0.85
            )

        # Exit/Sell signal for spot if trend reverses (Close < EMA50 or -DI crosses above +DI)
        if close < ema50 or (minus_di > plus_di and adx > 25):
            return SignalResult(
                strategy_name=self.name,
                action="SELL",
                symbol=symbol,
                entry_price=round(close, 4),
                reason=f"Xu hướng tăng bị phá vỡ: Giá ({close:.2f}) < EMA50 hoặc -DI vượt trội, cân nhắc đóng vị thế bảo toàn vốn.",
                confidence=0.80
            )

        return SignalResult(
            strategy_name=self.name,
            action="HOLD",
            symbol=symbol,
            reason=f"Thị trường chưa đạt đủ điều kiện xu hướng (ADX={adx:.1f}, RSI={rsi:.1f})",
            confidence=0.5
        )
