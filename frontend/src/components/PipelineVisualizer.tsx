import React from 'react';
import {
  Database,
  Cpu,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Clock,
  Send
} from 'lucide-react';

interface PipelineVisualizerProps {
  lastReport: any;
}

export const PipelineVisualizer: React.FC<PipelineVisualizerProps> = ({ lastReport }) => {
  const steps = lastReport?.steps || {};
  const isHoldAction = steps.consensus?.action === 'HOLD' || steps.gemini_analyst?.output?.action === 'HOLD';

  const getStepStatus = (stepKey: string) => {
    const data = steps[stepKey];
    if (!data) {
      if (isHoldAction && (stepKey === 'risk_engine' || stepKey === 'execution')) {
        return { status: 'PASS', color: 'border-cyan-500/40 text-cyan-400 bg-cyan-950/20' };
      }
      return { status: 'IDLE', color: 'border-gray-800 text-gray-500 bg-bg-card' };
    }
    if (data.status === 'SKIPPED') {
      return { status: 'PASS', color: 'border-emerald-900/50 text-emerald-400/80 bg-emerald-950/20' };
    }
    if (data.status === 'PASS') {
      return { status: 'PASS', color: 'border-bloomberg-green/50 text-bloomberg-green bg-bloomberg-green/10' };
    }
    if (data.status === 'STANDBY') {
      return { status: 'STANDBY', color: 'border-cyan-700/50 text-cyan-300 bg-cyan-950/20' };
    }
    if (isHoldAction && (stepKey === 'risk_engine' || stepKey === 'execution')) {
      return { status: 'STANDBY', color: 'border-cyan-700/50 text-cyan-300 bg-cyan-950/20' };
    }
    if (data.status === 'PASS') {
      return { status: 'PASS', color: 'border-bloomberg-green/50 text-bloomberg-green bg-bloomberg-green/10' };
    }
    if (data.status === 'FAIL' || data.status === 'DISAGREED' || data.status === 'BLOCKED' || data.passed === false) {
      return { status: 'FAIL', color: 'border-bloomberg-red/50 text-bloomberg-red bg-bloomberg-red/10' };
    }
    return { status: 'ACTIVE', color: 'border-bloomberg-cyan text-bloomberg-cyan bg-bloomberg-cyan/10 animate-pulse' };
  };

  const pipelineStages = [
    {
      key: 'market_data',
      name: 'Market Data',
      icon: Database,
      details: steps.market_data
        ? `Giá: ${steps.market_data.last_price} | Spread: ${steps.market_data.spread_percent?.toFixed(3)}%`
        : 'Chờ nến Binance',
    },
    {
      key: 'quant_engine',
      name: 'Quant Engine',
      icon: Cpu,
      details: steps.quant_engine
        ? `RSI: ${steps.quant_engine.indicators?.rsi14?.toFixed(0)} | Stoch: ${steps.quant_engine.indicators?.stoch_rsi_k?.toFixed(0) ?? 'N/A'}%`
        : 'EMA / RSI / Stoch / BB',
    },
    {
      key: 'gemini_analyst',
      name: 'Gemini Analyst',
      icon: Sparkles,
      details: steps.gemini_analyst
        ? steps.gemini_analyst.status === 'SKIPPED'
          ? 'Chưa gọi Gemini'
          : steps.gemini_analyst.status === 'FAIL'
          ? `Lỗi: ${steps.gemini_analyst.error || 'Không rõ nguyên nhân'}`
          : `${steps.gemini_analyst.output?.action || 'Chưa có kết quả'} (${typeof steps.gemini_analyst.latency_ms === 'number' ? `${steps.gemini_analyst.latency_ms}ms` : 'chưa có thời gian'})`
        : 'Chiến lược & Đề xuất',
    },
    {
      key: 'gpt_reviewer',
      name: 'GPT-6 Luna Review',
      icon: ShieldCheck,
      details: steps.gpt_reviewer
        ? steps.gpt_reviewer.status === 'SKIPPED'
          ? (steps.gpt_reviewer.note || 'Bỏ qua (Single Gemini 3.8)')
          : steps.gpt_reviewer.status === 'FAIL'
          ? `Lỗi: ${steps.gpt_reviewer.error || 'Không rõ nguyên nhân'}`
          : `${steps.gpt_reviewer.output?.decision || 'Chưa có kết quả'} (${typeof steps.gpt_reviewer.latency_ms === 'number' ? `${steps.gpt_reviewer.latency_ms}ms` : 'chưa có thời gian'})`
        : 'Góc nhìn bổ trợ & kiểm tra rủi ro',
    },
    {
      key: 'risk_engine',
      name: 'Risk Engine',
      icon: ShieldCheck,
      details: steps.risk_engine
        ? steps.risk_engine.passed
          ? isHoldAction
            ? 'BẢO TOÀN VỐN (0% RỦI RO)'
            : `PASS (Risk ${steps.risk_engine.calculated_risk_percent}%)`
          : 'TỪ CHỐI RỦI RO'
        : isHoldAction
        ? 'Bảo toàn vốn (HOLD)'
        : 'Quy tắc vốn & Drawdown',
    },
    {
      key: 'execution',
      name: 'Execution',
      icon: Send,
      details: steps.execution
        ? isHoldAction
          ? 'STANDBY (0 LỆNH)'
          : `${steps.execution.mode}: ${steps.execution.result?.status || 'DONE'}`
        : isHoldAction
        ? 'Standby (0 Lệnh)'
        : 'Khớp lệnh Spot',
    },
  ];

  return (
    <div className="bg-bg-darker p-4 rounded-lg border border-bg-border shadow-sm">
      <div className="flex items-center justify-between mb-3 border-b border-bg-border pb-2">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-bloomberg-cyan" />
          <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-gray-200">
            Pipeline Đa Tác Nhân Tự Động (AI Trading Pipeline)
          </h3>
          {lastReport?.symbol && (
            <span className="rounded border border-bloomberg-cyan/30 bg-cyan-950/30 px-2 py-0.5 text-[10px] font-mono font-bold text-bloomberg-cyan">
              {lastReport.symbol} · {lastReport.timeframe || 'N/A'} · {lastReport.mode || 'N/A'}
            </span>
          )}
        </div>
        {lastReport?.timestamp && (
          <span className="text-[11px] font-mono text-gray-400 flex items-center gap-1">
            <Clock className="w-3 h-3 text-gray-500" />
            Cập nhật: {new Date(lastReport.timestamp).toLocaleTimeString('vi-VN')}
          </span>
        )}
      </div>

      {/* Stage Flow */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {pipelineStages.map((stage, idx) => {
          const { status, color } = getStepStatus(stage.key);
          const IconComponent = stage.icon;
          return (
            <div
              key={stage.key}
              className={`p-2.5 rounded-lg border transition-all flex flex-col justify-between ${color}`}
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono font-bold text-gray-400">
                    BƯỚC {idx + 1}
                  </span>
                  {status === 'PASS' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-bloomberg-green" />
                  ) : status === 'FAIL' ? (
                    <XCircle className="w-3.5 h-3.5 text-bloomberg-red" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-gray-600" />
                  )}
                </div>
                <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-gray-100">
                  <IconComponent className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{stage.name}</span>
                </div>
              </div>

              <div className="mt-2 pt-2 border-t border-bg-border/60 text-[11px] font-mono truncate text-gray-300">
                <span title={stage.details}>{stage.details}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Multi-Timeframe Alignment Indicator */}
      {steps.mtf_alignment && steps.mtf_alignment.alignment && (
        <div className="mt-3 p-2.5 rounded-lg bg-bg-darkest border border-bg-border flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-gray-400">
              Multi-Timeframe (1H & {steps.mtf_alignment.ltf?.timeframe || lastReport?.timeframe || 'N/A'}):
            </span>
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
              steps.mtf_alignment.allow_buy
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/50'
                : 'bg-amber-950/60 text-amber-300 border border-amber-600/40'
            }`}>
              {steps.mtf_alignment.alignment}
            </span>
            <span className="text-gray-300 text-[11px]">{steps.mtf_alignment.note}</span>
          </div>
          <span className="text-gray-400 text-[11px] self-end sm:self-auto">
            Đồng thuận: <strong className="text-gray-200">{steps.mtf_alignment.alignment_strength}/100</strong>
          </span>
        </div>
      )}

      {/* Global Market Session Indicator */}
      {steps.quant_engine?.indicators?.market_session && (
        <div className="mt-2 p-2 rounded-lg bg-bg-card/40 border border-bg-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] font-mono text-gray-400">
          <div className="flex items-center gap-2">
            <span className="text-gray-300 font-bold">🌍 Phiên {steps.quant_engine.indicators.market_session.session}</span>
            <span className="text-gray-500">({steps.quant_engine.indicators.market_session.vn_time})</span>
            <span className="text-gray-400 hidden sm:inline">— {steps.quant_engine.indicators.market_session.recommendation}</span>
          </div>
          <span className="text-bloomberg-cyan text-[10px]">
            Chất lượng phiên: <strong>{steps.quant_engine.indicators.market_session.quality_score}/100</strong>
          </span>
        </div>
      )}
    </div>
  );
};
