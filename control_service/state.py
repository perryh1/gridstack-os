"""In-memory state store for the dispatch control service."""

import time
from datetime import datetime, timezone
from collections import deque
from typing import Optional

from .models import (
    DispatchDecision, MinerStatus, BESSStatus,
    SystemStateResponse, DispatchHistoryEntry, DispatchHistoryResponse,
)


class SystemState:
    """Thread-safe in-memory state for the running control service."""

    def __init__(self, max_history: int = 2880):
        # max_history = 2880 entries ≈ 10 days at 5-min intervals
        self._start_time = time.monotonic()
        self.cycle_count: int = 0
        self.last_cycle_at: Optional[datetime] = None
        self.loop_running: bool = False

        # Current readings
        self.current_lmp: float = 0.0
        self.current_gen_mw: float = 0.0
        self.last_decision: Optional[DispatchDecision] = None
        self.miner_status: MinerStatus = MinerStatus()
        self.bess_status: BESSStatus = BESSStatus()

        # Manual override
        self.manual_override_active: bool = False
        self.manual_miner_mode: str = "auto"
        self.manual_bess_mode: str = "auto"
        self.manual_bess_power: Optional[float] = None

        # Alerts
        self.alerts: list[str] = []

        # History ring buffer
        self._history: deque[DispatchHistoryEntry] = deque(maxlen=max_history)

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def update(
        self,
        decision: DispatchDecision,
        lmp: float,
        gen_mw: float,
        miner_status: MinerStatus,
        bess_status: BESSStatus,
        alerts: list[str],
    ):
        """Called after each dispatch cycle to record the result."""
        now = datetime.now(timezone.utc)
        self.cycle_count += 1
        self.last_cycle_at = now
        self.current_lmp = lmp
        self.current_gen_mw = gen_mw
        self.last_decision = decision
        self.miner_status = miner_status
        self.bess_status = bess_status
        self.alerts = alerts

        soc_pct = (
            (bess_status.soc_mwh / decision.new_soc_mwh * 100)
            if decision.new_soc_mwh > 0 else bess_status.soc_pct
        )

        self._history.append(DispatchHistoryEntry(
            timestamp=now,
            lmp=lmp,
            gen_mw=gen_mw,
            mining_mw=decision.mining_mw,
            bess_charge_mw=decision.bess_charge_mw,
            bess_discharge_mw=decision.bess_discharge_mw,
            bess_soc_pct=bess_status.soc_pct,
            grid_export_mw=decision.grid_export_mw,
            grid_import_mw=decision.grid_import_mw,
            dispatch_mode=decision.dispatch_mode,
        ))

    def set_override(self, miner_mode: str, bess_mode: str, bess_power: Optional[float]):
        self.manual_miner_mode = miner_mode
        self.manual_bess_mode = bess_mode
        self.manual_bess_power = bess_power
        self.manual_override_active = (miner_mode != "auto" or bess_mode != "auto")

    def clear_override(self):
        self.manual_miner_mode = "auto"
        self.manual_bess_mode = "auto"
        self.manual_bess_power = None
        self.manual_override_active = False

    def to_response(self) -> SystemStateResponse:
        d = self.last_decision
        return SystemStateResponse(
            dispatch_mode=d.dispatch_mode if d else "",
            current_lmp=self.current_lmp,
            current_gen_mw=self.current_gen_mw,
            mining_power_mw=d.mining_mw if d else 0.0,
            mining_mode=self.miner_status.power_mode,
            bess_soc_pct=self.bess_status.soc_pct,
            bess_soc_mwh=self.bess_status.soc_mwh,
            bess_mode=self.bess_status.mode,
            bess_power_mw=d.bess_charge_mw if d and d.bess_charge_mw > 0 else (
                d.bess_discharge_mw if d else 0.0
            ),
            grid_export_mw=d.grid_export_mw if d else 0.0,
            grid_import_mw=d.grid_import_mw if d else 0.0,
            last_cycle_at=self.last_cycle_at,
            cycle_count=self.cycle_count,
            uptime_seconds=self.uptime_seconds,
            alerts=self.alerts,
            manual_override_active=self.manual_override_active,
            loop_running=self.loop_running,
        )

    def get_history(self, hours: int = 24) -> DispatchHistoryResponse:
        """Return the most recent N hours of history."""
        # At 5-min intervals, 1 hour = 12 entries
        max_entries = hours * 12
        entries = list(self._history)[-max_entries:]
        return DispatchHistoryResponse(entries=entries)
