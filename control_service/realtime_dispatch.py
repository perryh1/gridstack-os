"""
Real-time dispatch wrapper around the core dispatch_single_step() logic.

Bridges live sensor readings into the same decision engine used by the
8760-hour simulation, producing a DispatchDecision for hardware execution.
"""

import sys
import os

# Ensure the project root is importable so `modules.calculations` resolves.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.calculations import dispatch_single_step
from .models import DispatchDecision
from .config import ControlSettings


def make_decision(
    lmp: float,
    generation_mw: float,
    bess_soc_mwh: float,
    future_lmp_avg: float,
    settings: ControlSettings,
) -> DispatchDecision:
    """
    Run one dispatch decision using live inputs.

    Parameters
    ----------
    lmp : float
        Current LMP ($/MWh).
    generation_mw : float
        Current on-site generation output (MW).
    bess_soc_mwh : float
        Current BESS state of charge (MWh).
    future_lmp_avg : float
        Rolling average of recent LMP for charge/discharge heuristics.
    settings : ControlSettings
        Site hardware parameters.

    Returns
    -------
    DispatchDecision
        The dispatch command to send to hardware.
    """
    raw = dispatch_single_step(
        generation_mw=generation_mw,
        lmp=lmp,
        break_even_mwh=settings.break_even_mwh,
        bess_soc_mwh=bess_soc_mwh,
        bess_power_mw=settings.bess_power_mw,
        bess_energy_mwh=settings.bess_energy_mwh,
        mining_power_mw_cap=settings.mining_power_mw,
        interconnection_mw=settings.interconnection_mw,
        rte=settings.rte,
        future_lmp_avg=future_lmp_avg,
        ancillary_premium=settings.ancillary_premium,
        grid_tied=settings.grid_tied,
    )

    return DispatchDecision(**raw)
