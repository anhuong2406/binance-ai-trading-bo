"""
Quant Engine - Pure Python Technical Indicators
Computes EMA 9/21/50/200, RSI 14, MACD, Bollinger Bands, ATR 14, ADX 14, Volume Ratio, and Multi-timeframe Alignment.
Requires sufficient historical data bars before calculating indicators.
"""
import math
from datetime import datetime, timezone, timedelta
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

def calculate_stoch_rsi(
    closes: List[float],
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3
) -> Dict[str, List[Optional[float]]]:
    """
    Stochastic RSI (%K, %D).
    Calculates StochRSI from Wilder's RSI, smoothed by SMA(k) and SMA(d).
    Output range: 0.0 - 100.0.
    Values < 20 indicate deeply oversold, > 80 indicate overbought.
    """
    n = len(closes)
    rsi_series = calculate_rsi(closes, rsi_period)

    stoch_rsi: List[Optional[float]] = [None] * n
    for i in range(n):
        if i < (rsi_period + stoch_period - 1):
            continue
        window = [r for r in rsi_series[i - stoch_period + 1 : i + 1] if r is not None]
        if len(window) < stoch_period:
            continue
        min_rsi = min(window)
        max_rsi = max(window)
        diff = max_rsi - min_rsi
        cur_rsi = rsi_series[i]
        if diff == 0 or cur_rsi is None:
            stoch_rsi[i] = 50.0
        else:
            stoch_rsi[i] = ((cur_rsi - min_rsi) / diff) * 100.0

    # Smooth %K = SMA(stoch_rsi, k_period)
    k_series: List[Optional[float]] = [None] * n
    for i in range(n):
        if i < k_period - 1:
            continue
        w = [v for v in stoch_rsi[i - k_period + 1 : i + 1] if v is not None]
        if len(w) == k_period:
            k_series[i] = sum(w) / k_period

    # Smooth %D = SMA(%K, d_period)
    d_series: List[Optional[float]] = [None] * n
    for i in range(n):
        if i < d_period - 1:
            continue
        w = [v for v in k_series[i - d_period + 1 : i + 1] if v is not None]
        if len(w) == d_period:
            d_series[i] = sum(w) / d_period

    return {
        "stoch_rsi": stoch_rsi,
        "k": k_series,
        "d": d_series
    }

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

def detect_market_session(utc_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Identifies active global trading sessions and liquidity characteristics.
    Times in UTC (Vietnam time is UTC+7):
      - ASIA:    00:00 - 08:00 UTC (07:00 - 15:00 VN) -> Moderate volatility, range-bound
      - EUROPE:  07:00 - 16:00 UTC (14:00 - 23:00 VN) -> High liquidity, London breakout
      - US:      13:30 - 21:00 UTC (20:30 - 04:00 VN) -> Peak volume & institutional trends
      - DEAD_ZONE: 21:30 - 23:59 UTC (04:30 - 07:00 VN) -> Low liquidity, wide spreads, false breakouts
    """
    now = utc_dt or datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60.0
    day_of_week = now.weekday()  # 5=Saturday, 6=Sunday
    is_weekend = day_of_week in (5, 6)

    active_sessions = []
    if 0.0 <= hour < 8.0:
        active_sessions.append("ASIA")
    if 7.0 <= hour < 16.0:
        active_sessions.append("EUROPE")
    if 13.5 <= hour < 21.0:
        active_sessions.append("US")

    is_dead_zone = (21.5 <= hour < 24.0) or (0.0 <= hour < 1.0)

    if "US" in active_sessions and "EUROPE" in active_sessions:
        primary = "US_EUROPE_OVERLAP"
        liquidity = "PEAK"
        quality_score = 95
        recommendation = "Phiên Mỹ - Âu trùng giờ: Thanh khoản đỉnh cao, xu hướng chuẩn xác nhất trong ngày."
    elif "US" in active_sessions:
        primary = "US_SESSION"
        liquidity = "HIGH"
        quality_score = 90
        recommendation = "Phiên Mỹ: Khối lượng giao dịch lớn, xu hướng rõ nét."
    elif "EUROPE" in active_sessions:
        primary = "EUROPE_SESSION"
        liquidity = "HIGH"
        quality_score = 85
        recommendation = "Phiên Âu: Thanh khoản tốt từ thị trường London."
    elif "ASIA" in active_sessions:
        primary = "ASIA_SESSION"
        liquidity = "MODERATE"
        quality_score = 70
        recommendation = "Phiên Á: Thanh khoản mức vừa, thị trường có xu hướng tích lũy dao động hộp (Sideway)."
    elif is_dead_zone:
        primary = "DEAD_ZONE_NIGHT"
        liquidity = "LOW"
        quality_score = 40
        recommendation = "Vùng thanh khoản mỏng ban đêm: Cẩn trọng râu quét stop-loss và bẫy giá giả (False Breakout)."
    else:
        primary = "OFF_PEAK"
        liquidity = "MODERATE"
        quality_score = 65
        recommendation = "Phiên giao dịch bình thường."

    if is_weekend:
        liquidity = "WEEKEND_LOW"
        quality_score = max(quality_score - 20, 30)
        recommendation += " Lưu ý: Cuối tuần dòng tiền tổ chức giảm mạnh."

    return {
        "session": primary,
        "active_sessions": active_sessions,
        "liquidity": liquidity,
        "quality_score": quality_score,
        "is_dead_zone": is_dead_zone,
        "is_weekend": is_weekend,
        "utc_time": now.strftime("%H:%M UTC"),
        "vn_time": (now + timedelta(hours=7)).strftime("%H:%M VN"),
        "recommendation": recommendation
    }

class QuantEngine:
    """
    Computes all technical indicators for market data and validates data sufficiency.
    """
    MIN_CANDLES_REQUIRED = 50  # Or 200 for full EMA 200

    @classmethod
    def compute_mtf_alignment(
        cls,
        htf_highs: List[float],
        htf_lows: List[float],
        htf_closes: List[float],
        htf_volumes: List[float],
        ltf_highs: List[float],
        ltf_lows: List[float],
        ltf_closes: List[float],
        ltf_volumes: List[float],
    ) -> Dict[str, Any]:
        """
        Multi-Timeframe Alignment Analysis.
        HTF = Higher Timeframe (1h), LTF = Lower Timeframe (15m).

        Returns alignment score and directional bias for BUY/SELL filter.
        Rules:
          - ALIGNED_BULLISH : HTF bullish + LTF bullish → Allow BUY
          - ALIGNED_BEARISH : HTF bearish + LTF bearish → Allow SELL (or avoid BUY)
          - DIVERGING       : HTF ≠ LTF → Conflict zone, quality of signal degraded significantly
        """
        htf = cls._compute_trend_bias(htf_highs, htf_lows, htf_closes, htf_volumes)
        ltf = cls._compute_trend_bias(ltf_highs, ltf_lows, ltf_closes, ltf_volumes)

        htf_bull = htf["bullish"]
        ltf_bull = ltf["bullish"]
        htf_bear = htf["bearish"]
        ltf_bear = ltf["bearish"]

        # Alignment logic
        if htf_bull and ltf_bull:
            alignment = "ALIGNED_BULLISH"
            bias = "BUY"
            alignment_strength = round((htf["strength"] + ltf["strength"]) / 2, 1)
            allow_buy = True
            note = "HTF và LTF đều TĂNG — Tín hiệu BUY được xác nhận liên khung."
        elif htf_bear and ltf_bear:
            alignment = "ALIGNED_BEARISH"
            bias = "SELL"
            alignment_strength = round((htf["strength"] + ltf["strength"]) / 2, 1)
            allow_buy = False
            note = "HTF và LTF đều GIẢM — Tránh BUY, chờ đảo chiều."
        elif htf_bull and not ltf_bull:
            alignment = "HTF_BULL_LTF_PULLBACK"
            bias = "WAIT"
            alignment_strength = round(htf["strength"] * 0.6, 1)
            allow_buy = False
            note = "HTF tăng nhưng LTF đang điều chỉnh — Chờ LTF xác nhận tăng trở lại."
        elif htf_bear and ltf_bull:
            alignment = "COUNTER_TREND"
            bias = "HOLD"
            alignment_strength = round(ltf["strength"] * 0.4, 1)
            allow_buy = False
            note = "LTF đang phản ứng tăng ngắn hạn nhưng HTF vẫn GIẢM — Rủi ro cao, không BUY."
        else:
            alignment = "NEUTRAL"
            bias = "HOLD"
            alignment_strength = 30.0
            allow_buy = False
            note = "Không có xu hướng rõ ràng trên cả hai khung thời gian."

        return {
            "alignment": alignment,
            "bias": bias,
            "allow_buy": allow_buy,
            "alignment_strength": alignment_strength,
            "htf_trend": htf,
            "ltf_trend": ltf,
            "note": note
        }

    @classmethod
    def _compute_trend_bias(
        cls,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
    ) -> Dict[str, Any]:
        """Helper: determine trend direction for a given timeframe."""
        if len(closes) < 30:
            return {"bullish": False, "bearish": False, "strength": 0.0, "ema9": None, "ema21": None, "ema50": None, "rsi": None, "adx": None}

        ema9  = calculate_ema(closes, 9)[-1]
        ema21 = calculate_ema(closes, 21)[-1]
        ema50 = calculate_ema(closes, 50)[-1]
        rsi   = calculate_rsi(closes, 14)[-1]
        adx_d = calculate_adx(highs, lows, closes, 14)
        adx   = adx_d["adx"][-1] or 0.0
        pdi   = adx_d["plus_di"][-1] or 0.0
        mdi   = adx_d["minus_di"][-1] or 0.0

        close  = closes[-1]
        bullish = bool(ema9 and ema21 and ema50 and ema9 > ema21 and ema21 > ema50 and close > ema9)
        bearish = bool(ema9 and ema21 and ema50 and ema9 < ema21 and ema21 < ema50 and close < ema9)

        # Strength score (0-100) based on ADX + RSI positioning
        strength = 0.0
        if adx > 25:
            strength += min(adx, 50)  # ADX contribution up to 50
        if bullish and rsi and 40 < rsi < 70:
            strength += 30.0
        elif bearish and rsi and 30 < rsi < 60:
            strength += 30.0
        if pdi > mdi and bullish:
            strength += 20.0
        elif mdi > pdi and bearish:
            strength += 20.0

        return {
            "bullish": bullish,
            "bearish": bearish,
            "strength": round(min(strength, 100.0), 1),
            "ema9": ema9,
            "ema21": ema21,
            "ema50": ema50,
            "rsi": rsi,
            "adx": adx,
            "plus_di": pdi,
            "minus_di": mdi,
            "close": close
        }

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
        stoch_rsi = calculate_stoch_rsi(closes, 14, 14, 3, 3)
        macd = calculate_macd(closes, 12, 26, 9)
        bb = calculate_bollinger_bands(closes, 20, 2.0)
        atr14 = calculate_atr(highs, lows, closes, 14)
        adx = calculate_adx(highs, lows, closes, 14)
        session_info = detect_market_session()

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
            "stoch_rsi_k": round(stoch_rsi["k"][-1], 2) if stoch_rsi["k"][-1] is not None else None,
            "stoch_rsi_d": round(stoch_rsi["d"][-1], 2) if stoch_rsi["d"][-1] is not None else None,
            "stoch_rsi_raw": round(stoch_rsi["stoch_rsi"][-1], 2) if stoch_rsi["stoch_rsi"][-1] is not None else None,
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
            "volume_ratio": volume_ratio,
            "market_session": session_info
        }

        return {
            "latest": latest,
            "series": {
                "ema9": ema9,
                "ema21": ema21,
                "ema50": ema50,
                "rsi14": rsi14,
                "stoch_rsi_k": stoch_rsi["k"],
                "stoch_rsi_d": stoch_rsi["d"],
                "macd": macd,
                "bb": bb,
                "atr14": atr14,
                "adx": adx
            }
        }

    @classmethod
    def evaluate_opportunity_trigger(
        cls,
        indicators: Dict[str, Any],
        candles: List[Any],
        has_open_position: bool = False,
        mtf_alignment: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Quant Opportunity Pre-Filter (Radar Sơ Tuyển Cơ Hội).
        Evaluates whether current technical conditions justify waking up LLMs (Gemini & GPT-6 Luna).
        If has_open_position is True: ALWAYS triggers AI to manage existing position.
        If NO setup is detected: skips AI call and returns HOLD, saving ~7,000 tokens per evaluation.
        """
        if has_open_position:
            return {
                "has_opportunity": True,
                "reasons": ["Đang có vị thế mở — Kích hoạt AI để quản lý thoát lệnh/chốt lời."]
            }

        latest = indicators.get("latest", {})
        series = indicators.get("series", {})
        triggers = []

        close = latest.get("close", 0.0)
        ema9 = latest.get("ema9")
        ema21 = latest.get("ema21")
        rsi14 = latest.get("rsi14")
        stoch_k = latest.get("stoch_rsi_k")
        stoch_d = latest.get("stoch_rsi_d")
        macd_hist = latest.get("macd_hist")
        bb_percent_b = latest.get("bb_percent_b")
        volume_ratio = latest.get("volume_ratio", 1.0)
        plus_di = latest.get("plus_di")
        minus_di = latest.get("minus_di")
        adx = latest.get("adx")

        # Previous MACD histogram for momentum change
        macd_data = series.get("macd")
        macd_series = macd_data.get("histogram", []) if isinstance(macd_data, dict) else []
        prev_macd_hist = macd_series[-2] if len(macd_series) >= 2 else None

        # 1. Oversold / Dip Buying Opportunity
        if rsi14 is not None and rsi14 <= 45.0:
            triggers.append(f"RSI chạm vùng giá rẻ ({rsi14:.1f} <= 45)")
        if stoch_k is not None and stoch_k <= 35.0:
            triggers.append(f"StochRSI vùng quá bán (%K={stoch_k:.1f} <= 35)")
        if stoch_k is not None and stoch_d is not None and stoch_k > stoch_d and stoch_k < 50.0:
            triggers.append(f"StochRSI giao cắt vàng (%K={stoch_k:.1f} cắt lên %D={stoch_d:.1f})")

        # 2. Bullish Momentum / EMA Breakout
        if ema9 and ema21 and close > ema9 and ema9 > ema21:
            triggers.append("Xu hướng tăng EMA9 > EMA21 và giá trên EMA9")
        if macd_hist is not None and prev_macd_hist is not None and macd_hist > 0 and macd_hist > prev_macd_hist:
            triggers.append("Động lượng MACD Histogram dương và đang mở rộng")
        if plus_di and minus_di and adx and plus_di > minus_di and adx > 20:
            triggers.append(f"Lực mua chiếm ưu thế (+DI={plus_di:.1f} > -DI={minus_di:.1f}, ADX={adx:.1f})")

        # 3. Mean Reversion / Bollinger Bands
        if bb_percent_b is not None and bb_percent_b <= 0.35:
            triggers.append(f"Giá tiệm cận dải dưới Bollinger Band (%B={bb_percent_b:.2f})")
        elif bb_percent_b is not None and bb_percent_b >= 0.75 and ema9 and close > ema9:
            triggers.append(f"Giá bám dải trên Bollinger Band (%B={bb_percent_b:.2f})")

        # 4. Volume Surge
        if volume_ratio >= 1.25:
            triggers.append(f"Khối lượng volume bùng nổ ({volume_ratio:.2f}x so với TB)")

        # 5. Bullish Reversal Candlestick
        if candles and len(candles) >= 2:
            cur = candles[-1]
            prev = candles[-2]
            if cur.close > cur.open and cur.open < prev.close:
                body = cur.close - cur.open
                total_range = cur.high - cur.low
                if total_range > 0 and (body / total_range) >= 0.6:
                    triggers.append("Nến xanh thân đặc lực mua mạnh (Bullish Candlestick)")

        # 6. Multi-Timeframe Alignment Bonus
        if mtf_alignment and mtf_alignment.get("allow_buy") is True:
            triggers.append(f"Khung lớn 1H và 15M đồng thuận TĂNG ({mtf_alignment.get('alignment')})")

        has_opportunity = len(triggers) > 0
        if has_opportunity:
            return {
                "has_opportunity": True,
                "reasons": triggers,
                "trigger_count": len(triggers),
                "summary": " | ".join(triggers[:3])
            }
        else:
            return {
                "has_opportunity": False,
                "reasons": [],
                "trigger_count": 0,
                "reason": (
                    "Radar Định Lượng: Thị trường chưa có tín hiệu kỹ thuật (không quá bán, không breakout, volume thấp). "
                    "Tự động giữ HOLD, tiết kiệm ~7,000 token."
                )
            }
