from .routes_system import router as system_router
from .routes_binance import router as binance_router
from .routes_ai import router as ai_router
from .routes_trading import router as trading_router
from .routes_risk import router as risk_router
from .routes_backtest import router as backtest_router
from .routes_skills import router as skills_router
from .websocket_handler import ws_manager

__all__ = [
    "system_router",
    "binance_router",
    "ai_router",
    "trading_router",
    "risk_router",
    "backtest_router",
    "skills_router",
    "ws_manager"
]
