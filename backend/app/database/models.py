"""
SQLAlchemy ORM Models for AI Binance Trading Company
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, Numeric, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

Base = declarative_base()

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    is_secret = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(String(20), default="PAPER")  # PAPER, TESTNET, LIVE
    status = Column(String(30), default="STOPPED")  # STOPPED, OBSERVING, ANALYZING, EXECUTING, PAUSED, EMERGENCY_STOP
    allocated_capital = Column(Float, default=100.0)
    peak_capital = Column(Float, default=100.0)
    emergency_stop = Column(Boolean, default=False)
    live_unlocked = Column(Boolean, default=False)
    started_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    side = Column(String(10), default="BUY")  # Spot is BUY to open, SELL to close
    amount = Column(Numeric(18, 8), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=False)
    current_price = Column(Numeric(18, 8), nullable=False)
    stop_loss = Column(Numeric(18, 8), nullable=True)
    take_profit = Column(Numeric(18, 8), nullable=True)
    trailing_stop = Column(Numeric(18, 8), nullable=True)
    status = Column(String(20), default="OPEN", index=True)  # OPEN, CLOSED
    realized_pnl = Column(Numeric(18, 8), default=0.0)
    realized_pnl_percent = Column(Float, default=0.0)
    unrealized_pnl = Column(Numeric(18, 8), default=0.0)
    total_fee = Column(Numeric(18, 8), default=0.0)
    mode = Column(String(20), default="PAPER")  # PAPER, TESTNET, LIVE
    opened_at = Column(DateTime, default=utc_now)
    closed_at = Column(DateTime, nullable=True)
    close_reason = Column(String(100), nullable=True)  # TAKE_PROFIT, STOP_LOSS, AI_CONSENSUS_SELL, EMERGENCY_STOP, MANUAL

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_order_id = Column(String(64), unique=True, index=True, nullable=False)
    exchange_order_id = Column(String(64), nullable=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    side = Column(String(10), nullable=False)  # BUY, SELL
    order_type = Column(String(20), default="LIMIT")  # LIMIT, MARKET, STOP_LOSS_LIMIT
    price = Column(Numeric(18, 8), nullable=True)
    quantity = Column(Numeric(18, 8), nullable=False)
    executed_qty = Column(Numeric(18, 8), default=0.0)
    cummulative_quote_qty = Column(Numeric(18, 8), default=0.0)
    status = Column(String(20), default="NEW", index=True)  # NEW, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED, EXPIRED
    mode = Column(String(20), default="PAPER")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class AIAnalysisLog(Base):
    __tablename__ = "ai_analysis_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(10), default="15m")
    gemini_output = Column(Text, nullable=False)  # JSON string
    gpt_output = Column(Text, nullable=False)     # JSON string
    consensus_action = Column(String(10), default="HOLD")  # BUY, SELL, HOLD
    execution_approved = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)
    gemini_latency_ms = Column(Integer, default=0)
    gpt_latency_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utc_now, index=True)

class RiskEvaluation(Base):
    __tablename__ = "risk_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), index=True, nullable=False)
    action = Column(String(10), nullable=False)
    proposed_entry = Column(Float, nullable=True)
    proposed_sl = Column(Float, nullable=True)
    proposed_tp = Column(Float, nullable=True)
    passed = Column(Boolean, default=False)
    rejection_reasons = Column(Text, nullable=True)  # JSON list
    calculated_risk_percent = Column(Float, default=0.0)
    calculated_position_size = Column(Float, default=0.0)
    current_drawdown_percent = Column(Float, default=0.0)
    daily_loss_percent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utc_now, index=True)

class DailyStat(Base):
    __tablename__ = "daily_stats"

    date = Column(String(10), primary_key=True, index=True)  # YYYY-MM-DD
    start_equity = Column(Float, default=100.0)
    current_equity = Column(Float, default=100.0)
    peak_equity = Column(Float, default=100.0)
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_percent = Column(Float, default=0.0)
    max_drawdown_percent = Column(Float, default=0.0)
    trade_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    total_fees = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), index=True, nullable=False)
    level = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)

class TradeMemory(Base):
    """
    Trade Memory & Lessons Learned Database
    Stores every closed trade's outcome, context, lessons learned, and recommendations.
    Fed directly into future AI analysis prompts so the bot learns from past wins/losses.
    """
    __tablename__ = "trade_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    side = Column(String(10), default="BUY")
    mode = Column(String(20), default="LIVE", index=True)  # LIVE, PAPER, TESTNET
    outcome = Column(String(10), nullable=False, index=True)  # WIN, LOSS, BREAKEVEN
    entry_price = Column(Numeric(18, 8), nullable=False)
    exit_price = Column(Numeric(18, 8), nullable=False)
    pnl_usd = Column(Numeric(18, 8), nullable=False)
    pnl_percent = Column(Float, nullable=False)
    hold_duration_minutes = Column(Integer, default=0)
    close_reason = Column(String(100), nullable=True)
    strategy_tag = Column(String(50), default="scalping-bounce")
    market_state = Column(String(50), nullable=True)
    lesson_learned = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)

