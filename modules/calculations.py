"""
Core quantitative engine for GridStack OS.

Covers:
  • Mining break-even electricity price
  • Generation-only revenue table (24h, 7d, 30d, 6mo, 1yr)
  • Synergy dispatch simulation (priority logic)
  • BESS arbitrage revenue
  • IRR / NPV / ROI with ITC
  • Capital allocation optimisation
"""

import math
import numpy as np
import numpy_financial as npf
import pandas as pd
from typing import Optional

from config import (
    BESS_RTE, BESS_CYCLES_PER_YEAR, BESS_OM_PER_MWH_YEAR, BESS_DEGRADATION,
    SOLAR_OM_PER_MW_YEAR, WIND_OM_PER_MW_YEAR, SOLAR_DEGRADATION, WIND_DEGRADATION,
    MINER_OM_RATE, PROJECT_LIFE_YEARS, MEGAPACK_PRESETS,
    ITC_BASE_RATE, ITC_DOMESTIC_CONTENT, ANCILLARY_PREMIUMS,
)

# ─── Mining Break-Even ────────────────────────────────────────────────────────

def mining_break_even_price(efficiency_jth: float, hashprice_per_th_day: float) -> float:
    """
    Return electricity price ($/kWh) at which miner revenue = electricity cost.

    Physics:
      Power per TH/s  = efficiency (J/TH) / 1 000  →  kW/TH
      Cost  per TH/day = power_kW × 24 h × elec_price
      Revenue/TH/day   = hashprice  ($/TH/day)
      Break-even: hashprice = (eff/1000) × 24 × price
      → price = hashprice / (eff × 24 / 1000)
    """
    power_kw_per_th = efficiency_jth / 1_000.0
    denominator = power_kw_per_th * 24.0
    if denominator <= 0:
        return float("inf")
    return hashprice_per_th_day / denominator   # $/kWh


def mining_power_mw(hashrate_th: float, efficiency_jth: float) -> float:
    """MW consumed by a given hashrate at a given efficiency."""
    return hashrate_th * efficiency_jth / 1_000_000.0   # J/TH × TH/s → W → MW


def mining_revenue_annual(hashrate_th: float, hashprice_per_th_day: float) -> float:
    """Annual gross revenue from mining ($$) — ignores electricity cost."""
    return hashrate_th * hashprice_per_th_day * 365.25


def hashrate_from_power(power_mw: float, efficiency_jth: float) -> float:
    """TH/s of mining capacity from a given MW power block."""
    if efficiency_jth <= 0:
        return 0.0
    return power_mw * 1_000_000.0 / efficiency_jth


# ─── Generation-Only Revenue Table ───────────────────────────────────────────

PERIOD_HOURS = {
    "24 Hours":  24,
    "7 Days":    24 * 7,
    "30 Days":   24 * 30,
    "6 Months":  24 * 182,
    "1 Year":    8760,
}


def generation_revenue_table(
    gen_mwh: np.ndarray,
    lmp_mwh: np.ndarray,
    grid_tied: bool = True,
) -> pd.DataFrame:
    """
    Build the generation-only revenue table for multiple time horizons.

    Columns:
      Period | Generation (MWh) | Revenue ($) | Avg LMP ($/MWh)
      | Hours Curtailed | Revenue Lost to Negative Pricing ($)
    """
    rows = []
    for label, hours in PERIOD_HOURS.items():
        h = min(hours, len(gen_mwh))
        g = gen_mwh[:h]
        p = lmp_mwh[:h]

        neg_mask   = p < 0
        pos_mask   = ~neg_mask

        revenue    = float((g[pos_mask] * p[pos_mask]).sum())
        # For grid-tied: negative prices mean curtailment cost; BTM: we curtail for free
        if grid_tied:
            rev_lost   = float((g[neg_mask] * np.abs(p[neg_mask])).sum())
        else:
            rev_lost   = 0.0
        curtailed  = int(neg_mask.sum())
        gen_total  = float(g.sum())
        avg_lmp    = float(p[pos_mask].mean()) if pos_mask.any() else 0.0

        rows.append({
            "Period": label,
            "Generation (MWh)": round(gen_total, 1),
            "Revenue ($)": round(revenue, 0),
            "Avg LMP ($/MWh)": round(avg_lmp, 2),
            "Hours Curtailed": curtailed,
            "Revenue Lost — Neg. Pricing ($)": round(rev_lost, 0),
        })
    return pd.DataFrame(rows)


# ─── Synergy Dispatch Simulation ─────────────────────────────────────────────

def simulate_synergy_dispatch(
    gen_mwh: np.ndarray,          # hourly generation (MWh)
    lmp_mwh: np.ndarray,          # hourly LMP ($/MWh)
    break_even_mwh: float,        # mining break-even in $/MWh
    bess_power_mw: float,
    bess_energy_mwh: float,
    mining_power_mw: float,
    interconnection_mw: float,
    ancillary_premium: float,     # $/MWh for BESS ancillary services
    rte: float = BESS_RTE,
    dc_avail_mwh: Optional[np.ndarray] = None,
    grid_tied: bool = True,       # True = can import/export; False = BTM (on-site only)
) -> pd.DataFrame:
    """
    Implements the Synergy Priority Logic hour-by-hour over 8760 hours.

    Grid-Tied vs Behind-the-Meter (BTM):
      Grid-Tied:
        - Export surplus to grid at LMP (Rule 3).
        - Import cheap grid power to run miners when LMP < break-even (Rule 2).
          This is the key night-time mode for solar sites — miners run 24/7
          whenever grid electricity is cheaper than the mining break-even price.
        - Import at negative LMP to charge BESS and mine — grid pays YOU (Rule 1).

      Behind-the-Meter (BTM):
        - No grid export, no grid import.
        - Miners and BESS can only consume on-site generation.
        - Mining revenue limited to hours when gen > 0.

    Priority Rules (Grid-Tied):
      1. LMP < 0:         Import + local gen → fill BESS → mine remainder.
                          Grid PAYS you for importing (negative LMP).
      2. 0 ≤ LMP < BE:    Mine at full capacity, importing from grid to fill
                          any shortfall from local generation. BESS charges
                          from remaining gen if future prices are favourable.
      3. LMP ≥ BE:        Discharge BESS → export to grid. No import (unprofitable).

    Priority Rules (BTM):
      Same as Grid-Tied Rules 1–2 but capped to local generation (no import).
      Rule 3: no grid export — all excess gen goes to BESS or is curtailed.
    """
    if dc_avail_mwh is None:
        dc_avail_mwh = np.zeros(len(gen_mwh))

    n = len(gen_mwh)
    soc = 0.0

    cols = {
        "hour":               np.arange(n),
        "generation_mwh":     gen_mwh.copy(),
        "lmp":                lmp_mwh.copy(),
        "grid_export_mwh":    np.zeros(n),
        "grid_import_mwh":    np.zeros(n),   # NEW — power imported from grid
        "mining_mw":          np.zeros(n),
        "bess_charge_mwh":    np.zeros(n),
        "bess_discharge_mwh": np.zeros(n),
        "bess_soc_mwh":       np.zeros(n),
        "rev_grid":           np.zeros(n),
        "rev_import":         np.zeros(n),   # NEW — net revenue from grid imports
        "rev_mining":         np.zeros(n),
        "rev_bess":           np.zeros(n),
        "rev_ancillary":      np.zeros(n),
        "dispatch_mode":      [""] * n,
    }

    lmp_future = np.convolve(lmp_mwh, np.ones(12) / 12, mode="same")

    for i in range(n):
        gen         = float(gen_mwh[i])
        dc_ex       = float(dc_avail_mwh[i])
        lmp         = float(lmp_mwh[i])
        total_avail = gen + dc_ex

        grid_exp    = 0.0
        grid_imp    = 0.0
        mine_mw     = 0.0
        bess_chg    = 0.0
        bess_dis    = 0.0
        mode        = ""

        # ── Rule 1: Negative LMP ─────────────────────────────────────────
        # Grid is paying to offload surplus — take as much as possible.
        if lmp < 0:
            mode = "Negative LMP"
            chg_cap  = min(bess_power_mw, (bess_energy_mwh - soc) / rte)

            if grid_tied:
                # Import enough to fill BESS AND run miners at full capacity,
                # limited by interconnection. Grid pays you for all of it.
                total_wanted  = chg_cap + mining_power_mw
                total_sourced = min(total_wanted, total_avail + interconnection_mw)
                bess_chg      = min(chg_cap, total_sourced)
                soc           = min(soc + bess_chg * rte, bess_energy_mwh)
                remaining     = total_sourced - bess_chg
                mine_mw       = min(mining_power_mw, remaining)
                grid_imp      = max(0.0, (bess_chg + mine_mw) - total_avail)
            else:
                bess_chg  = min(chg_cap, total_avail)
                soc       = min(soc + bess_chg * rte, bess_energy_mwh)
                remaining = total_avail - bess_chg
                mine_mw   = min(mining_power_mw, remaining)

        # ── Rule 2: Below break-even (0 ≤ LMP < break_even) ─────────────
        # Mining is profitable — run at full capacity.
        # Grid-Tied: import the shortfall from the grid (night-time mining).
        elif lmp < break_even_mwh:
            future_lmp = lmp_future[min(i + 6, n - 1)]
            # Discharge BESS when LMP is in the upper band — capture arb spread
            # even though mining is still profitable from grid power.
            discharge_threshold = break_even_mwh * 0.70  # discharge above 70% of BE
            discharge_incentive = (
                grid_tied
                and soc > bess_energy_mwh * 0.20
                and lmp > discharge_threshold
                and lmp > lmp_future[min(i + 6, n - 1)] * 0.90  # near local peak
            )
            charge_incentive = (
                soc < bess_energy_mwh * 0.80
                and future_lmp > break_even_mwh * 1.1
            )

            if discharge_incentive:
                # Discharge BESS to grid while miners run on gen + imports
                mode     = "Below Break-Even → Mine + Discharge"
                dis_cap  = min(bess_power_mw, soc)
                bess_dis = dis_cap
                soc      = max(0.0, soc - bess_dis)
                # Export BESS discharge to grid
                grid_exp = min(interconnection_mw, bess_dis)
                # Mine at full capacity from gen + grid import
                if grid_tied:
                    mine_mw  = min(mining_power_mw, total_avail + interconnection_mw - grid_exp)
                    grid_imp = max(0.0, mine_mw - total_avail)
                else:
                    mine_mw  = min(mining_power_mw, total_avail)
            elif charge_incentive:
                mode     = "Below Break-Even → Charge BESS"
                chg_cap  = min(bess_power_mw, (bess_energy_mwh - soc) / rte)
                bess_chg = min(chg_cap, total_avail)
                soc      = min(soc + bess_chg * rte, bess_energy_mwh)
                remaining = total_avail - bess_chg
                if grid_tied:
                    # Mine at full capacity — import what gen doesn't cover
                    mine_mw  = min(mining_power_mw, remaining + interconnection_mw)
                    grid_imp = max(0.0, mine_mw - remaining)
                else:
                    mine_mw = min(mining_power_mw, remaining)
            else:
                mode = "Below Break-Even → Mine"
                if grid_tied:
                    # Fill mining capacity from gen + grid import
                    mine_mw  = min(mining_power_mw, total_avail + interconnection_mw)
                    grid_imp = max(0.0, mine_mw - total_avail)
                else:
                    mine_mw  = min(mining_power_mw, total_avail)
                remaining = max(0.0, total_avail - mine_mw)
                chg_cap   = min(bess_power_mw, (bess_energy_mwh - soc) / rte)
                bess_chg  = min(chg_cap, remaining)
                soc       = min(soc + bess_chg * rte, bess_energy_mwh)

        # ── Rule 3: Above break-even ──────────────────────────────────────
        # Mining from grid would be unprofitable. Export/discharge instead.
        else:
            if grid_tied:
                mode     = "Above Break-Even → Export + Discharge"
                dis_cap  = min(bess_power_mw, soc)
                bess_dis = dis_cap
                soc      = max(0.0, soc - bess_dis)
                # Export generation to grid (separate from BESS discharge)
                gen_export = min(interconnection_mw, gen)
                # BESS discharge also exported (remaining interconnection capacity)
                bess_export = min(interconnection_mw - gen_export, bess_dis)
                grid_exp    = gen_export + bess_export
                surplus     = max(0.0, gen - gen_export)
                mine_mw     = min(mining_power_mw, surplus)
            else:
                # BTM: no export. Charge BESS from surplus or curtail.
                mode     = "BTM — Charge/Curtail"
                dis_cap  = min(bess_power_mw, soc)
                bess_dis = dis_cap
                soc      = max(0.0, soc - bess_dis)
                # Use gen + discharge on-site (miners paused — unprofitable at LMP ≥ BE)
                chg_cap  = min(bess_power_mw, (bess_energy_mwh - soc) / rte)
                bess_chg = min(chg_cap, max(0.0, total_avail - bess_dis))
                soc      = min(soc + bess_chg * rte, bess_energy_mwh)

        # ── Revenue calculations ──────────────────────────────────────────
        # Grid export revenue: only from generation (not BESS discharge)
        gen_exported = min(grid_exp, gen) if bess_dis > 0 else grid_exp
        rev_grid     = max(0.0, gen_exported * lmp)
        # BESS discharge revenue: separate from grid export
        rev_bess     = bess_dis * max(0.0, lmp)
        # Ancillary capacity payment: $/MWh × MW × 1 hr = $/hr earned while BESS is available
        # (SOC > 20% means the BESS can respond to dispatch calls)
        rev_ancillary = (
            bess_power_mw * ancillary_premium
            if soc > bess_energy_mwh * 0.20 else 0.0
        )
        # Grid import revenue: negative LMP = grid pays you (positive); positive LMP = cost (negative)
        rev_import  = grid_imp * (-lmp)   # positive when lmp<0 (income), negative when lmp>0 (cost)

        cols["grid_export_mwh"][i]    = grid_exp
        cols["grid_import_mwh"][i]    = grid_imp
        cols["mining_mw"][i]          = mine_mw
        cols["bess_charge_mwh"][i]    = bess_chg
        cols["bess_discharge_mwh"][i] = bess_dis
        cols["bess_soc_mwh"][i]       = soc
        cols["rev_grid"][i]           = rev_grid
        cols["rev_import"][i]         = rev_import
        cols["rev_mining"][i]         = 0.0   # aggregated at portfolio level
        cols["rev_bess"][i]           = rev_bess
        cols["rev_ancillary"][i]      = rev_ancillary
        cols["dispatch_mode"][i]      = mode

    return pd.DataFrame(cols)


def dispatch_summary(df: pd.DataFrame) -> dict:
    """Aggregate the dispatch DataFrame into annual summary metrics."""
    total_mining_mwh = float(df["mining_mw"].sum())
    # Fraction of 8760 hours miners are dispatched (used to scale annual mining revenue)
    max_mine_mwh = float(df["mining_mw"].max()) * 8760
    mining_utilization = (total_mining_mwh / max_mine_mwh) if max_mine_mwh > 0 else 0.0

    total_import_mwh = float(df["grid_import_mwh"].sum())
    # rev_import > 0 when grid pays you (neg LMP), < 0 when you pay the grid
    net_import_revenue = float(df["rev_import"].sum())

    return {
        "total_gen_mwh":          float(df["generation_mwh"].sum()),
        "total_grid_export_mwh":  float(df["grid_export_mwh"].sum()),
        "total_grid_import_mwh":  total_import_mwh,
        "total_mining_mwh":       total_mining_mwh,
        "mining_utilization":     min(1.0, mining_utilization),
        "total_bess_charge_mwh":  float(df["bess_charge_mwh"].sum()),
        "total_bess_disc_mwh":    float(df["bess_discharge_mwh"].sum()),
        "total_rev_grid":         float(df["rev_grid"].sum()),
        "total_rev_bess":         float(df["rev_bess"].sum()),
        "total_rev_ancillary":    float(df["rev_ancillary"].sum()),
        "net_import_revenue":     net_import_revenue,   # + = paid to consume, - = cost
        "neg_price_hours":        int((df["lmp"] < 0).sum()),
        "hours_mode_neg":         int((df["dispatch_mode"] == "Negative LMP").sum()),
        "hours_mode_charge":      int(df["dispatch_mode"].str.contains("Charge BESS").sum()),
        "hours_mode_mine":        int(df["dispatch_mode"].str.contains("Mine").sum()),
        "hours_mode_export":      int(df["dispatch_mode"].str.contains("Export").sum()),
    }


# ─── Portfolio Financial Model ────────────────────────────────────────────────

def build_annual_cashflows(
    gen_type: str,
    capacity_mw: float,
    hashrate_th: float,
    hashprice_per_th_day: float,
    efficiency_jth: float,
    bess_packs: int,
    pack_preset: dict,
    ancillary_premium: float,
    annual_rev_grid: float,
    annual_rev_bess: float,
    annual_rev_ancillary: float,
    annual_rev_import: float,
    itc_rate: float,
    solar_frac: float = 1.0,
    project_life: int = PROJECT_LIFE_YEARS,
) -> dict:
    """
    Build year-by-year cash flows for:
      • Miners Alone
      • BESS Alone
      • Hybrid Combined

    Returns dict of lists, length = project_life.
    """
    # ── CapEx ──────────────────────────────────────────────────────────────
    wind_frac = 1.0 - solar_frac
    gen_capex_per_mw = (
        1_100_000 * solar_frac + 1_400_000 * wind_frac
        if gen_type == "Hybrid"
        else (1_100_000 if gen_type == "Solar" else 1_400_000)
    )
    gen_capex        = capacity_mw * gen_capex_per_mw

    miner_hw_capex   = 0.0  # hardware cost handled externally (user supplies $/TH)
    # We track OpEx-only for miners here; CapEx = user's budget allocation
    bess_capex       = bess_packs * pack_preset["cost_usd"]
    bess_energy_mwh  = bess_packs * pack_preset["energy_mwh"]
    bess_power_mw    = bess_packs * pack_preset["power_mw"]

    # ── Annual revenue streams (year 0 = full operation) ─────────────────
    mining_rev_y0 = mining_revenue_annual(hashrate_th, hashprice_per_th_day)

    gen_om_y0  = capacity_mw * (
        SOLAR_OM_PER_MW_YEAR * solar_frac + WIND_OM_PER_MW_YEAR * wind_frac
        if gen_type == "Hybrid"
        else (SOLAR_OM_PER_MW_YEAR if gen_type == "Solar" else WIND_OM_PER_MW_YEAR)
    )
    bess_om_y0 = bess_energy_mwh * BESS_OM_PER_MWH_YEAR
    miner_om_y0 = hashrate_th * MINER_OM_RATE  # approx; user-defined base

    # ── Year-by-year degradation ──────────────────────────────────────────
    gen_deg  = (
        SOLAR_DEGRADATION * solar_frac + WIND_DEGRADATION * wind_frac
        if gen_type == "Hybrid"
        else (SOLAR_DEGRADATION if gen_type == "Solar" else WIND_DEGRADATION)
    )

    miners_cfs = []
    bess_cfs   = []
    hybrid_cfs = []

    for yr in range(1, project_life + 1):
        deg_gen   = (1 - gen_deg)  ** yr
        deg_bess  = max(0.75, (1 - BESS_DEGRADATION) ** yr)   # floor at 75%
        deg_miner = 1.0   # hashrate stays constant; assume fleet refresh

        # Grid export revenue scales with generation degradation
        rev_grid_yr = annual_rev_grid * deg_gen
        rev_bess_yr = (annual_rev_bess + annual_rev_ancillary) * deg_bess
        rev_mine_yr = mining_rev_y0 * deg_miner

        # Electricity cost for miners (only OpEx-relevant piece here)
        mine_power_mw = mining_power_mw(hashrate_th, efficiency_jth)
        mine_elec_cost_yr = (
            mine_power_mw * 1_000 * 8760   # kWh/yr
            * 0.00  # behind-the-meter / free curtailed generation → $0 marginal elec
        )

        # Miner standalone (only mining revenue, miner O&M)
        miners_cf  = rev_mine_yr - miner_om_y0
        bess_cf    = rev_bess_yr - bess_om_y0
        # Hybrid: user budget covers BESS + miners only; generation asset O&M is
        # the site owner's responsibility and not charged against this investment.
        hybrid_cf  = rev_mine_yr + rev_bess_yr + rev_grid_yr + annual_rev_import - bess_om_y0 - miner_om_y0

        miners_cfs.append(miners_cf)
        bess_cfs.append(bess_cf)
        hybrid_cfs.append(hybrid_cf)

    return {
        "gen_capex": gen_capex,
        "bess_capex": bess_capex,
        "miners_cfs": miners_cfs,
        "bess_cfs": bess_cfs,
        "hybrid_cfs": hybrid_cfs,
    }


def compute_irr_roi(
    capex: float,
    cashflows: list,
    itc_rate: float,
) -> dict:
    """
    Compute IRR, NPV (8% discount), and simple ROI for a given stream.
    ITC is applied as a year-1 tax credit (reduces effective CapEx).
    """
    itc_credit   = capex * itc_rate
    net_capex    = capex - itc_credit
    full_flows   = [-net_capex] + cashflows

    try:
        irr = npf.irr(full_flows)
        irr = float(irr) if np.isfinite(irr) else None
    except Exception:
        irr = None

    npv_8 = float(npf.npv(0.08, full_flows))
    total_revenue = sum(cashflows)
    roi = (total_revenue - net_capex) / net_capex if net_capex > 0 else 0.0

    payback = None
    cumulative = -net_capex
    for yr, cf in enumerate(cashflows, 1):
        cumulative += cf
        if cumulative >= 0:
            payback = yr
            break

    return {
        "irr": irr,
        "npv_8pct": npv_8,
        "roi": roi,
        "payback_years": payback,
        "net_capex": net_capex,
        "itc_credit": itc_credit,
    }


# ─── Capital Allocation Engine ────────────────────────────────────────────────

def allocate_capital(
    budget: float,
    gen_type: str,
    pack_key: str,
    hw_cost_per_th: float,       # $/TH
    efficiency_jth: float,
    hashprice_per_th_day: float,
    itc_rate: float,
    recommended_bess_split: float,  # 0-1 fraction to BESS
) -> dict:
    """
    Given a total budget, split between Megapacks and BTC miners per the
    recommended generation-type split.

    Returns a dict with:
      - n_packs, pack details, pack_cost, pack_power_mw, pack_energy_mwh
      - mining_th, mining_power_mw, mining_cost
      - remaining_budget
      - blended_irr (rough estimate)
    """
    preset = MEGAPACK_PRESETS[pack_key]

    bess_budget   = budget * recommended_bess_split
    miner_budget  = budget * (1 - recommended_bess_split)

    # ITC reduces effective BESS purchase cost (pre-tax credit cash outlay = full;
    # credit received ~year 1 per IRS §48E)
    n_packs   = max(0, int(bess_budget / preset["cost_usd"]))
    bess_cost = n_packs * preset["cost_usd"]

    # Remaining budget (incl. unused BESS budget) goes to miners
    miner_budget_actual = budget - bess_cost
    mining_th  = miner_budget_actual / hw_cost_per_th if hw_cost_per_th > 0 else 0.0
    mine_power = mining_power_mw(mining_th, efficiency_jth)
    mine_cost  = miner_budget_actual

    itc_savings = bess_cost * itc_rate

    return {
        "n_packs":         n_packs,
        "pack_label":      preset["label"],
        "pack_power_mw":   n_packs * preset["power_mw"],
        "pack_energy_mwh": n_packs * preset["energy_mwh"],
        "bess_cost":       bess_cost,
        "bess_split_pct":  recommended_bess_split,
        "mining_th":       mining_th,
        "mining_power_mw": mine_power,
        "mining_cost":     mine_cost,
        "miner_split_pct": 1 - recommended_bess_split,
        "total_deployed":  bess_cost + mine_cost,
        "itc_savings":     itc_savings,
        "remaining":       max(0.0, budget - bess_cost - mine_cost),
    }


# ─── Recommendation Logic ─────────────────────────────────────────────────────

def recommended_split(
    gen_type: str,
    solar_frac: float = 1.0,
    be_price_mwh: float = None,
    avg_lmp: float = None,
) -> tuple:
    """
    Return (bess_fraction, miner_fraction, explanation_text) recommended capital split.

    Base split is driven by generation shape (gen_type / solar_frac):
      Solar:  60 / 40  — duck curve demands evening storage
      Wind:   30 / 70  — long overnight curtailment suits miners
      Hybrid: interpolated between the two

    Then adjusted by mining profitability:
      ratio = break_even_price_mwh / avg_lmp
        >5x  → miners very profitable, shift +15% to miners
        3–5x → profitable, shift +8% to miners
        1.5–3x → balanced, no change
        0.8–1.5x → marginal, shift +8% to BESS
        <0.8x → miners often unprofitable, shift +15% to BESS

    Clamped to [20%, 80%] on each side.
    """
    # ── Step 1: gen-type base ─────────────────────────────────────────────
    if gen_type == "Solar":
        base_bess = 0.60
        gen_reason = (
            "Solar's predictable midday generation creates an evening 'Duck Curve' "
            "discharge opportunity that maximises battery IRR."
        )
    elif gen_type == "Wind":
        base_bess = 0.30
        gen_reason = (
            "Wind's long overnight curtailment windows suit miners as a "
            "flexible 24/7 load that mops up every curtailed MWh."
        )
    else:  # Hybrid
        base_bess = round(0.30 + solar_frac * 0.30, 2)
        gen_reason = (
            f"Hybrid mix ({int(solar_frac*100)}% solar / {int((1-solar_frac)*100)}% wind) "
            f"blends duck-curve storage demand with overnight curtailment absorption."
        )

    # ── Step 2: mining-economics adjustment ──────────────────────────────
    econ_note = ""
    if be_price_mwh is not None and avg_lmp is not None and avg_lmp > 0:
        ratio = be_price_mwh / avg_lmp
        if ratio > 5:
            adj = -0.15
            econ_note = (
                f"Mining break-even (${be_price_mwh:.0f}/MWh) is {ratio:.1f}× the avg LMP "
                f"(${avg_lmp:.0f}/MWh) — miners are highly profitable at current hashprice & "
                f"efficiency, so capital is shifted toward miners (+15%)."
            )
        elif ratio > 3:
            adj = -0.08
            econ_note = (
                f"Mining break-even (${be_price_mwh:.0f}/MWh) is {ratio:.1f}× avg LMP "
                f"(${avg_lmp:.0f}/MWh) — mining is profitable; modest shift toward miners (+8%)."
            )
        elif ratio > 1.5:
            adj = 0.0
            econ_note = (
                f"Mining break-even (${be_price_mwh:.0f}/MWh) is {ratio:.1f}× avg LMP "
                f"(${avg_lmp:.0f}/MWh) — mining and BESS arbitrage are balanced; no adjustment."
            )
        elif ratio > 0.8:
            adj = +0.08
            econ_note = (
                f"Mining break-even (${be_price_mwh:.0f}/MWh) is only {ratio:.1f}× avg LMP "
                f"(${avg_lmp:.0f}/MWh) — miners run marginally; BESS arbitrage preferred (+8% to BESS)."
            )
        else:
            adj = +0.15
            econ_note = (
                f"Mining break-even (${be_price_mwh:.0f}/MWh) is below avg LMP "
                f"(${avg_lmp:.0f}/MWh) — miners are often unprofitable at spot prices; "
                f"capital shifted strongly toward BESS (+15%)."
            )
        base_bess = round(min(0.80, max(0.20, base_bess + adj)), 2)

    bess = base_bess
    mine = round(1.0 - bess, 2)

    text = f"**{int(bess*100)}% BESS / {int(mine*100)}% Miners** — {gen_reason}"
    if econ_note:
        text += f"\n\n*Mining economics adjustment:* {econ_note}"

    return bess, mine, text


# ─── Highest-Value-of-an-Electron Table ──────────────────────────────────────

def electron_value_table(
    avg_lmp: float,
    peak_lmp: float,
    break_even_price_kwh: float,
    ancillary_premium_mwh: float,
    bess_rte: float = BESS_RTE,
) -> pd.DataFrame:
    """
    Compare three use-cases on a $/MWh basis so the user can see which
    use of each electron is most valuable right now.
    """
    break_even_mwh = break_even_price_kwh * 1_000
    bess_arbitrage = (peak_lmp - avg_lmp) * bess_rte + ancillary_premium_mwh

    rows = [
        {
            "Use Case":        "Grid Export (spot)",
            "Value ($/MWh)":   round(avg_lmp, 2),
            "Notes":           "Sell at average LMP; no storage premium.",
        },
        {
            "Use Case":        "BTC Mining",
            "Value ($/MWh)":   round(break_even_mwh, 2),
            "Notes":           "Break-even electricity value for selected miner config.",
        },
        {
            "Use Case":        "BESS Time-Shift + Ancillary",
            "Value ($/MWh)":   round(bess_arbitrage, 2),
            "Notes":           f"Peak discharge ({peak_lmp:.0f} $/MWh) × RTE {bess_rte:.0%} + ancillary.",
        },
    ]
    df = pd.DataFrame(rows)
    df["Highest Value?"] = df["Value ($/MWh)"] == df["Value ($/MWh)"].max()
    df["Highest Value?"] = df["Highest Value?"].map({True: "★ Best", False: ""})
    return df.sort_values("Value ($/MWh)", ascending=False).reset_index(drop=True)
