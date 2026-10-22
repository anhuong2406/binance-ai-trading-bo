"""
Decision Engine - Multi-Agent Trading Pipeline Orchestrator
Coordinates: Market Data -> Quant Engine -> MTF Alignment -> Gemini Analyst -> GPT-6 Luna Reviewer
-> Consensus -> Risk Engine -> Execution / Simulator
"""
import time
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
from app.database.models import AIAnalysisLog, RiskEvaluation, Position
from app.database.session import record_audit
from app.config.settings import settings
from app.skills import skill_selector, skill_audit

# HTF (Higher Timeframe) for multi-timeframe confirmation
HTF_TIMEFRAME = "1h"
HTF_CANDLE_LIMIT = 60  # 60 x 1h = 60 hours of context

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

        # Step 1: Market Data (15m + 1h for Multi-Timeframe)
        try:
            candles = await self.market_data.get_validated_candles(symbol, interval=timeframe, limit=100)
            # Fetch Higher Timeframe candles (1h) concurrently for MTF alignment
            try:
                candles_1h = await self.market_data.get_validated_candles(symbol, interval="1h", limit=60)
            except Exception:
                candles_1h = []
            snapshot = await self.market_data.get_market_snapshot(symbol)
            pipeline_log["steps"]["market_data"] = {
                "status": "PASS",
                "last_price": snapshot["lastPrice"],
                "spread_percent": snapshot["spreadPercent"],
                "candles_count": len(candles),
                "candles_1h_count": len(candles_1h)
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

        # Step 2.5: Multi-Timeframe Alignment (1h vs 15m)
        mtf_alignment: Dict[str, Any] = {}
        try:
            if candles_1h and len(candles_1h) >= 30:
                h_closes = [c.close for c in candles_1h]
                h_highs  = [c.high  for c in candles_1h]
                h_lows   = [c.low   for c in candles_1h]
                h_vols   = [c.volume for c in candles_1h]
                mtf_alignment = QuantEngine.compute_mtf_alignment(
                    htf_highs=h_highs, htf_lows=h_lows, htf_closes=h_closes, htf_volumes=h_vols,
                    ltf_highs=highs,   ltf_lows=lows,   ltf_closes=closes,   ltf_volumes=volumes
                )
                pipeline_log["steps"]["mtf_alignment"] = {
                    "status": "PASS",
                    "alignment": mtf_alignment["alignment"],
                    "bias": mtf_alignment["bias"],
                    "allow_buy": mtf_alignment["allow_buy"],
                    "alignment_strength": mtf_alignment["alignment_strength"],
                    "note": mtf_alignment["note"],
                    "htf_1h": {
                        "bullish": mtf_alignment["htf_trend"]["bullish"],
                        "bearish": mtf_alignment["htf_trend"]["bearish"],
                        "ema9":    round(mtf_alignment["htf_trend"]["ema9"] or 0, 6),
                        "ema21":   round(mtf_alignment["htf_trend"]["ema21"] or 0, 6),
                        "ema50":   round(mtf_alignment["htf_trend"]["ema50"] or 0, 6),
                        "rsi":     round(mtf_alignment["htf_trend"]["rsi"] or 0, 1),
                        "adx":     round(mtf_alignment["htf_trend"]["adx"] or 0, 1),
                    },
                    "ltf_15m": {
                        "bullish": mtf_alignment["ltf_trend"]["bullish"],
                        "bearish": mtf_alignment["ltf_trend"]["bearish"],
                        "ema9":    round(mtf_alignment["ltf_trend"]["ema9"] or 0, 6),
                        "ema21":   round(mtf_alignment["ltf_trend"]["ema21"] or 0, 6),
                        "ema50":   round(mtf_alignment["ltf_trend"]["ema50"] or 0, 6),
                        "rsi":     round(mtf_alignment["ltf_trend"]["rsi"] or 0, 1),
                        "adx":     round(mtf_alignment["ltf_trend"]["adx"] or 0, 1),
                    }
                }
            else:
                mtf_alignment = {"alignment": "UNKNOWN", "bias": "HOLD", "allow_buy": False, "note": "Không đủ nến 1h để tính MTF."}
                pipeline_log["steps"]["mtf_alignment"] = {"status": "SKIP", "note": "Không đủ dữ liệu 1h"}
        except Exception as e:
            mtf_alignment = {"alignment": "ERROR", "bias": "HOLD", "allow_buy": False, "note": str(e)}
            pipeline_log["steps"]["mtf_alignment"] = {"status": "WARN", "error": str(e)}

        # Format recent candles summary for AI prompt
        recent_summary = [
            {"time": c.open_time, "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles[-10:]
        ]

        # Step 2.5: Trading Skills Engine (Claude Trading Skills Integration)
        t_skills_start = time.time()
        order_book_data = None
        try:
            order_book_data = await self.binance_client.get_order_book(symbol, limit=10)
        except Exception:
            pass

        quant_skills = skill_selector.execute_and_bundle_quant_skills(
            candles=candles,
            order_book=order_book_data,
            allocated_capital=settings.BOT_ALLOCATED_CAPITAL_USDT
        )
        if mtf_alignment and mtf_alignment.get("alignment") != "UNKNOWN":
            quant_skills["multi_timeframe_alignment"] = mtf_alignment

        if "market_session" in indicators.get("latest", {}):
            quant_skills["market_session"] = indicators["latest"]["market_session"]

        if "stoch_rsi_k" in indicators.get("latest", {}):
            quant_skills["stoch_rsi"] = {
                "k": indicators["latest"]["stoch_rsi_k"],
                "d": indicators["latest"]["stoch_rsi_d"]
            }

        gemini_skills_prompt = skill_selector.get_gemini_skills_prompt(quant_skills)
        gpt_skills_prompt = skill_selector.get_gpt_skills_prompt(quant_skills)
        skill_audit.set_last_cycle_skills(list(quant_skills.keys()))

        pipeline_log["steps"]["trading_skills"] = {
            "status": "PASS",
            "skills_applied": list(quant_skills.keys()),
            "duration_ms": round((time.time() - t_skills_start) * 1000, 2),
            "data": quant_skills
        }

        # Step 2.8: Quant Opportunity Pre-Filter (Radar Cảnh Báo Sơ Tuyển Cơ Hội)
        # Saves 85-90% AI token costs by only invoking LLMs when technical setups exist
        has_open_pos = False
        try:
            pos_stmt = select(Position).where(
                Position.symbol == symbol,
                Position.status == "OPEN",
                Position.mode == mode
            )
            has_open_pos = (await session.scalar(pos_stmt)) is not None
        except Exception:
            pass

        opp_trigger = QuantEngine.evaluate_opportunity_trigger(
            indicators=indicators,
            candles=candles,
            has_open_position=has_open_pos,
            mtf_alignment=mtf_alignment
        )

        pipeline_log["steps"]["quant_pre_filter"] = {
            "status": "TRIGGERED" if opp_trigger["has_opportunity"] else "HOLD",
            "has_opportunity": opp_trigger["has_opportunity"],
            "triggers": opp_trigger.get("reasons", []),
            "summary": opp_trigger.get("summary", opp_trigger.get("reason", ""))
        }

        # If no opportunity exists and pre-filter is enabled: skip calling Gemini and Luna!
        if settings.QUANT_PREFILTER_ENABLED and not opp_trigger["has_opportunity"]:
            pipeline_log["steps"]["gemini_analyst"] = {
                "status": "SKIPPED",
                "output": {"action": "HOLD", "reasoning": opp_trigger["reason"]},
                "note": "Quant Pre-Filter: Tiết kiệm ~4,000 input tokens"
            }
            pipeline_log["steps"]["gpt_reviewer"] = {
                "status": "SKIPPED",
                "output": {"decision": "STANDBY", "reason": "Tiết kiệm ~3,000 tokens thẩm định"},
                "note": "Quant Pre-Filter: Tiết kiệm token"
            }
            pipeline_log["steps"]["consensus"] = {
                "status": "PASS",
                "action": "HOLD",
                "approved": False,
                "reason": opp_trigger["reason"]
            }
            pipeline_log["steps"]["risk_engine"] = {
                "status": "PASS",
                "passed": True,
                "reasons": ["Đứng ngoài thị trường bảo toàn vốn (Radar lọc cơ hội)."],
                "calculated_risk_percent": 0.0
            }
            pipeline_log["steps"]["execution"] = {
                "status": "PASS",
                "mode": mode,
                "result": {"status": "STANDBY", "action": "HOLD", "message": "Radar Định Lượng duy trì quan sát 0 token."}
            }
            return {"status": "HOLD", "reason": opp_trigger["reason"], "pipeline": pipeline_log}

        # If opportunity detected: pass trigger reasons to Gemini
        if opp_trigger.get("reasons"):
            quant_skills["opportunity_triggers"] = opp_trigger["reasons"]

        # Step 3: Gemini Market Analyst (with Trading Skills Context)
        try:
            gemini_out, gemini_ms, gemini_usage = await self.gemini_analyst.analyze(
                symbol=symbol,
                timeframe=timeframe,
                market_snapshot=snapshot,
                indicators=indicators,
                recent_candles_summary=recent_summary,
                skills_context=quant_skills,
                skills_prompt=gemini_skills_prompt
            )
            pipeline_log["steps"]["gemini_analyst"] = {
                "status": "PASS",
                "latency_ms": gemini_ms,
                "output": gemini_out
            }
        except Exception as e:
            pipeline_log["steps"]["gemini_analyst"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": f"Lỗi Gemini Analyst: {str(e)}", "pipeline": pipeline_log}

        # Step 4: GPT-6 Luna Independent Reviewer (with Risk Skills Context)
        try:
            gpt_out, gpt_ms, gpt_usage = await self.gpt_reviewer.review(
                symbol=symbol,
                gemini_proposal=gemini_out,
                market_snapshot=snapshot,
                indicators=indicators,
                skills_context=quant_skills,
                skills_prompt=gpt_skills_prompt
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

        # Multi-Timeframe Hard Safety Guard
        if consensus.approved and consensus.action == "BUY" and mtf_alignment.get("allow_buy") is False:
            consensus.approved = False
            consensus.action = "HOLD"
            consensus.reason = (
                f"Multi-Timeframe Veto: Khung 1h đang {mtf_alignment.get('alignment', 'COUNTER_TREND')} "
                f"({mtf_alignment.get('note', '')}). Tự động khóa lệnh BUY ngược xu hướng lớn để bảo vệ vốn."
            )

        # Market Session Guard (Dead Zone Low Liquidity)
        session_info = indicators.get("latest", {}).get("market_session", {})
        vol_ratio = indicators.get("latest", {}).get("volume_ratio", 1.0)
        if consensus.approved and consensus.action == "BUY" and session_info.get("is_dead_zone") and vol_ratio < 1.3:
            consensus.approved = False
            consensus.action = "HOLD"
            consensus.reason = (
                f"Session Guard Veto: Đang trong {session_info.get('session')} ({session_info.get('vn_time')}) "
                f"thanh khoản mỏng và volume chưa bùng nổ (Volume Ratio = {vol_ratio:.2f}x < 1.3x). "
                f"Tự động giữ trạng thái HOLD để tránh bẫy râu quét ban đêm."
            )

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
            pipeline_log["steps"]["risk_engine"] = {
                "status": "PASS",
                "passed": True,
                "reasons": ["Đứng ngoài thị trường bảo toàn vốn (Trạng thái HOLD). Không phát sinh rủi ro vị thế."],
                "calculated_risk_percent": 0.0
            }
            pipeline_log["steps"]["execution"] = {
                "status": "PASS",
                "mode": mode,
                "result": {"status": "STANDBY", "action": "HOLD", "message": "Giữ trạng thái quan sát, không mở vị thế bừa bãi."}
            }
            return {"status": "HOLD", "reason": consensus.reason, "pipeline": pipeline_log}

        # Step 6: Risk Engine
        # Query account balances
        allocated_capital = settings.BOT_ALLOCATED_CAPITAL_USDT
        avail_usdt = allocated_capital  # Default in paper

        if mode in ("TESTNET", "LIVE"):
            try:
                acc_info = await self.account_manager.get_spot_balances()
                avail_usdt = acc_info["usdtFree"]
                if avail_usdt < allocated_capital:
                    allocated_capital = avail_usdt
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
