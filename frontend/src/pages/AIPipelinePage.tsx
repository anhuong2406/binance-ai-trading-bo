import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Play,
  RotateCcw,
  Clock,
  Layers,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Scale
} from 'lucide-react';
import { PipelineVisualizer } from '../components/PipelineVisualizer';
import { LiveDebateCard } from '../components/LiveDebateCard';
import { AIAnalysisLog } from '../types';
import { api } from '../services/api';

interface AIPipelinePageProps {
  lastReport: any;
}

export const AIPipelinePage: React.FC<AIPipelinePageProps> = ({ lastReport }) => {
  const [logs, setLogs] = useState<AIAnalysisLog[]>([]);
  const [selectedLog, setSelectedLog] = useState<AIAnalysisLog | null>(null);
  const [currentReport, setCurrentReport] = useState<any>(lastReport);
  const [analyzingSymbol, setAnalyzingSymbol] = useState('BTCUSDT');
  const [availablePairs, setAvailablePairs] = useState<string[]>(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT']);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const currentGeminiError = currentReport?.steps?.gemini_analyst?.status === 'FAIL'
    ? currentReport.steps.gemini_analyst.error
    : null;

  useEffect(() => {
    api.getPairsList().then((res) => {
      if (res.active_symbols && res.active_symbols.length > 0) {
        setAvailablePairs(res.active_symbols);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (lastReport) {
      setCurrentReport(lastReport);
      loadLogs();
    }
  }, [lastReport]);

  const loadLogs = async () => {
    try {
      const data = await api.getAILogs(20);
      setLogs(data);
      if (data.length > 0 && !selectedLog) {
        setSelectedLog(data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadLogs();
    const interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleAnalyzeNow = async () => {
    try {
      setIsAnalyzing(true);
      setError(null);
      const res = await api.triggerAIAnalyze(analyzingSymbol);
      if (res?.result?.pipeline) {
        setCurrentReport(res.result.pipeline);
      }
      await loadLogs();
    } catch (err: any) {
      setError(err.message || 'Lỗi khi gọi phân tích đa tác nhân');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Action Header */}
      <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-bloomberg-cyan" />
          <div>
            <h2 className="font-mono text-sm font-bold text-gray-100">
              CÔNG TY GIAO DỊCH ĐA TÁC NHÂN (AI TRADING COMPANY)
            </h2>
            <p className="text-xs text-gray-400 font-mono">
              Hai mô hình AI kiểm tra chéo, giám sát lẫn nhau qua một API Gateway duy nhất
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={analyzingSymbol}
            onChange={(e) => setAnalyzingSymbol(e.target.value)}
            className="bg-bg-darkest border border-bg-border rounded px-3 py-1.5 text-xs font-mono text-gray-200 focus:outline-none"
          >
            {availablePairs.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          <button
            onClick={handleAnalyzeNow}
            disabled={isAnalyzing}
            className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition"
          >
            <Play className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
            <span>{isAnalyzing ? 'Đang phân tích...' : 'Phân tích ngay'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-bloomberg-red/20 border border-bloomberg-red/40 rounded-lg text-xs font-mono text-red-300">
          {error}
        </div>
      )}

      {currentGeminiError && (
        <div className="p-3 bg-bloomberg-red/20 border border-bloomberg-red/40 rounded-lg text-xs font-mono text-red-300">
          Gemini không hoàn tất phân tích chu kỳ hiện tại: {currentGeminiError}
        </div>
      )}

      {/* Informational Banner on Pipeline Status */}
      {selectedLog?.consensus_action === 'HOLD' && (
        <div className="p-3 bg-cyan-950/30 border border-cyan-700/40 rounded-lg text-xs font-mono text-cyan-200 flex items-start gap-2.5">
          <Scale className="w-4 h-4 text-bloomberg-cyan shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold text-bloomberg-cyan">
              Chu kỳ phân tích hoàn tất: Chưa có setup đủ điều kiện (HOLD)
            </span>
            <p className="text-2xs text-gray-400">
              Gemini chưa đề xuất lệnh phù hợp hoặc GPT thẩm định thấy cần chờ thêm dữ liệu/điều kiện an toàn chưa đạt.
              Hệ thống Spot sẽ đứng ngoài cho đến khi có setup được xác nhận; đây không phải lệnh bị Risk Engine từ chối.
            </p>
          </div>
        </div>
      )}

      {/* Pipeline Visualizer Component */}
      <PipelineVisualizer lastReport={currentReport || lastReport} />

      {/* Complementary AI Review Card for Selected Log */}
      {selectedLog ? (
        <>
          {currentGeminiError && (
            <p className="text-[11px] font-mono text-amber-300">
              Bên dưới là log AI đã lưu trước đó; chu kỳ hiện tại lỗi trước khi có kết quả Gemini.
            </p>
          )}
          <LiveDebateCard
            geminiOutput={selectedLog.gemini_output}
            gptOutput={selectedLog.gpt_output}
            consensusAction={selectedLog.consensus_action}
            rejectionReason={selectedLog.rejection_reason || undefined}
          />
        </>
      ) : lastReport?.steps?.gemini_analyst?.output ? (
        <LiveDebateCard
          geminiOutput={lastReport.steps.gemini_analyst.output}
          gptOutput={lastReport.steps.gpt_reviewer?.output}
          consensusAction={lastReport.steps.consensus?.action}
          rejectionReason={lastReport.steps.consensus?.reason}
        />
      ) : null}

      {/* Historical Debate Logs Table */}
      <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
        <h3 className="font-mono text-xs font-bold uppercase text-gray-200 mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-bloomberg-orange" />
          Lịch Sử Đánh Giá & Thẩm Định Độc Lập
        </h3>

        {logs.length === 0 ? (
          <div className="py-8 text-center text-gray-500 text-xs font-mono">
            Chưa có lịch sử phân tích nào được ghi nhận.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-bg-border text-gray-400 text-[11px]">
                  <th className="pb-2">Thời gian</th>
                  <th className="pb-2">Cặp</th>
                  <th className="pb-2">Khung</th>
                  <th className="pb-2">Kết quả thẩm định</th>
                  <th className="pb-2">Phê duyệt</th>
                  <th className="pb-2">Độ trễ (Gemini / GPT)</th>
                  <th className="pb-2">Tokens</th>
                  <th className="pb-2 text-right">Chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bg-border/50">
                {logs.map((l) => (
                  <tr
                    key={l.id}
                    onClick={() => setSelectedLog(l)}
                    className={`cursor-pointer hover:bg-bg-card/50 transition ${
                      selectedLog?.id === l.id ? 'bg-bg-card border-l-2 border-bloomberg-cyan' : ''
                    }`}
                  >
                    <td className="py-2.5 text-gray-400">
                      {new Date(l.created_at).toLocaleTimeString('vi-VN')}
                    </td>
                    <td className="py-2.5 font-bold text-gray-200">{l.symbol}</td>
                    <td className="py-2.5 text-gray-400">{l.timeframe}</td>
                    <td className="py-2.5">
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-[11px] ${
                          l.consensus_action === 'BUY'
                            ? 'bg-bloomberg-green/20 text-bloomberg-green'
                            : l.consensus_action === 'SELL'
                            ? 'bg-bloomberg-red/20 text-bloomberg-red'
                            : 'bg-gray-800 text-gray-400'
                        }`}
                      >
                        {l.consensus_action}
                      </span>
                    </td>
                    <td className="py-2.5">
                      {l.consensus_action === 'HOLD' ? (
                        <span className="text-gray-400 flex items-center gap-1">
                          <span aria-hidden="true">—</span> STANDBY
                        </span>
                      ) : l.execution_approved ? (
                        <span className="text-bloomberg-green flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> PASS
                        </span>
                      ) : (
                        <span className="text-bloomberg-red flex items-center gap-1">
                          <XCircle className="w-3.5 h-3.5" /> REJECT
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 text-gray-400">
                      {l.gemini_latency_ms}ms / {l.gpt_latency_ms}ms
                    </td>
                    <td className="py-2.5 text-gray-400">{l.total_tokens}</td>
                    <td className="py-2.5 text-right text-bloomberg-cyan underline">Xem</td>
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
