"""
Decision Engine - Multi-Agent Trading Pipeline Orchestrator
Coordinates: Market Data -> Quant Engine -> Gemini Analyst -> GPT-6 Luna Reviewer
-> Consensus -> Risk Engine -> Execution / Simulator
"""
import time
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.binance.client import BinanceSpotClient
from app.binance.market_data import MarketDataEngine
from app.binance.account import AccountManager
from app.binance.execution import ExecutionEngine
from app.trading.quant_engine import QuantEngine
from app.trading.risk_engine import risk_engine, RiskCheckResult
from app.trading.simulator import paper_simulator
from app.trading.position_manager import PositionManager
from app.ai.gateway import ai_gateway
from app.ai.gemini_analyst import GeminiMarketAnalyst
from app.ai.gpt_reviewer import GPTIndependentReviewer
from app.ai.consensus import DecisionConsensus, ConsensusResult
from app.database.models import AIAnalysisLog, RiskEvaluation
from app.database.session import record_audit
from app.config.settings import settings

class DecisionEngine:
    def __init__(self, binance_client: BinanceSpotClient):
        self.binance_client = binance_client
        self.market_data = MarketDataEngine(binance_client)
        self.account_manager = AccountManager(binance_client)
        self.execution = ExecutionEngine(binance_client)
        self.gemini_analyst = GeminiMarketAnalyst(ai_gateway)
        self.gpt_reviewer = GPTIndependentReviewer(ai_gateway)

    async def execute_cycle(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str = "15m",
        mode: str = "PAPER"
    ) -> Dict[str, Any]:
        """
        Runs one full multi-agent decision cycle for a trading pair.
        Returns detailed step-by-step pipeline report.
        """
        cycle_start = time.time()
        pipeline_log: Dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode,
            "timestamp": int(cycle_start * 1000),
            "steps": {}
        }

        # Step 1: Market Data
        try:
            candles = await self.market_data.get_validated_candles(symbol, interval=timeframe, limit=100)
            snapshot = await self.market_data.get_market_snapshot(symbol)
            pipeline_log["steps"]["market_data"] = {
                "status": "PASS",
                "last_price": snapshot["lastPrice"],
                "spread_percent": snapshot["spreadPercent"],
                "candles_count": len(candles)
            }
        except Exception as e:
            pipeline_log["steps"]["market_data"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": f"Lỗi Market Data: {str(e)}", "pipeline": pipeline_log}

        # Step 2: Quant Engine
        try:
            closes = [c.close for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            volumes = [c.volume for c in candles]
            indicators = QuantEngine.compute_all_indicators(highs, lows, closes, volumes)
            pipeline_log["steps"]["quant_engine"] = {
                "status": "PASS",
                "indicators": indicators["latest"]
            }
        except Exception as e:
            pipeline_log["steps"]["quant_engine"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": f"Lỗi Quant Engine: {str(e)}", "pipeline": pipeline_log}

        # Format recent candles summary for AI prompt
        recent_summary = [
            {"time": c.open_time, "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles[-10:]
        ]

        # Step 3: Gemini Market Analyst
        try:
            gemini_out, gemini_ms, gemini_usage = await self.gemini_analyst.analyze(
                symbol=symbol,
                timeframe=timeframe,
                market_snapshot=snapshot,
                indicators=indicators,
                recent_candles_summary=recent_summary
            )
            pipeline_log["steps"]["gemini_analyst"] = {
                "status": "PASS",
                "latency_ms": gemini_ms,
                "output": gemini_out
            }
        except Exception as e:
            pipeline_log["steps"]["gemini_analyst"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": f"Lỗi Gemini Analyst: {str(e)}", "pipeline": pipeline_log}

        # Step 4: GPT-6 Luna Independent Reviewer (Luôn luôn thẩm định độc lập)
        try:
            gpt_out, gpt_ms, gpt_usage = await self.gpt_reviewer.review(
                symbol=symbol,
                gemini_proposal=gemini_out,
                market_snapshot=snapshot,
                indicators=indicators
            )
            pipeline_log["steps"]["gpt_reviewer"] = {
                "status": "PASS",
                "latency_ms": gpt_ms,
                "output": gpt_out
            }
        except Exception as e:
            pipeline_log["steps"]["gpt_reviewer"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": f"Lỗi GPT-6 Luna Reviewer: {str(e)}", "pipeline": pipeline_log}

        # Step 5: Decision Consensus
        consensus = DecisionConsensus.evaluate_consensus(symbol, gemini_out, gpt_out)
        pipeline_log["steps"]["consensus"] = {
            "status": "PASS" if consensus.approved else "DISAGREED",
            "action": consensus.action,
            "approved": consensus.approved,
            "reason": consensus.reason
        }

        # Save AI Log
        total_tokens = gemini_usage.get("total_tokens", 0) + gpt_usage.get("total_tokens", 0)
        ai_log = AIAnalysisLog(
            symbol=symbol,
            timeframe=timeframe,
            gemini_output=json.dumps(gemini_out, ensure_ascii=False),
            gpt_output=json.dumps(gpt_out, ensure_ascii=False),
            consensus_action=consensus.action,
            execution_approved=consensus.approved,
            rejection_reason=None if consensus.approved else consensus.reason,
            gemini_latency_ms=gemini_ms,
            gpt_latency_ms=gpt_ms,
            total_tokens=total_tokens
        )
        session.add(ai_log)
        await session.commit()

        if not consensus.approved:
            return {"status": "HOLD", "reason": consensus.reason, "pipeline": pipeline_log}

        # Step 6: Risk Engine
        # Query account balances
        allocated_capital = settings.BOT_ALLOCATED_CAPITAL_USDT
        avail_usdt = allocated_capital  # Default in paper

        if mode in ("TESTNET", "LIVE"):
            try:
                acc_info = await self.account_manager.get_spot_balances()
                avail_usdt = acc_info["usdtFree"]
            except Exception as e:
                pipeline_log["steps"]["risk_engine"] = {"status": "FAIL", "error": f"Không thể đọc số dư sàn: {str(e)}"}
                return {"status": "ABORTED", "reason": "Lỗi kết nối tài khoản Binance", "pipeline": pipeline_log}

        # Exchange filters
        try:
            filters = await self.binance_client.get_symbol_filters(symbol)
        except Exception:
            filters = {
                "stepSize": Decimal("0.0001"),
                "minQty": Decimal("0.0001"),
                "minNotional": Decimal("5.0"),
                "tickSize": Decimal("0.01"),
                "minPrice": Decimal("0.01"),
                "maxPrice": Decimal("1000000")
            }

        risk_check: RiskCheckResult = await risk_engine.evaluate_trade(
            session=session,
            symbol=symbol,
            action=consensus.action,
            entry_price=consensus.entry_price or snapshot["lastPrice"],
            stop_loss=consensus.stop_loss,
            take_profit=consensus.take_profit,
            allocated_capital=allocated_capital,
            available_usdt=avail_usdt,
            symbol_filters=filters,
            mode=mode
        )

        pipeline_log["steps"]["risk_engine"] = risk_check.to_dict()

        # Log risk evaluation to DB
        risk_eval = RiskEvaluation(
            symbol=symbol,
            action=consensus.action,
            proposed_entry=consensus.entry_price,
            proposed_sl=consensus.stop_loss,
            proposed_tp=consensus.take_profit,
            passed=risk_check.passed,
            rejection_reasons=json.dumps(risk_check.reasons, ensure_ascii=False),
            calculated_risk_percent=risk_check.calculated_risk_percent,
            calculated_position_size=float(risk_check.notional_value)
        )
        session.add(risk_eval)
        await session.commit()

        if not risk_check.passed:
            return {
                "status": "RISK_REJECTED",
                "reasons": risk_check.reasons,
                "pipeline": pipeline_log
            }

        # Step 7: Execution Engine / Paper Simulator
        market_price = Decimal(str(snapshot["lastPrice"]))
        sl_dec = Decimal(str(consensus.stop_loss)) if consensus.stop_loss else None
        tp_dec = Decimal(str(consensus.take_profit)) if consensus.take_profit else None

        if mode == "PAPER":
            exec_res = await paper_simulator.execute_paper_order(
                session=session,
                symbol=symbol,
                side=consensus.action,
                quantity=risk_check.allowed_quantity,
                market_price=market_price,
                stop_loss=sl_dec,
                take_profit=tp_dec
            )
            pipeline_log["steps"]["execution"] = {
                "mode": "PAPER",
                "result": exec_res
            }
        else:
            # LIVE or TESTNET
            exec_res = await self.execution.execute_spot_order(
                symbol=symbol,
                side=consensus.action,
                order_type="MARKET",
                quantity=risk_check.allowed_quantity
            )
            pipeline_log["steps"]["execution"] = {
                "mode": mode,
                "result": exec_res
            }

        return {
            "status": "EXECUTED",
            "action": consensus.action,
            "symbol": symbol,
            "pipeline": pipeline_log
        }
