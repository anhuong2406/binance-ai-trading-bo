"""
Pair Management & Symbol Configuration Engine
AI Binance Trading Company
Allows users to select, toggle, add, and remove pairs for automated trading.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config.settings import DATA_DIR, settings

logger = logging.getLogger(__name__)

PAIRS_CONFIG_FILE = DATA_DIR / "pairs_config.json"

DEFAULT_PAIRS_CATALOG = [
    {
        "symbol": "BTCUSDT",
        "name": "Bitcoin",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "enabled": True,
        "min_notional": 5.0,
        "is_default": True
    },
    {
        "symbol": "ETHUSDT",
        "name": "Ethereum",
        "base_asset": "ETH",
        "quote_asset": "USDT",
        "enabled": True,
        "min_notional": 5.0,
        "is_default": True
    },
    {
        "symbol": "SOLUSDT",
        "name": "Solana",
        "base_asset": "SOL",
        "quote_asset": "USDT",
        "enabled": True,
        "min_notional": 5.0,
        "is_default": True
    },
    {
        "symbol": "DOGEUSDT",
        "name": "Dogecoin",
        "base_asset": "DOGE",
        "quote_asset": "USDT",
        "enabled": True,
        "min_notional": 1.0,
        "is_default": True
    }
]

class PairManager:
    def __init__(self, config_file: Path = PAIRS_CONFIG_FILE):
        self.config_file = config_file
        self.pairs: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Loads pairs from JSON or initializes defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.pairs = {p["symbol"]: p for p in data if "symbol" in p}
                    elif isinstance(data, dict):
                        self.pairs = data
            except Exception as e:
                logger.error(f"Failed to load pairs config from {self.config_file}: {e}")
                self.pairs = {p["symbol"]: dict(p) for p in DEFAULT_PAIRS_CATALOG}
        else:
            self.pairs = {p["symbol"]: dict(p) for p in DEFAULT_PAIRS_CATALOG}
            self._save()

        # Sync in-memory settings.DEFAULT_PAIRS with active symbols
        self._sync_settings()

    def _save(self):
        """Saves pairs to JSON."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(list(self.pairs.values()), f, indent=2, ensure_ascii=False)
            self._sync_settings()
        except Exception as e:
            logger.error(f"Failed to save pairs config: {e}")

    def _sync_settings(self):
        """Syncs active symbols into settings.DEFAULT_PAIRS."""
        active = self.get_active_symbols()
        if active:
            settings.DEFAULT_PAIRS = active

    def get_all_pairs(self) -> List[Dict[str, Any]]:
        """Returns all configured pairs."""
        return list(self.pairs.values())

    def get_active_symbols(self) -> List[str]:
        """Returns symbols that are currently enabled."""
        active = [p["symbol"] for p in self.pairs.values() if p.get("enabled", False)]
        return active if active else ["BTCUSDT"]  # Fallback: at least 1 symbol

    def toggle_pair(self, symbol: str, enabled: bool) -> bool:
        """Toggles a pair on or off."""
        symbol = symbol.upper().strip()
        if symbol not in self.pairs:
            return False

        # If disabling, ensure at least one active pair remains
        if not enabled:
            active_count = sum(1 for p in self.pairs.values() if p.get("enabled", False) and p["symbol"] != symbol)
            if active_count == 0:
                raise ValueError("Không thể tắt tất cả các cặp! Hệ thống yêu cầu ít nhất 1 cặp giao dịch được kích hoạt.")

        self.pairs[symbol]["enabled"] = enabled
        self._save()
        return True

    def add_pair(self, symbol: str, name: Optional[str] = None, min_notional: float = 5.0, base_asset: Optional[str] = None) -> Dict[str, Any]:
        """Adds a new pair to the catalog."""
        symbol = symbol.upper().strip()
        if symbol in self.pairs:
            self.pairs[symbol]["enabled"] = True
            self._save()
            return self.pairs[symbol]

        base = base_asset or (symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol)
        pair_data = {
            "symbol": symbol,
            "name": name or base,
            "base_asset": base,
            "quote_asset": "USDT",
            "enabled": True,
            "min_notional": min_notional,
            "is_default": False
        }
        self.pairs[symbol] = pair_data
        self._save()
        return pair_data

    def remove_pair(self, symbol: str) -> bool:
        """Removes a user-added pair."""
        symbol = symbol.upper().strip()
        if symbol not in self.pairs:
            return False

        # Don't delete if it leaves 0 active pairs
        active_remaining = [s for s, p in self.pairs.items() if s != symbol and p.get("enabled", False)]
        if not active_remaining:
            raise ValueError("Không thể xóa cặp này vì sẽ không còn cặp giao dịch nào hoạt động.")

        del self.pairs[symbol]
        self._save()
        return True

pair_manager = PairManager()
