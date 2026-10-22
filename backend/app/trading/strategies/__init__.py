from typing import Dict, List
from .base import BaseStrategy, SignalResult
from .trend_following import TrendFollowingStrategy
from .ema_crossover import EMACrossoverStrategy
from .rsi_reversion import RSIMeanReversionStrategy
from .macd_momentum import MACDMomentumStrategy
from .multi_timeframe import MultiTimeframeStrategy

ALL_STRATEGIES: List[BaseStrategy] = [
    TrendFollowingStrategy(),
    EMACrossoverStrategy(),
    RSIMeanReversionStrategy(),
    MACDMomentumStrategy(),
    MultiTimeframeStrategy(),
]

STRATEGY_MAP: Dict[str, BaseStrategy] = {s.name: s for s in ALL_STRATEGIES}

__all__ = [
    "BaseStrategy",
    "SignalResult",
    "TrendFollowingStrategy",
    "EMACrossoverStrategy",
    "RSIMeanReversionStrategy",
    "MACDMomentumStrategy",
    "MultiTimeframeStrategy",
    "ALL_STRATEGIES",
    "STRATEGY_MAP"
]
