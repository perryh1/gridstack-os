"""
GridStack OS — Real-Time Dispatch Control Service

FastAPI application that runs the dispatch loop and exposes endpoints
for monitoring (Streamlit dashboard) and manual overrides.

Start with:
    uvicorn control_service.main:app --port 8400
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ControlSettings
from .state import SystemState
from .safety import SafetyWatchdog
from .audit import AuditLogger
from .dispatch_loop import DispatchLoop
from .models import (
    SystemStateResponse, HealthResponse,
    ManualOverrideRequest, DispatchHistoryResponse,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Shared instances ─────────────────────────────────────────────────────────
settings = ControlSettings()
state = SystemState()
safety = SafetyWatchdog(settings)
audit = AuditLogger(settings.audit_db_path)
loop: DispatchLoop | None = None


def _create_adapters():
    """Instantiate hardware adapters based on configuration."""
    from .adapters.foreman import ForemanAdapter
    from .adapters.bess_rest import BESSRestAdapter
    from .adapters.bess_mqtt import BESSMqttAdapter

    miner = ForemanAdapter(
        api_url=settings.foreman_api_url,
        client_id=settings.foreman_client_id,
        api_key=settings.foreman_api_key,
    )

    if settings.bess_adapter_type == "mqtt":
        bess = BESSMqttAdapter(
            broker_host=settings.bess_mqtt_broker,
            broker_port=settings.bess_mqtt_port,
            command_topic=settings.bess_mqtt_command_topic,
            status_topic=settings.bess_mqtt_status_topic,
            username=settings.bess_mqtt_username,
            password=settings.bess_mqtt_password,
        )
    else:
        bess = BESSRestAdapter(
            base_url=settings.bess_rest_url,
            api_key=settings.bess_rest_api_key,
        )

    return miner, bess


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect adapters on startup, clean up on shutdown."""
    global loop
    miner, bess = _create_adapters()

    logger.info("Connecting to hardware adapters...")
    await miner.connect()
    await bess.connect()

    loop = DispatchLoop(
        miner_adapter=miner,
        bess_adapter=bess,
        settings=settings,
        state=state,
        safety=safety,
        audit=audit,
    )
    logger.info("Control service ready. Use POST /start to begin dispatching.")

    yield

    # Shutdown
    if loop and state.loop_running:
        await loop.stop()
    await miner.close()
    await bess.close()
    audit.close()
    logger.info("Control service shut down cleanly.")


# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="GridStack OS Control Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """System health: adapter connectivity, loop status."""
    miner_ok = loop and await loop.miner.health_check() if loop else False
    bess_ok = loop and await loop.bess.health_check() if loop else False
    return HealthResponse(
        status="ok" if state.loop_running else "idle",
        loop_running=state.loop_running,
        miner_connected=miner_ok,
        bess_connected=bess_ok,
        last_cycle_at=state.last_cycle_at,
        uptime_seconds=state.uptime_seconds,
    )


@app.get("/state", response_model=SystemStateResponse)
async def get_state():
    """Current dispatch mode, LMP, mining/BESS status, alerts."""
    return state.to_response()


@app.get("/history", response_model=DispatchHistoryResponse)
async def get_history(hours: int = 24):
    """Last N hours of dispatch decisions for charting."""
    return state.get_history(hours=hours)


@app.get("/audit")
async def get_audit_log(limit: int = 100):
    """Command audit log."""
    return audit.get_recent(limit=limit)


@app.post("/override")
async def set_manual_override(req: ManualOverrideRequest):
    """Set manual override for miners and/or BESS."""
    if req.miner_mode == "auto" and req.bess_mode == "auto":
        state.clear_override()
        return {"status": "override_cleared"}
    state.set_override(req.miner_mode, req.bess_mode, req.bess_power_mw)
    return {"status": "override_set", "miner_mode": req.miner_mode, "bess_mode": req.bess_mode}


@app.post("/start")
async def start_loop():
    """Start the dispatch loop."""
    if not loop:
        return {"status": "error", "message": "Loop not initialized"}
    if state.loop_running:
        return {"status": "already_running"}
    await loop.start()
    return {"status": "started"}


@app.post("/stop")
async def stop_loop():
    """Gracefully stop the dispatch loop (sets hardware to safe state)."""
    if not loop or not state.loop_running:
        return {"status": "not_running"}
    await loop.stop()
    return {"status": "stopped"}
