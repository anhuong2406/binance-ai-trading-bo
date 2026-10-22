import {
  SystemStatus,
  SpotAccount,
  Position,
  MarketSnapshot,
  CandleData,
  AIAnalysisLog,
  RiskStatus,
  BacktestReport,
  TradingMode
} from '../types';

const BASE_URL = '/api';

export const api = {
  // System
  async getSystemStatus(): Promise<SystemStatus> {
    const res = await fetch(`${BASE_URL}/system/status`);
    if (!res.ok) throw new Error('Không thể tải trạng thái hệ thống');
    return res.json();
  },

  async triggerEmergencyStop(): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/emergency-stop`, { method: 'POST' });
    if (!res.ok) throw new Error('Không thể kích hoạt Emergency Stop');
    return res.json();
  },

  async resetEmergencyStop(): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/emergency-stop/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Không thể mở khóa Emergency Stop');
    return res.json();
  },

  async setMode(mode: TradingMode): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể chuyển chế độ giao dịch');
    }
    return res.json();
  },

  async unlockLive(confirmation_phrase: string, allocated_capital: number): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/unlock-live`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation_phrase, allocated_capital })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể mở khóa LIVE');
    }
    return res.json();
  },

  async lockLive(): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/lock-live`, { method: 'POST' });
    return res.json();
  },

  async getSettings(): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/settings`);
    return res.json();
  },

  async updateSettings(settings: any): Promise<any> {
    const res = await fetch(`${BASE_URL}/system/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    return res.json();
  },

  async getAuditLogs(limit = 50): Promise<any[]> {
    const res = await fetch(`${BASE_URL}/system/audit-logs?limit=${limit}`);
    return res.json();
  },

  // Binance
  async testBinance(): Promise<any> {
    const res = await fetch(`${BASE_URL}/binance/test`);
    return res.json();
  },

  async getSpotAccount(): Promise<{ account: SpotAccount }> {
    const res = await fetch(`${BASE_URL}/binance/account`);
    return res.json();
  },

  async getKlines(symbol = 'BTCUSDT', interval = '15m', limit = 100): Promise<{ candles: CandleData[] }> {
    const res = await fetch(`${BASE_URL}/binance/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`);
    if (!res.ok) throw new Error('Lỗi tải dữ liệu nến');
    return res.json();
  },

  async getSnapshot(symbol = 'BTCUSDT'): Promise<{ snapshot: MarketSnapshot }> {
    const res = await fetch(`${BASE_URL}/binance/snapshot?symbol=${symbol}`);
    return res.json();
  },

  // Trading
  async startBot(): Promise<any> {
    const res = await fetch(`${BASE_URL}/trading/start`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể khởi động bot');
    }
    return res.json();
  },

  async stopBot(): Promise<any> {
    const res = await fetch(`${BASE_URL}/trading/stop`, { method: 'POST' });
    return res.json();
  },

  async getPositions(status?: string): Promise<Position[]> {
    const url = status ? `${BASE_URL}/trading/positions?status=${status}` : `${BASE_URL}/trading/positions`;
    const res = await fetch(url);
    return res.json();
  },

  async closePosition(positionId: number): Promise<any> {
    const res = await fetch(`${BASE_URL}/trading/positions/${positionId}/close`, { method: 'POST' });
    return res.json();
  },

  async getTradingStats(): Promise<any> {
    const res = await fetch(`${BASE_URL}/trading/stats`);
    return res.json();
  },

  // AI
  async testAI(payload?: {
    base_url?: string;
    api_key?: string;
    gpt_model_id?: string;
    gemini_model_id?: string;
  }): Promise<any> {
    const res = await fetch(`${BASE_URL}/ai/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    return res.json();
  },

  async getAILogs(limit = 20, symbol?: string): Promise<AIAnalysisLog[]> {
    const url = symbol ? `${BASE_URL}/ai/logs?limit=${limit}&symbol=${symbol}` : `${BASE_URL}/ai/logs?limit=${limit}`;
    const res = await fetch(url);
    return res.json();
  },

  async triggerAIAnalyze(symbol = 'BTCUSDT'): Promise<any> {
    const res = await fetch(`${BASE_URL}/ai/analyze-now?symbol=${symbol}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi phân tích đa tác nhân');
    }
    return res.json();
  },

  // Risk
  async getRiskStatus(): Promise<RiskStatus> {
    const res = await fetch(`${BASE_URL}/risk/status`);
    return res.json();
  },

  async updateRiskConfig(config: any): Promise<any> {
    const res = await fetch(`${BASE_URL}/risk/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi cập nhật cấu hình rủi ro');
    }
    return res.json();
  },

  async getRiskEvaluations(limit = 30): Promise<any[]> {
    const res = await fetch(`${BASE_URL}/risk/evaluations?limit=${limit}`);
    return res.json();
  },

  // Backtest
  async getStrategies(): Promise<{ name: string; description: string }[]> {
    const res = await fetch(`${BASE_URL}/backtest/strategies`);
    return res.json();
  },

  async runBacktest(payload: {
    strategy_name: string;
    symbol: string;
    timeframe: string;
    candle_limit: number;
    initial_capital: number;
  }): Promise<{ report: BacktestReport }> {
    const res = await fetch(`${BASE_URL}/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi thực thi backtest');
    }
    return res.json();
  }
};
