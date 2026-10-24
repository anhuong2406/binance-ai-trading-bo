import React from 'react';
import {
  ShieldAlert,
  Play,
  Square,
  Lock,
  Unlock,
  Activity,
  Bot,
  Zap,
  RefreshCw
} from 'lucide-react';
import { SystemStatus, TradingMode } from '../types';

interface NavbarProps {
  status: SystemStatus | null;
  onStart: () => void;
  onStop: () => void;
  onEmergencyStop: () => void;
  onResetEmergencyStop: () => void;
  onSelectMode: (mode: TradingMode) => void;
  onOpenLiveUnlockModal: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  status,
  onStart,
  onStop,
  onEmergencyStop,
  onResetEmergencyStop,
  onSelectMode,
  onOpenLiveUnlockModal,
}) => {
  const mode = status?.mode || 'PAPER';
  const isEmergency = status?.emergency_stop;
  const isRunning = status?.is_running;
  const botState = status?.bot_state || 'STOPPED';

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'OBSERVING':
      case 'RUNNING':
        return 'text-bloomberg-green border-bloomberg-green/30 bg-bloomberg-green/10';
      case 'ANALYZING':
      case 'WAITING_FOR_CONSENSUS':
        return 'text-bloomberg-cyan border-bloomberg-cyan/30 bg-bloomberg-cyan/10 animate-pulse';
      case 'EXECUTING':
        return 'text-bloomberg-orange border-bloomberg-orange/30 bg-bloomberg-orange/10';
      case 'MONITORING_POSITION':
        return 'text-amber-400 border-amber-400/40 bg-amber-400/10 font-bold';
      case 'EMERGENCY_STOP':
        return 'text-bloomberg-red border-bloomberg-red/40 bg-bloomberg-red/20 font-bold';
      default:
        return 'text-gray-400 border-gray-700 bg-gray-800/40';
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-bg-darker/95 backdrop-blur border-b border-bg-border px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-lg">
      {/* Brand & Terminal Logo */}
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center shadow-md shadow-amber-500/20 border border-amber-400/30">
          <Bot className="w-5 h-5 text-black" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-mono text-base font-bold text-gray-100 tracking-wider">
              AI BINANCE TRADING COMPANY
            </span>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-bg-card border border-bg-border text-bloomberg-orange">
              Spot Only
            </span>
          </div>
          <p className="text-xs text-gray-400 font-mono flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-bloomberg-green animate-ping" />
            {status?.ai_single_model_mode !== false
              ? 'AI: Gemini 3.8 Flash High (Single Model)'
              : 'Dual AI: Gemini Flash + GPT-6 Luna'}
          </p>
        </div>
      </div>

      {/* Trading Mode Switcher */}
      <div className="flex items-center bg-bg-darkest p-1 rounded-lg border border-bg-border">
        <button
          onClick={() => onSelectMode('PAPER')}
          className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
            mode === 'PAPER'
              ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          PAPER
        </button>
        <button
          onClick={() => onSelectMode('TESTNET')}
          className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
            mode === 'TESTNET'
              ? 'bg-amber-600/30 text-amber-300 border border-amber-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          TESTNET
        </button>
        <button
          onClick={() => {
            if (status?.live_locked) {
              onOpenLiveUnlockModal();
            } else {
              onSelectMode('LIVE');
            }
          }}
          className={`px-3 py-1 rounded text-xs font-mono font-medium flex items-center gap-1 transition-all ${
            mode === 'LIVE'
              ? 'bg-bloomberg-red/30 text-red-300 border border-bloomberg-red/50 shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {status?.live_locked ? (
            <Lock className="w-3 h-3 text-bloomberg-orange" />
          ) : (
            <Unlock className="w-3 h-3 text-bloomberg-green" />
          )}
          LIVE SPOT
        </button>
      </div>

      {/* Bot State Badge */}
      <div className="flex items-center space-x-2">
        <div
          title={status?.standby_reason || undefined}
          className={`px-3 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 ${getStatusColor(
            botState
          )}`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>{botState === 'MONITORING_POSITION' ? 'CHỜ BÁN (TIẾT KIỆM TOKEN)' : botState}</span>
        </div>

        {/* Start / Stop Controller */}
        {isRunning ? (
          <button
            onClick={onStop}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-mono border border-gray-600 transition shadow"
          >
            <Square className="w-3.5 h-3.5 text-bloomberg-orange" />
            <span>Tạm dừng</span>
          </button>
        ) : (
          <button
            onClick={onStart}
            disabled={isEmergency}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-mono font-medium border border-emerald-400/40 shadow-md shadow-emerald-900/30 transition"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Kích hoạt Auto</span>
          </button>
        )}

        {/* Emergency Stop Button */}
        {isEmergency ? (
          <button
            onClick={onResetEmergencyStop}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-600/30 hover:bg-amber-600/50 text-amber-300 text-xs font-mono border border-amber-500/60 shadow transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Mở khóa khẩn cấp</span>
          </button>
        ) : (
          <button
            onClick={onEmergencyStop}
            className="emergency-btn-pulse flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-bloomberg-red hover:bg-red-700 text-white text-xs font-mono font-bold border border-red-400 shadow-lg shadow-red-900/50 transition"
            title="Dừng ngay lập tức toàn bộ việc tạo lệnh và đặt trạng thái khóa an toàn"
          >
            <ShieldAlert className="w-4 h-4 fill-current" />
            <span>EMERGENCY STOP</span>
          </button>
        )}
      </div>
    </header>
  );
};
