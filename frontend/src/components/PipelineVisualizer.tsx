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

  const getStepStatus = (stepKey: string) => {
    const data = steps[stepKey];
    const isHoldAction = steps.gemini_analyst?.output?.action === 'HOLD';
    if (!data) {
      if (isHoldAction && (stepKey === 'risk_engine' || stepKey === 'execution')) {
        return { status: 'PASS', color: 'border-cyan-500/40 text-cyan-400 bg-cyan-950/20' };
      }
      return { status: 'IDLE', color: 'border-gray-800 text-gray-500 bg-bg-card' };
    }
    if (data.status === 'PASS') {
      return { status: 'PASS', color: 'border-bloomberg-green/50 text-bloomberg-green bg-bloomberg-green/10' };
    }
    if (data.status === 'FAIL' || data.status === 'DISAGREED' || data.passed === false) {
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
        ? `RSI: ${steps.quant_engine.indicators?.rsi14?.toFixed(1)} | ADX: ${steps.quant_engine.indicators?.adx?.toFixed(1)}`
        : 'EMA / RSI / MACD / BB',
    },
    {
      key: 'gemini_analyst',
      name: 'Gemini Analyst',
      icon: Sparkles,
      details: steps.gemini_analyst
        ? `${steps.gemini_analyst.output?.action} (${steps.gemini_analyst.latency_ms}ms)`
        : 'Chiến lược & Đề xuất',
    },
    {
      key: 'gpt_reviewer',
      name: 'GPT-6 Luna Review',
      icon: ShieldCheck,
      details: steps.gpt_reviewer
        ? `${steps.gpt_reviewer.output?.decision} (${steps.gpt_reviewer.latency_ms}ms)`
        : 'Thẩm định độc lập',
    },
    {
      key: 'risk_engine',
      name: 'Risk Engine',
      icon: ShieldCheck,
      details: steps.risk_engine
        ? steps.risk_engine.passed
          ? steps.gemini_analyst?.output?.action === 'HOLD'
            ? 'BẢO TOÀN VỐN (0% RỦI RO)'
            : `PASS (Risk ${steps.risk_engine.calculated_risk_percent}%)`
          : 'TỪ CHỐI RỦI RO'
        : steps.gemini_analyst?.output?.action === 'HOLD'
        ? 'Bảo toàn vốn (HOLD)'
        : 'Quy tắc vốn & Drawdown',
    },
    {
      key: 'execution',
      name: 'Execution',
      icon: Send,
      details: steps.execution
        ? steps.gemini_analyst?.output?.action === 'HOLD'
          ? 'STANDBY (0 LỆNH)'
          : `${steps.execution.mode}: ${steps.execution.result?.status || 'DONE'}`
        : steps.gemini_analyst?.output?.action === 'HOLD'
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
                {stage.details}
              </div>
            </div>
          );
        })}
      </div>

      {/* Multi-Timeframe Alignment Indicator */}
      {steps.mtf_alignment && steps.mtf_alignment.alignment && (
        <div className="mt-3 p-2.5 rounded-lg bg-bg-darkest border border-bg-border flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-gray-400">Multi-Timeframe (1H & 15M):</span>
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
    </div>
  );
};
