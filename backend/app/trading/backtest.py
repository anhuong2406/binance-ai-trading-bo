"""
Backtesting and Performance Analytics Engine
Calculates Net Profit, Max Drawdown, Sharpe Ratio, Profit Factor, Win Rate, Expectancy, and Fees.
Avoids look-ahead bias and data snooping.
"""
import math
from typing import List, Dict, Any, Optional
from decimal import Decimal
from app.trading.quant_engine import QuantEngine
from app.trading.strategies.base import BaseStrategy

class BacktestTrade:
    def __init__(
        self,
        symbol: str,
        entry_time: int,
        entry_price: float,
        exit_time: int,
        exit_price: float,
        quantity: float,
        pnl: float,
        pnl_percent: float,
        fee: float,
        reason: str
    ):
        self.symbol = symbol
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.quantity = quantity
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        self.fee = fee
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": round(self.pnl, 4),
            "pnl_percent": round(self.pnl_percent, 2),
            "fee": round(self.fee, 4),
            "reason": self.reason
        }

class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1000.0,
        fee_rate: float = 0.001,  # 0.1% spot fee
        slippage: float = 0.0005   # 0.05% slippage
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage

    def run_backtest(
        self,
        strategy: BaseStrategy,
        symbol: str,
        candles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Runs sequential bar-by-bar backtest without look-ahead bias.
        """
        if len(candles) < 60:
            raise ValueError("Cần tối thiểu 60 nến để thực hiện backtest.")

        capital = self.initial_capital
        equity_curve: List[Dict[str, Any]] = []
        trades: List[BacktestTrade] = []
        
        in_position = False
        pos_entry_price = 0.0
        pos_qty = 0.0
        pos_sl = 0.0
        pos_tp = 0.0
        pos_entry_time = 0

        # We warm up indicators using rolling window
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c["volume"] for c in candles]

        peak_capital = capital
        max_drawdown_usdt = 0.0
        max_drawdown_pct = 0.0

        for i in range(50, len(candles)):
            current_bar = candles[i]
            cur_time = current_bar["time"]
            cur_close = current_bar["close"]
            cur_high = current_bar["high"]
            cur_low = current_bar["low"]

            # Evaluate open position exits
            if in_position:
                # Check SL hit
                if cur_low <= pos_sl:
                    exit_price = pos_sl * (1.0 - self.slippage)
                    gross = (exit_price - pos_entry_price) * pos_qty
                    fee = (pos_entry_price * pos_qty * self.fee_rate) + (exit_price * pos_qty * self.fee_rate)
                    net_pnl = gross - fee
                    pnl_pct = (net_pnl / (pos_entry_price * pos_qty)) * 100
                    capital += (pos_entry_price * pos_qty) + net_pnl

                    trades.append(BacktestTrade(
                        symbol=symbol, entry_time=pos_entry_time, entry_price=pos_entry_price,
                        exit_time=cur_time, exit_price=exit_price, quantity=pos_qty,
                        pnl=net_pnl, pnl_percent=pnl_pct, fee=fee, reason="STOP_LOSS"
                    ))
                    in_position = False

                # Check TP hit
                elif cur_high >= pos_tp:
                    exit_price = pos_tp * (1.0 - self.slippage)
                    gross = (exit_price - pos_entry_price) * pos_qty
                    fee = (pos_entry_price * pos_qty * self.fee_rate) + (exit_price * pos_qty * self.fee_rate)
                    net_pnl = gross - fee
                    pnl_pct = (net_pnl / (pos_entry_price * pos_qty)) * 100
                    capital += (pos_entry_price * pos_qty) + net_pnl

                    trades.append(BacktestTrade(
                        symbol=symbol, entry_time=pos_entry_time, entry_price=pos_entry_price,
                        exit_time=cur_time, exit_price=exit_price, quantity=pos_qty,
                        pnl=net_pnl, pnl_percent=pnl_pct, fee=fee, reason="TAKE_PROFIT"
                    ))
                    in_position = False

            # Check new entry if flat
            if not in_position:
                sub_closes = closes[: i + 1]
                sub_highs = highs[: i + 1]
                sub_lows = lows[: i + 1]
                sub_vols = volumes[: i + 1]
                
                try:
                    ind = QuantEngine.compute_all_indicators(sub_highs, sub_lows, sub_closes, sub_vols)
                    signal = strategy.evaluate(symbol, sub_closes, sub_highs, sub_lows, sub_vols, ind)
                    
                    if signal.action == "BUY" and signal.stop_loss and signal.take_profit:
                        # Position sizing: 20% of capital
                        allocated = capital * 0.20
                        entry_price = cur_close * (1.0 + self.slippage)
                        pos_qty = allocated / entry_price
                        pos_entry_price = entry_price
                        pos_sl = signal.stop_loss
                        pos_tp = signal.take_profit
                        pos_entry_time = cur_time
                        capital -= allocated
                        in_position = True
                except Exception:
                    pass

            # Track equity curve
            cur_equity = capital + ((cur_close * pos_qty) if in_position else 0.0)
            if cur_equity > peak_capital:
                peak_capital = cur_equity
            dd_usdt = peak_capital - cur_equity
            dd_pct = (dd_usdt / peak_capital) * 100.0 if peak_capital > 0 else 0.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
                max_drawdown_usdt = dd_usdt

            equity_curve.append({
                "time": cur_time,
                "equity": round(cur_equity, 2),
                "drawdown": round(dd_pct, 2)
            })

        # Calculate performance statistics
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        total_net_profit = sum(t.pnl for t in trades)
        net_profit_pct = (total_net_profit / self.initial_capital) * 100.0
        total_fees = sum(t.fee for t in trades)

        avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0
        expectancy = ((avg_win * (win_rate / 100)) - (avg_loss * ((100 - win_rate) / 100)))

        # Sharpe ratio approximation
        returns = [t.pnl_percent for t in trades]
        if len(returns) >= 2:
            mean_ret = sum(returns) / len(returns)
            std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns))
            sharpe = (mean_ret / std_ret * math.sqrt(365)) if std_ret > 0 else 0.0
        else:
            sharpe = 0.0

        return {
            "strategy": strategy.name,
            "symbol": symbol,
            "initial_capital": self.initial_capital,
            "final_equity": round(capital, 2),
            "net_profit": round(total_net_profit, 2),
            "net_profit_percent": round(net_profit_pct, 2),
            "max_drawdown_percent": round(max_drawdown_pct, 2),
            "max_drawdown_usdt": round(max_drawdown_usdt, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
            "expectancy": round(expectancy, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "total_fees": round(total_fees, 2),
            "equity_curve": equity_curve[-100:],  # Tail for chart
            "trades": [t.to_dict() for t in trades[-50:]]
        }
