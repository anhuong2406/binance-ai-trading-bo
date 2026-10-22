"""
Skill Registry
Maintains catalog of approved skills, categories, targeted AI models, and enable/disable states.
Guarantees strict allowlist enforcement: unapproved skills can never be activated.
"""
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
from app.skills.skill_loader import skill_loader

CONFIG_FILE = Path("backend/data/skills_config.json")

# Explicit immutable allowlist of approved quant trading skills for Binance Spot
APPROVED_SKILLS_CATALOG: Dict[str, Dict[str, Any]] = {
    "regime-detection": {
        "name": "regime-detection",
        "category": "Regime",
        "target_ai": "both",
        "description": "Nhận diện chế độ thị trường 4 góc phần tử (Trending/Ranging x High/Low Volatility)",
        "priority": 1,
        "default_enabled": True
    },
    "volatility-modeling": {
        "name": "volatility-modeling",
        "category": "Volatility",
        "target_ai": "both",
        "description": "Mô hình hóa biến động Parkinson, Garman-Klass và phân vị ATR",
        "priority": 2,
        "default_enabled": True
    },
    "market-microstructure": {
        "name": "market-microstructure",
        "category": "Microstructure",
        "target_ai": "gpt_reviewer",
        "description": "Phân tích vi cấu trúc thị trường, Order Book Imbalance (OBI) và spread thực tế",
        "priority": 3,
        "default_enabled": True
    },
    "slippage-modeling": {
        "name": "slippage-modeling",
        "category": "Execution",
        "target_ai": "gpt_reviewer",
        "description": "Mô hình hóa trượt giá và độ sâu thanh khoản Spot trước khi vào lệnh",
        "priority": 4,
        "default_enabled": True
    },
    "mean-reversion": {
        "name": "mean-reversion",
        "category": "Strategy",
        "target_ai": "gemini_analyst",
        "description": "Chiến lược hồi quy giá trị trung bình Bollinger Bands %B và Z-Score",
        "priority": 5,
        "default_enabled": True
    },
    "position-sizing": {
        "name": "position-sizing",
        "category": "Risk",
        "target_ai": "gpt_reviewer",
        "description": "Định cỡ vị thế dựa trên độ biến động ATR và giới hạn vốn bot",
        "priority": 6,
        "default_enabled": True
    },
    "risk-management": {
        "name": "risk-management",
        "category": "Risk",
        "target_ai": "gpt_reviewer",
        "description": "Quản trị rủi ro đa lớp: tỷ lệ R:R, bảo vệ drawdown và stop-loss logic",
        "priority": 7,
        "default_enabled": True
    },
    "portfolio-analytics": {
        "name": "portfolio-analytics",
        "category": "Analytics",
        "target_ai": "gpt_reviewer",
        "description": "Đo lường hiệu suất danh mục: Sharpe, Sortino, Profit Factor",
        "priority": 8,
        "default_enabled": True
    },
    "ohlcv-processing": {
        "name": "ohlcv-processing",
        "category": "Data",
        "target_ai": "gemini_analyst",
        "description": "Tiền xử lý nến OHLCV, kiểm tra tính đầy đủ và phát hiện dị thường giá",
        "priority": 9,
        "default_enabled": True
    },
    "custom-indicators": {
        "name": "custom-indicators",
        "category": "Indicators",
        "target_ai": "gemini_analyst",
        "description": "Chỉ báo tùy biến nâng cao (Choppiness Index, Volume Weighted Metrics)",
        "priority": 10,
        "default_enabled": True
    },
    "kelly-criterion": {
        "name": "kelly-criterion",
        "category": "Risk",
        "target_ai": "gpt_reviewer",
        "description": "Ước lượng tỷ lệ vốn tối ưu theo Fractional Kelly (0.2x Kelly)",
        "priority": 11,
        "default_enabled": True
    },
    "exit-strategies": {
        "name": "exit-strategies",
        "category": "Strategy",
        "target_ai": "both",
        "description": "Chiến lược thoát lệnh tối ưu: Trailing ATR Stop, Multi-target Take Profit",
        "priority": 12,
        "default_enabled": True
    },
    "correlation-analysis": {
        "name": "correlation-analysis",
        "category": "Analytics",
        "target_ai": "gpt_reviewer",
        "description": "Ma trận tương quan tài sản và quản lý rủi ro tập trung",
        "priority": 13,
        "default_enabled": True
    },
    "liquidity-analysis": {
        "name": "liquidity-analysis",
        "category": "Microstructure",
        "target_ai": "gpt_reviewer",
        "description": "Đánh giá thanh khoản thực tế và độ sâu sổ lệnh trên Binance Spot",
        "priority": 14,
        "default_enabled": True
    },
    "feature-engineering": {
        "name": "feature-engineering",
        "category": "Data",
        "target_ai": "gemini_analyst",
        "description": "Trích xuất đặc trưng chuỗi thời gian nến và khối lượng",
        "priority": 15,
        "default_enabled": True
    },
    "signal-classification": {
        "name": "signal-classification",
        "category": "Strategy",
        "target_ai": "gemini_analyst",
        "description": "Phân loại độ tin cậy và xếp hạng tín hiệu giao dịch",
        "priority": 16,
        "default_enabled": True
    },
    "strategy-framework": {
        "name": "strategy-framework",
        "category": "Strategy",
        "target_ai": "both",
        "description": "Khung chuẩn hóa tín hiệu chiến lược giao dịch",
        "priority": 17,
        "default_enabled": True
    },
    "trade-journal": {
        "name": "trade-journal",
        "category": "Analytics",
        "target_ai": "both",
        "description": "Ghi chép và tổng kết phân tích giao dịch đa tác nhân",
        "priority": 18,
        "default_enabled": True
    },
    "trading-visualization": {
        "name": "trading-visualization",
        "category": "Visualization",
        "target_ai": "both",
        "description": "Biểu đồ hóa kỹ thuật và trực quan hóa phân tích",
        "priority": 19,
        "default_enabled": True
    },
    "walk-forward-validation": {
        "name": "walk-forward-validation",
        "category": "Backtest",
        "target_ai": "both",
        "description": "Kiểm định mô phỏng Walk-Forward tránh overfitting",
        "priority": 20,
        "default_enabled": True
    },
    "cointegration-analysis": {
        "name": "cointegration-analysis",
        "category": "Analytics",
        "target_ai": "gemini_analyst",
        "description": "Kiểm định đồng tích hợp cặp tài sản",
        "priority": 21,
        "default_enabled": True
    }
}

class SkillRegistry:
    def __init__(self):
        self._enabled_skills: Dict[str, bool] = {}
        self._load_config()

    def _load_config(self):
        """Load enabled/disabled states from persistent JSON."""
        # Default all approved to their default_enabled state
        for name, meta in APPROVED_SKILLS_CATALOG.items():
            self._enabled_skills[name] = meta.get("default_enabled", True)

        if CONFIG_FILE.exists():
            try:
                saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for name, enabled in saved.items():
                    if name in APPROVED_SKILLS_CATALOG:
                        self._enabled_skills[name] = bool(enabled)
            except Exception:
                pass

    def _save_config(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            CONFIG_FILE.write_text(json.dumps(self._enabled_skills, indent=2), encoding="utf-8")
        except Exception:
            pass

    def is_enabled(self, skill_name: str) -> bool:
        if skill_name not in APPROVED_SKILLS_CATALOG:
            return False
        return self._enabled_skills.get(skill_name, False)

    def set_enabled(self, skill_name: str, enabled: bool) -> bool:
        if skill_name not in APPROVED_SKILLS_CATALOG:
            return False
        self._enabled_skills[skill_name] = bool(enabled)
        self._save_config()
        return True

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """Return rich metadata for all approved skills plus installed status."""
        installed_docs = skill_loader.load_all_skills()
        out = []
        for name, meta in sorted(APPROVED_SKILLS_CATALOG.items(), key=lambda x: x[1].get("priority", 99)):
            doc = installed_docs.get(name)
            out.append({
                "name": name,
                "category": meta["category"],
                "target_ai": meta["target_ai"],
                "description": meta["description"],
                "priority": meta["priority"],
                "is_enabled": self.is_enabled(name),
                "is_installed": doc is not None,
                "has_scripts": doc.has_scripts if doc else False,
                "has_references": doc.has_references if doc else False
            })
        return out

    def get_enabled_skills_for_target(self, target: str) -> List[str]:
        """Get enabled skill names for specific AI (e.g. 'gemini_analyst' or 'gpt_reviewer')."""
        result = []
        for name, meta in APPROVED_SKILLS_CATALOG.items():
            if not self.is_enabled(name):
                continue
            t = meta.get("target_ai", "both")
            if t == "both" or t == target:
                result.append(name)
        return result

skill_registry = SkillRegistry()
