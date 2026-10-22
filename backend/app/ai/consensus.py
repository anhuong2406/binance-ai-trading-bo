"""
Decision Consensus Engine
Harmonizes Gemini Market Analyst and GPT-6 Luna Reviewer.
Proceeds only when both AI agents achieve affirmative consensus.
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
            return ConsensusResult(
                action="HOLD",
                approved=False,
                symbol=symbol,
                reason=f"Hai AI bất đồng: Gemini đề xuất {gemini_action} nhưng GPT-6 Luna {gpt_decision} vì: {gpt_reason}",
                gemini_action=gemini_action,
                gpt_decision=gpt_decision,
                gemini_reasoning=gemini_reason,
                gpt_reasoning=gpt_reason
            )

        # Both agree: validate prices
        entry = gemini_result.get("entry_price")
        sl = gemini_result.get("stop_loss")
        tp = gemini_result.get("take_profit")

        if gemini_action == "BUY":
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

        # Consensus reached!
        return ConsensusResult(
            action=gemini_action,
            approved=True,
            symbol=symbol,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            reason=f"ĐỒNG THUẬN CAO: Gemini đề xuất {gemini_action} và GPT-6 Luna đã thẩm định APPROVE. Sẵn sàng chuyển tới Risk Engine.",
            gemini_action=gemini_action,
            gpt_decision=gpt_decision,
            gemini_reasoning=gemini_reason,
            gpt_reasoning=gpt_reason
        )
