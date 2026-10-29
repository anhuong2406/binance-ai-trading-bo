"""
Market Screener & Best-Pick Selection Engine
AI Binance Trading Company

Two-stage quantitative screener:
Stage 1: Universe Filtering (Capital suitability, 24h volume, ATR volatility, momentum).
Stage 2: Deep Technical & Trade Memory Scoring (ATR%, RSI, EMA trend, Volume flow, Win Rate).
Ranks candidates to identify the #1 Best Pick for single-position capital allocation.
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config.settings import settings
from app.binance.client import BinanceSpotClient
from app.trading.quant_engine import QuantEngine, calculate_rsi, calculate_ema
from app.trading.pair_manager import pair_manager
from app.database.models import TradeMemory

logger = logging.getLogger("market_screener")

EXCLUDED_SYMBOLS = {
    "UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT",
    "FDUSDUSDT", "USDCUSDT", "EURUSDT", "TUSDUSDT",
    "DAIUSDT", "AEURUSDT", "USDPUSDT", "WBTCUSDT", "BUSDUSDT",
    "RLUSDUSDT", "USD1USDT", "USDEUSDT", "PYUSDUSDT", "USDDUSDT"
}

class MarketScreener:
    def __init__(self, binance_client: Optional[BinanceSpotClient] = None):
        if binance_client:
            self.binance_client = binance_client
        else:
            self.binance_client = BinanceSpotClient(
                api_key=settings.BINANCE_API_KEY,
                api_secret=settings.BINANCE_API_SECRET,
                use_testnet=(settings.TRADING_MODE == "TESTNET")
            )
        self._cached_radar: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._cache_ttl_seconds: float = 60.0

    async def scan_market(
        self,
        capital_usdt: float = 5.55,
        session: Optional[AsyncSession] = None,
        force_refresh: bool = False,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Executes complete 2-stage market screening and candidate ranking.
        """
        now = time.time()
        if not force_refresh and self._cached_radar and (now - self._cache_time) < self._cache_ttl_seconds:
            return self._cached_radar

        start_time = time.time()

        # Capital sanity check: If available capital is not enough to buy anything on Binance Spot, STOP scanning!
        active_watched_symbols = set(pair_manager.get_active_symbols())
        has_micro_pairs = any(p in ("DOGEUSDT", "SHIBUSDT") for p in active_watched_symbols)
        min_required_capital = 1.0 if has_micro_pairs else 5.0

        if capital_usdt < min_required_capital:
            logger.info("Vốn khả dụng (%.2f USDT) < %.1f USDT không đủ mua bất kỳ mã nào. Ngừng quét thị trường.", capital_usdt, min_required_capital)
            standby_payload = {
                "status": "INSUFFICIENT_CAPITAL",
                "message": (
                    f"Số dư khả dụng ({capital_usdt:.2f} USDT) < {min_required_capital:.1f} USDT không đủ mở bất kỳ lệnh nào trên sàn Binance. "
                    "Hệ thống đã tự động ngắt toàn bộ tác vụ quét thị trường & phân tích AI để tiết kiệm 100% tài nguyên."
                ),
                "timestamp": int(time.time() * 1000),
                "scan_duration_ms": 0,
                "capital_usdt": capital_usdt,
                "min_notional_eligible": min_required_capital,
                "total_screened_universe": 0,
                "stage1_passed_count": 0,
                "best_pick": None,
                "candidates": []
            }
            self._cached_radar = standby_payload
            self._cache_time = now
            return standby_payload

        logger.info("Bắt đầu quét thị trường Binance Spot (Vốn khả dụng: %.2f USDT)...", capital_usdt)

        # 1. Fetch 24hr tickers for the entire exchange
        try:
            tickers = await self.binance_client.get_ticker_24hr()
            if not isinstance(tickers, list):
                tickers = [tickers] if tickers else []
        except Exception as e:
            logger.error("Không thể lấy dữ liệu 24hr tickers từ Binance: %s", e)
            return self._fallback_response(capital_usdt, str(e))

        # 2. Stage 1: Universe Filtering
        active_watched_symbols = set(pair_manager.get_active_symbols())
        stage1_candidates = []

        min_vol_usdt = 5_000_000.0  # 5M USDT minimum 24h volume for deep liquidity
        # If capital is small, DOGE and SHIB have 1 USDT minNotional; standard pairs have 5 USDT
        min_notional_standard = 5.0

        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or sym in EXCLUDED_SYMBOLS:
                continue

            try:
                quote_vol = float(t.get("quoteVolume", 0.0))
                price_change = float(t.get("priceChangePercent", 0.0))
                last_price = float(t.get("lastPrice", 0.0))
            except (ValueError, TypeError):
                continue

            # Special exemption: always evaluate active watched symbols from pair_manager
            is_watched = sym in active_watched_symbols

            # Capital suitability check:
            # If available capital is under 5.0 USDT, only accept tokens that allow < 5.0 USDT (like DOGE, SHIB)
            if capital_usdt < min_notional_standard and sym not in ("DOGEUSDT", "SHIBUSDT"):
                continue

            # Filtering criteria:
            # 1. Adequate 24h volume
            # 2. Momentum sweet spot (-1.0% to +12.0%) to filter out dying coins or massive pumps
            if is_watched or (quote_vol >= min_vol_usdt and -1.0 <= price_change <= 15.0):
                stage1_candidates.append({
                    "symbol": sym,
                    "last_price": last_price,
                    "price_change_24h": price_change,
                    "quote_volume": quote_vol,
                    "quote_volume_m": round(quote_vol / 1_000_000, 2),
                    "is_watched": is_watched
                })

        # Sort stage 1 by quote volume and watched priority to select Top 12 for deep technical scan
        stage1_candidates.sort(
            key=lambda c: (1 if c["is_watched"] else 0, c["quote_volume"]),
            reverse=True
        )
        selected_for_deep_scan = stage1_candidates[:12]

        if not selected_for_deep_scan:
            return self._fallback_response(capital_usdt, "Không tìm thấy mã nào thỏa mãn điều kiện lọc Tầng 1.")

        # 3. Stage 2: Deep Technical Scan (Fetch 15m klines concurrently)
        deep_scan_tasks = [
            self._fetch_technical_profile(c["symbol"])
            for c in selected_for_deep_scan
        ]
        technical_results = await asyncio.gather(*deep_scan_tasks, return_exceptions=True)

        # 4. Integrate Trade Memory Stats (Historical Win Rate for symbols)
        memory_stats = {}
        if session:
            try:
                memory_stats = await self._get_symbols_trade_memory_stats(
                    session=session,
                    symbols=[c["symbol"] for c in selected_for_deep_scan]
                )
            except Exception as e:
                logger.warning("Không thể lấy thống kê Trade Memory: %s", e)

        # 5. Composite Scoring & Ranking
        ranked_candidates = []
        for i, cand in enumerate(selected_for_deep_scan):
            t_res = technical_results[i]
            if isinstance(t_res, Exception) or not t_res:
                tech_data = {
                    "atr_percent": 1.5,
                    "rsi14": 50.0,
                    "ema_trend": "NEUTRAL",
                    "volume_ratio": 1.0
                }
            else:
                tech_data = t_res

            sym = cand["symbol"]
            # Exclude flat tokens or stablecoins masquerading as trading pairs
            if tech_data["atr_percent"] < 0.35:
                continue

            mem_data = memory_stats.get(sym, {"trades": 0, "win_rate": 0.0})

            # Calculate composite score (0 - 100)
            score, breakdown, reason = self._calculate_candidate_score(
                price_change_24h=cand["price_change_24h"],
                quote_volume_m=cand["quote_volume_m"],
                atr_percent=tech_data["atr_percent"],
                rsi14=tech_data["rsi14"],
                ema_trend=tech_data["ema_trend"],
                mem_stats=mem_data
            )

            ranked_candidates.append({
                "symbol": sym,
                "price": cand["last_price"],
                "price_change_24h": round(cand["price_change_24h"], 2),
                "quote_volume_m": cand["quote_volume_m"],
                "atr_percent": round(tech_data["atr_percent"], 2),
                "rsi14": round(tech_data["rsi14"], 1),
                "ema_trend": tech_data["ema_trend"],
                "score": score,
                "score_breakdown": breakdown,
                "reason": reason,
                "historical_win_rate": mem_data["win_rate"],
                "historical_trades": mem_data["trades"],
                "is_watched": cand["is_watched"]
            })

        # Sort descending by composite score
        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Assign ranks and pick Best Pick
        for rank_idx, item in enumerate(ranked_candidates, start=1):
            item["rank"] = rank_idx
            item["is_best_pick"] = (rank_idx == 1)

        best_pick = ranked_candidates[0] if ranked_candidates else None
        top_candidates = ranked_candidates[:top_n]

        scan_duration_ms = round((time.time() - start_time) * 1000, 1)
        logger.info(
            "Hoàn tất quét thị trường trong %.1fms. Kèo số 1: %s (Điểm: %d/100).",
            scan_duration_ms,
            best_pick["symbol"] if best_pick else "None",
            best_pick["score"] if best_pick else 0
        )

        result_payload = {
            "status": "SUCCESS",
            "timestamp": int(time.time() * 1000),
            "scan_duration_ms": scan_duration_ms,
            "capital_usdt": capital_usdt,
            "min_notional_eligible": 1.0 if capital_usdt < 5.0 else 5.0,
            "total_screened_universe": len(tickers),
            "stage1_passed_count": len(stage1_candidates),
            "best_pick": best_pick,
            "candidates": top_candidates
        }

        self._cached_radar = result_payload
        self._cache_time = now
        return result_payload

    async def _fetch_technical_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetches 15m candles and computes key technical indicators.

        Uses limit=50 for reliable warmup:
          - EMA-21 needs 21 bars, EMA-9 needs 9 bars
          - ATR-14 needs 14 TrueRange values (15 bars)
          - Wilder RSI-14 needs 28+ bars for proper smoothing
          Buffer: 50 - 28 = 22 bars extra → stable values.
        """
        try:
            klines = await self.binance_client.get_klines(symbol, interval="15m", limit=50)
            if not klines or len(klines) < 28:
                return None

            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            closes = [float(k[4]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            last_price = closes[-1]

            # 1. ATR-14 (simple average of last 14 TrueRanges — fast and sufficient for screening)
            tr_list = []
            for j in range(1, len(klines)):
                tr = max(
                    highs[j] - lows[j],
                    abs(highs[j] - closes[j - 1]),
                    abs(lows[j] - closes[j - 1])
                )
                tr_list.append(tr)
            atr14 = sum(tr_list[-14:]) / 14 if len(tr_list) >= 14 else (highs[-1] - lows[-1])
            atr_percent = (atr14 / last_price * 100) if last_price > 0 else 1.5

            # 2. RSI-14 — Wilder's smoothing (proper, reusing QuantEngine logic)
            rsi = 50.0
            rsi_series = calculate_rsi(closes, period=14)
            valid_rsi = [v for v in rsi_series if v is not None]
            if valid_rsi:
                rsi = valid_rsi[-1]

            # 3. EMA Trend: true EMA-9 vs EMA-21 (reusing QuantEngine logic)
            ema9_series = calculate_ema(closes, period=9)
            ema21_series = calculate_ema(closes, period=21)
            ema9_vals = [v for v in ema9_series if v is not None]
            ema21_vals = [v for v in ema21_series if v is not None]

            if ema9_vals and ema21_vals:
                ema9_cur = ema9_vals[-1]
                ema21_cur = ema21_vals[-1]
                if ema9_cur > ema21_cur * 1.002:
                    ema_trend = "BULLISH"
                elif ema9_cur < ema21_cur * 0.998:
                    ema_trend = "BEARISH"
                else:
                    ema_trend = "NEUTRAL"
            else:
                ema_trend = "NEUTRAL"

            # 4. Volume ratio: last bar vs 14-bar average (match ATR period)
            recent_vol = volumes[-1]
            avg_vol = sum(volumes[-14:]) / 14 if len(volumes) >= 14 else recent_vol
            vol_ratio = (recent_vol / avg_vol) if avg_vol > 0 else 1.0

            return {
                "atr_percent": atr_percent,
                "rsi14": rsi,
                "ema_trend": ema_trend,
                "volume_ratio": vol_ratio
            }
        except Exception as e:
            logger.debug("Lỗi tính toán chỉ báo kỹ thuật cho %s: %s", symbol, e)
            return None

    def _calculate_candidate_score(
        self,
        price_change_24h: float,
        quote_volume_m: float,
        atr_percent: float,
        rsi14: float,
        ema_trend: str,
        mem_stats: Dict[str, Any]
    ) -> tuple[int, Dict[str, int], str]:
        """
        Computes composite score (0-100) and rationale.
        """
        breakdown = {
            "momentum": 0,
            "volatility": 0,
            "rsi": 0,
            "liquidity": 0,
            "trade_memory": 0
        }
        reasons = []

        # 1. Momentum & Trend (Max 30 pts)
        if 1.0 <= price_change_24h <= 6.0:
            breakdown["momentum"] += 15
            reasons.append(f"Biên tăng 24h vững chắc ({price_change_24h:+.1f}%)")
        elif 6.0 < price_change_24h <= 12.0:
            breakdown["momentum"] += 10
            reasons.append(f"Dòng tiền vào mạnh ({price_change_24h:+.1f}%)")
        elif 0.0 <= price_change_24h < 1.0:
            breakdown["momentum"] += 8
            reasons.append("Tích lũy ổn định")
        else:
            breakdown["momentum"] += 3

        if ema_trend == "BULLISH":
            breakdown["momentum"] += 15
            reasons.append("Xu hướng ngắn hạn EMA9 > EMA21 tăng")
        elif ema_trend == "NEUTRAL":
            breakdown["momentum"] += 8
        else:
            breakdown["momentum"] += 2

        # 2. Volatility & ATR Profit Potential (Max 25 pts)
        # Scalping with ~5.55 USDT needs enough ATR to cover fees and hit 1.5%-2.5% TP
        if 1.5 <= atr_percent <= 3.5:
            breakdown["volatility"] = 25
            reasons.append(f"Biên độ ATR {atr_percent:.1f}% lý tưởng chốt lời")
        elif 1.0 <= atr_percent < 1.5:
            breakdown["volatility"] = 18
            reasons.append(f"Biên độ ATR {atr_percent:.1f}% khá tốt")
        elif 3.5 < atr_percent <= 5.0:
            breakdown["volatility"] = 18
            reasons.append(f"Biên độ ATR {atr_percent:.1f}% cao, cần SL rộng hơn")
        elif 0.6 <= atr_percent < 1.0:
            breakdown["volatility"] = 12
        elif atr_percent > 5.0:
            breakdown["volatility"] = 10
            reasons.append("Biến động quá mạnh, rủi ro cao")
        else:
            breakdown["volatility"] = 6
            reasons.append("Biến động thấp, chậm chốt lời")

        # 3. RSI Health (Max 20 pts)
        if 45.0 <= rsi14 <= 62.0:
            breakdown["rsi"] = 20
            reasons.append(f"RSI 15m đẹp ({rsi14:.0f}) chưa bị quá mua")
        elif 35.0 <= rsi14 < 45.0:
            breakdown["rsi"] = 15
            reasons.append(f"RSI {rsi14:.0f} vùng hỗ trợ tiềm năng")
        elif 62.0 < rsi14 <= 70.0:
            breakdown["rsi"] = 10
        elif rsi14 < 35.0:
            breakdown["rsi"] = 8
            reasons.append("RSI quá bán")
        else:
            breakdown["rsi"] = 4
            reasons.append("RSI tiệm cận quá mua")

        # 4. Liquidity & Volume (Max 15 pts)
        if quote_volume_m >= 50.0:
            breakdown["liquidity"] = 15
            reasons.append(f"Thanh khoản dồi dào (${quote_volume_m:.0f}M)")
        elif quote_volume_m >= 20.0:
            breakdown["liquidity"] = 12
            reasons.append(f"Thanh khoản tốt (${quote_volume_m:.0f}M)")
        elif quote_volume_m >= 5.0:
            breakdown["liquidity"] = 10
        else:
            breakdown["liquidity"] = 5

        # 5. Trade Memory Bonus / Penalty (-10 to +10 pts)
        win_rate = mem_stats.get("win_rate", 0.0)
        trades = mem_stats.get("trades", 0)
        if trades >= 2:
            if win_rate >= 60.0:
                breakdown["trade_memory"] = 10
                reasons.append(f"Lịch sử giao dịch tốt (Thắng {win_rate:.0f}%)")
            elif win_rate <= 33.0:
                breakdown["trade_memory"] = -10
                reasons.append(f"Cảnh báo: Tỷ lệ thắng lịch sử thấp ({win_rate:.0f}%)")
            else:
                breakdown["trade_memory"] = 0

        total_score = max(5, min(100, sum(breakdown.values())))
        summary_reason = "; ".join(reasons) if reasons else "Đạt tiêu chí sàng lọc thị trường."

        return total_score, breakdown, summary_reason

    async def _get_symbols_trade_memory_stats(
        self,
        session: AsyncSession,
        symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Queries historical trade performance for a list of symbols.

        Uses a single batch IN (...) query instead of N separate queries
        to avoid the N+1 database round-trip pattern.
        """
        if not symbols:
            return {}

        stats: Dict[str, Dict[str, Any]] = {s: {"trades": 0, "win_rate": 0.0} for s in symbols}

        # Single batch query: fetch symbol + outcome for all symbols at once
        stmt = (
            select(TradeMemory.symbol, TradeMemory.outcome)
            .where(TradeMemory.symbol.in_(symbols))
        )
        res = await session.execute(stmt)
        rows = res.all()  # list of (symbol, outcome) tuples

        # Aggregate in Python — avoids GROUP BY complexity while keeping 1 round-trip
        counts: Dict[str, Dict[str, int]] = {}
        for sym, outcome in rows:
            if sym not in counts:
                counts[sym] = {"total": 0, "wins": 0}
            counts[sym]["total"] += 1
            if outcome == "WIN":
                counts[sym]["wins"] += 1

        for sym, c in counts.items():
            win_rate = (c["wins"] / c["total"]) * 100.0 if c["total"] > 0 else 0.0
            stats[sym] = {"trades": c["total"], "win_rate": win_rate}

        return stats

    def _fallback_response(self, capital_usdt: float, message: str) -> Dict[str, Any]:
        """Provides graceful fallback response if network fails.

        Note: Returns empty candidates — no hardcoded stale prices.
        The frontend should display the error message and retry.
        """
        return {
            "status": "FALLBACK",
            "message": f"⚠️ Không thể quét thị trường: {message}. Kiểm tra kết nối mạng và thử lại.",
            "timestamp": int(time.time() * 1000),
            "scan_duration_ms": 0,
            "capital_usdt": capital_usdt,
            "min_notional_eligible": 1.0 if capital_usdt < 5.0 else 5.0,
            "total_screened_universe": 0,
            "stage1_passed_count": 0,
            "best_pick": None,
            "candidates": []
        }

# Global singleton instance
market_screener = MarketScreener()
