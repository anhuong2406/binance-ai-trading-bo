"""
GPT-6 Luna Independent Reviewer (AI số 1)
Complementary Market and Risk Reviewer
Adds an independent view, validates the proposal, and can block plans that fail hard safety checks.
"""
import json
from typing import Dict, Any, Optional, Tuple
from app.ai.gateway import AIGateway
from app.config.settings import settings

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
# Rút gọn ~35% so với phiên bản cũ. Logic APPROVE/REJECT/HOLD giữ nguyên,
# bỏ các đoạn giải thích dài không cần thiết trong system prompt.
GPT_SYSTEM_PROMPT = """Bạn là GPT-6 Luna — AI Thẩm định Rủi ro độc lập của AI Binance Trading Company.
Gemini đề xuất kế hoạch; bạn xác nhận hoặc chặn dựa trên phân tích độc lập của chính mình.

QUY TRÌNH:
1. Đọc market_snapshot & quant_indicators TRƯỚC — tự hình thành nhận định riêng.
2. Đối chiếu với gemini_proposal: xác nhận điểm đúng, chỉ ra rủi ro bị bỏ sót.
3. Quyết định: APPROVE nếu kế hoạch khả thi; REJECT nếu vi phạm an toàn cứng; HOLD nếu cần thêm xác nhận.

CHẶN BUY (HOLD/REJECT) KHI:
• Chỉ báo kỹ thuật thực tế mâu thuẫn rõ với đề xuất
• SL bất hợp lý (quá hẹp dễ quét, quá xa vi phạm quản trị vốn)
• R:R ròng sau phí (0.1%/chiều) và spread không đạt tối thiểu
• Gemini đề xuất BUY khi thị trường đang rơi tự do hoặc dữ liệu không đủ tin cậy

KHÔNG tự đổi BUY→SELL hoặc bịa dữ liệu. suggested_adjustment chỉ là ghi chú.
Risk Engine độc lập là chốt cuối cùng ngay cả khi bạn APPROVE.

ĐẦU RA: JSON thuần (không markdown, không text ngoài JSON):
{"decision":"APPROVE","reason":"...","independent_view":"...","supporting_evidence":[],"key_risks":[],"suggested_adjustment":null,"technical_alignment":true,"risk_reward_acceptable":true,"spread_and_fee_acceptable":true,"volatility_acceptable":true,"stop_loss_reasonable":true,"counter_proposal":null}
"""

# Scalping addendum — compact, chỉ thêm khi cần
def _build_scalping_addendum(tf: str, sl_pct: float, min_rr: float) -> str:
    return (
        f"\n[CHẾ ĐỘ SCALPING — {tf}] "
        f"APPROVE khi R:R ròng ≥{min_rr}:1 sau phí+spread. "
        f"SL tối đa {sl_pct}%. "
        f"Chấp nhận BUY Mean Reversion (nảy BB/RSI quá bán) với SL chặt chẽ."
    )


class GPTIndependentReviewer:
    def __init__(self, gateway: AIGateway):
        self.gateway = gateway

    async def review(
        self,
        symbol: str,
        gemini_proposal: Dict[str, Any],
        market_snapshot: Dict[str, Any],
        indicators: Dict[str, Any],
        model_id: Optional[str] = None,
        skills_context: Optional[Dict[str, Any]] = None,
        skills_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], int, Dict[str, int]]:
        """Conduct independent review of Gemini's trading proposal with risk trading skills."""
        target_model = model_id or settings.GPT_MODEL_ID

        # Raw evidence first → reviewer forms own view before seeing proposal
        latest_indicators = indicators.get("latest", {})
        review_payload = {
            "symbol": symbol,
            "market_snapshot": {
                k: v for k, v in market_snapshot.items()
                if k in ("lastPrice", "bestBid", "bestAsk", "spreadPercent", "volume24h")
            },
            "quant_indicators": {
                k: v for k, v in latest_indicators.items()
                if k in (
                    "rsi14", "ema9", "ema21", "ema50", "macd", "macd_signal",
                    "bb_upper", "bb_lower", "atr14", "adx14",
                    "stoch_rsi_k", "stoch_rsi_d", "volume_ratio"
                )
            }
        }
        if skills_context:
            review_payload["risk_metrics"] = skills_context

        # Proposal comes last so reviewer reads evidence first
        review_payload["gemini_proposal"] = gemini_proposal

        prompt_parts = [
            f"Thẩm định giao dịch {symbol}:\n{json.dumps(review_payload, ensure_ascii=False, separators=(',', ':'))}"
        ]
        if skills_prompt:
            prompt_parts.append(f"\n[KỸ NĂNG THẨM ĐỊNH RỦI RO]\n{skills_prompt}")

        user_prompt = "\n".join(prompt_parts)

        effective_system_prompt = GPT_SYSTEM_PROMPT
        if settings.SCALPING_MODE_ENABLED:
            effective_system_prompt += _build_scalping_addendum(
                settings.SCALPING_TIMEFRAME,
                settings.TARGET_STOP_LOSS_PERCENT,
                settings.SCALPING_MIN_NET_RISK_REWARD
            )

        data, latency_ms, usage = await self.gateway.complete_chat(
            model_id=target_model,
            system_prompt=effective_system_prompt,
            user_prompt=user_prompt,
            reasoning_level=settings.GPT_REASONING_LEVEL
        )

        required_keys = ["decision", "reason", "technical_alignment", "risk_reward_acceptable"]
        for k in required_keys:
            if k not in data:
                raise ValueError(f"Thiếu trường bắt buộc '{k}' trong phản hồi của GPT-6 Luna Reviewer")

        if data["decision"] not in ("APPROVE", "REJECT", "HOLD"):
            data["decision"] = "HOLD"

        return data, latency_ms, usage
