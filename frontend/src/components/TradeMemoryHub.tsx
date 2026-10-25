import React, { useState, useEffect } from 'react';
import {
  Brain,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Lightbulb,
  Target,
  Clock,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle
} from 'lucide-react';
import { TradeMemoryRecord } from '../types';
import { api } from '../services/api';

interface TradeMemoryHubProps {
  symbolFilter?: string;
  className?: string;
}

export const TradeMemoryHub: React.FC<TradeMemoryHubProps> = ({ symbolFilter, className = '' }) => {
  const [memories, setMemories] = useState<TradeMemoryRecord[]>([]);
  const [stats, setStats] = useState<{ total: number; wins: number; losses: number; winRate: number }>({
    total: 0,
    wins: 0,
    losses: 0,
    winRate: 0,
  });
  const [selectedCoin, setSelectedCoin] = useState<string>(symbolFilter || 'ALL');
  const [loading, setLoading] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);

  const fetchMemories = async (coin: string = selectedCoin) => {
    setLoading(true);
    try {
      const sym = coin === 'ALL' ? undefined : coin;
      const res = await api.getTradeMemories(sym, 30);
      setMemories(res.memories || []);
      setStats({
        total: res.total_memories || 0,
        wins: res.win_count || 0,
        losses: res.loss_count || 0,
        winRate: res.win_rate || 0,
      });
    } catch (err) {
      console.error('Lỗi tải trade memories:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncTradeMemories();
      await fetchMemories();
    } catch (err) {
      console.error('Lỗi đồng bộ trade memories:', err);
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchMemories(selectedCoin);
  }, [selectedCoin]);

  const uniqueSymbols = ['ALL', ...Array.from(new Set(memories.map((m) => m.symbol)))];

  return (
    <div className={`bg-bg-darker rounded-lg border border-bg-border p-4 shadow-sm space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-bg-border pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-purple-950/40 border border-purple-500/40 text-purple-300">
            <Brain className="w-5 h-5 text-purple-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-mono text-sm font-bold text-gray-100 uppercase tracking-wide">
                Sổ Tay Kinh Nghiệm & Học Hỏi Thực Chiến
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-900/30 border border-purple-500/30 text-purple-300">
                AI Memory
              </span>
            </div>
            <p className="text-xs font-mono text-gray-400 mt-0.5">
              Tự động đúc rút bài học từ các lệnh lãi / lỗ và truyền trực tiếp vào bộ não AI để không lặp lại sai lầm.
            </p>
          </div>
        </div>

        {/* Sync & Refresh Button */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-bg-card hover:bg-bg-border border border-bg-border text-xs font-mono text-gray-300 hover:text-white transition disabled:opacity-50"
            title="Đồng bộ lại kinh nghiệm từ tất cả các lệnh đã đóng"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Đang đồng bộ...' : 'Đồng bộ bài học'}</span>
          </button>
        </div>
      </div>

      {/* Summary Metrics & Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Quick Stats */}
        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="px-3 py-1.5 rounded bg-bg-card border border-bg-border flex items-center gap-2">
            <span className="text-gray-400">Tỷ lệ thắng:</span>
            <span className={`font-bold ${stats.winRate >= 50 ? 'text-bloomberg-green' : 'text-bloomberg-orange'}`}>
              {stats.winRate.toFixed(1)}%
            </span>
          </div>
          <div className="px-3 py-1.5 rounded bg-bg-card border border-bg-border flex items-center gap-2">
            <span className="text-gray-400">Kết quả:</span>
            <span className="text-emerald-400 font-bold">{stats.wins} Thắng</span>
            <span className="text-gray-500">/</span>
            <span className="text-rose-400 font-bold">{stats.losses} Thua</span>
          </div>
          <div className="px-3 py-1.5 rounded bg-bg-card border border-bg-border flex items-center gap-2">
            <span className="text-gray-400">Bài học tích lũy:</span>
            <span className="text-cyan-300 font-bold">{stats.total}</span>
          </div>
        </div>

        {/* Coin Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto text-xs font-mono">
          {uniqueSymbols.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelectedCoin(sym)}
              className={`px-2.5 py-1 rounded transition ${
                selectedCoin === sym
                  ? 'bg-purple-600 text-white font-bold shadow-sm'
                  : 'bg-bg-card hover:bg-bg-border text-gray-400 hover:text-gray-200 border border-bg-border'
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      {/* List of Trade Memories */}
      {loading ? (
        <div className="py-8 text-center text-gray-500 text-xs font-mono">
          Đang tải kinh nghiệm giao dịch...
        </div>
      ) : memories.length === 0 ? (
        <div className="py-8 text-center text-gray-500 text-xs font-mono bg-bg-card/50 rounded-lg border border-bg-border border-dashed">
          Chưa có bài học kinh nghiệm nào được ghi nhận cho bộ lọc này.
        </div>
      ) : (
        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
          {memories.map((m) => {
            const isWin = m.outcome === 'WIN';
            const isLoss = m.outcome === 'LOSS';
            return (
              <div
                key={m.id}
                className={`p-3.5 rounded-lg border transition-all text-xs font-mono ${
                  isWin
                    ? 'bg-emerald-950/10 border-emerald-500/20 hover:border-emerald-500/40'
                    : isLoss
                    ? 'bg-rose-950/10 border-rose-500/20 hover:border-rose-500/40'
                    : 'bg-bg-card/50 border-bg-border'
                }`}
              >
                {/* Top Info Row */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border/60 pb-2 mb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-gray-100 text-sm">{m.symbol}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 ${
                        isWin
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : isLoss
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-gray-500/20 text-gray-300 border border-gray-500/30'
                      }`}
                    >
                      {isWin ? <CheckCircle2 className="w-3 h-3" /> : isLoss ? <XCircle className="w-3 h-3" /> : <HelpCircle className="w-3 h-3" />}
                      {isWin ? 'THẮNG' : isLoss ? 'THUA' : 'HÒA'} ({m.pnl_percent >= 0 ? '+' : ''}{m.pnl_percent}%)
                    </span>
                    <span className="text-[10px] text-gray-400 px-1.5 py-0.5 rounded bg-bg-card border border-bg-border">
                      {m.mode}
                    </span>
                    {m.strategy_tag && (
                      <span className="text-[10px] text-purple-300 px-1.5 py-0.5 rounded bg-purple-950/40 border border-purple-500/30">
                        #{m.strategy_tag}
                      </span>
                    )}
                  </div>

                  {/* Trade Metrics */}
                  <div className="flex items-center gap-3 text-[11px] text-gray-400">
                    <span>
                      Vào: <strong className="text-gray-200">{m.entry_price}</strong> $\rightarrow$ Thoát:{' '}
                      <strong className="text-gray-200">{m.exit_price}</strong>
                    </span>
                    <span>·</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {m.hold_duration_minutes} phút
                    </span>
                    <span>·</span>
                    <span className="text-gray-400 truncate max-w-[150px]" title={m.close_reason}>
                      {m.close_reason}
                    </span>
                  </div>
                </div>

                {/* Lesson Learned Block */}
                <div className="space-y-2">
                  <div className="p-2.5 rounded bg-bg-card/70 border border-bg-border flex items-start gap-2">
                    <Lightbulb className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div className="space-y-0.5">
                      <span className="text-[11px] font-bold text-amber-300 uppercase">Bài học rút ra:</span>
                      <p className="text-gray-300 text-xs leading-relaxed">{m.lesson_learned}</p>
                    </div>
                  </div>

                  {/* Actionable AI Recommendation Block */}
                  {m.recommendation && (
                    <div className="p-2.5 rounded bg-purple-950/20 border border-purple-500/30 flex items-start gap-2">
                      <Target className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                      <div className="space-y-0.5">
                        <span className="text-[11px] font-bold text-purple-300 uppercase">
                          Khuyến nghị hành động cho lần sau:
                        </span>
                        <p className="text-purple-200/90 text-xs leading-relaxed">{m.recommendation}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
