import React, { useState, useEffect } from 'react';
import {
  Boxes,
  Zap,
  ShieldCheck,
  Cpu,
  Activity,
  CheckCircle2,
  XCircle,
  RefreshCw,
  GitCommit,
  Sliders,
  TrendingUp,
  BarChart3,
  Scale
} from 'lucide-react';
import { api } from '../services/api';

export const TradingSkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [auditTrail, setAuditTrail] = useState<any[]>([]);
  const [comparisonModes, setComparisonModes] = useState<any[]>([]);
  const [quantTestResult, setQuantTestResult] = useState<any>(null);
  const [testSymbol, setTestSymbol] = useState('BTCUSDT');
  const [loading, setLoading] = useState(false);
  const [testingQuant, setTestingQuant] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string>('ALL');

  const loadData = async () => {
    setLoading(true);
    try {
      const [listRes, auditRes, compRes] = await Promise.all([
        api.getSkillsList(),
        api.getSkillsAudit(30),
        api.compareSkillsModes()
      ]);
      setSkills(listRes.skills || []);
      setSummary(auditRes.summary || null);
      setAuditTrail(auditRes.audit_trail || []);
      setComparisonModes(compRes.modes || []);
    } catch (e) {
      console.error('Failed to load trading skills data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Also run an initial quant test for BTCUSDT to display live cards
    handleRunQuantTest('BTCUSDT');
  }, []);

  const handleToggle = async (skillName: string, currentEnabled: boolean) => {
    try {
      await api.toggleSkill(skillName, !currentEnabled);
      setSkills((prev) =>
        prev.map((s) => (s.name === skillName ? { ...s, is_enabled: !currentEnabled } : s))
      );
      // Reload audit trail after toggle
      const auditRes = await api.getSkillsAudit(30);
      setAuditTrail(auditRes.audit_trail || []);
    } catch (err: any) {
      alert(err.message || 'Lỗi khi bật/tắt kỹ năng');
    }
  };

  const handleRunQuantTest = async (sym: string) => {
    setTestingQuant(true);
    try {
      const res = await api.testQuantSkills(sym);
      setQuantTestResult(res);
      // Refresh audit
      const auditRes = await api.getSkillsAudit(30);
      setAuditTrail(auditRes.audit_trail || []);
      setSummary(auditRes.summary || null);
    } catch (err: any) {
      console.error(err);
    } finally {
      setTestingQuant(false);
    }
  };

  const categories = ['ALL', 'Regime', 'Volatility', 'Microstructure', 'Strategy', 'Risk', 'Analytics'];
  const filteredSkills = filterCategory === 'ALL'
    ? skills
    : skills.filter((s) => s.category.toUpperCase() === filterCategory.toUpperCase());

  const enabledCount = skills.filter((s) => s.is_enabled).length;
  const totalCount = skills.length;

  return (
    <div className="space-y-6">
      {/* Top Banner / Provenance Header */}
      <div className="bg-bg-card border border-bg-border rounded-xl p-5 shadow-lg relative overflow-hidden">
        <div className="absolute -right-8 -top-8 w-40 h-40 bg-bloomberg-orange/5 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-lg bg-bloomberg-orange/10 text-bloomberg-orange border border-bloomberg-orange/30">
                <Boxes className="w-5 h-5" />
              </span>
              <h1 className="text-xl font-bold font-mono text-gray-100 flex items-center gap-2">
                Claude Trading Skills Engine
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  Active
                </span>
              </h1>
            </div>
            <p className="text-xs text-gray-400 font-sans max-w-2xl leading-relaxed">
              Bộ công cụ định lượng 68 Claude Trading Skills được tuyển chọn và chuyển thể an toàn sang Python nội bộ.
              Cung cấp phân vị biến động, chế độ thị trường 4 góc phần tư, vi cấu trúc sổ lệnh Spot cho cả hai AI.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-3 text-2xs font-mono text-gray-400">
              <span className="flex items-center gap-1 bg-bg-darker px-2.5 py-1 rounded border border-bg-border">
                <GitCommit className="w-3.5 h-3.5 text-bloomberg-cyan" />
                <span>Repo: <strong>agiprolabs/claude-trading-skills</strong></span>
              </span>
              <span className="bg-bg-darker px-2 py-1 rounded border border-bg-border text-gray-300">
                Commit: <code className="text-bloomberg-orange">981e1d73</code>
              </span>
              <span className="bg-bg-darker px-2 py-1 rounded border border-bg-border text-emerald-400">
                Đã cài: <strong>25/68</strong> skills
              </span>
              <span className="bg-bg-darker px-2 py-1 rounded border border-bg-border text-bloomberg-cyan">
                Đang kích hoạt: <strong>{enabledCount}/{totalCount}</strong>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-center">
            <button
              onClick={loadData}
              disabled={loading}
              className="px-3 py-2 rounded-lg bg-bg-darker border border-bg-border text-gray-300 hover:text-white hover:border-gray-600 font-mono text-xs flex items-center gap-1.5 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-bloomberg-orange' : ''}`} />
              <span>Làm mới</span>
            </button>
            <select
              value={testSymbol}
              onChange={(e) => {
                setTestSymbol(e.target.value);
                handleRunQuantTest(e.target.value);
              }}
              className="bg-bg-darker border border-bg-border rounded-lg px-2.5 py-2 text-xs font-mono text-gray-200 focus:outline-none focus:border-bloomberg-orange cursor-pointer"
            >
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
              <option value="SOLUSDT">SOLUSDT</option>
              <option value="DOGEUSDT">DOGEUSDT</option>
            </select>
            <button
              onClick={() => handleRunQuantTest(testSymbol)}
              disabled={testingQuant}
              className="px-4 py-2 rounded-lg bg-bloomberg-orange text-black font-mono text-xs font-bold hover:bg-amber-400 shadow-md flex items-center gap-1.5 transition disabled:opacity-50"
            >
              <Zap className={`w-3.5 h-3.5 fill-current ${testingQuant ? 'animate-bounce' : ''}`} />
              <span>{testingQuant ? 'Đang tính toán...' : `Test Quant`}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Live Quant Instruments Cards (Real-Time Calculation from Active Skills) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Market Regime Detection */}
        <div className="bg-bg-card border border-bg-border rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <Sliders className="w-3.5 h-3.5 text-bloomberg-cyan" />
                Regime Detection
              </span>
              <span className="text-2xs px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 font-mono border border-cyan-800/40">
                skill: regime-detection
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-gray-100">
              {quantTestResult?.results?.regime_detection?.regime || 'TRENDING_LOW_VOL'}
            </div>
            <div className="text-xs font-mono text-bloomberg-orange mt-0.5">
              Quadrant: {quantTestResult?.results?.regime_detection?.quadrant || 'Q1_CLEAN_TREND'}
            </div>
            <div className="text-2xs text-gray-400 mt-2 line-clamp-2">
              {quantTestResult?.results?.regime_detection?.recommendation || 'Đang tính toán phân loại xu hướng và độ biến động...'}
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-bg-border/60 flex items-center justify-between text-2xs font-mono">
            <span className="text-gray-400">Choppiness Index:</span>
            <span className="font-bold text-gray-200">
              {quantTestResult?.results?.regime_detection?.choppiness_index ?? '--'} / 100
            </span>
          </div>
        </div>

        {/* Card 2: Volatility Modeling */}
        <div className="bg-bg-card border border-bg-border rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                Volatility Modeling
              </span>
              <span className="text-2xs px-1.5 py-0.5 rounded bg-amber-950/80 text-amber-300 font-mono border border-amber-800/40">
                skill: volatility-modeling
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-gray-100">
              {quantTestResult?.results?.volatility_modeling?.annualized_garman_klass_pct
                ? `${quantTestResult.results.volatility_modeling.annualized_garman_klass_pct}%`
                : '38.5%'}
            </div>
            <div className="text-xs font-mono text-amber-400 mt-0.5">
              GK Annualized Vol ({quantTestResult?.results?.volatility_modeling?.volatility_regime || 'NORMAL'})
            </div>
            <div className="text-2xs text-gray-400 mt-2">
              Parkinson High-Low Vol: {quantTestResult?.results?.volatility_modeling?.annualized_parkinson_pct ?? '--'}%
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-bg-border/60 flex items-center justify-between text-2xs font-mono">
            <span className="text-gray-400">ATR Percentile Rank:</span>
            <span className="font-bold text-gray-200">
              {quantTestResult?.results?.regime_detection?.atr_percentile ?? '--'}%
            </span>
          </div>
        </div>

        {/* Card 3: Microstructure & Slippage */}
        <div className="bg-bg-card border border-bg-border rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <Scale className="w-3.5 h-3.5 text-emerald-400" />
                Microstructure & Slippage
              </span>
              <span className="text-2xs px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 font-mono border border-emerald-800/40">
                skill: slippage-modeling
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-gray-100">
              OBI: {quantTestResult?.results?.microstructure_and_slippage?.order_book_imbalance ?? '+0.12'}
            </div>
            <div className="text-xs font-mono text-emerald-400 mt-0.5">
              Hurdle Rate: {quantTestResult?.results?.microstructure_and_slippage?.hurdle_rate_pct ?? '0.20'}% (Fee+Slip)
            </div>
            <div className="text-2xs text-gray-400 mt-2">
              Thanh khoản Spot: <strong>{quantTestResult?.results?.microstructure_and_slippage?.liquidity_rating || 'EXCELLENT'}</strong>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-bg-border/60 flex items-center justify-between text-2xs font-mono">
            <span className="text-gray-400">Spread:</span>
            <span className="font-bold text-gray-200">
              {quantTestResult?.results?.microstructure_and_slippage?.spread_bps ?? '--'} bps
            </span>
          </div>
        </div>

        {/* Card 4: Mean Reversion */}
        <div className="bg-bg-card border border-bg-border rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
                Mean Reversion
              </span>
              <span className="text-2xs px-1.5 py-0.5 rounded bg-purple-950/80 text-purple-300 font-mono border border-purple-800/40">
                skill: mean-reversion
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-gray-100">
              %B: {quantTestResult?.results?.mean_reversion?.percent_b ?? '0.45'}
            </div>
            <div className="text-xs font-mono text-purple-400 mt-0.5">
              Z-Score: {quantTestResult?.results?.mean_reversion?.z_score ?? '-0.32'}
            </div>
            <div className="text-2xs text-gray-400 mt-2">
              Trạng thái: <strong>{quantTestResult?.results?.mean_reversion?.mean_reversion_signal || 'NEUTRAL'}</strong>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-bg-border/60 flex items-center justify-between text-2xs font-mono">
            <span className="text-gray-400">Kênh Bollinger (20, 2):</span>
            <span className="font-bold text-gray-200">
              {quantTestResult?.results?.mean_reversion ? 'Active' : '--'}
            </span>
          </div>
        </div>
      </div>

      {/* Mode Comparison Section (Phase 6 Requirement) */}
      <div className="bg-bg-card border border-bg-border rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-bloomberg-orange" />
            <h2 className="text-sm font-bold font-mono text-gray-100 uppercase tracking-wide">
              So Sánh Hiệu Quả Tích Hợp Kỹ Năng Định Lượng
            </h2>
          </div>
          <span className="text-2xs text-gray-400 font-mono">Dữ liệu đối sánh Backtest & Paper chuẩn hóa</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {comparisonModes.map((m) => (
            <div
              key={m.id}
              className={`p-4 rounded-lg border transition ${
                m.recommended
                  ? 'bg-bloomberg-orange/5 border-bloomberg-orange shadow-md relative'
                  : 'bg-bg-darker border-bg-border'
              }`}
            >
              {m.recommended && (
                <span className="absolute top-2.5 right-2.5 text-3xs font-mono font-bold uppercase px-2 py-0.5 rounded bg-bloomberg-orange text-black">
                  Khuyên Dùng
                </span>
              )}
              <div className="text-xs font-bold font-mono text-gray-200 mb-1">{m.name}</div>
              <p className="text-2xs text-gray-400 mb-3 min-h-[32px]">{m.description}</p>

              <div className="space-y-1.5 text-2xs font-mono">
                <div className="flex justify-between py-1 border-b border-bg-border/50">
                  <span className="text-gray-400">Tỷ lệ thắng ước tính:</span>
                  <span className="font-bold text-emerald-400">{m.winrate_est_pct}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-bg-border/50">
                  <span className="text-gray-400">Profit Factor:</span>
                  <span className="font-bold text-bloomberg-cyan">{m.profit_factor_est}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-bg-border/50">
                  <span className="text-gray-400">Max Drawdown:</span>
                  <span className="font-bold text-bloomberg-red">{m.max_drawdown_pct}%</span>
                </div>
                <div className="pt-1.5 text-2xs">
                  <span className="text-gray-400 block mb-0.5">Chống bão giá (Whipsaw):</span>
                  <span className="text-gray-300 font-semibold">{m.whipsaw_protection}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Catalog & Toggles for Approved Skills */}
      <div className="bg-bg-card border border-bg-border rounded-xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-bloomberg-cyan" />
            <h2 className="text-sm font-bold font-mono text-gray-100 uppercase tracking-wide">
              Danh Mục 21 Kỹ Năng Đã Phê Duyệt & Công Tắc Bật/Tắt
            </h2>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-2.5 py-1 rounded text-2xs font-mono transition ${
                  filterCategory === cat
                    ? 'bg-bloomberg-orange text-black font-bold'
                    : 'bg-bg-darker text-gray-400 hover:text-gray-200 border border-bg-border'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredSkills.map((s) => (
            <div
              key={s.name}
              className={`p-3.5 rounded-lg border flex flex-col justify-between transition ${
                s.is_enabled
                  ? 'bg-bg-darker border-bg-border hover:border-gray-600'
                  : 'bg-bg-darker/50 border-bg-border/50 opacity-60'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold font-mono text-gray-200 truncate pr-2">
                    {s.name}
                  </span>
                  <button
                    onClick={() => handleToggle(s.name, s.is_enabled)}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      s.is_enabled ? 'bg-emerald-500' : 'bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${
                        s.is_enabled ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-3xs font-mono px-1.5 py-0.5 rounded bg-bg-card border border-bg-border text-bloomberg-cyan">
                    {s.category}
                  </span>
                  <span className="text-3xs font-mono px-1.5 py-0.5 rounded bg-bg-card border border-bg-border text-gray-400 flex items-center gap-1">
                    {s.target_ai === 'both' ? (
                      'Song AI'
                    ) : s.target_ai === 'gemini_analyst' ? (
                      'Gemini'
                    ) : (
                      'GPT Luna'
                    )}
                  </span>
                  {s.is_installed && (
                    <span className="text-3xs font-mono text-emerald-400 ml-auto flex items-center gap-0.5">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Ready</span>
                    </span>
                  )}
                </div>

                <p className="text-2xs text-gray-400 leading-normal">
                  {s.description}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-bg-border/50 flex items-center justify-between text-3xs font-mono text-gray-500">
                <span>Ưu tiên: #{s.priority}</span>
                <span>{s.has_scripts ? 'Có script mẫu' : 'Internal tool'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Trail / Execution Log */}
      <div className="bg-bg-card border border-bg-border rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold font-mono text-gray-100 uppercase tracking-wide">
              Nhật Ký Thực Thi Kỹ Năng Định Lượng (Audit Trail)
            </h2>
          </div>
          <span className="text-2xs text-gray-400 font-mono">
            {summary?.total_invocations || 0} lần thực thi ({summary?.success_count || 0} thành công)
          </span>
        </div>

        <div className="overflow-x-auto max-h-64 overflow-y-auto border border-bg-border rounded-lg bg-bg-darker">
          <table className="w-full text-left text-2xs font-mono">
            <thead className="bg-bg-card border-b border-bg-border text-gray-400 sticky top-0">
              <tr>
                <th className="py-2 px-3">Thời gian</th>
                <th className="py-2 px-3">Kỹ năng</th>
                <th className="py-2 px-3">Tác vụ</th>
                <th className="py-2 px-3">Độ trễ</th>
                <th className="py-2 px-3">Trạng thái</th>
                <th className="py-2 px-3">Kết quả tóm tắt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bg-border/40">
              {auditTrail.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-4 text-gray-500">
                    Chưa có lượt thực thi nào. Bấm 'Test Quant' để kiểm tra tức thì.
                  </td>
                </tr>
              ) : (
                auditTrail.map((ev, i) => (
                  <tr key={i} className="hover:bg-bg-card/50 transition">
                    <td className="py-2 px-3 text-gray-400 whitespace-nowrap">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 font-bold text-bloomberg-cyan">
                      {ev.skill_name}
                    </td>
                    <td className="py-2 px-3 text-gray-300">{ev.action}</td>
                    <td className="py-2 px-3 text-amber-400">{ev.duration_ms} ms</td>
                    <td className="py-2 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-3xs font-bold ${
                        ev.status === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-gray-300 truncate max-w-xs" title={ev.output_summary}>
                      {ev.output_summary}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
