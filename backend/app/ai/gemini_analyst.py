"""
Gemini Market Analyst (AI số 2)
Opportunity Analyst / Strategy Generator
Finds candidate setups and gives GPT-6 Luna a clear, evidence-based plan to review.
"""
import json
from typing import Dict, Any, Tuple, Optional
from app.ai.gateway import AIGateway
from app.config.settings import settings

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
# Compact & action-oriented. Khoảng ~40% ít token hơn phiên bản cũ.
# Scalping addendum được thêm động ở dưới khi cần, tránh lặp thông tin.
GEMINI_SYSTEM_PROMPT = """Bạn là Gemini Market Analyst — chuyên gia phân tích kỹ thuật Spot Binance (BUY/SELL/HOLD; không Margin/Futures).

NHIỆM VỤ: Đọc dữ liệu → xác định trạng thái thị trường → đề xuất kế hoạch giao dịch.

QUY TẮC BẮT BUỘC:
1. market_state: TRENDING | RANGING | VOLATILE | UNCERTAIN
2. action: BUY (lợi thế rõ, entry/SL/TP hợp lệ) | SELL (đảo chiều/rủi ro) | HOLD (thị trường nhiễu)
3. Nếu BUY → PHẢI có: entry_price, stop_loss (dưới hỗ trợ/ATR), take_profit, validity_minutes (15–60)
4. ≥2 invalidation_conditions (điều kiện làm kế hoạch mất giá trị)
5. reasoning: Tiếng Việt — tách fact (quan sát) khỏi inference (suy luận), nêu rủi ro chính
6. Phí Spot 0.20%: TP phải vượt phí và đạt R:R tối thiểu sau chi phí
7. HOLD khi thiếu tín hiệu xác nhận; đừng ép BUY khi thị trường mơ hồ

ĐẦU RA: JSON thuần, không markdown, không text bên ngoài JSON:
{"market_state":"TRENDING","trend_strength":75,"action":"BUY","symbol":"BTCUSDT","entry_price":65400.0,"stop_loss":64200.0,"take_profit":67800.0,"validity_minutes":30,"invalidation_conditions":["Giá thủng 64000","KL bán đột biến"],"reasoning":"...","confidence_score":0.85}
"""

# Scalping addendum — chỉ nối vào khi SCALPING_MODE_ENABLED = True
def _build_scalping_addendum(tf: str, sl_pct: float, min_rr: float) -> str:
    return (
        f"\n[CHẾ ĐỘ SCALPING — {tf}] "
        f"Mục tiêu: chốt lời nhanh từng nhịp ngắn. "
        f"BUY hợp lệ khi: (a) Xu hướng thuận EMA9>EMA21 hoặc (b) Nảy kỹ thuật từ cận dưới Bollinger/RSI<30. "
        f"TP theo cản gần nhất (1.0%–1.8%); SL tối đa {sl_pct}%; R:R ròng sau phí ≥{min_rr}:1. "
        f"HOLD chỉ khi giá rơi tự do không có nến phản ứng hoặc spread >0.15%."
    )


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

        # Build compact user payload — only send what AI needs to reason
        latest_indicators = indicators.get("latest", {})
        user_content = {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_price": market_snapshot.get("lastPrice"),
            "spread_pct": market_snapshot.get("spreadPercent"),
            "best_bid": market_snapshot.get("bestBid"),
            "best_ask": market_snapshot.get("bestAsk"),
            "indicators": {
                k: v for k, v in latest_indicators.items()
                if k in (
                    "rsi14", "ema9", "ema21", "ema50", "macd", "macd_signal",
                    "bb_upper", "bb_lower", "bb_mid", "atr14", "adx14",
                    "stoch_rsi_k", "stoch_rsi_d", "volume_ratio", "market_session"
                )
            },
            "recent_candles": recent_candles_summary
        }
        if skills_context:
            user_content["quant_skills"] = skills_context

        prompt_parts = [
            f"Phân tích {symbol} ({timeframe}):\n{json.dumps(user_content, ensure_ascii=False, separators=(',', ':'))}"
        ]
        if skills_prompt:
            prompt_parts.append(f"\n[KỸ NĂNG ĐỊNH LƯỢNG]\n{skills_prompt}")

        user_prompt = "\n".join(prompt_parts)

        # Build effective system prompt
        effective_system_prompt = GEMINI_SYSTEM_PROMPT
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
