import pytest
from app.trading.market_screener import MarketScreener


def test_screener_calculate_score():
    screener = MarketScreener()

    # High quality candidate: ATR in sweet spot (2.2%), healthy RSI (52), bullish EMA, high volume
    score, breakdown, reason = screener._calculate_candidate_score(
        price_change_24h=3.5,
        quote_volume_m=65.0,
        atr_percent=2.2,
        rsi14=52.0,
        ema_trend="BULLISH",
        mem_stats={"trades": 4, "win_rate": 75.0}
    )
    assert score >= 75
    assert breakdown["volatility"] == 25
    assert breakdown["rsi"] == 20
    assert breakdown["liquidity"] == 15
    assert breakdown["trade_memory"] == 10
    assert "lý tưởng" in reason


def test_screener_stablecoin_or_dead_asset_low_score():
    screener = MarketScreener()

    # Flat asset: 0% change, tiny ATR (0.1%), neutral EMA, low volume
    score, breakdown, reason = screener._calculate_candidate_score(
        price_change_24h=0.0,
        quote_volume_m=2.0,
        atr_percent=0.1,
        rsi14=49.0,
        ema_trend="NEUTRAL",
        mem_stats={"trades": 0, "win_rate": 0.0}
    )
    assert score < 50
    assert breakdown["volatility"] <= 10


@pytest.mark.asyncio
async def test_screener_scan_live_or_fallback():
    from app.database.session import AsyncSessionLocal
    screener = MarketScreener()

    async with AsyncSessionLocal() as session:
        result = await screener.scan_market(capital_usdt=5.55, session=session, force_refresh=True)
        assert result["status"] in ("SUCCESS", "FALLBACK")
        assert "candidates" in result
        assert len(result["candidates"]) > 0
        assert result["best_pick"] is not None
        assert result["best_pick"]["rank"] == 1
        assert result["best_pick"]["is_best_pick"] is True


@pytest.mark.asyncio
async def test_screener_insufficient_capital_stops_scanning():
    from app.database.session import AsyncSessionLocal
    screener = MarketScreener()

    async with AsyncSessionLocal() as session:
        # With 0.25 USDT, it cannot open any order on Binance Spot -> must stop scanning immediately!
        result = await screener.scan_market(capital_usdt=0.25, session=session, force_refresh=True)
        assert result["status"] == "INSUFFICIENT_CAPITAL"
        assert result["total_screened_universe"] == 0
        assert len(result["candidates"]) == 0
        assert result["best_pick"] is None
        assert "không đủ mở bất kỳ lệnh nào" in result["message"]

