"""
MACD Momentum Strategy with Volume Confirmation
Enters when MACD histogram turns positive with above-average volume ratio.
"""
from typing import Dict, Any, List
from .base import BaseStrategy, SignalResult

class MACDMomentumStrategy(BaseStrategy):
    name = "MACD Momentum"
    description = "Xung lượng MACD kết hợp bùng nổ khối lượng giao dịch."

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
        macd_series = series.get("macd", {})
        hist_list = macd_series.get("histogram", [])

        if len(hist_list) < 2:
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Chưa đủ dữ liệu MACD", confidence=0.0
            )

        prev_hist = hist_list[-2]
        cur_hist = hist_list[-1]
        close = latest.get("close")
        vol_ratio = latest.get("volume_ratio", 1.0)
        atr = latest.get("atr14") or (close * 0.015)
        macd_val = latest.get("macd")
        signal_val = latest.get("macd_signal")

        if prev_hist is None or cur_hist is None or close is None:
            return SignalResult(
                strategy_name=self.name, action="HOLD", symbol=symbol,
                reason="Dữ liệu MACD/Giá chưa đầy đủ", confidence=0.0
            )

        # Bullish momentum trigger:
        # Histogram flips from negative to positive, and volume is above average (>1.2)
        if prev_hist <= 0 and cur_hist > 0 and vol_ratio >= 1.2:
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
                reason=f"Đảo chiều xung lượng MACD: Histogram chuyển dương ({cur_hist:.4f}) có xác nhận khối lượng x{vol_ratio:.2f}",
                confidence=0.84
            )

        # Momentum fading / negative flip
        if prev_hist >= 0 and cur_hist < 0:
            return SignalResult(
                strategy_name=self.name,
                action="SELL",
                symbol=symbol,
                entry_price=round(close, 4),
                reason=f"Xung lượng tăng suy yếu: Histogram MACD đảo chiều âm ({cur_hist:.4f})",
                confidence=0.76
            )

        return SignalResult(
            strategy_name=self.name,
            action="HOLD",
            symbol=symbol,
            reason=f"Không có điểm kích hoạt xung lượng mới (Hist={cur_hist:.4f}, Vol Ratio={vol_ratio:.2f})",
            confidence=0.45
        )
