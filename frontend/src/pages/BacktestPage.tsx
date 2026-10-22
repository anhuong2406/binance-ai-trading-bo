import React, { useState, useEffect } from 'react';
import {
  Play,
  RotateCcw,
  BarChart,
  Percent,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  Layers
} from 'lucide-react';
import { BacktestReport } from '../types';
import { api } from '../services/api';

export const BacktestPage: React.FC = () => {
  const [strategies, setStrategies] = useState<{ name: string; description: string }[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [availablePairs, setAvailablePairs] = useState<string[]>(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']);
  const [timeframe, setTimeframe] = useState('15m');
  const [candleLimit, setCandleLimit] = useState(300);
  const [initialCapital, setInitialCapital] = useState(1000.0);

  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<BacktestReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getStrategies().then((data) => {
      setStrategies(data);
      if (data.length > 0) setSelectedStrategy(data[0].name);
    });
    api.getPairsList().then((res) => {
      if (res.active_symbols && res.active_symbols.length > 0) {
        setAvailablePairs(res.active_symbols);
      }
    }).catch(console.error);
  }, []);

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStrategy) return;

    try {
      setLoading(true);
      setError(null);
      const res = await api.runBacktest({
        strategy_name: selectedStrategy,
        symbol,
        timeframe,
        candle_limit: candleLimit,
        initial_capital: initialCapital,
      });
      setReport(res.report);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi chạy backtest');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Controls */}
      <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-bg-border">
          <BarChart className="w-4 h-4 text-bloomberg-orange" />
          <h2 className="font-mono text-xs font-bold uppercase text-gray-200">
            Mô Phỏng Lịch Sử & Kiểm Thử Chiến Lược (Backtesting Engine)
          </h2>
        </div>

        <form onSubmit={handleRunBacktest} className="grid grid-cols-2 md:grid-cols-6 gap-3 text-xs font-mono">
          <div className="col-span-2">
            <label className="block text-gray-400 mb-1">Chiến lược:</label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none"
            >
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Cặp giao dịch:</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none"
            >
              {availablePairs.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Khung nến:</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none"
            >
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Vốn ban đầu ($):</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 1000)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none"
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold flex items-center justify-center gap-1.5 shadow"
            >
              <Play className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Đang chạy...' : 'Chạy Backtest'}</span>
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-3 p-2.5 bg-bloomberg-red/20 border border-bloomberg-red/40 rounded text-xs text-red-300 font-mono">
            {error}
          </div>
        )}
      </div>

      {/* Results View */}
      {report && (
        <div className="space-y-4">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border">
              <span className="text-gray-400 text-xs font-mono block mb-1">Lợi Nhuận Sau Phí</span>
              <div
                className={`font-mono text-xl font-bold ${
                  report.net_profit >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'
                }`}
              >
                {report.net_profit >= 0 ? '+' : ''}${report.net_profit} ({report.net_profit_percent}%)
              </div>
              <span className="text-[11px] font-mono text-gray-500 mt-1 block">
                Vốn cuối: ${report.final_equity}
              </span>
            </div>

            <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border">
              <span className="text-gray-400 text-xs font-mono block mb-1">Max Drawdown</span>
              <div className="font-mono text-xl font-bold text-bloomberg-red">
                -{report.max_drawdown_percent}%
              </div>
              <span className="text-[11px] font-mono text-gray-500 mt-1 block">
                -${report.max_drawdown_usdt} USDT
              </span>
            </div>

            <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border">
              <span className="text-gray-400 text-xs font-mono block mb-1">Win Rate & Trades</span>
              <div className="font-mono text-xl font-bold text-gray-100">
                {report.win_rate}%
              </div>
              <span className="text-[11px] font-mono text-gray-500 mt-1 block">
                Tổng lệnh: {report.total_trades}
              </span>
            </div>

            <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border">
              <span className="text-gray-400 text-xs font-mono block mb-1">Profit Factor / Sharpe</span>
              <div className="font-mono text-xl font-bold text-bloomberg-cyan">
                {report.profit_factor} / {report.sharpe_ratio}
              </div>
              <span className="text-[11px] font-mono text-gray-500 mt-1 block">
                Tổng phí sàn: ${report.total_fees}
              </span>
            </div>
          </div>

          {/* Trade-by-trade Table */}
          <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
            <h3 className="font-mono text-xs font-bold uppercase text-gray-200 mb-3">
              Danh Sách Lệnh Khớp Trong Giai Đoạn Backtest
            </h3>
            <div className="overflow-x-auto max-h-[300px]">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-bg-border text-gray-400 text-[11px]">
                    <th className="pb-2">Cặp</th>
                    <th className="pb-2">Giá vào</th>
                    <th className="pb-2">Giá ra</th>
                    <th className="pb-2">Khối lượng</th>
                    <th className="pb-2">PnL Net</th>
                    <th className="pb-2">Phí</th>
                    <th className="pb-2">Lý do đóng</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-bg-border/50">
                  {report.trades.map((t, idx) => (
                    <tr key={idx} className="hover:bg-bg-card/40 transition">
                      <td className="py-2 text-gray-200 font-bold">{t.symbol}</td>
                      <td className="py-2 text-gray-300">${t.entry_price.toFixed(2)}</td>
                      <td className="py-2 text-gray-300">${t.exit_price.toFixed(2)}</td>
                      <td className="py-2 text-gray-400">{t.quantity.toFixed(4)}</td>
                      <td
                        className={`py-2 font-bold ${
                          t.pnl >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'
                        }`}
                      >
                        {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)} ({t.pnl_percent}%)
                      </td>
                      <td className="py-2 text-gray-400">${t.fee.toFixed(2)}</td>
                      <td className="py-2 text-gray-300">{t.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
