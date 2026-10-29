export type TradingMode = 'PAPER' | 'TESTNET' | 'LIVE';

export interface SystemStatus {
  app_name: string;
  version: string;
  mode: TradingMode;
  bot_state: string;
  is_running: boolean;
  emergency_stop: boolean;
  live_locked: boolean;
  allocated_capital: number;
  active_pairs: string[];
  timeframe: string;
  interval_seconds: number;
  ai_single_model_mode?: boolean;
  max_concurrent_positions?: number;
  standby_reason?: string | null;
}

export interface SpotBalance {
  asset: string;
  free: number;
  locked: number;
  total: number;
  estimatedUsdt: number;
}

export interface SpotAccount {
  canTrade: boolean;
  permissions: string[];
  totalEquityUsdt: number;
  usdtFree: number;
  usdtLocked: number;
  balances: SpotBalance[];
}

export interface Position {
  id: number;
  symbol: string;
  side: string;
  amount: number;
  entry_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  status: 'OPEN' | 'CLOSED';
  realized_pnl: number;
  realized_pnl_percent: number;
  unrealized_pnl: number;
  total_fee: number;
  mode: TradingMode;
  opened_at: string;
  closed_at: string | null;
  close_reason: string | null;
}

export interface MarketSnapshot {
  symbol: string;
  lastPrice: number;
  priceChangePercent: number;
  highPrice: number;
  lowPrice: number;
  volume: number;
  quoteVolume: number;
  bestBid: number;
  bestAsk: number;
  spread: number;
  spreadPercent: number;
  timestamp: number;
}

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AIAnalysisLog {
  id: number;
  symbol: string;
  timeframe: string;
  gemini_output: string;
  gpt_output: string;
  consensus_action: string;
  execution_approved: boolean;
  rejection_reason: string | null;
  gemini_latency_ms: number;
  gpt_latency_ms: number;
  total_tokens: number;
  created_at: string;
}

export interface RiskStatus {
  allocated_capital: number;
  max_risk_per_trade_percent: number;
  max_position_size_percent: number;
  daily_max_loss_percent: number;
  max_drawdown_percent: number;
  max_concurrent_positions: number;
  max_daily_entries: number;
  cooldown_minutes: number;
  current_drawdown_percent: number;
  today_trade_count: number;
  today_loss_percent: number;
  today_pnl_percent?: number;
  trading_mode?: string;
  scalping_mode_enabled?: boolean;
  emergency_stop_active: boolean;
  live_locked: boolean;
}

export interface BacktestReport {
  strategy: string;
  symbol: string;
  initial_capital: number;
  final_equity: number;
  net_profit: number;
  net_profit_percent: number;
  max_drawdown_percent: number;
  max_drawdown_usdt: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  expectancy: number;
  avg_win: number;
  avg_loss: number;
  total_fees: number;
  equity_curve: { time: number; equity: number; drawdown: number }[];
  trades: {
    symbol: string;
    entry_time: number;
    entry_price: number;
    exit_time: number;
    exit_price: number;
    quantity: number;
    pnl: number;
    pnl_percent: number;
    fee: number;
    reason: string;
  }[];
}

export interface TradeMemoryRecord {
  id: number;
  position_id?: number;
  symbol: string;
  mode: string;
  outcome: 'WIN' | 'LOSS' | 'BREAKEVEN';
  entry_price: number;
  exit_price: number;
  pnl_usd: number;
  pnl_percent: number;
  hold_duration_minutes: number;
  close_reason: string;
  strategy_tag: string;
  market_state?: string;
  lesson_learned: string;
  recommendation: string;
  created_at?: string;
}

export interface MarketCandidate {
  symbol: string;
  price: number;
  price_change_24h: number;
  quote_volume_m: number;
  atr_percent: number;
  rsi14: number;
  ema_trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  volume_ratio?: number;
  score: number;
  score_breakdown: {
    momentum: number;
    volatility: number;
    rsi: number;
    liquidity: number;
    trade_memory: number;
  };
  reason: string;
  rank: number;
  is_best_pick: boolean;
  historical_win_rate: number;
  historical_trades: number;
  is_watched: boolean;
}

export interface MarketRadarData {
  status: string;
  message?: string;
  timestamp: number;
  scan_duration_ms: number;
  capital_usdt: number;
  min_notional_eligible: number;
  total_screened_universe: number;
  stage1_passed_count: number;
  best_pick: MarketCandidate | null;
  candidates: MarketCandidate[];
}
