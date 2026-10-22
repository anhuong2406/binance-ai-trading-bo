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
  defaultCapital = 5.67,
}) => {
  const [phrase, setPhrase] = useState('');
  const [capitalText, setCapitalText] = useState(defaultCapital ? defaultCapital.toString() : '5.67');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (phrase.trim() !== 'ENABLE LIVE SPOT') {
      setError("Vui lòng nhập chính xác cụm từ: 'ENABLE LIVE SPOT'");
      return;
    }
    const parsedCapital = parseFloat(capitalText.replace(',', '.').trim());
    if (isNaN(parsedCapital) || parsedCapital <= 0) {
      setError('Vốn cấp cho bot phải lớn hơn 0 USDT.');
      return;
    }

    try {
      setLoading(true);
      await onUnlock(phrase.trim(), parsedCapital);
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
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-mono text-gray-300">
                Số vốn Spot tối đa phân bổ cho Bot (USDT):
              </label>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => setCapitalText('5.67')}
                  className="px-2 py-0.5 bg-bg-card hover:bg-bg-border rounded text-[11px] font-mono text-bloomberg-orange border border-bg-border transition cursor-pointer"
                >
                  ⚡ Điền 5.67 USDT
                </button>
              </div>
            </div>
            <input
              type="text"
              inputMode="decimal"
              value={capitalText}
              onChange={(e) => setCapitalText(e.target.value)}
              placeholder="VD: 5.67 hoặc 5,67"
              className="w-full bg-bg-darkest border border-bg-border rounded px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:border-bloomberg-orange"
            />
            <p className="text-[10px] text-gray-400 mt-1 font-mono">
              Hỗ trợ cả dấu chấm (.) và dấu phẩy (,) như 5.67 hoặc 5,67
            </p>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-mono text-gray-300">
                Nhập chính xác cụm từ xác nhận:
              </label>
              <button
                type="button"
                onClick={() => setPhrase('ENABLE LIVE SPOT')}
                className="text-[11px] font-mono text-bloomberg-orange hover:underline cursor-pointer"
              >
                (Bấm để tự điền)
              </button>
            </div>
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
