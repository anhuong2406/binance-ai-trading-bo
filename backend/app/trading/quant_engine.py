"""
Quant Engine - Pure Python Technical Indicators
Computes EMA 9/21/50/200, RSI 14, MACD, Bollinger Bands, ATR 14, ADX 14, Volume Ratio, and Multi-timeframe Alignment.
Requires sufficient historical data bars before calculating indicators.
"""
import math
from typing import List, Dict, Any, Optional

def calculate_sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average."""
    if len(values) < period:
        return [None] * len(values)
    res: List[Optional[float]] = [None] * (period - 1)
    window_sum = sum(values[:period])
    res.append(window_sum / period)
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        res.append(window_sum / period)
    return res

def calculate_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average."""
    if len(values) < period:
        return [None] * len(values)
    
    multiplier = 2.0 / (period + 1)
    res: List[Optional[float]] = [None] * (period - 1)
    
    # First EMA value is SMA of first 'period' values
    sma_init = sum(values[:period]) / period
    res.append(sma_init)
    
    prev_ema = sma_init
    for i in range(period, len(values)):
        cur_ema = (values[i] - prev_ema) * multiplier + prev_ema
        res.append(cur_ema)
        prev_ema = cur_ema
        
    return res

def calculate_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """Relative Strength Index (Wilder's RSI)."""
    if len(closes) <= period:
        return [None] * len(closes)
        
    res: List[Optional[float]] = [None] * period
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
        
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        res.append(100.0)
    else:
        rs = avg_gain / avg_loss
        res.append(100.0 - (100.0 / (1.0 + rs)))
        
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            res.append(100.0)
        else:
            rs = avg_gain / avg_loss
            res.append(100.0 - (100.0 / (1.0 + rs)))
            
    return res

def calculate_macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Dict[str, List[Optional[float]]]:
    """Moving Average Convergence Divergence."""
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)
    
    macd_line: List[Optional[float]] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)
            
    # Filter valid macd points for signal line EMA
    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal:
        return {
            "macd": macd_line,
            "signal": [None] * len(closes),
            "histogram": [None] * len(closes)
        }
        
    signal_sub = calculate_ema(valid_macd, signal)
    
    # Pad signal line to match original closes length
    none_pad_count = len(closes) - len(valid_macd)
    signal_line: List[Optional[float]] = [None] * none_pad_count + signal_sub
    
    histogram: List[Optional[float]] = []
    for m, sig in zip(macd_line, signal_line):
        if m is not None and sig is not None:
            histogram.append(m - sig)
        else:
            histogram.append(None)
            
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }

def calculate_bollinger_bands(
    closes: List[float],
    period: int = 20,
    num_std: float = 2.0
) -> Dict[str, List[Optional[float]]]:
    """Bollinger Bands."""
    if len(closes) < period:
        return {
            "upper": [None] * len(closes),
            "middle": [None] * len(closes),
            "lower": [None] * len(closes),
            "bandwidth": [None] * len(closes),
            "percent_b": [None] * len(closes)
        }
        
    sma = calculate_sma(closes, period)
    upper: List[Optional[float]] = [None] * (period - 1)
    lower: List[Optional[float]] = [None] * (period - 1)
    bandwidth: List[Optional[float]] = [None] * (period - 1)
    percent_b: List[Optional[float]] = [None] * (period - 1)
    
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = sma[i]
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)
        
        u = mean + (num_std * std)
        l = mean - (num_std * std)
        upper.append(u)
        lower.append(l)
        
        bw = ((u - l) / mean) * 100.0 if mean else 0.0
        pb = ((closes[i] - l) / (u - l)) if (u - l) > 0 else 0.5
        bandwidth.append(bw)
        percent_b.append(pb)
        
    return {
        "upper": upper,
        "middle": sma,
        "lower": lower,
        "bandwidth": bandwidth,
        "percent_b": percent_b
    }

def calculate_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> List[Optional[float]]:
    """Average True Range (ATR)."""
    if len(closes) <= period:
        return [None] * len(closes)
        
    tr: List[float] = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr.append(max(hl, hc, lc))
        
    res: List[Optional[float]] = [None] * (period - 1)
    atr_val = sum(tr[:period]) / period
    res.append(atr_val)
    
    for i in range(period, len(tr)):
        atr_val = (atr_val * (period - 1) + tr[i]) / period
        res.append(atr_val)
        
    return res

def calculate_adx(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> Dict[str, List[Optional[float]]]:
    """Average Directional Index (ADX) with +DI and -DI."""
    length = len(closes)
    if length <= period * 2:
        return {
            "adx": [None] * length,
            "plus_di": [None] * length,
            "minus_di": [None] * length
        }
        
    plus_dm = []
    minus_dm = []
    tr = []
    
    for i in range(1, length):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr.append(max(hl, hc, lc))
        
    # Smooth TR, +DM, -DM
    smooth_tr = sum(tr[:period])
    smooth_pdm = sum(plus_dm[:period])
    smooth_mdm = sum(minus_dm[:period])
    
    dx_list = []
    plus_di_list = [None] * period
    minus_di_list = [None] * period
    
    pdi = (100 * smooth_pdm / smooth_tr) if smooth_tr else 0
    mdi = (100 * smooth_mdm / smooth_tr) if smooth_tr else 0
    plus_di_list.append(pdi)
    minus_di_list.append(mdi)
    dx = (100 * abs(pdi - mdi) / (pdi + mdi)) if (pdi + mdi) else 0
    dx_list.append(dx)
    
    for i in range(period, len(tr)):
        smooth_tr = smooth_tr - (smooth_tr / period) + tr[i]
        smooth_pdm = smooth_pdm - (smooth_pdm / period) + plus_dm[i]
        smooth_mdm = smooth_mdm - (smooth_mdm / period) + minus_dm[i]
        
        pdi = (100 * smooth_pdm / smooth_tr) if smooth_tr else 0
        mdi = (100 * smooth_mdm / smooth_tr) if smooth_tr else 0
        plus_di_list.append(pdi)
        minus_di_list.append(mdi)
        
        dx = (100 * abs(pdi - mdi) / (pdi + mdi)) if (pdi + mdi) else 0
        dx_list.append(dx)
        
    # ADX is smoothed DX
    adx_list: List[Optional[float]] = [None] * (period * 2 - 1)
    if len(dx_list) >= period:
        adx_val = sum(dx_list[:period]) / period
        adx_list.append(adx_val)
        for i in range(period, len(dx_list)):
            adx_val = (adx_val * (period - 1) + dx_list[i]) / period
            adx_list.append(adx_val)
    else:
        adx_list = [None] * length
        
    # Pad to match original length
    diff = length - len(adx_list)
    if diff > 0:
        adx_list = [None] * diff + adx_list
        
    return {
        "adx": adx_list,
        "plus_di": plus_di_list + [None] * (length - len(plus_di_list)),
        "minus_di": minus_di_list + [None] * (length - len(minus_di_list))
    }

class QuantEngine:
    """
    Computes all technical indicators for market data and validates data sufficiency.
    """
    MIN_CANDLES_REQUIRED = 50  # Or 200 for full EMA 200

    @classmethod
    def compute_all_indicators(
        cls,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float]
    ) -> Dict[str, Any]:
        """Compute full suite of technical indicators."""
        n = len(closes)
        if n < cls.MIN_CANDLES_REQUIRED:
            raise ValueError(
                f"Không đủ dữ liệu nến để tính chỉ báo kỹ thuật ({n}/{cls.MIN_CANDLES_REQUIRED})"
            )

        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200) if n >= 200 else [None] * n

        rsi14 = calculate_rsi(closes, 14)
        macd = calculate_macd(closes, 12, 26, 9)
        bb = calculate_bollinger_bands(closes, 20, 2.0)
        atr14 = calculate_atr(highs, lows, closes, 14)
        adx = calculate_adx(highs, lows, closes, 14)

        # Volume ratio = current volume / 20-period volume SMA
        vol_sma20 = calculate_sma(volumes, 20)
        cur_vol = volumes[-1]
        avg_vol = vol_sma20[-1] if vol_sma20[-1] else cur_vol
        volume_ratio = (cur_vol / avg_vol) if avg_vol > 0 else 1.0

        # Current values summary
        latest = {
            "close": closes[-1],
            "ema9": ema9[-1],
            "ema21": ema21[-1],
            "ema50": ema50[-1],
            "ema200": ema200[-1],
            "rsi14": rsi14[-1],
            "macd": macd["macd"][-1],
            "macd_signal": macd["signal"][-1],
            "macd_hist": macd["histogram"][-1],
            "bb_upper": bb["upper"][-1],
            "bb_middle": bb["middle"][-1],
            "bb_lower": bb["lower"][-1],
            "bb_percent_b": bb["percent_b"][-1],
            "atr14": atr14[-1],
            "adx": adx["adx"][-1],
            "plus_di": adx["plus_di"][-1],
            "minus_di": adx["minus_di"][-1],
            "volume_ratio": volume_ratio
        }

        return {
            "latest": latest,
            "series": {
                "ema9": ema9,
                "ema21": ema21,
                "ema50": ema50,
                "rsi14": rsi14,
                "macd": macd,
                "bb": bb,
                "atr14": atr14,
                "adx": adx
            }
        }
