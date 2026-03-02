"""
Main dispatch loop — the heart of the real-time control service.

Lifecycle per cycle:
  1. Fetch live LMP
  2. Read BESS and miner status from adapters
  3. Estimate current generation
  4. Run dispatch_single_step() → decision
  5. Safety watchdog check → possibly override
  6. Manual override check → possibly override
  7. Send commands to hardware
  8. Update state + audit log
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import deque

from .config import ControlSettings
from .state import SystemState
from .safety import SafetyWatchdog
from .audit import AuditLogger
from .realtime_dispatch import make_decision
from .models import DispatchDecision, MinerStatus, BESSStatus
from .adapters.base import MinerAdapter, BESSAdapter

logger = logging.getLogger(__name__)


class DispatchLoop:
    """Runs the dispatch cycle on a configurable interval."""

    def __init__(
        self,
        miner_adapter: MinerAdapter,
        bess_adapter: BESSAdapter,
        settings: ControlSettings,
        state: SystemState,
        safety: SafetyWatchdog,
        audit: AuditLogger,
    ):
        self.miner = miner_adapter
        self.bess = bess_adapter
        self.settings = settings
        self.state = state
        self.safety = safety
        self.audit = audit
        self._lmp_history: deque[float] = deque(maxlen=settings.lmp_history_window)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the dispatch loop as an asyncio task."""
        if self._running:
            logger.warning("Dispatch loop already running")
            return
        self._running = True
        self.state.loop_running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Dispatch loop started (interval=%ds)", self.settings.dispatch_interval_seconds)

    async def stop(self):
        """Stop the loop gracefully and set hardware to safe state."""
        self._running = False
        self.state.loop_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Set hardware to safe state on shutdown
        logger.info("Setting hardware to safe state before shutdown")
        try:
            await self.miner.set_power_mode("sleep")
        except Exception as e:
            logger.error("Failed to sleep miners on shutdown: %s", e)
        try:
            await self.bess.set_idle()
        except Exception as e:
            logger.error("Failed to idle BESS on shutdown: %s", e)
        logger.info("Dispatch loop stopped")

    async def _run(self):
        """Main loop — runs until stopped."""
        while self._running:
            cycle_start = time.monotonic()
            try:
                await self._execute_cycle()
            except Exception as e:
                logger.error("Dispatch cycle error: %s", e, exc_info=True)
                self.state.alerts = [f"Cycle error: {e}"]

            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0, self.settings.dispatch_interval_seconds - elapsed)
            await asyncio.sleep(sleep_time)

    async def _execute_cycle(self):
        """Execute one complete dispatch cycle."""

        # 1. Fetch live LMP
        lmp, lmp_ok = await self._fetch_lmp()

        # 2. Read hardware status
        miner_status, miner_ok = await self._read_miner()
        bess_status, bess_ok = await self._read_bess()

        # 3. Estimate generation (placeholder — SCADA integration point)
        gen_mw = await self._estimate_generation()

        # 4. Compute future LMP average from history
        if lmp_ok:
            self._lmp_history.append(lmp)
        future_lmp_avg = (
            sum(self._lmp_history) / len(self._lmp_history)
            if self._lmp_history else lmp
        )

        # 5. Run dispatch decision
        decision = make_decision(
            lmp=lmp,
            generation_mw=gen_mw,
            bess_soc_mwh=bess_status.soc_mwh,
            future_lmp_avg=future_lmp_avg,
            settings=self.settings,
        )

        # 6. Safety watchdog
        decision, alerts = self.safety.check(
            decision=decision,
            lmp_ok=lmp_ok,
            miner_ok=miner_ok,
            bess_ok=bess_ok,
            bess_soc_mwh=bess_status.soc_mwh,
        )

        # 7. Manual override
        if self.state.manual_override_active:
            decision = self._apply_override(decision)
            alerts.append("Manual override active")

        # 8. Send commands to hardware
        miner_cmd_ok = await self._send_miner_command(decision)
        bess_cmd_ok = await self._send_bess_command(decision)

        # 9. Update state + audit
        self.state.update(decision, lmp, gen_mw, miner_status, bess_status, alerts)
        self.audit.record(
            decision=decision,
            lmp=lmp,
            gen_mw=gen_mw,
            bess_soc_mwh=bess_status.soc_mwh,
            alerts=alerts,
            miner_cmd_ok=miner_cmd_ok,
            bess_cmd_ok=bess_cmd_ok,
        )

        logger.info(
            "Cycle #%d: mode=%s | LMP=$%.2f | mine=%.1fMW | BESS chg=%.1f dis=%.1f | alerts=%d",
            self.state.cycle_count, decision.dispatch_mode, lmp,
            decision.mining_mw, decision.bess_charge_mw, decision.bess_discharge_mw,
            len(alerts),
        )

    # ── Data fetching ────────────────────────────────────────────────────

    async def _fetch_lmp(self) -> tuple[float, bool]:
        """Fetch latest LMP from gridstatus.io."""
        try:
            import gridstatusio
            from config import GRIDSTATUS_HUB_MAP

            client = gridstatusio.GridStatusClient(self.settings.gridstatus_api_key)
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=2)

            hub_info = GRIDSTATUS_HUB_MAP.get(self.settings.iso, {})
            if not hub_info:
                logger.warning("No hub mapping for ISO %s", self.settings.iso)
                return 0.0, False

            df = client.get_dataset(
                dataset=hub_info["dataset"],
                filter_column=hub_info.get("filter_col", "location"),
                filter_value=hub_info["hub"],
                start=start.strftime("%Y-%m-%dT%H:%M"),
                end=end.strftime("%Y-%m-%dT%H:%M"),
                limit=5,
            )
            price_col = hub_info.get("price_col", "lmp")
            if df is not None and not df.empty:
                return float(df[price_col].iloc[-1]), True
            return 0.0, False
        except Exception as e:
            logger.error("LMP fetch failed: %s", e)
            return self._lmp_history[-1] if self._lmp_history else 0.0, False

    async def _read_miner(self) -> tuple[MinerStatus, bool]:
        try:
            status = await self.miner.get_status()
            return status, status.online
        except Exception as e:
            logger.error("Miner status read failed: %s", e)
            return MinerStatus(), False

    async def _read_bess(self) -> tuple[BESSStatus, bool]:
        try:
            status = await self.bess.get_status()
            return status, status.online
        except Exception as e:
            logger.error("BESS status read failed: %s", e)
            return BESSStatus(), False

    async def _estimate_generation(self) -> float:
        """
        Placeholder for real-time generation estimation.

        In production, this would read from:
          - Inverter SCADA/Modbus
          - Weather API + PVWatts model
          - Revenue meter
        For now, returns 0.0 (conservative — treats all power as grid-sourced).
        """
        return 0.0

    # ── Hardware commands ────────────────────────────────────────────────

    async def _send_miner_command(self, decision: DispatchDecision) -> bool:
        """Map dispatch decision to miner power mode and send."""
        try:
            if decision.mining_mw <= 0:
                return await self.miner.set_power_mode("sleep")
            elif decision.mining_mw < self.settings.mining_power_mw * 0.5:
                return await self.miner.set_power_mode("low")
            else:
                return await self.miner.set_power_mode("high")
        except Exception as e:
            logger.error("Miner command failed: %s", e)
            return False

    async def _send_bess_command(self, decision: DispatchDecision) -> bool:
        """Map dispatch decision to BESS charge/discharge/idle."""
        try:
            if decision.bess_charge_mw > 0:
                return await self.bess.set_charge(decision.bess_charge_mw)
            elif decision.bess_discharge_mw > 0:
                return await self.bess.set_discharge(decision.bess_discharge_mw)
            else:
                return await self.bess.set_idle()
        except Exception as e:
            logger.error("BESS command failed: %s", e)
            return False

    def _apply_override(self, decision: DispatchDecision) -> DispatchDecision:
        """Apply manual overrides from the dashboard."""
        if self.state.manual_miner_mode == "sleep":
            decision.mining_mw = 0.0
        elif self.state.manual_miner_mode == "high":
            decision.mining_mw = self.settings.mining_power_mw
        elif self.state.manual_miner_mode == "low":
            decision.mining_mw = self.settings.mining_power_mw * 0.5

        if self.state.manual_bess_mode == "charge":
            power = self.state.manual_bess_power or self.settings.bess_power_mw
            decision.bess_charge_mw = power
            decision.bess_discharge_mw = 0.0
        elif self.state.manual_bess_mode == "discharge":
            power = self.state.manual_bess_power or self.settings.bess_power_mw
            decision.bess_discharge_mw = power
            decision.bess_charge_mw = 0.0
        elif self.state.manual_bess_mode == "idle":
            decision.bess_charge_mw = 0.0
            decision.bess_discharge_mw = 0.0

        decision.dispatch_mode = f"MANUAL OVERRIDE ({decision.dispatch_mode})"
        return decision
