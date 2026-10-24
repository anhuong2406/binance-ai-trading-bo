import React from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Layers,
  Percent,
  CheckCircle,
  AlertOctagon,
  ArrowUpRight,
  ArrowDownRight,
  XCircle,
  Coins
} from 'lucide-react';
import { SpotAccount, Position, SystemStatus } from '../types';

interface OverviewPageProps {
  status: SystemStatus | null;
  account: SpotAccount | null;
  positions: Position[];
  stats: any;
  onClosePosition: (id: number) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  status,
  account,
  positions,
  stats,
  onClosePosition,
}) => {
  const openPositions = positions.filter((p) => p.status === 'OPEN');
  const closedPositions = positions.filter((p) => p.status === 'CLOSED').slice(0, 5);

  const totalEquity = account?.totalEquityUsdt || 0.0;
  const usdtFree = account?.usdtFree || 0.0;
  const allocated = status?.allocated_capital || 100.0;
  const realizedPnl = stats?.total_realized_pnl || 0.0;
  const unrealizedPnl = stats?.total_unrealized_pnl || 0.0;
  const winRate = stats?.win_rate || 0.0;
  const totalTrades = stats?.total_trades || 0;

  return (
    <div className="space-y-4">
      {/* Standby Token-Saving Notice */}
      {status?.standby_reason && (
        <div className="bg-amber-950/40 border border-amber-500/40 rounded-lg p-3 flex items-center gap-2.5 text-xs font-mono text-amber-200 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
          <span>{status.standby_reason}</span>
        </div>
      )}

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Total Spot Value */}
        <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border shadow-sm">
          <div className="flex items-center justify-between text-gray-400 text-xs font-mono mb-1">
            <span>Tổng Tài Sản Spot</span>
            <Wallet className="w-4 h-4 text-bloomberg-orange" />
          </div>
          <div className="font-mono text-xl font-bold text-gray-100">
            ${totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] font-mono text-gray-400 mt-1 flex justify-between">
            <span>Khả dụng: ${usdtFree.toFixed(2)} USDT</span>
          </div>
        </div>

        {/* Bot Allocated Capital */}
        <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border shadow-sm">
          <div className="flex items-center justify-between text-gray-400 text-xs font-mono mb-1">
            <span>Vốn Cấp Cho Bot</span>
            <Layers className="w-4 h-4 text-bloomberg-cyan" />
          </div>
          <div className="font-mono text-xl font-bold text-cyan-300">
            ${allocated.toFixed(2)} USDT
          </div>
          <div className="text-[11px] font-mono text-gray-400 mt-1">
            Chế độ: <span className="font-bold text-gray-200">{status?.mode}</span>
          </div>
        </div>

        {/* Realized PnL */}
        <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border shadow-sm">
          <div className="flex items-center justify-between text-gray-400 text-xs font-mono mb-1">
            <span>PnL Thực Nhận</span>
            {realizedPnl >= 0 ? (
              <TrendingUp className="w-4 h-4 text-bloomberg-green" />
            ) : (
              <TrendingDown className="w-4 h-4 text-bloomberg-red" />
            )}
          </div>
          <div
            className={`font-mono text-xl font-bold ${
              realizedPnl >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'
            }`}
          >
            {realizedPnl >= 0 ? '+' : ''}
            ${realizedPnl.toFixed(2)}
          </div>
          <div className="text-[11px] font-mono text-gray-400 mt-1">
            Chưa thực nhận: ${unrealizedPnl.toFixed(2)}
          </div>
        </div>

        {/* Win Rate & Trades */}
        <div className="bg-bg-darker p-3.5 rounded-lg border border-bg-border shadow-sm">
          <div className="flex items-center justify-between text-gray-400 text-xs font-mono mb-1">
            <span>Tỷ Lệ Thắng (Win Rate)</span>
            <Percent className="w-4 h-4 text-purple-400" />
          </div>
          <div className="font-mono text-xl font-bold text-gray-100">
            {winRate.toFixed(1)}%
          </div>
          <div className="text-[11px] font-mono text-gray-400 mt-1">
            Tổng lệnh đã đóng: {totalTrades}
          </div>
        </div>
      </div>

      {/* Main Grid: Open Positions & Balances */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Open Positions List (2 cols) */}
        <div className="lg:col-span-2 bg-bg-darker rounded-lg border border-bg-border p-4">
          <div className="flex items-center justify-between mb-3 border-b border-bg-border pb-2">
            <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-gray-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-bloomberg-green" />
              Vị Thế Spot Đang Mở ({openPositions.length}/2)
            </h3>
            <span className="text-xs font-mono text-gray-500">Giới hạn tối đa 2 vị thế</span>
          </div>

          {openPositions.length === 0 ? (
            <div className="py-12 text-center text-gray-500 font-mono text-xs">
              Hiện không có vị thế mở nào. Bot đang quét tín hiệu thị trường.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-bg-border text-gray-400 text-[11px]">
                    <th className="pb-2">Cặp</th>
                    <th className="pb-2">Khối lượng</th>
                    <th className="pb-2">Giá vào</th>
                    <th className="pb-2">Giá hiện tại</th>
                    <th className="pb-2">Stop Loss</th>
                    <th className="pb-2">Take Profit</th>
                    <th className="pb-2">PnL</th>
                    <th className="pb-2 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-bg-border/50">
                  {openPositions.map((pos) => {
                    const pnlVal = pos.unrealized_pnl || 0.0;
                    const pnlPct =
                      pos.entry_price > 0
                        ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
                        : 0.0;
                    return (
                      <tr key={pos.id} className="hover:bg-bg-card/40 transition">
                        <td className="py-2.5 font-bold text-gray-100">{pos.symbol}</td>
                        <td className="py-2.5 text-gray-300">{pos.amount}</td>
                        <td className="py-2.5 text-gray-300">${pos.entry_price}</td>
                        <td className="py-2.5 font-bold text-gray-100">${pos.current_price}</td>
                        <td className="py-2.5 text-bloomberg-red">${pos.stop_loss || 'None'}</td>
                        <td className="py-2.5 text-bloomberg-green">${pos.take_profit || 'None'}</td>
                        <td className="py-2.5">
                          <span
                            className={`font-bold ${
                              pnlVal >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'
                            }`}
                          >
                            {pnlVal >= 0 ? '+' : ''}${pnlVal.toFixed(2)} ({pnlPct.toFixed(2)}%)
                          </span>
                        </td>
                        <td className="py-2.5 text-right">
                          <button
                            onClick={() => onClosePosition(pos.id)}
                            className="px-2.5 py-1 rounded bg-bg-card hover:bg-red-900/40 text-red-300 border border-red-500/30 text-[11px] transition"
                          >
                            Đóng lệnh
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Spot Account Holdings (1 col) */}
        <div className="bg-bg-darker rounded-lg border border-bg-border p-4">
          <div className="flex items-center justify-between mb-3 border-b border-bg-border pb-2">
            <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-gray-200 flex items-center gap-2">
              <Coins className="w-4 h-4 text-bloomberg-orange" />
              Số Dư Spot Binance
            </h3>
            <span className="text-[11px] font-mono text-gray-400">Read-Only</span>
          </div>

          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {account?.balances?.map((b) => (
              <div
                key={b.asset}
                className="flex items-center justify-between p-2 rounded bg-bg-card/50 border border-bg-border text-xs font-mono"
              >
                <div>
                  <span className="font-bold text-gray-200">{b.asset}</span>
                  <div className="text-[10px] text-gray-500">Khả dụng: {b.free}</div>
                </div>
                <div className="text-right">
                  <span className="text-gray-200">${b.estimatedUsdt.toFixed(2)}</span>
                  {b.locked > 0 && (
                    <div className="text-[10px] text-amber-500/80">Khóa: {b.locked}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
