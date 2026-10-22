"""
Skill Executor
Converts approved Claude Trading Skills into pure, secure, battle-tested Python quant tools.
Executes purely local mathematical functions.
STRICT SECURITY: Never runs eval(), exec(), shell scripts, or arbitrary AI-generated code.
"""
import math
import statistics
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN

class SkillExecutor:
    """Executes quantitative algorithms ported from Claude Trading Skills."""

    @staticmethod
    def run_regime_detection(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        lookback: int = 14
    ) -> Dict[str, Any]:
        """
        Ported from skills/regime-detection:
        Calculates:
        1. Choppiness Index (CI)
        2. ATR Percentile Rank
        3. Trend classification (Trending vs Ranging)
        4. Volatility classification (High Vol vs Low Vol)
        5. 4-Quadrant Market Regime:
           - Q1: TRENDING_LOW_VOL (Clean Trend)
           - Q2: TRENDING_HIGH_VOL (Volatile Trend)
           - Q3: RANGING_LOW_VOL (Quiet Range / Mean Reversion)
           - Q4: RANGING_HIGH_VOL (Choppy Chaos / Danger Zone)
        """
        n = len(closes)
        if n < lookback + 1:
            return {
                "regime": "UNCERTAIN",
                "quadrant": "UNKNOWN",
                "choppiness_index": 50.0,
                "atr_percentile": 50.0,
                "recommendation": "Dữ liệu chưa đủ chu kỳ để xác định Regime"
            }

        # 1. True Range calculation
        tr_list = []
        for i in range(1, n):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)

        # 2. Choppiness Index (over lookback)
        recent_tr_sum = sum(tr_list[-lookback:])
        period_high = max(highs[-lookback:])
        period_low = min(lows[-lookback:])
        hl_range = period_high - period_low

        if hl_range > 0 and recent_tr_sum > 0:
            ci = 100.0 * (math.log10(recent_tr_sum / hl_range) / math.log10(lookback))
            ci = max(0.0, min(100.0, ci))
        else:
            ci = 50.0

        # CI > 61.8 -> Ranging/Consolidation; CI < 38.2 -> Strong Trending
        is_trending = ci < 50.0

        # 3. ATR Percentile Rank
        recent_atrs = []
        atr_window = 14
        if len(tr_list) >= atr_window:
            for i in range(atr_window, len(tr_list) + 1):
                recent_atrs.append(sum(tr_list[i - atr_window : i]) / atr_window)
        
        current_atr = recent_atrs[-1] if recent_atrs else (tr_list[-1] if tr_list else 1.0)
        if recent_atrs:
            rank = sum(1 for a in recent_atrs if a <= current_atr)
            atr_pct = (rank / len(recent_atrs)) * 100.0
        else:
            atr_pct = 50.0

        is_high_vol = atr_pct > 50.0

        # 4. Determine 4-Quadrant Regime
        if is_trending and not is_high_vol:
            regime = "TRENDING_LOW_VOL"
            quadrant = "Q1_CLEAN_TREND"
            desc = "Xu hướng mượt mà, biến động thấp. Thích hợp nhất cho Trend Following và nắm giữ vị thế."
            tradeable = True
        elif is_trending and is_high_vol:
            regime = "TRENDING_HIGH_VOL"
            quadrant = "Q2_VOLATILE_TREND"
            desc = "Xu hướng mạnh nhưng biến động cao. Đòi hỏi trailing stop nới rộng, giảm quy mô lệnh."
            tradeable = True
        elif not is_trending and not is_high_vol:
            regime = "RANGING_LOW_VOL"
            quadrant = "Q3_QUIET_RANGE"
            desc = "Đi ngang tích lũy biên độ hẹp. Thích hợp cho chiến lược Mean-Reversion ở biên Bollinger."
            tradeable = True
        else:
            regime = "RANGING_HIGH_VOL"
            quadrant = "Q4_CHOPPY_CHAOS"
            desc = "Biến động giật hỗn loạn không xu hướng (Danger Zone). Khuyến nghị đứng ngoài HOLD."
            tradeable = False

        return {
            "regime": regime,
            "quadrant": quadrant,
            "choppiness_index": round(ci, 2),
            "is_trending": is_trending,
            "atr_percentile": round(atr_pct, 1),
            "is_high_vol": is_high_vol,
            "tradeable": tradeable,
            "recommendation": desc
        }

    @staticmethod
    def run_volatility_modeling(
        highs: List[float],
        lows: List[float],
        opens: List[float],
        closes: List[float]
    ) -> Dict[str, Any]:
        """
        Ported from skills/volatility-modeling:
        Computes:
        1. Parkinson Volatility (High-Low estimator)
        2. Garman-Klass Volatility (Open-High-Low-Close estimator)
        3. Close-to-Close historical volatility
        """
        n = len(closes)
        if n < 10:
            return {"status": "INSUFFICIENT_DATA"}

        # 1. Parkinson Volatility
        sum_hl_sq = 0.0
        for i in range(n):
            if lows[i] > 0 and highs[i] >= lows[i]:
                log_hl = math.log(highs[i] / lows[i])
                sum_hl_sq += log_hl * log_hl

        parkinson_vol = math.sqrt((1.0 / (4.0 * math.log(2.0) * n)) * sum_hl_sq)

        # 2. Garman-Klass Volatility
        sum_gk = 0.0
        for i in range(n):
            if lows[i] > 0 and highs[i] >= lows[i] and opens[i] > 0 and closes[i] > 0:
                log_hl = math.log(highs[i] / lows[i])
                log_co = math.log(closes[i] / opens[i])
                sum_gk += 0.5 * (log_hl ** 2) - (2.0 * math.log(2.0) - 1.0) * (log_co ** 2)

        gk_vol = math.sqrt(max(0.0, sum_gk / n))

        # Annualized values (assuming 15m intervals: 365 * 24 * 4 = 35040 bars/year)
        ann_factor = math.sqrt(35040)
        ann_parkinson_pct = parkinson_vol * ann_factor * 100.0
        ann_gk_pct = gk_vol * ann_factor * 100.0

        return {
            "parkinson_vol": round(parkinson_vol, 6),
            "garman_klass_vol": round(gk_vol, 6),
            "annualized_parkinson_pct": round(ann_parkinson_pct, 2),
            "annualized_garman_klass_pct": round(ann_gk_pct, 2),
            "volatility_regime": "HIGH" if ann_gk_pct > 60.0 else ("LOW" if ann_gk_pct < 25.0 else "NORMAL")
        }

    @staticmethod
    def run_microstructure_and_slippage(
        order_book: Dict[str, Any],
        target_notional_usdt: float = 25.0,
        taker_fee_pct: float = 0.1
    ) -> Dict[str, Any]:
        """
        Ported from skills/market-microstructure and skills/slippage-modeling:
        Analyzes Binance Spot Order Book:
        1. Order Book Imbalance (OBI)
        2. Bid/Ask Spread in bps
        3. Simulated Taker Slippage for target notional
        4. Hurdle rate to cover round-trip fees (0.20%) + slippage
        """
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        if not bids or not asks:
            return {
                "obi": 0.0,
                "spread_bps": 0.0,
                "slippage_bps": 0.0,
                "hurdle_rate_pct": round(taker_fee_pct * 2, 3),
                "liquidity_rating": "UNKNOWN"
            }

        # 1. Order Book Imbalance (Top 5 levels)
        top_n = min(5, len(bids), len(asks))
        bid_vol = sum(float(bids[i][1]) for i in range(top_n))
        ask_vol = sum(float(asks[i][1]) for i in range(top_n))
        total_vol = bid_vol + ask_vol

        obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

        # 2. Spread in basis points
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2.0
        spread_bps = ((best_ask - best_bid) / mid_price) * 10000.0 if mid_price > 0 else 0.0

        # 3. Simulated VWAP Slippage for BUY order of target_notional_usdt
        accum_cost = 0.0
        accum_qty = 0.0
        needed = target_notional_usdt

        for price_str, qty_str in asks:
            p = float(price_str)
            q = float(qty_str)
            level_notional = p * q
            if accum_cost + level_notional >= needed:
                rem_cost = needed - accum_cost
                rem_qty = rem_cost / p
                accum_qty += rem_qty
                accum_cost = needed
                break
            else:
                accum_qty += q
                accum_cost += level_notional

        vwap_buy = (accum_cost / accum_qty) if accum_qty > 0 else best_ask
        slippage_bps = ((vwap_buy - best_ask) / best_ask) * 10000.0 if best_ask > 0 else 0.0

        # 4. Hurdle rate: roundtrip fees + slippage
        roundtrip_fee_pct = taker_fee_pct * 2.0
        slippage_pct = slippage_bps / 100.0
        hurdle_rate_pct = roundtrip_fee_pct + slippage_pct

        return {
            "order_book_imbalance": round(obi, 3),  # > 0: buying pressure, < 0: selling pressure
            "spread_bps": round(spread_bps, 2),
            "simulated_slippage_bps": round(slippage_bps, 2),
            "hurdle_rate_pct": round(hurdle_rate_pct, 3),
            "liquidity_rating": "EXCELLENT" if spread_bps < 2.0 and slippage_bps < 2.0 else ("GOOD" if spread_bps < 5.0 else "THIN")
        }

    @staticmethod
    def run_mean_reversion(
        closes: List[float],
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, Any]:
        """
        Ported from skills/mean-reversion:
        Calculates:
        1. Bollinger Bands %B
        2. Z-Score of price deviation from SMA
        3. Mean Reversion Signal
        """
        if len(closes) < period:
            return {"status": "INSUFFICIENT_DATA"}

        window = closes[-period:]
        sma = statistics.mean(window)
        stdev = statistics.stdev(window) if len(window) > 1 else 1.0

        current_close = closes[-1]
        z_score = (current_close - sma) / stdev if stdev > 0 else 0.0

        upper = sma + num_std * stdev
        lower = sma - num_std * stdev
        band_range = upper - lower

        percent_b = (current_close - lower) / band_range if band_range > 0 else 0.5

        if percent_b < 0.05 or z_score < -2.0:
            signal = "OVERSOLD_POTENTIAL_BOUNCE"
        elif percent_b > 0.95 or z_score > 2.0:
            signal = "OVERBOUGHT_POTENTIAL_REVERSAL"
        else:
            signal = "NEUTRAL"

        return {
            "percent_b": round(percent_b, 4),
            "z_score": round(z_score, 2),
            "sma_20": round(sma, 4),
            "upper_band": round(upper, 4),
            "lower_band": round(lower, 4),
            "mean_reversion_signal": signal
        }

    @staticmethod
    def run_position_sizing(
        allocated_capital: float,
        entry_price: float,
        stop_loss_price: float,
        current_atr: float,
        max_risk_pct: float = 1.0,
        max_pos_size_pct: float = 25.0
    ) -> Dict[str, Any]:
        """
        Ported from skills/position-sizing and skills/kelly-criterion:
        Calculates:
        1. Fixed Fractional Risk position size
        2. Volatility parity position size
        3. Recommended safe Spot position size in USDT
        """
        if entry_price <= 0 or stop_loss_price <= 0 or entry_price <= stop_loss_price:
            return {"error": "Entry price must be strictly greater than Stop Loss price for Spot BUY"}

        sl_distance = entry_price - stop_loss_price
        sl_pct = (sl_distance / entry_price) * 100.0

        # Maximum USDT willing to lose on this trade
        risk_budget_usdt = allocated_capital * (max_risk_pct / 100.0)

        # 1. Size based on Risk Budget: Size = Risk / (SL Distance %)
        risk_based_size_usdt = (risk_budget_usdt / (sl_pct / 100.0))

        # 2. Hard Cap based on max position size percent (e.g. 25% of bot capital)
        hard_cap_size_usdt = allocated_capital * (max_pos_size_pct / 100.0)

        # 3. ATR Volatility Parity check: Size = (Risk / (2 * ATR)) * Entry Price
        atr_based_size_usdt = (risk_budget_usdt / (2.0 * current_atr)) * entry_price if current_atr > 0 else risk_based_size_usdt

        # Conservative selection: take minimum of all risk-constrained sizes
        recommended_size_usdt = min(risk_based_size_usdt, hard_cap_size_usdt, atr_based_size_usdt)

        # Binance Spot minimum check
        is_above_min_notional = recommended_size_usdt >= 5.0

        return {
            "risk_budget_usdt": round(risk_budget_usdt, 2),
            "sl_distance_pct": round(sl_pct, 2),
            "risk_based_size_usdt": round(risk_based_size_usdt, 2),
            "hard_cap_size_usdt": round(hard_cap_size_usdt, 2),
            "atr_based_size_usdt": round(atr_based_size_usdt, 2),
            "recommended_size_usdt": round(recommended_size_usdt, 2),
            "is_above_min_notional": is_above_min_notional
        }

skill_executor = SkillExecutor()
