"""
Safety watchdog for the dispatch control service.

Monitors adapter health and overrides dispatch decisions with failsafe
defaults when components are unreachable or operating out of bounds.
"""

import logging
from .models import DispatchDecision
from .config import ControlSettings

logger = logging.getLogger(__name__)


class SafetyWatchdog:
    """
    Tracks consecutive failures per component and triggers failsafe overrides.

    Failsafe actions:
      - Miners → SLEEP (stop power consumption)
      - BESS → IDLE (stop charge/discharge)
    """

    def __init__(self, settings: ControlSettings):
        self.max_failures = settings.safety_max_consecutive_failures
        self.min_soc_pct = settings.safety_min_soc_pct
        self.max_soc_pct = settings.safety_max_soc_pct
        self.bess_energy_mwh = settings.bess_energy_mwh

        self.lmp_failures: int = 0
        self.miner_failures: int = 0
        self.bess_failures: int = 0

    def check(
        self,
        decision: DispatchDecision,
        lmp_ok: bool,
        miner_ok: bool,
        bess_ok: bool,
        bess_soc_mwh: float,
    ) -> tuple[DispatchDecision, list[str]]:
        """
        Evaluate health signals and return (possibly overridden) decision + alerts.

        Parameters
        ----------
        decision : DispatchDecision
            The raw dispatch decision from the engine.
        lmp_ok : bool
            Whether the LMP data fetch succeeded this cycle.
        miner_ok : bool
            Whether the miner adapter health check passed.
        bess_ok : bool
            Whether the BESS adapter health check passed.
        bess_soc_mwh : float
            Current BESS state of charge in MWh.

        Returns
        -------
        (DispatchDecision, list[str])
            Possibly modified decision and list of alert messages.
        """
        alerts: list[str] = []

        # ── Track consecutive failures ───────────────────────────────────
        self.lmp_failures = self.lmp_failures + 1 if not lmp_ok else 0
        self.miner_failures = self.miner_failures + 1 if not miner_ok else 0
        self.bess_failures = self.bess_failures + 1 if not bess_ok else 0

        # ── LMP failsafe: no price data → miners to sleep ───────────────
        if self.lmp_failures >= self.max_failures:
            decision.mining_mw = 0.0
            decision.bess_charge_mw = 0.0
            decision.bess_discharge_mw = 0.0
            decision.dispatch_mode = "FAILSAFE: No LMP data"
            msg = f"LMP unavailable for {self.lmp_failures} cycles — failsafe active"
            alerts.append(msg)
            logger.warning(msg)

        # ── Miner adapter failsafe ──────────────────────────────────────
        if self.miner_failures >= self.max_failures:
            msg = f"Miner adapter unreachable for {self.miner_failures} cycles"
            alerts.append(msg)
            logger.warning(msg)
            # Can't send commands, but decision still reflects intent

        # ── BESS adapter failsafe ───────────────────────────────────────
        if self.bess_failures >= self.max_failures:
            decision.bess_charge_mw = 0.0
            decision.bess_discharge_mw = 0.0
            msg = f"BESS adapter unreachable for {self.bess_failures} cycles"
            alerts.append(msg)
            logger.warning(msg)

        # ── SOC safety bounds ───────────────────────────────────────────
        if self.bess_energy_mwh > 0:
            soc_pct = (bess_soc_mwh / self.bess_energy_mwh) * 100

            if soc_pct < self.min_soc_pct and decision.bess_discharge_mw > 0:
                decision.bess_discharge_mw = 0.0
                msg = f"BESS SOC {soc_pct:.1f}% below minimum ({self.min_soc_pct}%) — discharge blocked"
                alerts.append(msg)
                logger.warning(msg)

            if soc_pct > self.max_soc_pct and decision.bess_charge_mw > 0:
                decision.bess_charge_mw = 0.0
                msg = f"BESS SOC {soc_pct:.1f}% above maximum ({self.max_soc_pct}%) — charge blocked"
                alerts.append(msg)
                logger.warning(msg)

        return decision, alerts

    def reset(self):
        """Reset all failure counters."""
        self.lmp_failures = 0
        self.miner_failures = 0
        self.bess_failures = 0
