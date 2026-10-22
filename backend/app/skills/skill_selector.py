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
        enabled = skill_registry.get_enabled_skills_for_target("gemini_analyst")
        guidelines = [
            f"KỸ NĂNG ĐỊNH LƯỢNG ĐÃ KÍCH HOẠT CHO GEMINI: {', '.join(enabled)}"
        ]

        if "regime_detection" in quant_results:
            reg = quant_results["regime_detection"]
            guidelines.append(
                f"[REGIME DETECTION]: Thị trường hiện tại thuộc {reg['regime']} ({reg['quadrant']}). "
                f"Choppiness Index = {reg['choppiness_index']} (< 50 là Trend, > 61.8 là Ranging/Sideway). "
                f"Khuyến nghị kỹ năng: {reg['recommendation']}"
            )

        if "volatility_modeling" in quant_results:
            vol = quant_results["volatility_modeling"]
            guidelines.append(
                f"[VOLATILITY MODELING]: Biến động Garman-Klass năm hóa = {vol.get('annualized_garman_klass_pct')}%, "
                f"Phân loại rủi ro biến động: {vol.get('volatility_regime')}."
            )

        if "mean_reversion" in quant_results:
            mr = quant_results["mean_reversion"]
            guidelines.append(
                f"[MEAN REVERSION]: Bollinger %B = {mr.get('percent_b')}, Z-Score = {mr.get('z_score')}. "
                f"Trạng thái: {mr.get('mean_reversion_signal')}."
            )

        if "multi_timeframe_alignment" in quant_results:
            mtf = quant_results["multi_timeframe_alignment"]
            htf = mtf.get("htf_trend", {})
            ltf = mtf.get("ltf_trend", {})
            htf_state = "TĂNG (BULLISH)" if htf.get("bullish") else ("GIẢM (BEARISH)" if htf.get("bearish") else "ĐI NGANG (SIDEWAYS)")
            ltf_state = "TĂNG (BULLISH)" if ltf.get("bullish") else ("GIẢM (BEARISH)" if ltf.get("bearish") else "ĐI NGANG (SIDEWAYS)")
            guidelines.append(
                f"[MULTI-TIMEFRAME CONFIRMATION (1H vs 15M)]:\n"
                f"  - Khung lớn 1H (HTF): {htf_state} | EMA9={htf.get('ema9')} | RSI={htf.get('rsi')} | ADX={htf.get('adx')}\n"
                f"  - Khung ngắn 15M (LTF): {ltf_state} | EMA9={ltf.get('ema9')} | RSI={ltf.get('rsi')} | ADX={ltf.get('adx')}\n"
                f"  - Trạng thái liên khung: {mtf.get('alignment')} (Sức mạnh đồng thuận: {mtf.get('alignment_strength')}/100)\n"
                f"  - Đánh giá MTF: {mtf.get('note')}\n"
                f"  - QUY TẮC BẮT BUỘC: CHỈ đề xuất BUY khi allow_buy = True (Cả 1H và 15M đồng thuận TĂNG). "
                f"Tuyệt đối KHÔNG BUY nếu khung 1H đang GIẢM để tránh bắt dao rơi!"
            )

        guidelines.append(
            "YÊU CẦU CHIẾN LƯỢC: Nếu Regime là RANGING_HIGH_VOL (Q4 Choppy Chaos) hoặc Choppiness Index > 61.8, "
            "bắt buộc ưu tiên đề xuất HOLD để tránh bị quét stop loss trong vùng giật hỗn loạn."
        )

        return "\n".join(guidelines)

    @staticmethod
    def get_gpt_skills_prompt(quant_results: Dict[str, Any]) -> str:
        """Builds structured risk and audit guidance from active skills for GPT-6 Luna."""
        enabled = skill_registry.get_enabled_skills_for_target("gpt_reviewer")
        guidelines = [
            f"KỸ NĂNG ĐỊNH LƯỢNG ĐÃ KÍCH HOẠT CHO GPT-6 LUNA REVIEWER: {', '.join(enabled)}"
        ]

        if "microstructure_and_slippage" in quant_results:
            ms = quant_results["microstructure_and_slippage"]
            guidelines.append(
                f"[MARKET MICROSTRUCTURE & SLIPPAGE]: Order Book Imbalance (OBI) = {ms.get('order_book_imbalance')} "
                f"(> 0: lực mua chiếm ưu thế, < 0: lực bán chiếm ưu thế). "
                f"Spread = {ms.get('spread_bps')} bps, Độ trượt giá ước tính = {ms.get('simulated_slippage_bps')} bps. "
                f"Rào cản hòa vốn (Hurdle Rate gồm phí Taker + Slippage) = {ms.get('hurdle_rate_pct')}%. "
                f"Chất lượng thanh khoản: {ms.get('liquidity_rating')}."
            )

        if "regime_detection" in quant_results:
            reg = quant_results["regime_detection"]
            guidelines.append(
                f"[REGIME VETO]: Nếu Gemini đề xuất BUY nhưng thị trường đang ở {reg['regime']} ({reg['quadrant']}) "
                f"hoặc OBI < -0.2 (áp lực bán đè nặng sổ lệnh), bạn có toàn quyền VETO / REJECT hoặc hạ về HOLD."
            )

        if "multi_timeframe_alignment" in quant_results:
            mtf = quant_results["multi_timeframe_alignment"]
            guidelines.append(
                f"[MULTI-TIMEFRAME RISK VETO (1H vs 15M)]:\n"
                f"  - Trạng thái liên khung: {mtf.get('alignment')} (allow_buy = {mtf.get('allow_buy')})\n"
                f"  - Đánh giá: {mtf.get('note')}\n"
                f"  - QUY TẮC THẨM ĐỊNH: Nếu Gemini đề xuất BUY nhưng allow_buy = False hoặc khung lớn 1H đang là DOWNTREND/BEARISH, "
                f"bạn BẮT BUỘC PHẢI REJECT hoặc yêu cầu HOLD để bảo vệ vốn khỏi xu hướng giảm lớn."
            )

        guidelines.append(
            "YÊU CẦU THẨM ĐỊNH RỦI RO: Phải đối chiếu khoảng cách Stop Loss với biến động ATR thực tế. "
            "Nếu khoảng cách Stop Loss nhỏ hơn hurdle rate hòa vốn hoặc không đủ bù đắp trượt giá và phí giao dịch, "
            "phải từ chối lệnh phê duyệt (REJECT)."
        )

        return "\n".join(guidelines)

skill_selector = SkillSelector()
