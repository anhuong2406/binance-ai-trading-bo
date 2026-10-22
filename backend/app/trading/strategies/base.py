"""
Base Strategy Plugin Interface
All quantitative strategies inherit from BaseStrategy.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class SignalResult(BaseModel):
    strategy_name: str
    action: str  # BUY, SELL, HOLD
    symbol: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    reason: str
    confidence: float  # 0.0 to 1.0

class BaseStrategy(ABC):
    name: str = "BaseStrategy"
    description: str = "Base Strategy Description"

    @abstractmethod
    def evaluate(
        self,
        symbol: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        indicators: Dict[str, Any]
    ) -> SignalResult:
        """Evaluate market data and technical indicators to produce a signal."""
        pass
