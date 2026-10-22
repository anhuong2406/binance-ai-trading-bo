import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Sliders,
  Lock,
  Clock,
  CheckCircle,
  XCircle,
  Percent,
  TrendingDown
} from 'lucide-react';
import { RiskStatus } from '../types';
import { api } from '../services/api';

export const RiskControlPage: React.FC = () => {
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [evaluations, setEvaluations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Form state
  const [maxRisk, setMaxRisk] = useState(1.0);
  const [maxPos, setMaxPos] = useState(25.0);
  const [dailyLoss, setDailyLoss] = useState(2.0);
  const [maxDd, setMaxDd] = useState(5.0);

  const loadData = async () => {
    try {
      const [statusData, evalData] = await Promise.all([
        api.getRiskStatus(),
        api.getRiskEvaluations(25),
      ]);
      setRiskStatus(statusData);
      setEvaluations(evalData);
      setMaxRisk(statusData.max_risk_per_trade_percent);
      setMaxPos(statusData.max_position_size_percent);
      setDailyLoss(statusData.daily_max_loss_percent);
      setMaxDd(statusData.max_drawdown_percent);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSaveRisk = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setMessage(null);
      await api.updateRiskConfig({
        max_risk_per_trade_percent: maxRisk,
        max_position_size_percent: maxPos,
        daily_max_loss_percent: dailyLoss,
        max_drawdown_percent: maxDd,
      });
      setMessage('Đã lưu tham số quản trị rủi ro mới thành công!');
      await loadData();
    } catch (err: any) {
      setMessage(`Lỗi: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="bg-bg-darker p-4 rounded-lg border border-bg-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-900/30 border border-emerald-500/40 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-bloomberg-green" />
          </div>
          <div>
            <h2 className="font-mono text-sm font-bold text-gray-100 uppercase">
              Hệ Thống Quản Trị Rủi Ro Độc Lập (Risk Engine)
            </h2>
            <p className="text-xs text-gray-400 font-mono">
              Chạy bằng Python thuần, cách ly 100% với AI. AI không có quyền can thiệp hoặc nới lỏng giới hạn.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-3 py-1 rounded bg-bg-card border border-bg-border text-bloomberg-cyan">
            Small Balance Mode: BẬT
          </span>
        </div>
      </div>

      {/* Gauges & Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Drawdown Gauge */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>Drawdown Hiện Tại</span>
            <TrendingDown className="w-4 h-4 text-bloomberg-red" />
          </div>
          <div className="font-mono text-2xl font-bold text-gray-100">
            {riskStatus?.current_drawdown_percent?.toFixed(2) || '0.00'}%
          </div>
          <div className="w-full bg-bg-darkest h-2 rounded-full mt-3 overflow-hidden border border-bg-border">
            <div
              className="bg-bloomberg-red h-full rounded-full transition-all"
              style={{
                width: `${Math.min(
                  ((riskStatus?.current_drawdown_percent || 0) / (riskStatus?.max_drawdown_percent || 5)) *
                    100,
                  100
                )}%`,
              }}
            />
          </div>
          <span className="text-[11px] font-mono text-gray-500 mt-1.5 block">
            Giới hạn tối đa: {riskStatus?.max_drawdown_percent}% (Khóa bot nếu chạm)
          </span>
        </div>

        {/* Daily Loss Gauge */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>Mức Lỗ Hôm Nay</span>
            <Percent className="w-4 h-4 text-bloomberg-orange" />
          </div>
          <div className="font-mono text-2xl font-bold text-gray-100">
            {riskStatus?.today_loss_percent?.toFixed(2) || '0.00'}%
          </div>
          <div className="w-full bg-bg-darkest h-2 rounded-full mt-3 overflow-hidden border border-bg-border">
            <div
              className="bg-bloomberg-orange h-full rounded-full transition-all"
              style={{
                width: `${Math.min(
                  ((riskStatus?.today_loss_percent || 0) / (riskStatus?.daily_max_loss_percent || 2)) *
                    100,
                  100
                )}%`,
              }}
            />
          </div>
          <span className="text-[11px] font-mono text-gray-500 mt-1.5 block">
            Giới hạn ngày: {riskStatus?.daily_max_loss_percent}% vốn đầu ngày
          </span>
        </div>

        {/* Cooldown & Daily Entries */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border space-y-2 text-xs font-mono">
          <div className="text-gray-400 font-bold mb-2">Quy Tắc An Toàn Tự Động</div>
          <div className="flex justify-between p-2 rounded bg-bg-card border border-bg-border">
            <span className="text-gray-400">Số lệnh đã mở hôm nay:</span>
            <span className="text-gray-100 font-bold">
              {riskStatus?.today_trade_count || 0} / {riskStatus?.max_daily_entries || 5}
            </span>
          </div>
          <div className="flex justify-between p-2 rounded bg-bg-card border border-bg-border">
            <span className="text-gray-400">Thời gian nghỉ Cooldown:</span>
            <span className="text-gray-100 font-bold">{riskStatus?.cooldown_minutes || 20} phút</span>
          </div>
        </div>
      </div>

      {/* Risk Limits Tuner Form */}
      <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
        <h3 className="font-mono text-xs font-bold uppercase text-gray-200 mb-3 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-bloomberg-cyan" />
          Điều Chỉnh Ngưỡng Rủi Ro (Tùy chỉnh siết chặt)
        </h3>

        <form onSubmit={handleSaveRisk} className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
          <div>
            <label className="block text-gray-400 mb-1">Rủi ro tối đa / lệnh (%):</label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="3.0"
              value={maxRisk}
              onChange={(e) => setMaxRisk(parseFloat(e.target.value) || 0.1)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
            />
            <span className="text-[10px] text-gray-500">Mặc định: 1.0% (Trần: 3.0%)</span>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Quy mô vị thế tối đa (%):</label>
            <input
              type="number"
              step="1"
              min="5"
              max="50"
              value={maxPos}
              onChange={(e) => setMaxPos(parseFloat(e.target.value) || 5)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
            />
            <span className="text-[10px] text-gray-500">Mặc định: 25.0% vốn bot</span>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Giới hạn lỗ trong ngày (%):</label>
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="5.0"
              value={dailyLoss}
              onChange={(e) => setDailyLoss(parseFloat(e.target.value) || 0.5)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
            />
            <span className="text-[10px] text-gray-500">Mặc định: 2.0%</span>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Giới hạn Drawdown đỉnh (%):</label>
            <input
              type="number"
              step="0.5"
              min="1.0"
              max="10.0"
              value={maxDd}
              onChange={(e) => setMaxDd(parseFloat(e.target.value) || 1.0)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
            />
            <span className="text-[10px] text-gray-500">Mặc định: 5.0%</span>
          </div>

          <div className="md:col-span-4 flex items-center justify-between pt-2 border-t border-bg-border">
            {message ? (
              <span className="text-xs text-bloomberg-cyan">{message}</span>
            ) : (
              <span className="text-[11px] text-gray-500">
                Lưu ý: Bạn chỉ có thể siết chặt các giới hạn để tăng độ an toàn.
              </span>
            )}
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold shadow"
            >
              {loading ? 'Đang lưu...' : 'Lưu cài đặt rủi ro'}
            </button>
          </div>
        </form>
      </div>

      {/* Risk Evaluations Log */}
      <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
        <h3 className="font-mono text-xs font-bold uppercase text-gray-200 mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-bloomberg-orange" />
          Nhật Ký Thẩm Định Của Risk Engine (Audit Trail)
        </h3>

        {evaluations.length === 0 ? (
          <div className="py-8 text-center text-gray-500 text-xs font-mono">
            Chưa có lần thẩm định rủi ro nào.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-bg-border text-gray-400 text-[11px]">
                  <th className="pb-2">Thời gian</th>
                  <th className="pb-2">Cặp</th>
                  <th className="pb-2">Lệnh</th>
                  <th className="pb-2">Entry / SL / TP</th>
                  <th className="pb-2">Kết quả</th>
                  <th className="pb-2">Lý do thẩm định</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bg-border/50">
                {evaluations.map((ev) => (
                  <tr key={ev.id} className="hover:bg-bg-card/40 transition">
                    <td className="py-2.5 text-gray-400">
                      {new Date(ev.created_at).toLocaleTimeString('vi-VN')}
                    </td>
                    <td className="py-2.5 font-bold text-gray-200">{ev.symbol}</td>
                    <td className="py-2.5">{ev.action}</td>
                    <td className="py-2.5 text-gray-400">
                      {ev.proposed_entry || '-'} / {ev.proposed_sl || '-'} / {ev.proposed_tp || '-'}
                    </td>
                    <td className="py-2.5">
                      {ev.passed ? (
                        <span className="text-bloomberg-green font-bold flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> PASS
                        </span>
                      ) : (
                        <span className="text-bloomberg-red font-bold flex items-center gap-1">
                          <XCircle className="w-3.5 h-3.5" /> REJECT
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 text-gray-300 max-w-xs truncate">
                      {ev.rejection_reasons || 'Thỏa mãn toàn bộ điều kiện'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
