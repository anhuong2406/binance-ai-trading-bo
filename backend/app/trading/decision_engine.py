"""
Decision Engine - Multi-Agent Trading Pipeline Orchestrator
Coordinates: Market Data -> Quant Engine -> MTF Alignment -> Gemini Opportunity Analyst
-> GPT-6 Luna Complementary Review -> Risk Engine -> Execution / Simulator
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
from app.database.models import AIAnalysisLog, RiskEvaluation, Position, Order
from app.database.session import record_audit
from app.config.settings import settings
from app.skills import skill_selector, skill_audit
from app.trading.trade_memory import TradeMemoryService

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

        # Step 1: Market Data (selected lower timeframe + 1h for Multi-Timeframe)
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

        # Step 2.5: Multi-Timeframe Alignment (1h vs configured lower timeframe)
        mtf_alignment: Dict[str, Any] = {}
        try:
            if candles_1h and len(candles_1h) >= 30:
                h_closes = [c.close for c in candles_1h]
                h_highs  = [c.high  for c in candles_1h]
                h_lows   = [c.low   for c in candles_1h]
                h_vols   = [c.volume for c in candles_1h]
                mtf_alignment = QuantEngine.compute_mtf_alignment(
                    htf_highs=h_highs, htf_lows=h_lows, htf_closes=h_closes, htf_volumes=h_vols,
                    ltf_highs=highs,   ltf_lows=lows,   ltf_closes=closes,   ltf_volumes=volumes,
                    scalping_mode=settings.SCALPING_MODE_ENABLED
                )
                if settings.SCALPING_MODE_ENABLED and mtf_alignment.get("alignment") in ("NEUTRAL", "COUNTER_TREND"):
                    reversal_confirmed = QuantEngine.has_confirmed_scalping_reversal(indicators, candles)
                    mtf_alignment["neutral_reversal_confirmed"] = reversal_confirmed
                    if reversal_confirmed:
                        mtf_alignment["allow_buy"] = True
                        mtf_alignment["bias"] = "BUY"
                        mtf_alignment["note"] = (
                            f"Scalping {timeframe}: Đã xác nhận nhịp nảy kỹ thuật / hồi sớm (giá lấy lại EMA9 hoặc bật lên từ Stoch/BB quá bán), "
                            "cho phép mở vị thế lướt sóng ngắn chốt lời nhanh."
                        )
                    else:
                        mtf_alignment["allow_buy"] = False
                        mtf_alignment["bias"] = "HOLD"
                        mtf_alignment["note"] = (
                            f"Scalping {timeframe}: Đang chờ tín hiệu nảy kỹ thuật xác nhận (chạm cận dưới BB, Stoch/RSI quá bán hoặc nến đảo chiều)."
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
                    "ltf": {
                        "timeframe": timeframe,
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

        if settings.SCALPING_MODE_ENABLED:
            quant_skills["scalping_profile"] = {
                "enabled": True,
                "reference_take_profit_percent": settings.TARGET_TAKE_PROFIT_PERCENT,
                "max_stop_loss_percent": settings.TARGET_STOP_LOSS_PERCENT,
                "minimum_net_risk_reward": settings.SCALPING_MIN_NET_RISK_REWARD,
                "strategy_note": (
                    "TP là mục tiêu tham khảo, phải theo vùng cản/ATR và chi phí thực tế; "
                    f"SL không vượt {settings.TARGET_STOP_LOSS_PERCENT}%, R:R ròng tối thiểu "
                    f"{settings.SCALPING_MIN_NET_RISK_REWARD}:1. Không đạt thì HOLD."
                )
            }

        gemini_skills_prompt = skill_selector.get_gemini_skills_prompt(quant_skills)
        gpt_skills_prompt = skill_selector.get_gpt_skills_prompt(quant_skills)
        skill_audit.set_last_cycle_skills(list(quant_skills.keys()))

        # Trade Memory & Lessons Learned Injection
        trade_lessons_prompt = ""
        try:
            trade_lessons_prompt = await TradeMemoryService.format_lessons_for_ai_prompt(
                session=session, symbol=symbol, mode=mode
            )
        except Exception:
            pass

        if trade_lessons_prompt:
            gemini_skills_prompt = f"{gemini_skills_prompt}\n\n{trade_lessons_prompt}" if gemini_skills_prompt else trade_lessons_prompt
            gpt_skills_prompt = f"{gpt_skills_prompt}\n\n{trade_lessons_prompt}" if gpt_skills_prompt else trade_lessons_prompt
            pipeline_log["steps"]["trade_memory"] = {
                "status": "APPLIED",
                "lessons_injected": True
            }

        pipeline_log["steps"]["trading_skills"] = {
            "status": "PASS",
            "skills_applied": list(quant_skills.keys()),
            "duration_ms": round((time.time() - t_skills_start) * 1000, 2),
            "data": quant_skills
        }

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

        # Step 4: Reviewer step (Single AI Mode bypasses GPT-6 Luna entirely to save 50% token)
        if settings.AI_SINGLE_MODEL_MODE:
            gpt_out = {
                "decision": "BYPASS",
                "reason": "Single AI Mode: Đã bỏ qua GPT-6 Luna để tiết kiệm 100% chi phí token thẩm định và giảm độ trễ.",
                "technical_alignment": True,
                "risk_reward_acceptable": True,
                "spread_and_fee_acceptable": True,
                "volatility_acceptable": True,
                "stop_loss_reasonable": True
            }
            gpt_ms = 0
            gpt_usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            pipeline_log["steps"]["gpt_reviewer"] = {
                "status": "SKIPPED",
                "latency_ms": 0,
                "output": gpt_out,
                "note": "Single AI Mode: Tiết kiệm token, chỉ sử dụng duy nhất Gemini 3.8 Flash High"
            }
            # Step 5: Single Model Consensus directly from Gemini 3.8 Flash High
            consensus = DecisionConsensus.evaluate_single_analyst(symbol, gemini_out)
        else:
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

            # Step 5: Analyst proposal plus reviewer verdict; the Risk Engine stays authoritative.
            consensus = DecisionConsensus.evaluate_consensus(symbol, gemini_out, gpt_out)

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
            "status": (
                "PASS" if consensus.approved
                else "STANDBY" if consensus.gemini_action == "HOLD"
                else "BLOCKED"
            ),
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
        # Refresh the executable quote after AI analysis; scalping levels and
        # sizing must not use the potentially stale pre-analysis snapshot.
        try:
            snapshot = await self.market_data.get_market_snapshot(symbol)
            pipeline_log["steps"]["execution_quote"] = {
                "status": "PASS",
                "best_bid": snapshot["bestBid"],
                "best_ask": snapshot["bestAsk"],
                "spread_percent": snapshot["spreadPercent"],
                "timestamp": snapshot["timestamp"]
            }
        except Exception as e:
            pipeline_log["steps"]["execution_quote"] = {"status": "FAIL", "error": str(e)}
            return {"status": "ABORTED", "reason": "Không thể làm mới giá trước khi đặt lệnh.", "pipeline": pipeline_log}

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

        # Re-anchor the analyst's ATR/structure plan to the fresh executable quote.
        entry_key = "bestAsk" if consensus.action == "BUY" else "bestBid"
        effective_entry = float(snapshot.get(entry_key) or snapshot["lastPrice"])
        effective_sl = consensus.stop_loss
        effective_tp = consensus.take_profit
        effective_sl_rate = None
        effective_tp_rate = None

        if consensus.action == "BUY" and settings.SCALPING_MODE_ENABLED:
            proposed_entry = float(consensus.entry_price or effective_entry)
            if proposed_entry <= 0 or not effective_sl or not effective_tp:
                return {"status": "RISK_REJECTED", "reasons": ["Kế hoạch scalping thiếu entry/SL/TP hợp lệ."], "pipeline": pipeline_log}

            ai_stop_rate = (proposed_entry - float(consensus.stop_loss)) / proposed_entry
            ai_target_rate = (float(consensus.take_profit) - proposed_entry) / proposed_entry
            latest = indicators.get("latest", {})
            atr = latest.get("atr14")
            atr_rate = float(atr) / proposed_entry if isinstance(atr, (int, float)) and atr > 0 else 0.0
            max_stop_rate = settings.TARGET_STOP_LOSS_PERCENT / 100.0
            # Keep the analyst's structural stop where possible, but never exceed
            # the configured loss cap; ATR prevents a stop tighter than market noise.
            stop_rate = min(max_stop_rate, max(ai_stop_rate, atr_rate * 1.2))
            effective_sl_rate = stop_rate
            effective_tp_rate = ai_target_rate
            effective_sl = round(effective_entry * (1.0 - stop_rate), 8)
            effective_tp = round(effective_entry * (1.0 + ai_target_rate), 8)
            pipeline_log["steps"]["scalping_plan"] = {
                "status": "PASS",
                "method": "ATR/structure stop re-anchored to fresh quote; analyst target preserved",
                "atr_percent": round(atr_rate * 100, 4),
                "stop_percent": round(stop_rate * 100, 4),
                "target_percent": round(ai_target_rate * 100, 4),
                "max_stop_percent": settings.TARGET_STOP_LOSS_PERCENT,
                "net_rr_minimum": settings.SCALPING_MIN_NET_RISK_REWARD,
                "note": "Risk Engine sẽ tính lại R:R ròng bằng spread và phí của báo giá mới nhất."
            }
            if ai_target_rate <= 0 or stop_rate <= 0:
                return {"status": "RISK_REJECTED", "reasons": ["TP/SL scalping không tạo được khoảng giá hợp lệ."], "pipeline": pipeline_log}

        sell_position = None
        if consensus.action == "SELL":
            position_stmt = select(Position).where(
                Position.symbol == symbol,
                Position.mode == mode,
                Position.status == "OPEN"
            ).order_by(Position.opened_at.desc())
            sell_position = (await session.execute(position_stmt)).scalars().first()
            if sell_position is None:
                pipeline_log["steps"]["risk_engine"] = {
                    "status": "REJECTED",
                    "passed": False,
                    "reasons": [f"Không có vị thế {symbol} do bot quản lý để đóng bằng lệnh SELL."]
                }
                return {
                    "status": "RISK_REJECTED",
                    "reasons": pipeline_log["steps"]["risk_engine"]["reasons"],
                    "pipeline": pipeline_log
                }

        risk_check: RiskCheckResult = await risk_engine.evaluate_trade(
            session=session,
            symbol=symbol,
            action=consensus.action,
            entry_price=effective_entry,
            stop_loss=effective_sl,
            take_profit=effective_tp,
            allocated_capital=allocated_capital,
            available_usdt=avail_usdt,
            symbol_filters=filters,
            mode=mode,
            spread_percent=float(snapshot.get("spreadPercent", 0.0))
        )

        pipeline_log["steps"]["risk_engine"] = risk_check.to_dict()

        # Log risk evaluation to DB
        risk_eval = RiskEvaluation(
            symbol=symbol,
            action=consensus.action,
            proposed_entry=effective_entry,
            proposed_sl=effective_sl,
            proposed_tp=effective_tp,
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
        market_price = Decimal(str(snapshot.get(entry_key) or snapshot["lastPrice"]))
        sl_dec = Decimal(str(effective_sl)) if effective_sl else None
        tp_dec = Decimal(str(effective_tp)) if effective_tp else None
        order_quantity = (
            sell_position.amount
            if consensus.action == "SELL" and sell_position is not None
            else risk_check.allowed_quantity
        )

        if mode == "PAPER":
            exec_res = await paper_simulator.execute_paper_order(
                session=session,
                symbol=symbol,
                side=consensus.action,
                quantity=order_quantity,
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
            used_convert = False
            if consensus.action == "SELL" and sell_position is not None:
                base_asset = symbol[:-4] if symbol.endswith("USDT") else symbol
                try:
                    free_bal = await self.account_manager.get_free_balance(base_asset)
                    if free_bal > 0:
                        order_quantity = min(order_quantity, free_bal)
                except Exception:
                    pass

            try:
                exec_res = await self.execution.execute_spot_order(
                    symbol=symbol,
                    side=consensus.action,
                    order_type="MARKET",
                    quantity=order_quantity
                )
            except Exception as spot_err:
                if consensus.action == "SELL" and sell_position is not None:
                    base_asset = symbol[:-4] if symbol.endswith("USDT") else symbol
                    try:
                        convert_res = await self.binance_client.convert_asset(
                            from_asset=base_asset,
                            to_asset="USDT",
                            from_amount=order_quantity
                        )
                        used_convert = True
                        quote_id_val = convert_res.get("quoteId") or sell_position.id
                        exec_res = {
                            "orderId": convert_res.get("orderId"),
                            "clientOrderId": f"CONVERT_{quote_id_val}",
                            "executedQty": str(convert_res.get("fromAmount", order_quantity)),
                            "cummulativeQuoteQty": str(convert_res.get("toAmount", "0")),
                            "status": "FILLED"
                        }
                    except Exception as conv_err:
                        raise RuntimeError(
                            f"Lệnh SELL thất bại (Spot: {spot_err} | Convert: {conv_err})"
                        )
                else:
                    raise

            executed_qty = Decimal(str(exec_res.get("executedQty", "0")))
            quote_qty = Decimal(str(exec_res.get("cummulativeQuoteQty", "0")))
            order_status = str(exec_res.get("status", "UNKNOWN")).upper()
            client_order_id = str(
                exec_res.get("clientOrderId") or f"BINANCE_{exec_res.get('orderId', time.time_ns())}"
            )
            order_record = Order(
                client_order_id=client_order_id,
                exchange_order_id=str(exec_res["orderId"]) if exec_res.get("orderId") is not None else None,
                symbol=symbol,
                side=consensus.action,
                order_type="MARKET",
                quantity=order_quantity,
                executed_qty=executed_qty,
                cummulative_quote_qty=quote_qty,
                status=order_status,
                mode=mode
            )
            session.add(order_record)

            if executed_qty <= 0:
                await session.commit()
                pipeline_log["steps"]["execution"] = {
                    "mode": mode,
                    "result": exec_res,
                    "status": "NOT_FILLED"
                }
                return {
                    "status": "ORDER_NOT_FILLED",
                    "action": consensus.action,
                    "symbol": symbol,
                    "pipeline": pipeline_log
                }

            fill_price = quote_qty / executed_qty if quote_qty > 0 else market_price
            fee_basis = quote_qty if quote_qty > 0 else executed_qty * fill_price
            estimated_fee = Decimal("0.0") if used_convert else fee_basis * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
            position_id = None
            remaining_quantity = 0.0

            if consensus.action == "BUY":
                if settings.SCALPING_MODE_ENABLED and effective_sl_rate is not None and effective_tp_rate is not None:
                    tp_dec = fill_price * (Decimal("1") + Decimal(str(effective_tp_rate)))
                    sl_dec = fill_price * (Decimal("1") - Decimal(str(effective_sl_rate)))

                # Deduct taker fee from base asset if trading in LIVE/TESTNET mode (0.1% fee)
                net_amount = executed_qty
                if mode in ("LIVE", "TESTNET"):
                    base_asset = symbol[:-4] if symbol.endswith("USDT") else symbol
                    try:
                        free_bal = await self.account_manager.get_free_balance(base_asset)
                        if free_bal > 0 and free_bal < executed_qty:
                            net_amount = free_bal
                        else:
                            net_amount = executed_qty * Decimal("0.999")
                    except Exception:
                        net_amount = executed_qty * Decimal("0.999")

                position = await PositionManager.open_position(
                    session=session,
                    symbol=symbol,
                    amount=net_amount,
                    entry_price=fill_price,
                    stop_loss=sl_dec,
                    take_profit=tp_dec,
                    fee=estimated_fee,
                    mode=mode
                )
                position_id = position.id
            else:
                closed_qty = min(executed_qty, Decimal(sell_position.amount))
                closed_quote = fee_basis * closed_qty / executed_qty
                exit_fee = Decimal("0.0") if used_convert else closed_quote * Decimal(str(settings.BINANCE_TAKER_FEE_PERCENT / 100.0))
                close_reason = "AI_SELL_SIGNAL (Binance Convert)" if used_convert else "AI_SELL_SIGNAL"
                closed = await PositionManager.close_position(
                    session=session,
                    position_id=sell_position.id,
                    exit_price=fill_price,
                    exit_fee=exit_fee,
                    reason=close_reason,
                    quantity=closed_qty
                )
                position_id = closed.id
                remaining_quantity = float(closed.amount)

            pipeline_log["steps"]["execution"] = {
                "mode": mode,
                "result": exec_res,
                "position_id": position_id,
                "remaining_quantity": remaining_quantity
            }

        return {
            "status": "EXECUTED",
            "action": consensus.action,
            "symbol": symbol,
            "pipeline": pipeline_log
        }
