"""
Skill Selector
Intelligently selects relevant approved skills and builds targeted prompt guidelines
and quantitative context for Gemini 3.8 Flash High and GPT-6 Luna.
"""
from typing import Dict, Any, List, Optional
from app.skills.skill_registry import skill_registry
from app.skills.skill_executor import skill_executor
from app.skills.skill_validator import skill_validator
from app.skills.skill_audit import skill_audit
from app.config.settings import settings

class SkillSelector:
    """Selects and compiles skill heuristics and calculations for each AI agent."""

    @staticmethod
    def execute_and_bundle_quant_skills(
        candles: List[Any],
        order_book: Optional[Dict[str, Any]] = None,
        allocated_capital: float = 100.0
    ) -> Dict[str, Any]:
        """
        Executes all active pure-Python quant tools and aggregates results.
        Runs validation and logs to SkillAudit.
        """
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        opens = [c.open for c in candles]
        volumes = [c.volume for c in candles]

        results: Dict[str, Any] = {}

        # 1. Regime Detection
        if skill_registry.is_enabled("regime-detection"):
            t_start = skill_audit.get_time_ms()
            try:
                regime = skill_executor.run_regime_detection(highs, lows, closes, volumes)
                val_ok, err = skill_validator.validate_skill_output("regime-detection", regime)
                if val_ok:
                    results["regime_detection"] = regime
                    skill_audit.record(
                        skill_name="regime-detection",
                        action="EXECUTE",
                        status="SUCCESS",
                        duration_ms=skill_audit.get_time_ms() - t_start,
                        output_summary=f"Regime: {regime['regime']} ({regime['quadrant']}), CI: {regime['choppiness_index']}"
                    )
            except Exception as e:
                skill_audit.record("regime-detection", "EXECUTE", "ERROR", skill_audit.get_time_ms() - t_start, str(e))

        # 2. Volatility Modeling
        if skill_registry.is_enabled("volatility-modeling"):
            t_start = skill_audit.get_time_ms()
            try:
                vol = skill_executor.run_volatility_modeling(highs, lows, opens, closes)
                val_ok, err = skill_validator.validate_skill_output("volatility-modeling", vol)
                if val_ok:
                    results["volatility_modeling"] = vol
                    skill_audit.record(
                        skill_name="volatility-modeling",
                        action="EXECUTE",
                        status="SUCCESS",
                        duration_ms=skill_audit.get_time_ms() - t_start,
                        output_summary=f"GK Vol: {vol.get('annualized_garman_klass_pct')}% (Regime: {vol.get('volatility_regime')})"
                    )
            except Exception as e:
                skill_audit.record("volatility-modeling", "EXECUTE", "ERROR", skill_audit.get_time_ms() - t_start, str(e))

        # 3. Mean Reversion
        if skill_registry.is_enabled("mean-reversion"):
            t_start = skill_audit.get_time_ms()
            try:
                mr = skill_executor.run_mean_reversion(closes)
                val_ok, err = skill_validator.validate_skill_output("mean-reversion", mr)
                if val_ok:
                    results["mean_reversion"] = mr
                    skill_audit.record(
                        skill_name="mean-reversion",
                        action="EXECUTE",
                        status="SUCCESS",
                        duration_ms=skill_audit.get_time_ms() - t_start,
                        output_summary=f"%B: {mr.get('percent_b')}, Z-Score: {mr.get('z_score')}, Signal: {mr.get('mean_reversion_signal')}"
                    )
            except Exception as e:
                skill_audit.record("mean-reversion", "EXECUTE", "ERROR", skill_audit.get_time_ms() - t_start, str(e))

        # 4. Microstructure & Slippage (if order_book available)
        if order_book and (skill_registry.is_enabled("market-microstructure") or skill_registry.is_enabled("slippage-modeling")):
            t_start = skill_audit.get_time_ms()
            try:
                micro = skill_executor.run_microstructure_and_slippage(order_book, target_notional_usdt=25.0)
                val_ok, err = skill_validator.validate_skill_output("market-microstructure", micro)
                if val_ok:
                    results["microstructure_and_slippage"] = micro
                    skill_audit.record(
                        skill_name="market-microstructure",
                        action="EXECUTE",
                        status="SUCCESS",
                        duration_ms=skill_audit.get_time_ms() - t_start,
                        output_summary=f"OBI: {micro.get('order_book_imbalance')}, Hurdle: {micro.get('hurdle_rate_pct')}%, Liquidity: {micro.get('liquidity_rating')}"
                    )
            except Exception as e:
                skill_audit.record("market-microstructure", "EXECUTE", "ERROR", skill_audit.get_time_ms() - t_start, str(e))

        return results

    @staticmethod
    def get_gemini_skills_prompt(quant_results: Dict[str, Any]) -> str:
        """Builds structured analytical guidance from active skills for Gemini 3.8 Flash High."""
        guidelines = ["[TÍN HIỆU ĐỊNH LƯỢNG KỸ NĂNG]:"]

        if "regime_detection" in quant_results:
            reg = quant_results["regime_detection"]
            guidelines.append(f"• Regime: {reg['regime']} ({reg['quadrant']}), Choppiness={reg['choppiness_index']:.1f}")

        if "volatility_modeling" in quant_results:
            vol = quant_results["volatility_modeling"]
            guidelines.append(f"• Biến động: Garman-Klass={vol.get('annualized_garman_klass_pct')}%, Mức độ={vol.get('volatility_regime')}")

        if "mean_reversion" in quant_results:
            mr = quant_results["mean_reversion"]
            guidelines.append(f"• Mean Reversion: BB_%B={mr.get('percent_b')}, Z-Score={mr.get('z_score')}, Tín hiệu={mr.get('mean_reversion_signal')}")

        if "multi_timeframe_alignment" in quant_results:
            mtf = quant_results["multi_timeframe_alignment"]
            htf = mtf.get("htf_trend", {})
            ltf = mtf.get("ltf_trend", {})
            htf_state = "TĂNG" if htf.get("bullish") else ("GIẢM" if htf.get("bearish") else "NGANG")
            ltf_state = "TĂNG" if ltf.get("bullish") else ("GIẢM" if ltf.get("bearish") else "NGANG")
            ltf_label = settings.SCALPING_TIMEFRAME if settings.SCALPING_MODE_ENABLED else "15m"
            guidelines.append(f"• MTF (1H vs {ltf_label}): 1H={htf_state} | {ltf_label}={ltf_state} | Đồng thuận={mtf.get('alignment')} ({mtf.get('alignment_strength')}/100) | allow_buy={mtf.get('allow_buy')}")

        if "stoch_rsi" in quant_results:
            sr = quant_results["stoch_rsi"]
            k, d = sr.get("k"), sr.get("d")
            stoch_status = "OVERSOLD" if (k and k < 20) else ("OVERBOUGHT" if (k and k > 80) else "NEUTRAL")
            guidelines.append(f"• StochRSI: K={k}, D={d} ({stoch_status})")

        if "market_session" in quant_results:
            ms = quant_results["market_session"]
            guidelines.append(f"• Phiên: {ms.get('session')} ({ms.get('vn_time')}), Thanh khoản={ms.get('liquidity')}")

        return "\n".join(guidelines)

    @staticmethod
    def get_gpt_skills_prompt(quant_results: Dict[str, Any]) -> str:
        """Builds structured risk and audit guidance from active skills for GPT-6 Luna."""
        guidelines = ["[KIỂM SOÁT RỦI RO KỸ NĂNG]:"]

        if "microstructure_and_slippage" in quant_results:
            ms = quant_results["microstructure_and_slippage"]
            guidelines.append(f"• OBI={ms.get('order_book_imbalance')} | Spread={ms.get('spread_bps')}bps | Slippage={ms.get('simulated_slippage_bps')}bps | Hurdle={ms.get('hurdle_rate_pct')}%")

        if "regime_detection" in quant_results:
            reg = quant_results["regime_detection"]
            guidelines.append(f"• Regime: {reg['regime']} ({reg['quadrant']}) — VETO nếu Choppy Chaos hoặc OBI < -0.2")

        if "multi_timeframe_alignment" in quant_results:
            mtf = quant_results["multi_timeframe_alignment"]
            guidelines.append(f"• MTF: Đồng thuận={mtf.get('alignment')}, allow_buy={mtf.get('allow_buy')} — VETO nếu rơi tự do / spread > 0.15%")

        if "market_session" in quant_results:
            ms = quant_results["market_session"]
            if ms.get("is_dead_zone") or ms.get("quality_score", 100) < 50:
                guidelines.append(f"• Phiên {ms.get('session')}: Thanh khoản mỏng — VETO BUY nếu không có volume bùng nổ")

        guidelines.append("• SL check: Khoảng cách SL phải lớn hơn hurdle rate và trượt giá.")
        return "\n".join(guidelines)

skill_selector = SkillSelector()
