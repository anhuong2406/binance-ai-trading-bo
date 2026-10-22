"""
Unified AI Gateway Adapter for Dual AI Models (Gemini + GPT)
Connects to single AI Base URL with shared API Key.
Supports structured JSON parsing, latency tracking, token accounting, and reasoning levels.
"""
import json
import time
import re
from typing import Dict, Any, Optional, Tuple
import httpx
from app.config.settings import settings
from app.security.sanitizer import sanitize_for_prompt

class AIGateway:
    def resolve_base_url(self, base_url: Optional[str], api_key: str) -> str:
        if base_url and base_url.strip():
            return base_url.rstrip("/")
        # Auto-detect endpoint based on key pattern
        if api_key.startswith("AIzaSy"):
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        if api_key.startswith("sk-or-"):
            return "https://openrouter.ai/api/v1"
        return "https://api.openai.com/v1"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        raw_key = api_key or settings.AI_API_KEY
        self.api_key = raw_key
        self.base_url = self.resolve_base_url(base_url or settings.AI_BASE_URL, self.api_key)
        self.timeout = settings.AI_TIMEOUT_SECONDS
        self.max_retries = settings.AI_MAX_RETRIES

    def update_config(self, base_url: str, api_key: str):
        self.api_key = api_key
        self.base_url = self.resolve_base_url(base_url, api_key)

    def _extract_json(self, raw_content: str) -> Dict[str, Any]:
        """Extract and parse valid JSON from AI response, handling markdown blocks."""
        if not raw_content:
            raise ValueError("Phản hồi từ AI rỗng")
        
        # Look for ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content, re.IGNORECASE)
        candidate = json_match.group(1).strip() if json_match else raw_content.strip()

        # Try parsing candidate
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Fallback: find first '{' and last '}'
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(candidate[start : end + 1])
            raise ValueError(f"Không thể phân tích phản hồi AI thành JSON hợp lệ: {raw_content[:200]}")

    async def complete_chat(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        reasoning_level: Optional[str] = None,
        temperature: float = 0.2
    ) -> Tuple[Dict[str, Any], int, Dict[str, int]]:
        """
        Sends chat completion request to Gateway.
        Returns: (parsed_json_dict, latency_ms, token_usage)
        """
        if not self.api_key:
            raise ValueError("Chưa cấu hình AI API Key!")

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Sanitize prompts
        clean_system = sanitize_for_prompt(system_prompt)
        clean_user = sanitize_for_prompt(user_prompt)

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": clean_system},
                {"role": "user", "content": clean_user}
            ],
            "temperature": temperature,
            "max_tokens": settings.AI_MAX_TOKENS,
            "response_format": {"type": "json_object"}
        }

        # Add reasoning effort if model / gateway supports it
        if reasoning_level and reasoning_level.lower() in ("high", "medium", "low"):
            # Some gateways accept reasoning_effort
            payload["reasoning_effort"] = reasoning_level.lower()

        last_error = None
        for attempt in range(self.max_retries):
            start_time = time.time()
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    
                    # If gateway rejected response_format or reasoning_effort, retry without them
                    if resp.status_code == 400 and ("response_format" in resp.text or "reasoning" in resp.text):
                        payload.pop("response_format", None)
                        payload.pop("reasoning_effort", None)
                        resp = await client.post(endpoint, json=payload, headers=headers)

                    resp.raise_for_status()
                    latency_ms = int((time.time() - start_time) * 1000)

                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise ValueError(f"Gateway không trả về choices nào: {data}")

                    content = choices[0].get("message", {}).get("content", "")
                    parsed_json = self._extract_json(content)
                    usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

                    return parsed_json, latency_ms, usage
            except Exception as e:
                last_error = e
                # Wait briefly before retry
                time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"Lỗi gọi AI Model [{model_id}]: {str(last_error)}")

    async def test_connection(
        self,
        gemini_model_id: str,
        gpt_model_id: str
    ) -> Dict[str, Any]:
        """Test both models via the single gateway."""
        test_sys = "You are a trading test probe. Output valid JSON only."
        test_user = "Respond with JSON containing status 'ok' and test timestamp."

        results = {}
        # Test Gemini
        try:
            gemini_json, gemini_ms, gemini_usage = await self.complete_chat(
                model_id=gemini_model_id,
                system_prompt=test_sys,
                user_prompt=test_user
            )
            results["gemini"] = {
                "status": "connected",
                "model_id": gemini_model_id,
                "latency_ms": gemini_ms,
                "tokens": gemini_usage,
                "output": gemini_json
            }
        except Exception as e:
            results["gemini"] = {
                "status": "error",
                "model_id": gemini_model_id,
                "error": str(e)
            }

        # Test GPT
        try:
            gpt_json, gpt_ms, gpt_usage = await self.complete_chat(
                model_id=gpt_model_id,
                system_prompt=test_sys,
                user_prompt=test_user
            )
            results["gpt"] = {
                "status": "connected",
                "model_id": gpt_model_id,
                "latency_ms": gpt_ms,
                "tokens": gpt_usage,
                "output": gpt_json
            }
        except Exception as e:
            results["gpt"] = {
                "status": "error",
                "model_id": gpt_model_id,
                "error": str(e)
            }

        return results

ai_gateway = AIGateway()
