import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  BarChart2,
  Sliders,
  DollarSign,
  Maximize2,
  RefreshCw,
  Compass
} from 'lucide-react';
import { CandleChart } from '../components/CandleChart';
import { CandleData, MarketSnapshot, Position } from '../types';
import { api } from '../services/api';

interface TradingPageProps {
  positions: Position[];
  onClosePosition: (id: number) => void;
}

export const TradingPage: React.FC<TradingPageProps> = ({ positions, onClosePosition }) => {
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [selectedInterval, setSelectedInterval] = useState('15m');
  const [candles, setCandles] = useState<CandleData[]>([]);
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [loading, setLoading] = useState(false);

  const pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT'];
  const intervals = ['5m', '15m', '1h', '4h'];

  const loadData = async () => {
    try {
      setLoading(true);
      const [klineRes, snapRes] = await Promise.all([
        api.getKlines(selectedSymbol, selectedInterval, 120),
        api.getSnapshot(selectedSymbol),
      ]);
      setCandles(klineRes.candles || []);
      setSnapshot(snapRes.snapshot || null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // 10s auto refresh
    return () => clearInterval(interval);
  }, [selectedSymbol, selectedInterval]);

  const activeSymbolPositions = positions.filter(
    (p) => p.symbol === selectedSymbol && p.status === 'OPEN'
  );

  return (
    <div className="space-y-4">
      {/* Top Bar: Pair & Timeframe Selector + 24h Ticker Stats */}
      <div className="bg-bg-darker p-3 rounded-lg border border-bg-border flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {/* Pair Pills */}
          <div className="flex bg-bg-darkest p-1 rounded-lg border border-bg-border">
            {pairs.map((p) => (
              <button
                key={p}
                onClick={() => setSelectedSymbol(p)}
                className={`px-3 py-1 rounded text-xs font-mono font-bold transition ${
                  selectedSymbol === p
                    ? 'bg-bloomberg-orange/20 text-bloomberg-orange border border-bloomberg-orange/40'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Timeframe Pills */}
          <div className="flex bg-bg-darkest p-1 rounded-lg border border-bg-border">
            {intervals.map((tf) => (
              <button
                key={tf}
                onClick={() => setSelectedInterval(tf)}
                className={`px-2.5 py-1 rounded text-xs font-mono transition ${
                  selectedInterval === tf
                    ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-1.5 rounded bg-bg-card hover:bg-gray-700 text-gray-400 border border-bg-border transition"
            title="Làm mới dữ liệu"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* 24h Snapshot stats */}
        {snapshot && (
          <div className="flex items-center gap-4 text-xs font-mono text-gray-300">
            <div>
              <span className="text-gray-500 text-[10px] block">Giá mới nhất</span>
              <span className="text-base font-bold text-gray-100">${snapshot.lastPrice}</span>
            </div>
            <div>
              <span className="text-gray-500 text-[10px] block">Thay đổi 24h</span>
              <span
                className={`font-bold ${
                  snapshot.priceChangePercent >= 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'
                }`}
              >
                {snapshot.priceChangePercent >= 0 ? '+' : ''}
                {snapshot.priceChangePercent.toFixed(2)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500 text-[10px] block">Cao / Thấp 24h</span>
              <span>
                ${snapshot.highPrice} / ${snapshot.lowPrice}
              </span>
            </div>
            <div>
              <span className="text-gray-500 text-[10px] block">Spread</span>
              <span className="text-bloomberg-cyan">
                ${snapshot.spread.toFixed(2)} ({snapshot.spreadPercent.toFixed(3)}%)
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Main Candlestick Chart */}
      <div className="w-full h-[450px]">
        <CandleChart candles={candles} symbol={selectedSymbol} />
      </div>

      {/* Active Positions for this symbol */}
      {activeSymbolPositions.length > 0 && (
        <div className="bg-bg-darker p-4 rounded-lg border border-bg-border">
          <h3 className="font-mono text-xs font-bold text-gray-200 uppercase mb-3 flex items-center gap-2">
            <Compass className="w-4 h-4 text-bloomberg-green" />
            Vị Thế Đang Nắm Giữ Cho {selectedSymbol}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
            {activeSymbolPositions.map((p) => (
              <div key={p.id} className="p-3 bg-bg-card rounded border border-bg-border">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold text-gray-200">{p.symbol} (Spot)</span>
                  <button
                    onClick={() => onClosePosition(p.id)}
                    className="px-2 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-500/40 text-[10px]"
                  >
                    Đóng lệnh
                  </button>
                </div>
                <div className="text-gray-400 text-[11px] space-y-0.5">
                  <div>Khối lượng: {p.amount}</div>
                  <div>Giá vào: ${p.entry_price}</div>
                  <div>Giá hiện tại: ${p.current_price}</div>
                  <div className="text-bloomberg-red">Stop Loss: ${p.stop_loss}</div>
                  <div className="text-bloomberg-green">Take Profit: ${p.take_profit}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
