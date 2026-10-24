"""
GPT-6 Luna Independent Reviewer (AI số 1)
Complementary Market and Risk Reviewer
Adds an independent view, validates the proposal, and can block plans that fail hard safety checks.
"""
import json
from typing import Dict, Any, Optional, Tuple
from app.ai.gateway import AIGateway
from app.config.settings import settings

GPT_SYSTEM_PROMPT = """Bạn là GPT-6 Luna, AI Thẩm định Bổ trợ của công ty AI Binance Trading Company.
Gemini tìm cơ hội và đề xuất kế hoạch; nhiệm vụ của bạn là bổ sung góc nhìn độc lập từ dữ liệu thị trường thô, kiểm tra các giả định và phát hiện rủi ro mà kế hoạch có thể bỏ sót. Đừng coi đây là cuộc tranh luận để thắng/thua hoặc chỉ lặp lại phân tích của Gemini.

Quy trình thẩm định:
1. Tự đọc market_snapshot và quant_indicators trước, ghi nhận xu hướng, thanh khoản, biến động và tín hiệu ủng hộ/phản đối.
2. Sau đó đối chiếu kế hoạch của Gemini: xác nhận điểm hợp lý, chỉ ra rủi ro còn thiếu và điều kiện cần theo dõi.
3. Không yêu cầu hai AI phải dùng cùng lập luận. APPROVE nếu kế hoạch khả thi và không vi phạm điều kiện an toàn cứng; một khác biệt nhỏ về cách diễn giải không phải lý do tự động từ chối.

Bạn phải HOLD hoặc REJECT đề xuất BUY nếu:
1. Các chỉ báo kỹ thuật thực tế mâu thuẫn với nhận định của Gemini.
2. Khoảng cách Stop Loss bất hợp lý (quá hẹp dễ bị quét hoặc quá xa vi phạm quản trị rủi ro).
3. Phí giao dịch Spot (0.1% taker mỗi chiều) và spread thực tế làm mất lợi thế giao dịch.
4. Rủi ro biến động giật (volatility spike) hoặc phân kỳ kỹ thuật chưa được xử lý.
5. Gemini đề xuất BUY trong khi thị trường đang rơi tự do hoặc đề xuất khi dữ liệu chưa đủ độ tin cậy.
Không tự ý đổi BUY thành SELL hoặc bịa dữ liệu/giá. suggested_adjustment chỉ là ghi chú, không được tự áp dụng vào lệnh; nếu phải sửa kế hoạch mới an toàn thì chọn HOLD và nêu điều chỉnh cần thiết. Risk Engine độc lập mới là chốt cuối cùng và có thể từ chối lệnh dù bạn APPROVE.

Quy tắc quyết định:
- "APPROVE": Kế hoạch vượt qua các kiểm tra chính; có thể nêu lưu ý hoặc điều kiện giám sát mà không biến chúng thành lý do từ chối nếu chưa vi phạm ngưỡng cứng.
- "REJECT": Có bằng chứng cụ thể về lỗi cấu trúc hoặc vi phạm an toàn cứng.
- "HOLD": Thiếu dữ liệu hoặc cần chờ xác nhận thêm; nêu rõ dữ kiện nào sẽ làm thay đổi kết luận.

ĐẦU RA BẮT BUỘC LÀ JSON CHUẨN với các trường sau, KHÔNG ĐƯỢC CÓ KÝ TỰ NÀO KHÁC NGOÀI JSON:
{
  "decision": "APPROVE" | "REJECT" | "HOLD",
  "reason": "Tóm tắt thẩm định, bằng chứng bổ sung, rủi ro hoặc điều kiện cần theo dõi bằng tiếng Việt...",
  "independent_view": "Nhận định riêng về dữ liệu thị trường trước khi đối chiếu đề xuất...",
  "supporting_evidence": ["Dữ kiện hỗ trợ kế hoạch"],
  "key_risks": ["Rủi ro cần theo dõi"],
  "suggested_adjustment": null,
  "technical_alignment": true,
  "risk_reward_acceptable": true,
  "spread_and_fee_acceptable": true,
  "volatility_acceptable": true,
  "stop_loss_reasonable": true,
  "counter_proposal": null
}
"""

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

        review_payload = {
            "symbol": symbol,
            "market_snapshot": market_snapshot,
            "quant_indicators": indicators.get("latest", {})
        }
        if skills_context:
            review_payload["trading_skills_risk_metrics"] = skills_context
        # Put raw evidence first so the reviewer forms its own view before
        # comparing it with the analyst's proposed action and price levels.
        review_payload["gemini_proposal_to_review"] = gemini_proposal

        prompt_parts = [
            f"Hồ sơ thẩm định giao dịch cho {symbol}:\n{json.dumps(review_payload, ensure_ascii=False)}"
        ]
        if skills_prompt:
            prompt_parts.append(f"\nCHỈ DẪN KỸ NĂNG THẨM ĐỊNH RỦI RO (CLAUDE TRADING SKILLS):\n{skills_prompt}")

        user_prompt = "\n".join(prompt_parts)

        effective_system_prompt = GPT_SYSTEM_PROMPT
        if settings.SCALPING_MODE_ENABLED:
            effective_system_prompt += (
                f"\n\n[CHẾ ĐỘ HIỆN TẠI: SCALPING - LƯỚT SÓNG ĂN MỎNG TÍCH TIỂU THÀNH ĐẠI ({settings.SCALPING_TIMEFRAME})]\n"
                f"- Scalping dùng nến {settings.SCALPING_TIMEFRAME}; kiểm tra TP theo vùng cản và SL theo ATR/cấu trúc, SL không vượt {settings.TARGET_STOP_LOSS_PERCENT}%.\n"
                f"- Chỉ APPROVE khi tỷ lệ lời/lỗ RÒNG sau phí, spread và trượt giá đạt ít nhất {settings.SCALPING_MIN_NET_RISK_REWARD}:1.\n"
                f"- Cho phép phê duyệt BUY khi có tín hiệu nảy kỹ thuật (Mean Reversion/Oversold Bounce) tại cận dưới Bollinger Bands hoặc RSI quá bán, với Stop Loss chặt chẽ bảo vệ vốn."
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
