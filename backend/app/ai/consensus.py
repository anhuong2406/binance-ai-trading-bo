"""
Decision Review Engine
Gemini proposes a trade setup; GPT adds an independent review and safety verdict.
The deterministic Risk Engine remains the final execution gate.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel

class ConsensusResult(BaseModel):
    action: str  # BUY, SELL, HOLD
    approved: bool
    symbol: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str
    gemini_action: str
    gpt_decision: str
    gemini_reasoning: str
    gpt_reasoning: str

class DecisionConsensus:
    @classmethod
    def evaluate_consensus(
        cls,
        symbol: str,
        gemini_result: Dict[str, Any],
        gpt_result: Dict[str, Any]
    ) -> ConsensusResult:
        gemini_action = gemini_result.get("action", "HOLD").upper()
        gpt_decision = gpt_result.get("decision", "HOLD").upper()
        gemini_reason = gemini_result.get("reasoning", "")
        gpt_reason = gpt_result.get("reason", "")

        # Default fallback
        if gemini_action not in ("BUY", "SELL"):
            return ConsensusResult(
                action="HOLD",
                approved=False,
                symbol=symbol,
                reason=f"Gemini đề xuất {gemini_action}: Giữ trạng thái quan sát.",
                gemini_action=gemini_action,
                gpt_decision=gpt_decision,
                gemini_reasoning=gemini_reason,
                gpt_reasoning=gpt_reason
            )

        if gpt_decision != "APPROVE":
            verdict = "cần chờ xác nhận thêm" if gpt_decision == "HOLD" else "phát hiện rủi ro cần chặn"
            return ConsensusResult(
                action="HOLD",
                approved=False,
                symbol=symbol,
                reason=(
                    f"GPT thẩm định {gpt_decision} ({verdict}); đề xuất {gemini_action} của Gemini chưa được chuyển tới Risk Engine. "
                    f"GPT bổ sung điểm bất đồng cần xem xét trước khi vào lệnh: {gpt_reason}"
                ),
                gemini_action=gemini_action,
                gpt_decision=gpt_decision,
                gemini_reasoning=gemini_reason,
                gpt_reasoning=gpt_reason
            )

        # Validate the executable prices before sending the proposal to risk checks.
        entry = gemini_result.get("entry_price")
        sl = gemini_result.get("stop_loss")
        tp = gemini_result.get("take_profit")

        if gemini_action == "BUY":
            # The reviewer may add caveats without requiring the exact same
            # interpretation, but explicit failures on core safety checks block.
            failed_checks = [
                label for key, label in (
                    ("technical_alignment", "đối chiếu kỹ thuật"),
                    ("risk_reward_acceptable", "tỷ lệ lời/lỗ"),
                    ("spread_and_fee_acceptable", "phí và spread"),
                    ("volatility_acceptable", "biến động"),
                    ("stop_loss_reasonable", "Stop Loss"),
                )
                if gpt_result.get(key) is False
            ]
            if failed_checks:
                return ConsensusResult(
                    action="HOLD",
                    approved=False,
                    symbol=symbol,
                    reason=(
                        "GPT thẩm định phát hiện điểm an toàn chưa đạt ("
                        + ", ".join(failed_checks)
                        + f"); đề xuất BUY chưa được chuyển tới Risk Engine. Chi tiết: {gpt_reason}"
                    ),
                    gemini_action=gemini_action,
                    gpt_decision=gpt_decision,
                    gemini_reasoning=gemini_reason,
                    gpt_reasoning=gpt_reason
                )

            if not (entry and sl and tp):
                return ConsensusResult(
                    action="HOLD",
                    approved=False,
                    symbol=symbol,
                    reason="Kế hoạch BUY của Gemini thiếu thông tin Entry, Stop Loss hoặc Take Profit.",
                    gemini_action=gemini_action,
                    gpt_decision=gpt_decision,
                    gemini_reasoning=gemini_reason,
                    gpt_reasoning=gpt_reason
                )
            if not (sl < entry < tp):
                return ConsensusResult(
                    action="HOLD",
                    approved=False,
                    symbol=symbol,
                    reason=f"Mức giá bất hợp lý cho lệnh BUY: SL ({sl}) >= Entry ({entry}) hoặc TP ({tp}) <= Entry ({entry})",
                    gemini_action=gemini_action,
                    gpt_decision=gpt_decision,
                    gemini_reasoning=gemini_reason,
                    gpt_reasoning=gpt_reason
                )

        # A reviewer verdict is a quality gate, not a requirement that both
        # agents use identical reasoning. Risk Engine still checks execution.
        return ConsensusResult(
            action=gemini_action,
            approved=True,
            symbol=symbol,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            reason=f"Đã thẩm định: Gemini đề xuất {gemini_action}; GPT bổ sung góc nhìn và APPROVE. Chuyển tới Risk Engine để kiểm tra giới hạn cuối.",
            gemini_action=gemini_action,
            gpt_decision=gpt_decision,
            gemini_reasoning=gemini_reason,
            gpt_reasoning=gpt_reason
        )

    @classmethod
    def evaluate_single_analyst(
        cls,
        symbol: str,
        gemini_result: Dict[str, Any]
    ) -> ConsensusResult:
        """
        Single AI Model Evaluation (Gemini 3.8 Flash High only).
        Bypasses GPT Reviewer to save 50% tokens and minimize latency.
        Directly validates price sanity before sending to Risk Engine.
        """
        gemini_action = gemini_result.get("action", "HOLD").upper()
        gemini_reason = gemini_result.get("reasoning", "")

        if gemini_action not in ("BUY", "SELL"):
            return ConsensusResult(
                action="HOLD",
                approved=False,
                symbol=symbol,
                reason=f"Gemini 3.8 Flash High đề xuất {gemini_action}: Giữ trạng thái quan sát.",
                gemini_action=gemini_action,
                gpt_decision="BYPASS",
                gemini_reasoning=gemini_reason,
                gpt_reasoning="Single AI Mode: Đã bỏ qua GPT Reviewer để tiết kiệm 100% token thẩm định."
            )

        entry = gemini_result.get("entry_price")
        sl = gemini_result.get("stop_loss")
        tp = gemini_result.get("take_profit")

        if gemini_action == "BUY":
            if not (entry and sl and tp):
                return ConsensusResult(
                    action="HOLD",
                    approved=False,
                    symbol=symbol,
                    reason="Kế hoạch BUY của Gemini 3.8 Flash thiếu thông tin Entry, Stop Loss hoặc Take Profit.",
                    gemini_action=gemini_action,
                    gpt_decision="BYPASS",
                    gemini_reasoning=gemini_reason,
                    gpt_reasoning="Single AI Mode"
                )
            if not (sl < entry < tp):
                return ConsensusResult(
                    action="HOLD",
                    approved=False,
                    symbol=symbol,
                    reason=f"Mức giá bất hợp lý cho lệnh BUY: SL ({sl}) >= Entry ({entry}) hoặc TP ({tp}) <= Entry ({entry})",
                    gemini_action=gemini_action,
                    gpt_decision="BYPASS",
                    gemini_reasoning=gemini_reason,
                    gpt_reasoning="Single AI Mode"
                )

        return ConsensusResult(
            action=gemini_action,
            approved=True,
            symbol=symbol,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            reason=f"Gemini 3.8 Flash High đề xuất {gemini_action}. Chuyển trực tiếp tới Risk Engine thẩm định an toàn vốn.",
            gemini_action=gemini_action,
            gpt_decision="BYPASS",
            gemini_reasoning=gemini_reason,
            gpt_reasoning="Single AI Mode: Phê duyệt trực tiếp từ Gemini 3.8 Flash High (0 token GPT)."
        )
