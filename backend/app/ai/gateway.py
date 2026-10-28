"""
Unified AI Gateway Adapter for Dual AI Models (Gemini + GPT)
Connects to single AI Base URL with shared API Key.
Supports structured JSON parsing, latency tracking, token accounting, and reasoning levels.
"""
import json
import time
import re
import asyncio
from typing import Dict, Any, Optional, Tuple, Set
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
        # Cache gateways that rejected response_format / reasoning_effort to avoid redundant 400 retries
        self._unsupported_features: Set[str] = set()
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self, timeout: float = 90.0) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=25, keepalive_expiry=30.0)
            self._http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._http_client

    async def aclose(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def update_config(self, base_url: str, api_key: str):
        self.api_key = api_key
        self.base_url = self.resolve_base_url(base_url, api_key)
        self._unsupported_features.clear()
        if self._http_client and not self._http_client.is_closed:
            asyncio.create_task(self._http_client.aclose())
            self._http_client = None

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
        active_key = self.api_key or settings.AI_API_KEY
        if not active_key:
            raise ValueError("Chưa cấu hình AI API Key!")

        active_base = self.resolve_base_url(self.base_url or settings.AI_BASE_URL, active_key)
        active_timeout = float(settings.AI_TIMEOUT_SECONDS or self.timeout or 90.0)
        endpoint = f"{active_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {active_key}",
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
            "stream": False,
        }

        # Only add response_format if not previously rejected by this gateway
        if "response_format" not in self._unsupported_features:
            payload["response_format"] = {"type": "json_object"}

        # Add reasoning effort if model / gateway supports it
        if (reasoning_level and reasoning_level.lower() in ("high", "medium", "low")
                and "reasoning_effort" not in self._unsupported_features):
            payload["reasoning_effort"] = reasoning_level.lower()

        client = self._get_http_client(timeout=active_timeout)
        last_error = None
        for attempt in range(self.max_retries):
            start_time = time.time()
            try:
                resp = await client.post(endpoint, json=payload, headers=headers)

                # If unauthorized or not found, fail immediately without retrying
                if resp.status_code == 401:
                    err_msg = resp.text[:200]
                    try:
                        err_msg = resp.json().get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    raise ValueError(f"API Key không hợp lệ: {err_msg}")
                if resp.status_code == 404:
                    raise ValueError(f"Model [{model_id}] không tồn tại trên Gateway (404)")

                # If gateway rejected response_format or reasoning_effort, strip & cache the failure
                if resp.status_code == 400 and ("response_format" in resp.text or "reasoning" in resp.text):
                    if "response_format" in resp.text:
                        self._unsupported_features.add("response_format")
                        payload.pop("response_format", None)
                    if "reasoning" in resp.text:
                        self._unsupported_features.add("reasoning_effort")
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
            except ValueError as ve:
                raise ve
            except Exception as e:
                last_error = e
                # A timeout already consumed the full per-attempt budget. Retrying
                # the same slow model route repeatedly can stall a 1m scalping cycle.
                if isinstance(e, httpx.TimeoutException):
                    break
                # Wait briefly before retry (exponential back-off: 0.5s, 1.0s, ...)
                await asyncio.sleep(0.5 * (attempt + 1))

        if isinstance(last_error, httpx.TimeoutException):
            error_detail = f"{type(last_error).__name__} sau {self.timeout}s"
        elif isinstance(last_error, httpx.HTTPStatusError):
            response = last_error.response
            try:
                body = response.json()
                error_obj = body.get("error", body) if isinstance(body, dict) else body
                message = error_obj.get("message") if isinstance(error_obj, dict) else str(error_obj)
            except Exception:
                message = response.text.strip()
            error_detail = f"HTTP {response.status_code}"
            if message:
                error_detail += f": {str(message)[:400]}"
        else:
            message = str(last_error).strip() if last_error is not None else ""
            error_detail = message or (
                f"{type(last_error).__name__} (exception không có thông báo chi tiết)"
                if last_error is not None else "Không nhận được phản hồi từ Gateway"
            )

        raise RuntimeError(f"Lỗi gọi AI Model [{model_id}]: {error_detail}")

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
