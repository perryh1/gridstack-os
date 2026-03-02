"""
Data sourcing module: NREL PVWatts API (solar), synthetic wind profiles,
and ISO/LMP pricing data with historical fallbacks.
"""

import numpy as np
import requests
from typing import Optional

from config import (
    HISTORICAL_LMP, SOLAR_CF, WIND_CF, CITY_COORDS,
    STATE_ISO, GRIDSTATUS_HUB_MAP,
)

# ─── NREL PVWatts V8 Integration ──────────────────────────────────────────────

PVWATTS_URL = "https://developer.nrel.gov/api/pvwatts/v8.json"
PVWATTS_DEMO_KEY = "DEMO_KEY"   # free, rate-limited; users should supply own key


def fetch_pvwatts(
    city: str,
    capacity_kw: float,
    tilt: float = 20.0,
    azimuth: float = 180.0,
    array_type: int = 1,   # 1 = fixed, open rack
    module_type: int = 1,  # 1 = premium monocrystalline
    losses: float = 10.0,
    api_key: str = PVWATTS_DEMO_KEY,
) -> Optional[dict]:
    """
    Query NREL PVWatts V8 for hourly AC output (kWh/hr).
    Returns dict with 'ac' (8760-length list) and 'capacity_factor' on success,
    or None if the request fails.

    Data source: NREL National Solar Radiation Database (NSRDB) TMY3 / PSM3.
    Reference:   https://developer.nrel.gov/docs/solar/pvwatts/v8/
    """
    lat, lon = _get_coords(city)
    if lat is None:
        return None

    params = {
        "api_key": api_key,
        "lat": lat,
        "lon": lon,
        "system_capacity": capacity_kw,
        "tilt": tilt,
        "azimuth": azimuth,
        "array_type": array_type,
        "module_type": module_type,
        "losses": losses,
        "timeframe": "hourly",
    }
    try:
        resp = requests.get(PVWATTS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        outputs = data.get("outputs", {})
        ac_kwh = outputs.get("ac", [])
        if len(ac_kwh) == 8760:
            return {
                "ac_kwh": np.array(ac_kwh, dtype=float),
                "capacity_factor": outputs.get("capacity_factor", None),
                "source": "NREL PVWatts V8 (NSRDB TMY3/PSM3)",
                "lat": lat,
                "lon": lon,
            }
    except Exception:
        pass
    return None


# ─── Synthetic Solar Profile ──────────────────────────────────────────────────

def synthetic_solar_profile(
    capacity_mw: float,
    state: str,
    city: str,
    coupling: str = "AC",
    dc_ac_ratio: float = 1.25,
    seed: int = 42,
) -> dict:
    """
    Generate a synthetic 8760-hour solar generation profile (MWh) using
    state-level capacity factors from NREL's PVWatts atlas and a
    physics-inspired bell-curve irradiance model.

    Coupling:
      • AC-Coupled: inverter clips output at AC nameplate; excess is lost.
      • DC-Coupled: battery can absorb clipped DC energy directly.
    """
    rng = np.random.default_rng(seed)
    annual_cf = SOLAR_CF.get(state, 0.200)

    hours      = np.arange(8760)
    hour_of_day = hours % 24
    day_of_year = hours // 24

    # Day length varies: ~10 hr (winter) → ~14 hr (summer)
    day_length  = 12.0 + 2.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    solar_noon  = 12.0
    sigma       = day_length / 4.5

    # Gaussian irradiance shape centered at solar noon
    raw_irr = np.exp(-0.5 * ((hour_of_day - solar_noon) / sigma) ** 2)
    in_day  = (hour_of_day >= solar_noon - day_length / 2) & \
              (hour_of_day <= solar_noon + day_length / 2)
    raw_irr = np.where(in_day, raw_irr, 0.0)

    # Seasonal efficiency variation (heat de-rating in summer)
    seasonal = 1.0 - 0.04 * np.cos(4 * np.pi * day_of_year / 365)

    # Day-to-day cloud factor (correlated within each day)
    daily_cloud = rng.uniform(0.55, 1.0, 365)
    hourly_cloud = np.repeat(daily_cloud, 24)[:8760]

    # Uncapped DC generation (normalised by target CF later)
    gen_dc = raw_irr * seasonal * hourly_cloud * capacity_mw * dc_ac_ratio

    # Compute clipped and AC output
    ac_limit  = capacity_mw
    gen_ac    = np.minimum(gen_dc, ac_limit)
    clipped   = gen_dc - gen_ac   # energy lost at inverter (AC-coupled)

    # Scale to match target annual capacity factor (AC basis)
    ac_cf_raw = gen_ac.sum() / (capacity_mw * 8760)
    scale = annual_cf / ac_cf_raw if ac_cf_raw > 0 else 1.0
    gen_ac  = np.clip(gen_ac  * scale, 0, capacity_mw)
    clipped = np.clip(clipped * scale, 0, None)

    # DC-coupled: clipped energy available to battery directly
    available_for_bess = clipped if coupling == "DC" else np.zeros(8760)

    lat, lon = _get_coords(city)
    return {
        "generation_mwh": gen_ac,
        "clipped_mwh": clipped,
        "bess_dc_avail_mwh": available_for_bess,
        "annual_cf": float(gen_ac.sum() / (capacity_mw * 8760)),
        "source": (
            f"Synthetic model · NREL PVWatts atlas CF ({state}: {annual_cf:.1%}) · "
            "NSRDB TMY3 irradiance basis"
        ),
        "lat": lat,
        "lon": lon,
    }


# ─── Synthetic Wind Profile ───────────────────────────────────────────────────

def synthetic_wind_profile(
    capacity_mw: float,
    state: str,
    seed: int = 42,
) -> dict:
    """
    Generate a synthetic 8760-hour wind generation profile (MWh) using
    a Weibull-distributed wind speed model scaled to state-level capacity
    factors from NREL's Wind Toolkit.

    Wind has stronger nocturnal generation and less predictable diurnal cycles
    than solar, captured by the random day-level base plus Weibull draw.
    """
    rng  = np.random.default_rng(seed)
    annual_cf = WIND_CF.get(state, 0.300)

    hours      = np.arange(8760)
    hour_of_day = hours % 24
    day_of_year = hours // 24

    # Weibull wind speed (shape k=2 → Rayleigh, typical for wind resources)
    wind_speeds = rng.weibull(2.0, 8760) * 8.5  # scale ≈ 8.5 m/s median

    # Nocturnal boost: wind is ~20% stronger at night at hub height (100 m)
    nocturnal = 1.0 + 0.20 * np.cos(np.pi * hour_of_day / 12)

    # Seasonal: stronger winter winds in most US regions
    seasonal = 1.0 + 0.15 * np.cos(2 * np.pi * (day_of_year - 15) / 365)

    # Simple cubic power curve: cut-in 3, rated 12, cut-out 25 m/s
    ws = wind_speeds * nocturnal * seasonal
    gen_raw = np.where(
        ws < 3.0,  0.0,
        np.where(
            ws < 12.0, capacity_mw * ((ws - 3.0) / (12.0 - 3.0)) ** 3,
            np.where(ws < 25.0, capacity_mw, 0.0)
        )
    )

    # Scale to target annual CF
    raw_cf = gen_raw.mean() / capacity_mw if capacity_mw > 0 else 1.0
    scale  = annual_cf / raw_cf if raw_cf > 0 else 1.0
    gen    = np.clip(gen_raw * scale, 0.0, capacity_mw)

    return {
        "generation_mwh": gen,
        "clipped_mwh": np.zeros(8760),
        "bess_dc_avail_mwh": np.zeros(8760),
        "annual_cf": float(gen.mean() / capacity_mw),
        "source": (
            f"Synthetic Weibull model · NREL Wind Toolkit atlas CF ({state}: {annual_cf:.1%}) · "
            "100 m hub height"
        ),
        "lat": None,
        "lon": None,
    }


# ─── LMP Profile ─────────────────────────────────────────────────────────────

def synthetic_lmp_profile(
    iso: str,
    gen_type: str,
    seed: int = 42,
) -> dict:
    """
    Generate a synthetic 8760-hour LMP profile ($/MWh) shaped by the
    ISO's historical average, peak, off-peak, negative-price frequency,
    and price spread characteristics.

    Modelling layers:
      1. Base price (ISO historical average)
      2. Time-of-use daily shape (ISO-specific duck curve / morning-evening peaks)
      3. Seasonal component
      4. White-noise volatility
      5. Negative-price events correlated with high-renewable hours
      6. Scarcity spike events (<0.5% of hours)

    Data basis: EIA Electric Power Monthly (2022-2023) + ISO annual reports.
    """
    rng = np.random.default_rng(seed)
    p   = HISTORICAL_LMP.get(iso, HISTORICAL_LMP["PJM"])
    avg, peak, offpeak = p["avg"], p["peak"], p["offpeak"]
    neg_pct = p["negative_pct"]

    hours       = np.arange(8760)
    hod         = hours % 24   # hour of day
    doy         = hours // 24  # day of year

    # ── 1. Daily TOU shape ────────────────────────────────────────────────
    if iso == "CAISO":
        # Duck curve: midday surplus (solar), steep evening ramp
        daily_delta = np.select(
            [hod < 6,
             (hod >= 6)  & (hod < 10),
             (hod >= 10) & (hod < 16),
             (hod >= 16) & (hod < 21),
             hod >= 21],
            [-0.35, 0.15, -0.30, 0.60, 0.05]
        ) * avg
    elif iso == "ERCOT":
        # Afternoon peak, moderate mornings
        daily_delta = np.select(
            [hod < 6,
             (hod >= 6)  & (hod < 9),
             (hod >= 9)  & (hod < 18),
             (hod >= 18) & (hod < 22),
             hod >= 22],
            [-0.25, 0.25, 0.35, 0.50, -0.10]
        ) * avg
    elif iso in ("NYISO", "ISO-NE"):
        # Morning and evening peaks, winter-heavy
        daily_delta = np.select(
            [hod < 5,
             (hod >= 5)  & (hod < 9),
             (hod >= 9)  & (hod < 17),
             (hod >= 17) & (hod < 21),
             hod >= 21],
            [-0.20, 0.40, 0.10, 0.45, -0.10]
        ) * avg
    elif iso == "HIISO":
        # Hawaii: very high baseline, afternoon peaks
        daily_delta = np.select(
            [hod < 6,
             (hod >= 6)  & (hod < 11),
             (hod >= 11) & (hod < 17),
             (hod >= 17) & (hod < 22),
             hod >= 22],
            [-0.20, -0.10, 0.10, 0.60, 0.00]
        ) * avg
    else:
        # Generic morning/evening dual peak (PJM, MISO, SPP, WECC, SERC)
        daily_delta = np.select(
            [hod < 5,
             (hod >= 5)  & (hod < 9),
             (hod >= 9)  & (hod < 17),
             (hod >= 17) & (hod < 22),
             hod >= 22],
            [-0.22, 0.35, 0.05, 0.38, -0.12]
        ) * avg

    # ── 2. Seasonal component (higher prices in summer & winter peaks) ────
    seasonal = 0.12 * avg * (
        np.cos(2 * np.pi * (doy - 200) / 365) +   # summer heat
        0.5 * np.cos(2 * np.pi * (doy - 10) / 365)  # winter cold
    )

    # ── 3. Assemble base + noise ──────────────────────────────────────────
    noise = rng.normal(0, avg * 0.08, 8760)
    lmp   = avg + daily_delta + seasonal + noise

    # ── 4. Negative-price events ──────────────────────────────────────────
    n_neg = int(8760 * neg_pct / 100.0)
    if gen_type == "Solar":
        neg_mask = (hod >= 10) & (hod <= 15) & (
            (doy >= 60) & (doy <= 180)
        )
    elif gen_type == "Hybrid":
        # Both midday solar and overnight wind curtailment windows
        neg_mask = (
            ((hod >= 10) & (hod <= 15) & (doy >= 60) & (doy <= 180)) |
            ((hod >= 0) & (hod <= 6) & ((doy <= 60) | (doy >= 300)))
        )
    else:  # Wind
        neg_mask = (hod >= 0) & (hod <= 6) & (
            (doy <= 60) | (doy >= 300)
        )
    neg_candidates = np.where(neg_mask)[0]
    if len(neg_candidates) >= n_neg:
        neg_hours = rng.choice(neg_candidates, n_neg, replace=False)
    else:
        neg_hours = neg_candidates
    lmp[neg_hours] = -rng.uniform(5, 35, len(neg_hours))

    # ── 5. Scarcity spikes ────────────────────────────────────────────────
    n_spikes   = max(1, int(8760 * 0.004))
    spike_hrs  = rng.choice(8760, n_spikes, replace=False)
    lmp[spike_hrs] = peak * rng.uniform(1.8, 5.0, n_spikes)

    lmp = np.clip(lmp, -75.0, 2000.0)

    return {
        "lmp_mwh": lmp,
        "avg_lmp": float(lmp[lmp > 0].mean()),
        "peak_lmp": float(lmp.max()),
        "n_negative_hours": int((lmp < 0).sum()),
        "source": (
            f"Synthetic LMP model · {iso} 2022-2023 historical averages · "
            "EIA Electric Power Monthly + ISO annual reports"
        ),
    }


# ─── Live LMP from gridstatus.io ─────────────────────────────────────────────

def load_lmp_gridstatus(iso: str, api_key: str) -> Optional[dict]:
    """
    Fetch ~1 year of day-ahead hourly LMP from gridstatus.io.
    Returns dict matching synthetic_lmp_profile() shape, or None on failure.
    Requires the ``gridstatusio`` package (pip install gridstatusio).
    """
    hub_info = GRIDSTATUS_HUB_MAP.get(iso)
    if hub_info is None:
        return None

    try:
        import gridstatusio
    except ImportError:
        return None

    try:
        from datetime import datetime, timedelta

        client = gridstatusio.GridStatusClient(api_key)
        end = datetime.utcnow()
        start = end - timedelta(days=365)

        df = client.get_dataset(
            dataset=hub_info["dataset"],
            filter_column="location",
            filter_value=hub_info["hub"],
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            limit=9000,
            verbose=False,
        )

        if df is None or (hasattr(df, "empty") and df.empty):
            return None

        price_col = hub_info["price_col"]
        if price_col not in df.columns:
            return None

        # Sort by time to ensure chronological order
        if "interval_start_utc" in df.columns:
            df = df.sort_values("interval_start_utc").reset_index(drop=True)

        lmp_series = df[price_col].dropna().values.astype(float)

        if len(lmp_series) == 0:
            return None

        # Pad or truncate to exactly 8760 hours
        if len(lmp_series) >= 8760:
            lmp_arr = lmp_series[:8760]
        else:
            repeats = (8760 // len(lmp_series)) + 1
            lmp_arr = np.tile(lmp_series, repeats)[:8760]

        date_range = f"{start.strftime('%b %Y')}–{end.strftime('%b %Y')}"
        return {
            "lmp_mwh": lmp_arr,
            "avg_lmp": float(lmp_arr[lmp_arr > 0].mean()) if (lmp_arr > 0).any() else 0.0,
            "peak_lmp": float(lmp_arr.max()),
            "n_negative_hours": int((lmp_arr < 0).sum()),
            "source": (
                f"gridstatus.io · {iso} {hub_info['hub']} · "
                f"Day-Ahead Hourly LMP · {date_range}"
            ),
        }
    except Exception:
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_coords(city: str):
    coords = CITY_COORDS.get(city)
    if coords:
        return coords
    return None, None


def get_iso_for_state(state: str) -> str:
    return STATE_ISO.get(state, "PJM")
