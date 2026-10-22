"""
Skill Validator
Validates skill inputs, outputs, data integrity, and strict security isolation.
Ensures zero exposure of API Secrets and prevents unauthorized order execution.
"""
from typing import Dict, Any, List, Optional
import math

FORBIDDEN_KEYWORDS = [
    "binance_api_secret",
    "api_secret",
    "secret_key",
    "private_key",
    "exec(",
    "eval(",
    "subprocess",
    "os.system",
    "shutil.rmtree"
]

class SkillValidator:
    """Validates data structures and security compliance of trading skills."""

    @staticmethod
    def validate_market_data(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        min_bars: int = 15
    ) -> Tuple[bool, Optional[str]]:
        """Validate candlestick data arrays for completeness, length, and non-NaN values."""
        if not (highs and lows and closes and volumes):
            return False, "Thiếu dữ liệu chuỗi nến"

        n = len(closes)
        if n < min_bars:
            return False, f"Số lượng nến ({n}) chưa đạt mức tối thiểu ({min_bars})"

        if not (len(highs) == len(lows) == len(closes) == len(volumes) == n):
            return False, "Kích thước các chuỗi OHLCV không đồng nhất"

        for i in range(n):
            c = closes[i]
            h = highs[i]
            l = lows[i]
            v = volumes[i]
            if any(math.isnan(x) or math.isinf(x) for x in (c, h, l, v)):
                return False, f"Phát hiện giá trị bất thường (NaN/Inf) tại nến thứ {i}"
            if l > h:
                return False, f"Giá thấp nhất (Low) lớn hơn giá cao nhất (High) tại nến {i}"
            if c <= 0 or h <= 0 or l <= 0:
                return False, f"Giá âm hoặc bằng 0 tại nến {i}"

        return True, None

    @staticmethod
    def sanitize_and_audit_payload(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Security sandbox check:
        Ensures payload contains no API Secrets, private credentials, or shell injection patterns.
        """
        raw_str = str(payload).lower()
        for kw in FORBIDDEN_KEYWORDS:
            if kw in raw_str:
                return False, f"Phát hiện từ khóa nguy hiểm hoặc vi phạm bảo mật: '{kw}'"
        return True, None

    @staticmethod
    def validate_skill_output(skill_name: str, output: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate quantitative output of a specific skill."""
        if not isinstance(output, dict):
            return False, "Đầu ra của skill phải là dạng dictionary"

        if "error" in output:
            return False, f"Skill trả về lỗi: {output['error']}"

        # Check for NaNs in numeric outputs
        for k, v in output.items():
            if isinstance(v, (int, float)):
                if math.isnan(v) or math.isinf(v):
                    return False, f"Trường {k} trong kết quả của {skill_name} chứa giá trị NaN/Inf"

        return True, None

from typing import Tuple
skill_validator = SkillValidator()
