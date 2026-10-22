"""
Input Sanitizer & Prompt Injection Defense
Prevents untrusted external market/user inputs from altering AI behavior or overriding risk rules.
"""
import re
from typing import Any, Dict

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*:\s*override", re.IGNORECASE),
    re.compile(r"disable\s+(the\s+)?risk\s+engine", re.IGNORECASE),
    re.compile(r"turn\s+off\s+stop\s*loss", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|rules|limits)", re.IGNORECASE),
    re.compile(r"execute\s+(code|script|bash|cmd|sh|python)", re.IGNORECASE),
    re.compile(r"enable\s+live\s+(mode|trading)", re.IGNORECASE),
    re.compile(r"secret[_\s]?key", re.IGNORECASE),
]

def detect_prompt_injection(text: str) -> bool:
    """Returns True if input text contains suspicious prompt injection patterns."""
    if not isinstance(text, str):
        return False
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False

def sanitize_for_prompt(data: Any) -> Any:
    """
    Recursively sanitize input objects (strings, dicts, lists)
    to neutralize any prompt injection and strip control characters.
    """
    if isinstance(data, str):
        # Strip null bytes and non-printable control characters (except newline, tab)
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", data)
        # If injection is detected, replace with sanitized warning tag
        if detect_prompt_injection(cleaned):
            return "[WARNING: SUSPICIOUS INPUT REMOVED BY SANITIZER]"
        return cleaned
    elif isinstance(data, dict):
        return {str(k): sanitize_for_prompt(v) for k, v in data.items() if not str(k).lower().startswith("secret")}
    elif isinstance(data, list):
        return [sanitize_for_prompt(item) for item in data]
    return data
