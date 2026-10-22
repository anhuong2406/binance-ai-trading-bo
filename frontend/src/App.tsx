import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  CandlestickChart,
  Cpu,
  ShieldCheck,
  BarChart,
  Settings,
  AlertTriangle,
  Boxes
} from 'lucide-react';
import { Navbar } from './components/Navbar';
import { LiveUnlockModal } from './components/LiveUnlockModal';
import { OverviewPage } from './pages/OverviewPage';
import { TradingPage } from './pages/TradingPage';
import { AIPipelinePage } from './pages/AIPipelinePage';
import { TradingSkillsPage } from './pages/TradingSkillsPage';
import { RiskControlPage } from './pages/RiskControlPage';
import { BacktestPage } from './pages/BacktestPage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemStatus, SpotAccount, Position, TradingMode } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'trading' | 'ai' | 'skills' | 'risk' | 'backtest' | 'settings'>('overview');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [account, setAccount] = useState<SpotAccount | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [lastReport, setLastReport] = useState<any>(null);
  const [isLiveUnlockOpen, setIsLiveUnlockOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load initial REST data
  const refreshData = async () => {
    try {
      const [statusRes, accountRes, posRes, statsRes] = await Promise.all([
        api.getSystemStatus(),
        api.getSpotAccount(),
        api.getPositions(),
        api.getTradingStats(),
      ]);
      setStatus(statusRes);
      setAccount(accountRes.account);
      setPositions(posRes);
      setStats(statsRes);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 10000);
    return () => clearInterval(interval);
  }, []);

  // Live WebSocket Connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWS = () => {
      try {
        ws = new WebSocket(wsUrl);
        ws.onopen = () => {
          console.log('[WS] Connected to live trading feed');
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'INITIAL_STATE' || data.type === 'BOT_STATE_UPDATE') {
              setStatus((prev) => (prev ? { ...prev, ...data } : data));
              if (data.last_report) {
                setLastReport(data.last_report);
              }
            }
          } catch (err) {
            console.error('[WS] Parse error', err);
          }
        };
        ws.onclose = () => {
          console.log('[WS] Closed, reconnecting in 3s...');
          reconnectTimeout = setTimeout(connectWS, 3000);
        };
      } catch (e) {
        reconnectTimeout = setTimeout(connectWS, 3000);
      }
    };

    connectWS();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  // Handlers
  const handleStartBot = async () => {
    try {
      await api.startBot();
      await refreshData();
      showToast('Đã khởi động bot giao dịch tự động 24/7');
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const handleStopBot = async () => {
    try {
      await api.stopBot();
      await refreshData();
      showToast('Đã dừng bot giao dịch');
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const handleEmergencyStop = async () => {
    try {
      await api.triggerEmergencyStop();
      await refreshData();
      showToast('ĐÃ KÍCH HOẠT DỪNG KHẨN CẤP (EMERGENCY STOP)');
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const handleResetEmergency = async () => {
    try {
      await api.resetEmergencyStop();
      await refreshData();
      showToast('Đã mở khóa an toàn sau dừng khẩn cấp');
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const handleSelectMode = async (mode: TradingMode) => {
    try {
      await api.setMode(mode);
      await refreshData();
      showToast(`Đã chuyển chế độ sang: ${mode}`);
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const handleUnlockLive = async (phrase: string, capital: number) => {
    await api.unlockLive(phrase, capital);
    await api.setMode('LIVE');
    await refreshData();
    showToast('ĐÃ MỞ KHÓA VÀ KÍCH HOẠT CHẾ ĐỘ LIVE SPOT!');
  };

  const handleClosePosition = async (id: number) => {
    try {
      await api.closePosition(id);
      await refreshData();
      showToast(`Đã đóng thủ công vị thế #${id}`);
    } catch (err: any) {
      showToast(`Lỗi: ${err.message}`);
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  return (
    <div className="min-h-screen flex flex-col bg-bg-darkest text-gray-200">
      {/* Top Navbar */}
      <Navbar
        status={status}
        onStart={handleStartBot}
        onStop={handleStopBot}
        onEmergencyStop={handleEmergencyStop}
        onResetEmergencyStop={handleResetEmergency}
        onSelectMode={handleSelectMode}
        onOpenLiveUnlockModal={() => setIsLiveUnlockOpen(true)}
      />

      {/* Emergency Alert Banner */}
      {status?.emergency_stop && (
        <div className="bg-bloomberg-red text-white px-4 py-2 text-xs font-mono font-bold flex items-center justify-between shadow-md">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 fill-current" />
            <span>
              CẢNH BÁO: CHẾ ĐỘ DỪNG KHẨN CẤP ĐANG BẬT. MỌI TÁC VỤ ĐẶT LỆNH BỊ PHONG TỎA TUYỆT ĐỐI!
            </span>
          </div>
          <button
            onClick={handleResetEmergency}
            className="px-3 py-0.5 rounded bg-white text-bloomberg-red font-bold hover:bg-gray-100 transition"
          >
            Mở khóa an toàn
          </button>
        </div>
      )}

      {/* Toast Notification Pill */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-bg-card border border-bloomberg-cyan text-cyan-200 px-4 py-2.5 rounded-lg shadow-xl font-mono text-xs animate-bounce">
          {toastMessage}
        </div>
      )}

      {/* Main Tab Navigation Bar */}
      <div className="bg-bg-darker border-b border-bg-border px-4 py-1.5 flex items-center space-x-1 overflow-x-auto">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'overview'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          <span>Tổng Quan</span>
        </button>

        <button
          onClick={() => setActiveTab('trading')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'trading'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <CandlestickChart className="w-3.5 h-3.5" />
          <span>Đồ Thị & Vị Thế</span>
        </button>

        <button
          onClick={() => setActiveTab('ai')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'ai'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>Hội Đồng AI (Company)</span>
        </button>

        <button
          onClick={() => setActiveTab('skills')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'skills'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Boxes className="w-3.5 h-3.5" />
          <span>Trading Skills</span>
        </button>

        <button
          onClick={() => setActiveTab('risk')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'risk'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Quản Trị Rủi Ro</span>
        </button>

        <button
          onClick={() => setActiveTab('backtest')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'backtest'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <BarChart className="w-3.5 h-3.5" />
          <span>Kiểm Thử (Backtest)</span>
        </button>

        <button
          onClick={() => setActiveTab('settings')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-xs transition ${
            activeTab === 'settings'
              ? 'bg-bg-card text-bloomberg-orange font-bold border border-bg-border'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Cài Đặt Hệ Thống</span>
        </button>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 p-4 overflow-y-auto max-w-7xl w-full mx-auto">
        {activeTab === 'overview' && (
          <OverviewPage
            status={status}
            account={account}
            positions={positions}
            stats={stats}
            onClosePosition={handleClosePosition}
          />
        )}
        {activeTab === 'trading' && (
          <TradingPage positions={positions} onClosePosition={handleClosePosition} />
        )}
        {activeTab === 'ai' && <AIPipelinePage lastReport={lastReport} />}
        {activeTab === 'skills' && <TradingSkillsPage />}
        {activeTab === 'risk' && <RiskControlPage />}
        {activeTab === 'backtest' && <BacktestPage />}
        {activeTab === 'settings' && <SettingsPage />}
      </main>

      {/* Live Unlock Modal */}
      <LiveUnlockModal
        isOpen={isLiveUnlockOpen}
        onClose={() => setIsLiveUnlockOpen(false)}
        onUnlock={handleUnlockLive}
        defaultCapital={status?.allocated_capital}
      />
    </div>
  );
};
