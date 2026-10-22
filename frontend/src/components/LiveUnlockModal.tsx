import React, { useState } from 'react';
import { AlertTriangle, Lock, ShieldAlert, X } from 'lucide-react';

interface LiveUnlockModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUnlock: (phrase: string, capital: number) => Promise<void>;
  defaultCapital?: number;
}

export const LiveUnlockModal: React.FC<LiveUnlockModalProps> = ({
  isOpen,
  onClose,
  onUnlock,
  defaultCapital = 100.0,
}) => {
  const [phrase, setPhrase] = useState('');
  const [capital, setCapital] = useState(defaultCapital);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (phrase !== 'ENABLE LIVE SPOT') {
      setError("Vui lòng nhập chính xác cụm từ: 'ENABLE LIVE SPOT'");
      return;
    }
    if (capital <= 0) {
      setError('Vốn cấp cho bot phải lớn hơn 0 USDT.');
      return;
    }

    try {
      setLoading(true);
      await onUnlock(phrase, capital);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Lỗi mở khóa LIVE SPOT');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-bg-darker border border-bloomberg-red/60 rounded-xl max-w-lg w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-bloomberg-red/20 border border-bloomberg-red/50 flex items-center justify-center shrink-0">
            <ShieldAlert className="w-6 h-6 text-bloomberg-red" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-100 font-mono">
              XÁC THỰC MỞ KHÓA LIVE SPOT
            </h2>
            <p className="text-xs text-bloomberg-red font-mono">
              Cảnh báo: Bạn đang kích hoạt giao dịch bằng số dư Spot thực tế
            </p>
          </div>
        </div>

        <div className="bg-bg-card p-3 rounded-lg border border-bg-border text-xs text-gray-300 font-mono space-y-2 mb-5">
          <div className="flex items-start gap-2 text-amber-300">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Bot sẽ sử dụng trực tiếp số dư USDT trong tài khoản Binance Spot của bạn để mở lệnh khi có tín hiệu đồng thuận.
            </span>
          </div>
          <p className="text-gray-400">
            - Giới hạn rủi ro tối đa mỗi lệnh: 1% vốn bot.<br />
            - Giới hạn drawdown tối đa: 5% vốn đỉnh (tự động khóa bot khi chạm).<br />
            - Khi khởi động lại ứng dụng, hệ thống sẽ tự động khóa lại về LIVE LOCKED.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-gray-300 mb-1">
              Số vốn Spot tối đa phân bổ cho Bot (USDT):
            </label>
            <input
              type="number"
              step="any"
              min="1"
              value={capital}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 0)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:border-bloomberg-orange"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-gray-300 mb-1">
              Nhập chính xác cụm từ xác nhận:{' '}
              <span className="text-bloomberg-orange font-bold select-all">ENABLE LIVE SPOT</span>
            </label>
            <input
              type="text"
              placeholder="ENABLE LIVE SPOT"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-sm text-gray-100 font-mono uppercase focus:outline-none focus:border-bloomberg-red"
            />
          </div>

          {error && (
            <div className="p-2.5 rounded bg-bloomberg-red/20 border border-bloomberg-red/40 text-xs text-red-300 font-mono">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-bg-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded text-xs font-mono text-gray-400 hover:text-gray-200 transition"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              disabled={loading || phrase !== 'ENABLE LIVE SPOT'}
              className="px-5 py-2 rounded bg-bloomberg-red hover:bg-red-700 disabled:opacity-40 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow-lg shadow-red-900/40 transition"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>{loading ? 'Đang mở khóa...' : 'Xác nhận mở khóa LIVE'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
