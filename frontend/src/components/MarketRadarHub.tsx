import React, { useState, useEffect } from 'react';
import {
  Compass,
  Sparkles,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Award,
  Zap,
  ShieldCheck,
  Activity,
  Layers,
  ChevronRight,
  DollarSign,
  PauseCircle,
  ShieldAlert
} from 'lucide-react';
import { MarketRadarData, MarketCandidate } from '../types';
import { api } from '../services/api';

interface MarketRadarHubProps {
  className?: string;
  onSelectSymbol?: (symbol: string) => void;
}

export const MarketRadarHub: React.FC<MarketRadarHubProps> = ({
  className = '',
  onSelectSymbol
}) => {
  const [radar, setRadar] = useState<MarketRadarData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchRadar = async (forceRefresh = false) => {
    try {
      if (forceRefresh) {
        setScanning(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const data = forceRefresh
        ? await api.triggerMarketScan()
        : await api.getMarketRadar(false);
      setRadar(data);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err?.message || 'Không thể tải dữ liệu radar thị trường');
    } finally {
      setLoading(false);
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchRadar();
    // Auto-refresh radar every 60s only when capital is sufficient
    const timer = setInterval(() => {
      setRadar((current) => {
        if (current && (current.status === 'INSUFFICIENT_CAPITAL' || current.capital_usdt < 1.0)) {
          // Skip auto-polling when capital is insufficient to buy anything
          return current;
        }
        fetchRadar(false);
        return current;
      });
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  const bestPick: MarketCandidate | null = radar?.best_pick || null;
  const candidates: MarketCandidate[] = radar?.candidates || [];

  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-xl ${className}`}>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-gray-800 gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-gradient-to-tr from-amber-500/20 to-cyan-500/20 border border-amber-500/30 rounded-lg text-amber-400">
            <Compass className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-bold text-white tracking-wide">
                Radar Thị Trường & Phân Tích Chọn Lọc
              </h3>
              <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
                Sàng lọc 2 tầng
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Quét toàn bộ sàn Binance Spot theo quy mô vốn thực tế &bull; Hội đồng AI chấm điểm chọn ra Kèo Số 1
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {radar && (
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 bg-gray-800/80 border border-gray-700/60 rounded-lg text-xs">
              <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-gray-400">Vốn khả dụng:</span>
              <span className="font-bold text-emerald-400">
                {radar.capital_usdt.toFixed(2)} USDT
              </span>
            </div>
          )}

          <button
            onClick={() => fetchRadar(true)}
            disabled={scanning || loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-gray-950 font-semibold rounded-lg text-xs transition-all shadow-md shadow-amber-500/10 disabled:opacity-50"
            title="Quét lại toàn bộ thị trường ngay lập tức"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
            <span>{scanning ? 'Đang Quét...' : 'Quét Lại Thị Trường'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => fetchRadar(true)} className="underline ml-2">Thử lại</button>
        </div>
      )}

      {loading && !radar ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-3">
          <RefreshCw className="w-8 h-8 text-amber-400 animate-spin" />
          <p className="text-sm text-gray-400">Đang quét 700+ cặp USDT trên Binance Spot và chấm điểm định lượng...</p>
        </div>
      ) : radar?.status === 'INSUFFICIENT_CAPITAL' ? (
        <div className="py-8 px-4 bg-gray-800/40 border border-amber-500/30 rounded-xl text-center space-y-3 mt-4">
          <div className="inline-flex p-3 bg-amber-500/10 rounded-full text-amber-400">
            <PauseCircle className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-amber-300 uppercase tracking-wide">
              Tạm Dừng Quét Thị Trường &amp; AI (Tiết Kiệm 100% Tài Nguyên)
            </h4>
            <p className="text-xs text-gray-300 max-w-lg mx-auto">
              {radar.message || `Số dư khả dụng (${radar.capital_usdt.toFixed(2)} USDT) không đủ mở bất kỳ lệnh nào trên sàn Binance. Hệ thống đã tự động dừng quét để tiết kiệm 100% token AI và tài nguyên.`}
            </p>
          </div>
          <div className="pt-2">
            <span className="text-[11px] text-gray-500 italic">
              Hệ thống sẽ tự động quét lại khi có đủ số dư khả dụng hoặc khi vị thế hiện tại chốt lời thành công.
            </span>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {/* Spotlight Card: #1 Best Pick */}
          {bestPick && (
            <div className="relative overflow-hidden rounded-xl border border-amber-500/40 bg-gradient-to-br from-amber-950/20 via-gray-900 to-gray-900/90 p-4 shadow-lg">
              <div className="absolute top-0 right-0 w-48 h-48 bg-amber-500/5 rounded-full blur-2xl pointer-events-none" />

              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <span className="flex items-center space-x-1 px-2.5 py-0.5 text-xs font-bold bg-amber-500 text-gray-950 rounded-full shadow-sm">
                      <Award className="w-3.5 h-3.5" />
                      <span>KÈO SỐ 1 ĐƯỢC CHỌN</span>
                    </span>
                    <span className="text-xs text-gray-400">
                      (Xác suất thắng &amp; R:R cao nhất thời điểm này)
                    </span>
                  </div>

                  <div className="flex items-baseline space-x-3">
                    <h4 className="text-2xl font-black text-white tracking-wider flex items-center gap-1.5">
                      {bestPick.symbol}
                      {bestPick.is_watched && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded">
                          Đã theo dõi
                        </span>
                      )}
                    </h4>
                    <span className="text-lg font-bold text-gray-200">
                      ${bestPick.price >= 1 ? bestPick.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : bestPick.price.toFixed(6)}
                    </span>
                    <span
                      className={`text-sm font-semibold flex items-center ${
                        bestPick.price_change_24h >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {bestPick.price_change_24h >= 0 ? (
                        <TrendingUp className="w-4 h-4 mr-0.5" />
                      ) : (
                        <TrendingDown className="w-4 h-4 mr-0.5" />
                      )}
                      {bestPick.price_change_24h >= 0 ? '+' : ''}
                      {bestPick.price_change_24h.toFixed(2)}%
                    </span>
                  </div>

                  <div className="text-xs text-amber-200/90 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5 flex items-start space-x-2">
                    <Zap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-amber-300">Đánh giá hệ thống: </span>
                      <span>{bestPick.reason}</span>
                    </div>
                  </div>
                </div>

                {/* Score & Key Metrics */}
                <div className="flex flex-wrap sm:flex-nowrap items-center gap-3">
                  <div className="bg-gray-800/90 border border-gray-700/80 rounded-xl px-4 py-3 text-center min-w-[100px]">
                    <div className="text-[11px] text-gray-400 font-medium">ĐIỂM TỔNG HỢP</div>
                    <div className="text-2xl font-black text-amber-400 mt-0.5">
                      {bestPick.score}
                      <span className="text-xs text-gray-500 font-normal">/100</span>
                    </div>
                    <div className="w-full bg-gray-700 h-1.5 rounded-full mt-1.5 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-amber-500 to-emerald-400 h-full rounded-full"
                        style={{ width: `${Math.min(100, bestPick.score)}%` }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2">
                      <div className="text-gray-400 text-[10px]">Biên độ ATR 15m</div>
                      <div className="font-bold text-white mt-0.5 flex items-center text-xs">
                        <Activity className="w-3 h-3 text-cyan-400 mr-1" />
                        {bestPick.atr_percent.toFixed(2)}%
                      </div>
                    </div>
                    <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2">
                      <div className="text-gray-400 text-[10px]">RSI (14) 15m</div>
                      <div className="font-bold text-emerald-400 mt-0.5 text-xs">
                        {bestPick.rsi14.toFixed(1)}
                      </div>
                    </div>
                    <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2">
                      <div className="text-gray-400 text-[10px]">Thanh khoản 24h</div>
                      <div className="font-bold text-white mt-0.5 text-xs flex items-center justify-between">
                        <span>${bestPick.quote_volume_m}M</span>
                        {bestPick.volume_ratio && bestPick.volume_ratio >= 1.5 && (
                          <span className="text-[10px] text-amber-400 font-mono ml-1" title={`Volume nến 15m gần nhất gấp ${bestPick.volume_ratio}x trung bình`}>
                            ⚡{bestPick.volume_ratio}x
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2">
                      <div className="text-gray-400 text-[10px]">Xu hướng EMA</div>
                      <div className="font-bold text-amber-300 mt-0.5 text-xs">
                        {bestPick.ema_trend}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Score Breakdown Pills */}
              {bestPick.score_breakdown && (
                <div className="mt-3 pt-3 border-t border-gray-800/80 flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="text-gray-400 mr-1">Cơ cấu điểm:</span>
                  <span className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60" title="Xu hướng EMA & Động lượng 24h (Tối đa 30 điểm)">
                    Xu hướng: <strong className="text-amber-400">+{bestPick.score_breakdown.momentum}</strong>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60" title="Biên độ ATR 15m (Tối đa 25 điểm)">
                    Biến động: <strong className="text-cyan-400">+{bestPick.score_breakdown.volatility}</strong>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60" title="RSI 14 (Tối đa 20 điểm)">
                    RSI: <strong className="text-emerald-400">+{bestPick.score_breakdown.rsi}</strong>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60" title="Thanh khoản 24h & Đột biến Volume (Tối đa 18 điểm)">
                    Thanh khoản: <strong className="text-blue-400">+{bestPick.score_breakdown.liquidity}</strong>
                  </span>
                  {bestPick.score_breakdown.trade_memory !== 0 && (
                    <span className="px-2 py-0.5 rounded bg-gray-800/90 text-gray-300 border border-gray-700/60" title="Thưởng/phạt từ lịch sử giao dịch thực chiến (-10 đến +10)">
                      Ký ức: <strong className={bestPick.score_breakdown.trade_memory > 0 ? "text-emerald-400" : "text-rose-400"}>
                        {bestPick.score_breakdown.trade_memory > 0 ? `+${bestPick.score_breakdown.trade_memory}` : bestPick.score_breakdown.trade_memory}
                      </strong>
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Candidates Matrix Table */}
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-800/70 text-gray-400 border-b border-gray-800">
                  <th className="py-2.5 px-3 font-semibold">Hạng</th>
                  <th className="py-2.5 px-3 font-semibold">Cặp Giao Dịch</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Giá</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Tăng 24h</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Volume 24h</th>
                  <th className="py-2.5 px-3 font-semibold text-right">ATR (15m)</th>
                  <th className="py-2.5 px-3 font-semibold text-right">RSI (14)</th>
                  <th className="py-2.5 px-3 font-semibold text-center">Điểm AI</th>
                  <th className="py-2.5 px-3 font-semibold">Lý Do Đánh Giá</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {candidates.map((cand) => {
                  const isTop = cand.rank === 1;
                  return (
                    <tr
                      key={cand.symbol}
                      onClick={() => onSelectSymbol && onSelectSymbol(cand.symbol)}
                      className={`transition-colors cursor-pointer ${
                        isTop
                          ? 'bg-amber-500/5 hover:bg-amber-500/10'
                          : 'hover:bg-gray-800/50'
                      }`}
                    >
                      <td className="py-2.5 px-3">
                        <span
                          className={`inline-flex items-center justify-center w-5 h-5 rounded-full font-bold text-[11px] ${
                            cand.rank === 1
                              ? 'bg-amber-500 text-gray-950 shadow-sm'
                              : cand.rank === 2
                              ? 'bg-gray-300 text-gray-900'
                              : cand.rank === 3
                              ? 'bg-amber-700/60 text-amber-200'
                              : 'bg-gray-800 text-gray-400 border border-gray-700'
                          }`}
                        >
                          {cand.rank}
                        </span>
                      </td>

                      <td className="py-2.5 px-3 font-bold text-white flex items-center space-x-1.5">
                        <span>{cand.symbol}</span>
                        {isTop && (
                          <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.2 rounded">
                            Số 1
                          </span>
                        )}
                        {cand.is_watched && !isTop && (
                          <span className="text-[9px] font-medium text-cyan-400 bg-cyan-500/10 px-1 rounded">
                            Watch
                          </span>
                        )}
                      </td>

                      <td className="py-2.5 px-3 text-right font-medium text-gray-200">
                        ${cand.price >= 1 ? cand.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : cand.price.toFixed(6)}
                      </td>

                      <td
                        className={`py-2.5 px-3 text-right font-semibold ${
                          cand.price_change_24h >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {cand.price_change_24h >= 0 ? '+' : ''}
                        {cand.price_change_24h.toFixed(2)}%
                      </td>

                      <td className="py-2.5 px-3 text-right text-gray-300 font-medium">
                        <div>${cand.quote_volume_m}M</div>
                        {cand.volume_ratio && cand.volume_ratio >= 1.5 && (
                          <div className="text-[10px] text-amber-400 font-mono" title={`Volume nến 15m gấp ${cand.volume_ratio}x trung bình`}>
                            ⚡ {cand.volume_ratio}x
                          </div>
                        )}
                      </td>

                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`px-1.5 py-0.5 rounded font-mono text-[11px] ${
                            cand.atr_percent >= 1.5 && cand.atr_percent <= 3.5
                              ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                              : 'text-gray-300'
                          }`}
                        >
                          {cand.atr_percent.toFixed(2)}%
                        </span>
                      </td>

                      <td className="py-2.5 px-3 text-right font-mono">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[11px] ${
                            cand.rsi14 >= 45 && cand.rsi14 <= 62
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : cand.rsi14 > 68
                              ? 'bg-rose-500/10 text-rose-400'
                              : 'text-gray-300'
                          }`}
                        >
                          {cand.rsi14.toFixed(1)}
                        </span>
                      </td>

                      <td
                        className="py-2.5 px-3 text-center"
                        title={cand.score_breakdown ? `Điểm chi tiết: Xu hướng +${cand.score_breakdown.momentum} | Biến động +${cand.score_breakdown.volatility} | RSI +${cand.score_breakdown.rsi} | Dòng tiền +${cand.score_breakdown.liquidity} | Ký ức ${cand.score_breakdown.trade_memory >= 0 ? '+' : ''}${cand.score_breakdown.trade_memory}` : undefined}
                      >
                        <div className="inline-flex items-center space-x-1.5">
                          <div className="w-12 bg-gray-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                cand.score >= 70
                                  ? 'bg-emerald-400'
                                  : cand.score >= 50
                                  ? 'bg-amber-400'
                                  : 'bg-gray-500'
                              }`}
                              style={{ width: `${cand.score}%` }}
                            />
                          </div>
                          <span
                            className={`font-bold font-mono text-[11px] ${
                              cand.score >= 70
                                ? 'text-emerald-400'
                                : cand.score >= 50
                                ? 'text-amber-400'
                                : 'text-gray-400'
                            }`}
                          >
                            {cand.score}
                          </span>
                        </div>
                      </td>

                      <td className="py-2.5 px-3 text-gray-400 max-w-xs truncate" title={cand.reason}>
                        {cand.reason}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Footer Metrics */}
          <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-400 pt-2 px-1">
            <div className="flex items-center space-x-4">
              <span>
                Đã quét: <strong className="text-gray-300">{radar?.total_screened_universe || 0}</strong> thị trường
              </span>
              <span>
                Qua vòng 1: <strong className="text-gray-300">{radar?.stage1_passed_count || 0}</strong> ứng viên
              </span>
              <span>
                Thời gian quét: <strong className="text-gray-300">{radar?.scan_duration_ms || 0}ms</strong>
              </span>
            </div>
            <div>
              Cập nhật lúc: {lastUpdated.toLocaleTimeString('vi-VN')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
