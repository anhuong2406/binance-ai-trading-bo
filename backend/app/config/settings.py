"""
Application Configuration and Settings
AI Binance Trading Company
"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "AI Binance Trading Company"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'trading_company.db'}"

    # Trading Mode: "PAPER", "TESTNET", "LIVE"
    TRADING_MODE: str = "PAPER"
    DEFAULT_PAIRS: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]
    DEFAULT_TIMEFRAME: str = "15m"
    EVALUATION_INTERVAL_SECONDS: int = 300  # 5 minutes

    # Binance Spot API
    BINANCE_BASE_URL: str = "https://api.binance.com"
    BINANCE_TESTNET_URL: str = "https://testnet.binance.vision"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"
    BINANCE_TESTNET_WS_URL: str = "wss://testnet.binance.vision/ws"

    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET_API_KEY: str = ""
    BINANCE_TESTNET_API_SECRET: str = ""

    # Live Mode Safety Locks - MUST be locked on startup/restart
    LIVE_SPOT_LOCKED: bool = True
    LIVE_SPOT_CONFIRMATION_PHRASE: str = "ENABLE LIVE SPOT"
    EMERGENCY_STOP_ACTIVE: bool = False

    # AI Configuration (Single Gateway for Dual Models)
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_API_KEY: str = ""
    GPT_MODEL_ID: str = "gpt-6-luna"
    GEMINI_MODEL_ID: str = "gemini-3.8-flash"
    GPT_REASONING_LEVEL: str = "high"
    GEMINI_REASONING_LEVEL: str = "high"
    AI_TIMEOUT_SECONDS: int = 30
    AI_MAX_RETRIES: int = 3
    AI_MAX_TOKENS: int = 2048
    MAX_AI_COST_PER_DAY: float = 5.0
    QUANT_PREFILTER_ENABLED: bool = True  # Cost optimizer: only calls LLMs when technical trigger occurs

    # Risk Engine Rules (Conservative defaults)
    BOT_ALLOCATED_CAPITAL_USDT: float = 100.0  # Cap on spot capital allocated to bot
    MAX_RISK_PER_TRADE_PERCENT: float = 1.0     # 1% max risk per trade
    MAX_POSITION_SIZE_PERCENT: float = 25.0    # 25% max position value of bot capital
    DAILY_MAX_LOSS_PERCENT: float = 2.0        # 2% max daily loss of start equity
    MAX_DRAWDOWN_PERCENT: float = 5.0          # 5% max drawdown from peak equity
    MAX_CONCURRENT_POSITIONS: int = 2          # Max 2 concurrent bot positions
    MAX_DAILY_ENTRIES: int = 5                 # Max 5 position opens per day
    COOLDOWN_MINUTES: int = 20                 # Min 20 min cooldown after closing a position
    SLIPPAGE_ESTIMATE_PERCENT: float = 0.05    # 0.05% slippage simulation
    BINANCE_TAKER_FEE_PERCENT: float = 0.1     # 0.10% spot taker fee

    # Notifications
    DESKTOP_NOTIFICATIONS_ENABLED: bool = True
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

settings = Settings()
