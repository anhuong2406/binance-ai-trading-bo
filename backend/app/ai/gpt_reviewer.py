"""
GPT-6 Luna Independent Reviewer (AI số 1)
Chief Risk Reviewer / Independent Analyst
Independently cross-checks Gemini's proposal against raw indicators, fees, spread, and risks.
Has full authority to REJECT or veto Gemini.
"""
import json
from typing import Dict, Any, Optional, Tuple
from app.ai.gateway import AIGateway
from app.config.settings import settings

GPT_SYSTEM_PROMPT = """Bạn là GPT-6 Luna, Chief Risk Reviewer & Giám đốc Thẩm định Độc lập của công ty AI Binance Trading Company.
Mục tiêu: Đánh giá phản biện độc lập, khách quan, khắt khe đối với đề xuất giao dịch của Gemini Market Analyst trước khi lệnh có thể được chuyển sang Risk Engine.

Bạn CÓ TOÀN QUYỀN VETO / TỪ CHỐI đề xuất của Gemini nếu:
1. Các chỉ báo kỹ thuật thực tế mâu thuẫn với nhận định của Gemini.
2. Tỷ lệ Risk:Reward không đạt ít nhất 1.8:1 hoặc khoảng cách Stop Loss bất hợp lý (quá hẹp dễ bị quét hoặc quá xa vi phạm quản trị rủi ro).
3. Phí giao dịch Spot (0.1% taker mỗi chiều) và spread thực tế làm mất lợi thế giao dịch.
4. Rủi ro biến động giật (volatility spike) hoặc phân kỳ kỹ thuật chưa được xử lý.
5. Gemini đề xuất BUY trong khi thị trường đang rơi tự do hoặc đề xuất khi dữ liệu chưa đủ độ tin cậy.

Quy tắc quyết định:
- "APPROVE": Chỉ phê duyệt khi bạn hoàn toàn đồng ý về mặt kỹ thuật và rủi ro.
- "REJECT": Từ chối thẳng thừng khi nhận thấy rủi ro bất cân xứng, chỉ báo mâu thuẫn.
- "HOLD": Khuyên nên đứng ngoài quan sát thêm một vài nến.

ĐẦU RA BẮT BUỘC LÀ JSON CHUẨN với các trường sau, KHÔNG ĐƯỢC CÓ KÝ TỰ NÀO KHÁC NGOÀI JSON:
{
  "decision": "APPROVE" | "REJECT" | "HOLD",
  "reason": "Giải trình phản biện độc lập chi tiết bằng tiếng Việt...",
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
        model_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], int, Dict[str, int]]:
        """Conduct independent review of Gemini's trading proposal."""
        target_model = model_id or settings.GPT_MODEL_ID

        review_payload = {
            "symbol": symbol,
            "gemini_proposal": gemini_proposal,
            "market_snapshot": market_snapshot,
            "quant_indicators": indicators.get("latest", {})
        }

        user_prompt = f"Hồ sơ thẩm định giao dịch cho {symbol}:\n{json.dumps(review_payload, ensure_ascii=False)}"

        data, latency_ms, usage = await self.gateway.complete_chat(
            model_id=target_model,
            system_prompt=GPT_SYSTEM_PROMPT,
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
