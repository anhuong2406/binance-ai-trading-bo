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
  Activity
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
  const [allocatedCapital, setAllocatedCapital] = useState(100.0);
  const [evalInterval, setEvalInterval] = useState(300);

  useEffect(() => {
    api.getSettings().then((s) => {
      setAiBaseUrl(s.ai_base_url || 'https://api.openai.com/v1');
      setGptModelId(s.gpt_model_id || 'gpt-6-luna');
      setGeminiModelId(s.gemini_model_id || 'gemini-3.8-flash');
      setAllocatedCapital(s.bot_allocated_capital || 100.0);
      setEvalInterval(s.evaluation_interval_seconds || 300);
    });
  }, []);

  const handleTestAI = async () => {
    try {
      setTestingAI(true);
      setAiTestResult(null);
      const res = await api.testAI();
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
        bot_allocated_capital: allocatedCapital,
        evaluation_interval_seconds: evalInterval,
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
                type="number"
                step="5"
                min="10"
                value={allocatedCapital}
                onChange={(e) => setAllocatedCapital(parseFloat(e.target.value) || 10)}
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
