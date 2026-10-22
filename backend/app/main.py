"""
FastAPI Application Entry Point
AI Binance Trading Company
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.database.session import init_db, AsyncSessionLocal, record_audit
from app.api import (
    system_router, binance_router, ai_router,
    trading_router, risk_router, backtest_router, ws_manager
)
from app.scheduler.controller import trading_controller

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    await init_db()
    
    # Live mode MUST be locked upon startup/restart
    settings.LIVE_SPOT_LOCKED = True
    settings.EMERGENCY_STOP_ACTIVE = False
    
    # Hook up websocket broadcast callback
    trading_controller.set_ws_broadcast(ws_manager.broadcast)

    async with AsyncSessionLocal() as session:
        await record_audit(
            session=session,
            event_type="APP_STARTUP",
            message=f"{settings.APP_NAME} đã khởi động thành công trên hệ điều hành {sys.platform}. Mặc định chế độ: {settings.TRADING_MODE}, LIVE LOCKED = True.",
            level="INFO"
        )

    yield

    # Shutdown: clean up running jobs
    if trading_controller.is_running:
        await trading_controller.stop()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(system_router)
app.include_router(binance_router)
app.include_router(ai_router)
app.include_router(trading_router)
app.include_router(risk_router)
app.include_router(backtest_router)

# Live WebSocket endpoint
@app.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state snapshot immediately upon connection
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "state": trading_controller.state,
            "mode": trading_controller.mode,
            "is_running": trading_controller.is_running,
            "emergency_stop": settings.EMERGENCY_STOP_ACTIVE,
            "live_locked": settings.LIVE_SPOT_LOCKED,
            "allocated_capital": settings.BOT_ALLOCATED_CAPITAL_USDT,
            "pairs": settings.DEFAULT_PAIRS
        })
        while True:
            # Keep alive and receive any client ping/pong
            msg = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Mount static build files if frontend was built
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
