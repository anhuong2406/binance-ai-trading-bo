import React, { useState, useEffect } from 'react';
import {
  Settings,
  Sparkles,
  Key,
  Shield,
  Clock,
  Coins,
  CheckCircle,
  XCircle,
  Save,
  Activity,
  Plus,
  Trash2,
  Zap,
  Target
} from 'lucide-react';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [testingAI, setTestingAI] = useState(false);
  const [testingBinance, setTestingBinance] = useState(false);
  const [aiTestResult, setAiTestResult] = useState<any | null>(null);
  const [binanceTestResult, setBinanceTestResult] = useState<any | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Form State
  const [aiBaseUrl, setAiBaseUrl] = useState('');
  const [aiApiKey, setAiApiKey] = useState('');
  const [gptModelId, setGptModelId] = useState('gpt-6-luna');
  const [geminiModelId, setGeminiModelId] = useState('gemini-3.8-flash');
  const [binanceApiKey, setBinanceApiKey] = useState('');
  const [binanceApiSecret, setBinanceApiSecret] = useState('');
  const [binanceTestnetKey, setBinanceTestnetKey] = useState('');
  const [binanceTestnetSecret, setBinanceTestnetSecret] = useState('');
  const [allocatedCapital, setAllocatedCapital] = useState<string | number>(100.0);
  const [evalInterval, setEvalInterval] = useState(300);
  const [quantPrefilter, setQuantPrefilter] = useState(true);
  const [scalpingMode, setScalpingMode] = useState(true);
  const [targetTakeProfit, setTargetTakeProfit] = useState<string | number>(1.2);
  const [targetStopLoss, setTargetStopLoss] = useState<string | number>(1.0);

  // Trading Pairs State
  const [pairs, setPairs] = useState<any[]>([]);
  const [newSymbol, setNewSymbol] = useState('');
  const [newName, setNewName] = useState('');
  const [pairLoading, setPairLoading] = useState(false);
  const [pairError, setPairError] = useState<string | null>(null);
  const [pairSuccess, setPairSuccess] = useState<string | null>(null);

  const loadPairs = async () => {
    try {
      const res = await api.getPairsList();
      setPairs(res.pairs || []);
    } catch (e: any) {
      console.error(e);
    }
  };

  useEffect(() => {
    api.getSettings().then((s) => {
      setAiBaseUrl(s.ai_base_url || 'https://api.openai.com/v1');
      setGptModelId(s.gpt_model_id || 'gpt-6-luna');
      setGeminiModelId(s.gemini_model_id || 'gemini-3.8-flash');
      setAllocatedCapital(s.bot_allocated_capital || 100.0);
      setEvalInterval(s.evaluation_interval_seconds || 300);
      setQuantPrefilter(s.quant_prefilter_enabled !== false);
      setScalpingMode(s.scalping_mode_enabled !== false);
      setTargetTakeProfit(s.target_take_profit_percent !== undefined ? s.target_take_profit_percent : 1.2);
      setTargetStopLoss(s.target_stop_loss_percent !== undefined ? s.target_stop_loss_percent : 1.0);
    });
    loadPairs();
  }, []);

  const handleTogglePair = async (symbol: string, currentEnabled: boolean) => {
    try {
      setPairError(null);
      setPairSuccess(null);
      await api.togglePair(symbol, !currentEnabled);
      await loadPairs();
    } catch (e: any) {
      setPairError(e.message);
    }
  };

  const handleAddPair = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSymbol.trim()) return;
    try {
      setPairLoading(true);
      setPairError(null);
      setPairSuccess(null);
      const res = await api.addPair(newSymbol.trim(), newName.trim() || undefined);
      setPairSuccess(res.message);
      setNewSymbol('');
      setNewName('');
      await loadPairs();
    } catch (e: any) {
      setPairError(e.message);
    } finally {
      setPairLoading(false);
    }
  };

  const handleRemovePair = async (symbol: string) => {
    if (!confirm(`Bạn có chắc muốn xóa cặp ${symbol}?`)) return;
    try {
      setPairError(null);
      setPairSuccess(null);
      await api.removePair(symbol);
      await loadPairs();
    } catch (e: any) {
      setPairError(e.message);
    }
  };

  const handleTestAI = async () => {
    try {
      setTestingAI(true);
      setAiTestResult(null);
      const res = await api.testAI({
        base_url: aiBaseUrl,
        api_key: aiApiKey,
        gpt_model_id: gptModelId,
        gemini_model_id: geminiModelId,
      });
      setAiTestResult(res);
    } catch (e: any) {
      setAiTestResult({ status: 'ERROR', message: e.message });
    } finally {
      setTestingAI(false);
    }
  };

  const handleTestBinance = async () => {
    try {
      setTestingBinance(true);
      setBinanceTestResult(null);
      const res = await api.testBinance();
      setBinanceTestResult(res);
    } catch (e: any) {
      setBinanceTestResult({ status: 'ERROR', message: e.message });
    } finally {
      setTestingBinance(false);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setMessage(null);

      const payload: any = {
        ai_base_url: aiBaseUrl,
        gpt_model_id: gptModelId,
        gemini_model_id: geminiModelId,
        bot_allocated_capital: parseFloat(String(allocatedCapital).replace(',', '.')),
        evaluation_interval_seconds: evalInterval,
        quant_prefilter_enabled: quantPrefilter,
        scalping_mode_enabled: scalpingMode,
        target_take_profit_percent: parseFloat(String(targetTakeProfit).replace(',', '.')),
        target_stop_loss_percent: parseFloat(String(targetStopLoss).replace(',', '.')),
      };

      if (aiApiKey) payload.ai_api_key = aiApiKey;
      if (binanceApiKey) payload.binance_api_key = binanceApiKey;
      if (binanceApiSecret) payload.binance_api_secret = binanceApiSecret;
      if (binanceTestnetKey) payload.binance_testnet_api_key = binanceTestnetKey;
      if (binanceTestnetSecret) payload.binance_testnet_api_secret = binanceTestnetSecret;

      await api.updateSettings(payload);
      setMessage('Đã lưu cấu hình an toàn thành công!');
    } catch (err: any) {
      setMessage(`Lỗi lưu cài đặt: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 max-w-5xl">
      <form onSubmit={handleSaveSettings} className="space-y-4">
        {/* AI Gateway Section */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border space-y-4">
          <div className="flex items-center justify-between border-b border-bg-border pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-bloomberg-cyan" />
              <h3 className="font-mono text-xs font-bold uppercase text-gray-200">
                Cấu Hình Một API Gateway Cho Hai Mô Hình AI
              </h3>
            </div>
            <button
              type="button"
              onClick={handleTestAI}
              disabled={testingAI}
              className="px-3 py-1 bg-bg-card hover:bg-gray-700 text-bloomberg-cyan border border-cyan-800/60 rounded text-xs font-mono font-bold flex items-center gap-1.5 transition"
            >
              <Activity className={`w-3.5 h-3.5 ${testingAI ? 'animate-spin' : ''}`} />
              <span>{testingAI ? 'Đang kiểm tra...' : 'Kiểm tra kết nối AI'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <label className="block text-gray-400 mb-1">AI Base URL (Gateway):</label>
              <input
                type="text"
                placeholder="https://api.openai.com/v1"
                value={aiBaseUrl}
                onChange={(e) => setAiBaseUrl(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
              />
            </div>

            <div>
              <label className="block text-gray-400 mb-1">AI API Key (Được mã hóa an toàn):</label>
              <input
                type="password"
                placeholder="sk-••••••••••••••••"
                value={aiApiKey}
                onChange={(e) => setAiApiKey(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
              />
            </div>

            <div>
              <label className="block text-gray-400 mb-1">
                AI số 1: Model ID Thẩm định (GPT-6 Luna / Reviewer):
              </label>
              <input
                type="text"
                value={gptModelId}
                onChange={(e) => setGptModelId(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
              />
              <span className="text-[10px] text-gray-500">Mặc định: gpt-6-luna</span>
            </div>

            <div>
              <label className="block text-gray-400 mb-1">
                AI số 2: Model ID Phân tích (Gemini Flash / Market Analyst):
              </label>
              <input
                type="text"
                value={geminiModelId}
                onChange={(e) => setGeminiModelId(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-cyan"
              />
              <span className="text-[10px] text-gray-500">Mặc định: gemini-3.8-flash</span>
            </div>
          </div>

          {/* AI Test Results Feedback */}
          {aiTestResult && (
            <div className="p-3 bg-bg-card rounded border border-bg-border text-xs font-mono space-y-1">
              <div className="font-bold text-gray-200">Kết quả kiểm tra AI Gateway:</div>
              <div className="text-gray-400">
                Gemini: {aiTestResult.results?.gemini?.status === 'connected' ? (
                  <span className="text-bloomberg-green font-bold">
                    CONNECTED ({aiTestResult.results?.gemini?.latency_ms}ms)
                  </span>
                ) : (
                  <span className="text-bloomberg-red font-bold">
                    ERROR: {aiTestResult.results?.gemini?.error}
                  </span>
                )}
              </div>
              <div className="text-gray-400">
                GPT-6 Luna: {aiTestResult.results?.gpt?.status === 'connected' ? (
                  <span className="text-bloomberg-green font-bold">
                    CONNECTED ({aiTestResult.results?.gpt?.latency_ms}ms)
                  </span>
                ) : (
                  <span className="text-bloomberg-red font-bold">
                    ERROR: {aiTestResult.results?.gpt?.error}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Binance Spot API Section */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border space-y-4">
          <div className="flex items-center justify-between border-b border-bg-border pb-3">
            <div className="flex items-center gap-2">
              <Coins className="w-4 h-4 text-bloomberg-orange" />
              <h3 className="font-mono text-xs font-bold uppercase text-gray-200">
                Cấu Hình Binance Spot API
              </h3>
            </div>
            <button
              type="button"
              onClick={handleTestBinance}
              disabled={testingBinance}
              className="px-3 py-1 bg-bg-card hover:bg-gray-700 text-bloomberg-orange border border-amber-800/60 rounded text-xs font-mono font-bold flex items-center gap-1.5 transition"
            >
              <Activity className={`w-3.5 h-3.5 ${testingBinance ? 'animate-spin' : ''}`} />
              <span>{testingBinance ? 'Đang kiểm tra...' : 'Kiểm tra kết nối Binance'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <label className="block text-gray-400 mb-1">Binance LIVE API Key:</label>
              <input
                type="password"
                placeholder="Nhập API Key sàn Binance (Spot)"
                value={binanceApiKey}
                onChange={(e) => setBinanceApiKey(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-orange"
              />
            </div>

            <div>
              <label className="block text-gray-400 mb-1">Binance LIVE API Secret:</label>
              <input
                type="password"
                placeholder="Nhập API Secret sàn Binance"
                value={binanceApiSecret}
                onChange={(e) => setBinanceApiSecret(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-orange"
              />
            </div>

            <div>
              <label className="block text-gray-400 mb-1">Binance Testnet API Key:</label>
              <input
                type="password"
                placeholder="Testnet API Key (testnet.binance.vision)"
                value={binanceTestnetKey}
                onChange={(e) => setBinanceTestnetKey(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-orange"
              />
            </div>

            <div>
              <label className="block text-gray-400 mb-1">Binance Testnet Secret:</label>
              <input
                type="password"
                placeholder="Testnet Secret"
                value={binanceTestnetSecret}
                onChange={(e) => setBinanceTestnetSecret(e.target.value)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none focus:border-bloomberg-orange"
              />
            </div>
          </div>

          {binanceTestResult && (
            <div className="p-3 bg-bg-card rounded border border-bg-border text-xs font-mono">
              {binanceTestResult.status === 'SUCCESS' ? (
                <div className="text-bloomberg-green font-bold flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4" />
                  <span>
                    Kết nối Binance Spot thành công! Độ lệch thời gian máy chủ:{' '}
                    {binanceTestResult.details?.time_offset_ms}ms
                  </span>
                </div>
              ) : (
                <div className="text-bloomberg-red font-bold flex items-center gap-1.5">
                  <XCircle className="w-4 h-4" />
                  <span>Lỗi kết nối: {binanceTestResult.message}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Trading Pairs Management Section */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-bg-border gap-2">
            <div>
              <h3 className="font-mono text-xs font-bold uppercase text-gray-200 flex items-center gap-2">
                <Coins className="w-4 h-4 text-bloomberg-orange" />
                Chọn Mã Giao Dịch Tự Động (Trading Pairs Selector)
              </h3>
              <p className="text-[11px] text-gray-400 font-mono mt-0.5">
                Bật/tắt cặp giao dịch để chỉ định AI và Bot quét & đặt lệnh cho mã bạn muốn.
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-bg-card border border-bg-border text-bloomberg-cyan self-start sm:self-auto">
              Đang chạy: <strong>{pairs.filter((p) => p.enabled).length}/{pairs.length} cặp</strong>
            </span>
          </div>

          {pairError && (
            <div className="mb-3 p-2.5 bg-bloomberg-red/20 border border-bloomberg-red/40 rounded text-xs text-red-300 font-mono flex items-center gap-2">
              <XCircle className="w-4 h-4 shrink-0" />
              <span>{pairError}</span>
            </div>
          )}

          {pairSuccess && (
            <div className="mb-3 p-2.5 bg-emerald-950/40 border border-emerald-500/40 rounded text-xs text-emerald-300 font-mono flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{pairSuccess}</span>
            </div>
          )}

          {/* Pairs Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            {pairs.map((p) => (
              <div
                key={p.symbol}
                className={`p-3 rounded-lg border transition flex items-center justify-between ${
                  p.enabled
                    ? 'bg-bg-card border-bloomberg-orange/40 shadow-sm'
                    : 'bg-bg-card/40 border-bg-border opacity-60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => handleTogglePair(p.symbol, p.enabled)}
                    className={`w-9 h-5 flex items-center rounded-full p-0.5 transition cursor-pointer ${
                      p.enabled ? 'bg-bloomberg-orange justify-end' : 'bg-gray-700 justify-start'
                    }`}
                    title={p.enabled ? 'Bấm để tắt mã này' : 'Bấm để bật mã này'}
                  >
                    <div className="w-4 h-4 rounded-full bg-white shadow-md"></div>
                  </button>

                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-sm text-gray-100">{p.symbol}</span>
                      <span className="text-2xs font-mono text-gray-400">({p.name})</span>
                      {p.min_notional <= 1.0 && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-600/50 text-emerald-400">
                          ⚡ Min {p.min_notional}$
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] font-mono text-gray-400 mt-0.5">
                      {p.last_price > 0 && (
                        <span>Giá: <strong className="text-gray-200">${p.last_price.toLocaleString()}</strong></span>
                      )}
                      {p.price_change_percent !== 0 && (
                        <span className={p.price_change_percent >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'}>
                          {p.price_change_percent >= 0 ? '+' : ''}{p.price_change_percent.toFixed(2)}%
                        </span>
                      )}
                      <span className="text-gray-500">| Lệnh min: {p.min_notional} USDT</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                    p.enabled ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-700/40' : 'bg-gray-800 text-gray-400'
                  }`}>
                    {p.enabled ? 'ĐANG CHẠY' : 'ĐÃ TẮT'}
                  </span>
                  {!p.is_default && (
                    <button
                      type="button"
                      onClick={() => handleRemovePair(p.symbol)}
                      className="p-1 hover:text-red-400 text-gray-500 transition cursor-pointer"
                      title="Xóa mã này khỏi danh sách"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Add New Pair Form */}
          <div className="p-3 bg-bg-darkest rounded-lg border border-bg-border/60">
            <h4 className="text-xs font-mono font-bold text-gray-300 mb-2 flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5 text-bloomberg-orange" />
              Thêm cặp giao dịch mới từ Binance Spot:
            </h4>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                placeholder="VD: BNB, PEPE, XRP, ADA..."
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
                className="flex-1 bg-bg-card border border-bg-border rounded px-3 py-1.5 text-xs font-mono text-gray-100 uppercase focus:outline-none focus:border-bloomberg-orange"
              />
              <input
                type="text"
                placeholder="Tên gợi nhớ (VD: Binance Coin)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="flex-1 bg-bg-card border border-bg-border rounded px-3 py-1.5 text-xs font-mono text-gray-100 focus:outline-none focus:border-bloomberg-orange"
              />
              <button
                type="button"
                onClick={handleAddPair}
                disabled={pairLoading || !newSymbol.trim()}
                className="px-4 py-1.5 bg-bloomberg-orange hover:bg-amber-500 disabled:opacity-50 text-black font-mono text-xs font-bold rounded flex items-center justify-center gap-1.5 transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{pairLoading ? 'Đang kiểm tra Binance...' : 'Thêm Vào Bot'}</span>
              </button>
            </div>
            <p className="text-[10px] text-gray-500 font-mono mt-1.5">
              * Hệ thống sẽ tự động kết nối Binance Spot API để kiểm tra cặp giao dịch, xác thực bộ lọc lệnh (minNotional) và kích hoạt cho Bot.
            </p>
          </div>
        </div>

        {/* Quant Opportunity Pre-Filter Toggle */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-950/60 border border-emerald-500/40 flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-mono text-xs font-bold uppercase text-gray-200">
                  Bộ Lọc Cơ Hội Tiết Kiệm Token (Quant Opportunity Pre-Filter)
                </h4>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-600/40">
                  Tiết kiệm 85-90% Token
                </span>
              </div>
              <p className="text-[11px] text-gray-400 font-mono mt-0.5">
                Chỉ đánh thức Gemini 3.8 và GPT-6 Luna khi phát hiện tín hiệu kỹ thuật (quá bán, breakout, volume gom hàng). Khi thị trường cắm đầu giảm hoặc sideway vô hướng, Python tự động giữ HOLD mà không tốn token 9Router.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setQuantPrefilter(!quantPrefilter)}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition cursor-pointer shrink-0 ${
              quantPrefilter ? 'bg-bloomberg-green justify-end' : 'bg-gray-700 justify-start'
            }`}
          >
            <div className="w-4 h-4 rounded-full bg-white shadow-md"></div>
          </button>
        </div>

        {/* Scalping & Micro-Profit Settings (Tích tiểu thành đại) */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-bg-border gap-2">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-amber-950/60 border border-bloomberg-orange/40 flex items-center justify-center shrink-0">
                <Zap className="w-5 h-5 text-bloomberg-orange" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-mono text-xs font-bold uppercase text-gray-200">
                    Chế Độ Lướt Sóng Siêu Ngắn (Scalping & Take Profit Vi Mô)
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-600/40">
                    Tích Tiểu Thành Đại
                  </span>
                </div>
                <p className="text-[11px] text-gray-400 font-mono mt-0.5">
                  Mua đi bán lại liên tục trong các nhịp nảy sóng ngắn, chốt lời nhanh ở mức lãi nhỏ (+1.0% ~ +1.5%) để quay vòng vốn liên tục thay vì gồng chờ đỉnh xa.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setScalpingMode(!scalpingMode)}
              className={`w-12 h-6 flex items-center rounded-full p-1 transition cursor-pointer shrink-0 ${
                scalpingMode ? 'bg-bloomberg-orange justify-end' : 'bg-gray-700 justify-start'
              }`}
              title="Bật/Tắt chế độ Scalping ăn mỏng chốt nhanh"
            >
              <div className="w-4 h-4 rounded-full bg-white shadow-md"></div>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono pt-1">
            <div>
              <label className="block text-gray-300 font-bold mb-1 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-bloomberg-green" />
                <span>Mục tiêu Chốt Lời (Take Profit %):</span>
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={targetTakeProfit}
                  onChange={(e) => setTargetTakeProfit(e.target.value)}
                  placeholder="VD: 1.2"
                  className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 font-bold focus:outline-none focus:border-bloomberg-green"
                />
                <span className="text-gray-400 font-bold">%</span>
              </div>
              <p className="text-[10px] text-gray-500 mt-1">
                * Khuyến nghị: <strong>1.0% - 1.5%</strong>. Trừ phí sàn (~0.2%), mỗi vòng ăn ròng ~0.8% - 1.3%, tiền về ví ngay để quét lệnh mới.
              </p>
              {parseFloat(String(targetTakeProfit)) < 0.5 && (
                <p className="text-[10px] text-amber-400 mt-1">
                  ⚠️ Cảnh báo: TP &lt; 0.5% có thể bị phí sàn (~0.2%) ăn mòn lợi nhuận. Nên đặt ≥ 0.8%.
                </p>
              )}
            </div>

            <div>
              <label className="block text-gray-300 font-bold mb-1 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-bloomberg-red" />
                <span>Mục tiêu Cắt Lỗ (Stop Loss %):</span>
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={targetStopLoss}
                  onChange={(e) => setTargetStopLoss(e.target.value)}
                  placeholder="VD: 1.0"
                  className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 font-bold focus:outline-none focus:border-bloomberg-red"
                />
                <span className="text-gray-400 font-bold">%</span>
              </div>
              <p className="text-[10px] text-gray-500 mt-1">
                * Khuyến nghị: <strong>0.8% - 1.2%</strong>. Cắt dứt khoát nếu thị trường quay đầu phá vỡ điểm nảy để bảo toàn vốn.
              </p>
            </div>
          </div>
        </div>

        {/* Capital & Intervals */}
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <h3 className="font-mono text-xs font-bold uppercase text-gray-200 mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            Cấu Hình Vận Hành Bot & Chu Kỳ Đánh Giá
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <label className="block text-gray-400 mb-1">Vốn Spot phân bổ cho Bot (USDT):</label>
              <input
                type="text"
                inputMode="decimal"
                value={allocatedCapital}
                onChange={(e) => setAllocatedCapital(e.target.value)}
                placeholder="VD: 5.67 hoặc 5,67"
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none"
              />
              <span className="text-[10px] text-gray-500">
                Bot chỉ giao dịch trong phạm vi số vốn này, không dùng hết số dư Spot của bạn.
              </span>
            </div>

            <div>
              <label className="block text-gray-400 mb-1">Chu kỳ đánh giá (Giây):</label>
              <input
                type="number"
                step="30"
                min="30"
                value={evalInterval}
                onChange={(e) => setEvalInterval(parseInt(e.target.value) || 300)}
                className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-gray-100 focus:outline-none"
              />
              <span className="text-[10px] text-gray-500">
                Mặc định: 300 giây (5 phút). Tránh gọi AI liên tục gây lãng phí chi phí.
              </span>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between p-3 bg-bg-darker rounded-lg border border-bg-border">
          {message && (
            <span className="text-xs font-mono text-bloomberg-cyan font-bold">{message}</span>
          )}
          <button
            type="submit"
            disabled={loading}
            className="ml-auto px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold rounded shadow flex items-center gap-1.5 transition"
          >
            <Save className="w-4 h-4" />
            <span>{loading ? 'Đang lưu...' : 'Lưu tất cả cài đặt'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
