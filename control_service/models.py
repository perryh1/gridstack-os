"""Pydantic models for the control service API."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ─── Adapter status models ───────────────────────────────────────────────────

class MinerStatus(BaseModel):
    online: bool = False
    power_mode: str = "unknown"        # high, low, sleep, unknown
    power_mw: float = 0.0
    hashrate_th: float = 0.0
    timestamp: Optional[datetime] = None


class BESSStatus(BaseModel):
    online: bool = False
    mode: str = "unknown"              # charge, discharge, idle, unknown
    soc_mwh: float = 0.0
    soc_pct: float = 0.0
    power_mw: float = 0.0
    timestamp: Optional[datetime] = None


# ─── Dispatch decision ───────────────────────────────────────────────────────

class DispatchDecision(BaseModel):
    mining_mw: float = 0.0
    bess_charge_mw: float = 0.0
    bess_discharge_mw: float = 0.0
    grid_export_mw: float = 0.0
    grid_import_mw: float = 0.0
    dispatch_mode: str = ""
    new_soc_mwh: float = 0.0


# ─── API request / response models ──────────────────────────────────────────

class SystemStateResponse(BaseModel):
    dispatch_mode: str = ""
    current_lmp: float = 0.0
    current_gen_mw: float = 0.0
    mining_power_mw: float = 0.0
    mining_mode: str = "unknown"
    bess_soc_pct: float = 0.0
    bess_soc_mwh: float = 0.0
    bess_mode: str = "unknown"
    bess_power_mw: float = 0.0
    grid_export_mw: float = 0.0
    grid_import_mw: float = 0.0
    last_cycle_at: Optional[datetime] = None
    cycle_count: int = 0
    uptime_seconds: float = 0.0
    alerts: list[str] = []
    manual_override_active: bool = False
    loop_running: bool = False


class ManualOverrideRequest(BaseModel):
    miner_mode: str = "auto"           # high, low, sleep, auto
    bess_mode: str = "auto"            # charge, discharge, idle, auto
    bess_power_mw: Optional[float] = None


class DispatchHistoryEntry(BaseModel):
    timestamp: datetime
    lmp: float
    gen_mw: float
    mining_mw: float
    bess_charge_mw: float
    bess_discharge_mw: float
    bess_soc_pct: float
    grid_export_mw: float
    grid_import_mw: float
    dispatch_mode: str


class DispatchHistoryResponse(BaseModel):
    entries: list[DispatchHistoryEntry] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    loop_running: bool = False
    miner_connected: bool = False
    bess_connected: bool = False
    last_cycle_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
