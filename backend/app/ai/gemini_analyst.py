"""
Gemini Market Analyst (AI số 2)
Chief Market Analyst / Strategy Generator
Analyzes technical indicators, market state, generates trade plan with SL/TP.
"""
import json
from typing import Dict, Any, Tuple, Optional
from app.ai.gateway import AIGateway
from app.config.settings import settings

GEMINI_SYSTEM_PROMPT = """Bạn là Chief Market Analyst (Giám đốc Phân tích Thị trường) của công ty AI Binance Trading Company.
Mục tiêu: Phân tích kỹ thuật, cấu trúc nến, khối lượng và biến động để xác định trạng thái thị trường và đề xuất kế hoạch giao dịch SPOT (Chỉ Mua/Bán Spot, không Margin/Futures).

Yêu cầu nghiêm ngặt:
1. Nhận diện trạng thái thị trường: TRENDING, RANGING, VOLATILE hoặc UNCERTAIN.
2. Đánh giá sức mạnh xu hướng (0-100).
3. Đề xuất action:
   - "BUY": Mở vị thế Spot khi có lợi thế rõ rệt.
   - "SELL": Thoát vị thế Spot nếu đang có tín hiệu đảo chiều hoặc rủi ro.
   - "HOLD": Giữ nguyên trạng thái, kiên nhẫn quan sát khi thị trường nhiễu.
4. Nếu BUY: Bắt buộc cung cấp entry_price, stop_loss hợp lý (dưới hỗ trợ/dựa trên ATR), take_profit, và validity_minutes (thời hạn hiệu lực từ 15-60 phút).
5. Nêu rõ ít nhất 2 điều kiện làm kế hoạch mất hiệu lực (invalidation_conditions).
6. Viết reasoning bằng Tiếng Việt súc tích, chuyên nghiệp theo phong cách Quantitative Trading.
7. ĐẦU RA BẮT BUỘC LÀ JSON CHUẨN với các trường sau, KHÔNG ĐƯỢC CÓ KÝ TỰ NÀO KHÁC NGOÀI JSON:
{
  "market_state": "TRENDING" | "RANGING" | "VOLATILE" | "UNCERTAIN",
  "trend_strength": 75,
  "action": "BUY" | "SELL" | "HOLD",
  "symbol": "BTCUSDT",
  "entry_price": 65400.0,
  "stop_loss": 64200.0,
  "take_profit": 67800.0,
  "validity_minutes": 30,
  "invalidation_conditions": ["Giá thủng 64000", "Khối lượng bán tăng đột biến"],
  "reasoning": "Phân tích chi tiết...",
  "confidence_score": 0.85
}
"""

class GeminiMarketAnalyst:
    def __init__(self, gateway: AIGateway):
        self.gateway = gateway

    async def analyze(
        self,
        symbol: str,
        timeframe: str,
        market_snapshot: Dict[str, Any],
        indicators: Dict[str, Any],
        recent_candles_summary: Dict[str, Any],
        model_id: Optional[str] = None,
        skills_context: Optional[Dict[str, Any]] = None,
        skills_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], int, Dict[str, int]]:
        """Run market analysis using Gemini model with enhanced trading skills."""
        target_model = model_id or settings.GEMINI_MODEL_ID

        user_content = {
            "symbol": symbol,
            "timeframe": timeframe,
            "market_snapshot": market_snapshot,
            "indicators": indicators.get("latest", {}),
            "recent_candles": recent_candles_summary
        }
        if skills_context:
            user_content["trading_skills_quantitative_metrics"] = skills_context

        prompt_parts = [
            f"Dữ liệu thị trường mới nhất cho {symbol} ({timeframe}):\n{json.dumps(user_content, ensure_ascii=False)}"
        ]
        if skills_prompt:
            prompt_parts.append(f"\nCHỈ DẪN KỸ NĂNG ĐỊNH LƯỢNG (CLAUDE TRADING SKILLS):\n{skills_prompt}")

        user_prompt = "\n".join(prompt_parts)

        effective_system_prompt = GEMINI_SYSTEM_PROMPT
        if settings.SCALPING_MODE_ENABLED:
            effective_system_prompt += (
                f"\n\n[CHẾ ĐỘ HIỆN TẠI: SCALPING - LƯỚT SÓNG ĂN MỎNG TÍCH TIỂU THÀNH ĐẠI]\n"
                f"- Hệ thống đang ưu tiên chốt lời nhanh (+{settings.TARGET_TAKE_PROFIT_PERCENT}%) để xoay vòng vốn liên tục.\n"
                f"- Trong thị trường đi ngang (RANGING/SIDEWAY): Hãy CHỦ ĐỘNG đề xuất action: 'BUY' khi có tín hiệu nảy giá ngắn hạn (RSI/StochRSI nảy lên, chạm dải Bollinger dưới bật lên, hoặc volume gom hàng). KHÔNG cần chờ khung 1H phải uptrend mạnh.\n"
                f"- Chỉ đề xuất 'HOLD' khi giá đang đu đỉnh sát dải trên Bollinger (%B > 0.85) hoặc cả hai khung thời gian đang cắm đầu rơi tự do.\n"
                f"- Mục tiêu Take Profit: ~+{settings.TARGET_TAKE_PROFIT_PERCENT}% so với Entry Price.\n"
                f"- Mức Stop Loss: ~-{settings.TARGET_STOP_LOSS_PERCENT}% so với Entry Price.\n"
                f"- Tỷ lệ Risk:Reward tối thiểu từ 1.1:1 đến 1.5:1 là hoàn toàn hợp lệ."
            )

        data, latency_ms, usage = await self.gateway.complete_chat(
            model_id=target_model,
            system_prompt=effective_system_prompt,
            user_prompt=user_prompt,
            reasoning_level=settings.GEMINI_REASONING_LEVEL
        )

        # Validate mandatory fields
        required_keys = ["market_state", "action", "reasoning"]
        for k in required_keys:
            if k not in data:
                raise ValueError(f"Thiếu trường bắt buộc '{k}' trong phản hồi của Gemini Analyst")

        if data["action"] not in ("BUY", "SELL", "HOLD"):
            data["action"] = "HOLD"

        return data, latency_ms, usage
