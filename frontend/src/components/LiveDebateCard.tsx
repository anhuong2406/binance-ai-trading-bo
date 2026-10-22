import React from 'react';
import { Sparkles, ShieldCheck, Check, X, AlertTriangle, Scale } from 'lucide-react';

interface LiveDebateCardProps {
  geminiOutput: any;
  gptOutput: any;
  consensusAction?: string;
  rejectionReason?: string;
}

export const LiveDebateCard: React.FC<LiveDebateCardProps> = ({
  geminiOutput,
  gptOutput,
  consensusAction,
  rejectionReason,
}) => {
  if (!geminiOutput) {
    return (
      <div className="bg-bg-darker p-5 rounded-lg border border-bg-border text-center text-gray-500 font-mono text-xs">
        Chưa có dữ liệu phân tích từ hai AI. Nhấn "Phân tích ngay" hoặc kích hoạt Auto để bắt đầu.
      </div>
    );
  }

  const geminiData = typeof geminiOutput === 'string' ? JSON.parse(geminiOutput) : geminiOutput;
  const gptData = typeof gptOutput === 'string' ? JSON.parse(gptOutput) : gptOutput;

  return (
    <div className="bg-bg-darker rounded-lg border border-bg-border p-4 shadow-sm">
      <div className="flex items-center justify-between border-b border-bg-border pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-bloomberg-orange" />
          <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-gray-200">
            Hội Đồng Giao Dịch AI: Gemini Flash vs GPT-6 Luna
          </h3>
        </div>
        {consensusAction && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-gray-400">Đồng thuận:</span>
            <span
              className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold ${
                consensusAction === 'BUY'
                  ? 'bg-bloomberg-green/20 text-bloomberg-green border border-bloomberg-green/40'
                  : consensusAction === 'SELL'
                  ? 'bg-bloomberg-red/20 text-bloomberg-red border border-bloomberg-red/40'
                  : 'bg-gray-800 text-gray-300 border border-gray-700'
              }`}
            >
              {consensusAction}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Gemini Market Analyst Card */}
        <div className="bg-bg-card p-3.5 rounded-lg border border-cyan-900/40">
          <div className="flex items-center justify-between mb-2 pb-2 border-b border-bg-border">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-bloomberg-cyan" />
              <span className="font-mono text-xs font-bold text-bloomberg-cyan">
                Gemini Market Analyst (AI số 2)
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-bg-darker border border-bg-border text-gray-300">
              {geminiData.market_state || 'TRENDING'}
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between bg-bg-darker p-2 rounded border border-bg-border">
              <span className="text-gray-400">Đề xuất lệnh:</span>
              <span
                className={`font-bold px-2 py-0.5 rounded ${
                  geminiData.action === 'BUY'
                    ? 'bg-bloomberg-green/20 text-bloomberg-green'
                    : geminiData.action === 'SELL'
                    ? 'bg-bloomberg-red/20 text-bloomberg-red'
                    : 'bg-gray-700 text-gray-300'
                }`}
              >
                {geminiData.action}
              </span>
            </div>

            {geminiData.action === 'BUY' && (
              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div className="bg-bg-darker p-1.5 rounded border border-bg-border text-center">
                  <div className="text-gray-500">Entry</div>
                  <div className="text-gray-200 font-bold">{geminiData.entry_price}</div>
                </div>
                <div className="bg-bg-darker p-1.5 rounded border border-bg-border text-center">
                  <div className="text-bloomberg-red">Stop Loss</div>
                  <div className="text-red-400 font-bold">{geminiData.stop_loss}</div>
                </div>
                <div className="bg-bg-darker p-1.5 rounded border border-bg-border text-center">
                  <div className="text-bloomberg-green">Take Profit</div>
                  <div className="text-green-400 font-bold">{geminiData.take_profit}</div>
                </div>
              </div>
            )}

            <div>
              <span className="text-gray-400 block mb-1">Lập luận kỹ thuật:</span>
              <p className="text-gray-300 bg-bg-darker p-2 rounded border border-bg-border text-[11px] leading-relaxed">
                {geminiData.reasoning}
              </p>
            </div>

            {geminiData.invalidation_conditions && (
              <div>
                <span className="text-gray-400 block mb-1 text-[11px]">Điều kiện mất hiệu lực:</span>
                <ul className="list-disc list-inside text-[11px] text-amber-300/80 bg-bg-darker p-2 rounded border border-bg-border space-y-0.5">
                  {geminiData.invalidation_conditions.map((cond: string, idx: number) => (
                    <li key={idx}>{cond}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* GPT-6 Luna Reviewer Card */}
        <div className="bg-bg-card p-3.5 rounded-lg border border-amber-900/40">
          <div className="flex items-center justify-between mb-2 pb-2 border-b border-bg-border">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-bloomberg-orange" />
              <span className="font-mono text-xs font-bold text-bloomberg-orange">
                GPT-6 Luna Reviewer (AI số 1)
              </span>
            </div>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                gptData?.decision === 'APPROVE'
                  ? 'bg-bloomberg-green/20 text-bloomberg-green border border-bloomberg-green/40'
                  : gptData?.decision === 'REJECT'
                  ? 'bg-bloomberg-red/20 text-bloomberg-red border border-bloomberg-red/40'
                  : 'bg-gray-800 text-gray-300 border border-gray-700'
              }`}
            >
              {gptData?.decision || 'CHỜ PHẢN BIỆN'}
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono">
            {/* Checklist */}
            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
              <div className="flex items-center gap-1.5 bg-bg-darker p-1.5 rounded border border-bg-border">
                {gptData?.technical_alignment ? (
                  <Check className="w-3.5 h-3.5 text-bloomberg-green" />
                ) : (
                  <X className="w-3.5 h-3.5 text-bloomberg-red" />
                )}
                <span className="text-gray-300">Đồng thuận chỉ báo</span>
              </div>
              <div className="flex items-center gap-1.5 bg-bg-darker p-1.5 rounded border border-bg-border">
                {gptData?.risk_reward_acceptable ? (
                  <Check className="w-3.5 h-3.5 text-bloomberg-green" />
                ) : (
                  <X className="w-3.5 h-3.5 text-bloomberg-red" />
                )}
                <span className="text-gray-300">Tỷ lệ Risk:Reward</span>
              </div>
              <div className="flex items-center gap-1.5 bg-bg-darker p-1.5 rounded border border-bg-border">
                {gptData?.spread_and_fee_acceptable !== false ? (
                  <Check className="w-3.5 h-3.5 text-bloomberg-green" />
                ) : (
                  <X className="w-3.5 h-3.5 text-bloomberg-red" />
                )}
                <span className="text-gray-300">Chi phí & Spread</span>
              </div>
              <div className="flex items-center gap-1.5 bg-bg-darker p-1.5 rounded border border-bg-border">
                {gptData?.stop_loss_reasonable !== false ? (
                  <Check className="w-3.5 h-3.5 text-bloomberg-green" />
                ) : (
                  <X className="w-3.5 h-3.5 text-bloomberg-red" />
                )}
                <span className="text-gray-300">Stop Loss hợp lý</span>
              </div>
            </div>

            <div>
              <span className="text-gray-400 block mb-1">Đánh giá phản biện độc lập:</span>
              <p className="text-gray-300 bg-bg-darker p-2 rounded border border-bg-border text-[11px] leading-relaxed">
                {gptData?.reason || 'Chưa có dữ liệu phản biện.'}
              </p>
            </div>

            {rejectionReason && (
              <div className="bg-bloomberg-red/10 border border-bloomberg-red/30 p-2 rounded text-[11px] text-red-300 flex items-start gap-1.5">
                <AlertTriangle className="w-4 h-4 text-bloomberg-red shrink-0 mt-0.5" />
                <span>{rejectionReason}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
