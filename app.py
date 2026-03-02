"""
GridStack OS
───────────────────────────
Techno-Economic Modeling Tool for Hybrid BTC Mining + BESS Sites
Built on Streamlit 1.32+ | Python 3.11+
"""

# ── Page config MUST be the very first Streamlit call ────────────────────────
import streamlit as st

st.set_page_config(
    page_title="GridStack OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

import numpy as np
import pandas as pd
import sys, os
import re as _re_std
import urllib.request, ssl as _ssl
from datetime import date as _date
from fpdf import FPDF

sys.path.insert(0, os.path.dirname(__file__))

# ── Password gate ────────────────────────────────────────────────────────────
def _check_password():
    """Return True if the user has entered the correct password."""
    correct_pw = st.secrets.get("APP_PASSWORD", "")
    if not correct_pw:
        return True                       # no password configured → open access

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<h1 style='text-align:center;margin-top:15vh'>⚡ GridStack OS</h1>"
        "<p style='text-align:center;color:grey'>Hybrid BTC Mining + BESS Site Modeler</p>",
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        pw = st.text_input("Password", type="password", placeholder="Enter access password")
        submitted = st.form_submit_button("Log in", use_container_width=True)
    if submitted:
        if pw == correct_pw:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

if not _check_password():
    st.stop()


@st.cache_data(ttl=300)   # cache for 5 minutes
def fetch_live_hashprice() -> float:
    """
    Fetch current BTC hashprice ($/TH/day) from hashrateindex.com.
    Parses the __NEXT_DATA__ JSON embedded in the homepage.
    Returns None on any failure so the caller can fall back gracefully.
    """
    try:
        ctx = _ssl.create_default_context()
        req = urllib.request.Request(
            "https://hashrateindex.com",
            headers={"User-Agent": "Mozilla/5.0 (compatible; RenewableOptimizer/1.0)"},
        )
        html = urllib.request.urlopen(req, context=ctx, timeout=6).read().decode("utf-8", errors="ignore")
        m = _re_std.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, _re_std.DOTALL)
        if not m:
            return None
        blob = m.group(1)
        # Extract getLastUsdHashprice block: {"currentHashprice": 0.029...}
        hp_m = _re_std.search(r'"getLastUsdHashprice[^"]*":\s*\{"currentHashprice":\s*([\d.]+)', blob)
        if hp_m:
            return round(float(hp_m.group(1)), 4)
        return None
    except Exception:
        return None

from config import (
    STATE_CITIES, STATE_ISO, MEGAPACK_PRESETS, ANCILLARY_PREMIUMS,
    HISTORICAL_LMP, UNDERSERVED_OPTIONS, BESS_RTE, PROJECT_LIFE_YEARS,
)
from modules.data_sources import (
    synthetic_solar_profile, synthetic_wind_profile,
    synthetic_lmp_profile, fetch_pvwatts, get_iso_for_state,
    load_lmp_gridstatus,
)
from modules.calculations import (
    mining_break_even_price, mining_power_mw, mining_revenue_annual,
    hashrate_from_power, generation_revenue_table, simulate_synergy_dispatch,
    dispatch_summary, build_annual_cashflows, compute_irr_roi,
    allocate_capital, recommended_split, electron_value_table,
)
from modules.charts import (
    chart_gen_lmp, chart_annual_heatmap, chart_dispatch_stacked,
    chart_revenue_comparison, chart_irr_comparison, chart_capital_allocation,
    chart_duration_curve, chart_electron_value, chart_cumulative_cashflow,
    chart_tornado, chart_portfolio_irr, chart_portfolio_revenue,
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0D1321;
    border-right: 1px solid #1E2A45;
}
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #0EA5E9;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid #1E2A45;
    padding-bottom: 6px;
}

/* Sidebar brand */
.sidebar-brand {
    padding: 4px 0 12px 0;
    border-bottom: 1px solid #1E2A45;
    margin-bottom: 4px;
}
.sidebar-brand h2 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: #E8EAF0;
    letter-spacing: -0.01em;
}
.sidebar-brand h2 span { color: #0EA5E9; }
.sidebar-brand p {
    margin: 2px 0 0 0;
    font-size: 0.7rem;
    color: #64748B;
    letter-spacing: 0.02em;
}

/* Sidebar footer */
.sidebar-footer {
    border-top: 1px solid #1E2A45;
    padding-top: 10px;
    margin-top: 8px;
    text-align: center;
}
.sidebar-footer .version {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: #1E2A45;
    color: #64748B;
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.05em;
}
.sidebar-footer .powered {
    margin-top: 4px;
    font-size: 0.62rem;
    color: #475569;
}

/* Metric tiles */
div[data-testid="metric-container"] {
    background: #161B2E;
    border: 1px solid #1E2A45;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    transition: border-color 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    border-color: #0EA5E933;
}
div[data-testid="metric-container"] label {
    color: #94A3B8 !important;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #E8EAF0 !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}

/* Tab headers */
button[data-baseweb="tab"] {
    color: #64748B !important;
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.01em;
    transition: color 0.15s ease;
}
button[data-baseweb="tab"]:hover {
    color: #94A3B8 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #0EA5E9 !important;
    border-bottom: 2px solid #0EA5E9 !important;
    font-weight: 600;
}

/* DataFrame */
div[data-testid="stDataFrame"] {
    border: 1px solid #1E2A45;
    border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.15);
}

/* Alerts */
div[data-testid="stAlert"] { border-radius: 8px; }

/* Expander headers */
details summary {
    font-weight: 500 !important;
    letter-spacing: 0.01em;
}

/* Header badge */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    vertical-align: middle;
}
.badge-solar  { background: rgba(250,204,21,0.12); color: #FACC15; border: 1px solid #FACC1530; }
.badge-wind   { background: rgba(14,165,233,0.12); color: #0EA5E9; border: 1px solid #0EA5E930; }
.badge-hybrid { background: rgba(52,211,153,0.12); color: #34D399; border: 1px solid #34D39930; }

/* Context bar */
.context-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #64748B;
    font-size: 0.82rem;
    margin-top: 0;
    padding: 0;
}
.context-bar .sep { color: #334155; }

/* Section heading */
.section-heading {
    font-size: 1.15rem;
    font-weight: 600;
    color: #E8EAF0;
    margin: 1.2rem 0 0.6rem 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #1E2A45;
}

/* Recommendation box */
.rec-box {
    background: linear-gradient(135deg, #161B2E, #0D1321);
    border: 1px solid #0EA5E933;
    border-left: 4px solid #0EA5E9;
    border-radius: 10px;
    padding: 20px 24px;
    margin: 12px 0;
    box-shadow: 0 2px 12px rgba(14,165,233,0.08);
}
.rec-box h4 { color: #0EA5E9 !important; }

/* Divider */
.subtle-divider {
    border: none;
    border-top: 1px solid #1E2A45;
    margin: 1.5rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Sidebar (slim: Location + Generation + Miner only) ─────────────────────

def render_sidebar() -> dict:
    """Render sidebar input widgets and return a dict of user selections."""
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand">'
            '<h2><span>Grid</span>Stack OS</h2>'
            '<p>HYBRID BTC MINING + BESS SITE MODELER</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Location ─────────────────────────────────────────────────────
        st.markdown("### LOCATION")
        _state_opts = sorted(STATE_CITIES.keys())
        state = st.selectbox("State", options=_state_opts, index=42)  # default: Texas
        cities = STATE_CITIES.get(state, ["—"])
        # Default to Lubbock when Texas is selected, otherwise first city
        _city_default = cities.index("Lubbock") if (state == "Texas" and "Lubbock" in cities) else 0
        city  = st.selectbox("City / Hub", options=cities, index=_city_default)
        iso   = get_iso_for_state(state)
        st.caption(f"ISO/RTO: **{iso}**")

        # ── Generation ────────────────────────────────────────────────────
        st.markdown("### GENERATION ASSET")
        gen_type = st.radio(
            "Resource Type", ["Solar", "Wind", "Hybrid"],
            horizontal=True, index=0,
        )
        if gen_type == "Hybrid":
            solar_pct = st.slider(
                "Solar Mix (%)", 10, 90, 50, step=5,
                help="Share of nameplate capacity sourced from solar. Remainder is wind.",
            )
            solar_frac = solar_pct / 100.0
            st.caption(f"☀️ {solar_pct}% Solar · 💨 {100 - solar_pct}% Wind")
        else:
            solar_frac = 1.0 if gen_type == "Solar" else 0.0
        capacity_mw = st.slider(
            "Nameplate Capacity (MW AC)", 1, 500, 100, step=5,
        )
        coupling = st.radio(
            "Coupling Configuration",
            ["AC-Coupled", "DC-Coupled"],
            horizontal=True, index=0,
            help=(
                "AC-Coupled: inverter clips excess DC generation.\n"
                "DC-Coupled: battery charges directly from DC bus, capturing clipped energy."
            ),
        )
        connection = st.radio(
            "Grid Connection",
            ["Grid-Tied", "Behind-the-Meter (BTM)"],
            horizontal=True, index=0,
        )
        interconnection_mw = st.slider(
            "Interconnection Limit (MW)", 1, capacity_mw, capacity_mw, step=1,
            help="Maximum MW you can export to the grid per your interconnection agreement.",
        )

        # ── BTC Miner Settings ────────────────────────────────────────────
        st.markdown("### BTC MINER")
        efficiency_jth = st.slider(
            "Miner Efficiency (J/TH)", 5.0, 50.0, 18.0, step=0.5,
            help="Joules per terahash — lower = more efficient. S21 XP ≈ 13.5 J/TH.",
        )
        hw_cost_per_th = st.slider(
            "Hardware Cost ($/TH)", 4.0, 30.0, 12.0, step=0.5,
            help="Upfront cost per terahash of mining hashrate.",
        )
        _live_hp = fetch_live_hashprice()
        _hp_default = _live_hp if _live_hp is not None else 0.030
        if _live_hp is not None:
            st.caption(f"⚡ Live hashprice: **${_live_hp:.4f}/TH/day** · hashrateindex.com")
        else:
            st.caption("⚡ Hashprice: using default (live fetch unavailable)")
        hashprice = st.slider(
            "Network Hashprice ($/TH/day)", 0.001, 0.300, _hp_default, step=0.001,
            format="$%.3f",
            help="Expected daily mining revenue per TH. Auto-loaded from Hashrate Index on startup.",
        )

        # ── API Keys (optional) ────────────────────────────────────────
        with st.expander("API Settings", expanded=False):
            _nrel_default = st.secrets.get("NREL_API_KEY", "")
            nrel_key = st.text_input(
                "NREL API Key",
                value=_nrel_default,
                type="password",
                help="Free at https://developer.nrel.gov — unlocks live PVWatts data.",
            )
            _gs_default = st.secrets.get("GRIDSTATUS_API_KEY", "")
            gridstatus_key = st.text_input(
                "GridStatus API Key",
                value=_gs_default,
                type="password",
                help="Free at https://www.gridstatus.io — unlocks live ISO LMP data.",
            )

        st.markdown(
            '<div class="sidebar-footer">'
            '<span class="version">v1.0.0</span>'
            '<p class="powered">Streamlit + Plotly</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    return dict(
        state=state, city=city, iso=iso,
        gen_type=gen_type, solar_frac=solar_frac, capacity_mw=capacity_mw,
        coupling=coupling.split("-")[0],           # "AC" or "DC"
        grid_tied=(connection == "Grid-Tied"),
        interconnection_mw=interconnection_mw,
        efficiency_jth=efficiency_jth,
        hw_cost_per_th=hw_cost_per_th,
        hashprice=hashprice,
        nrel_key=nrel_key or "DEMO_KEY",
        gridstatus_key=gridstatus_key,
    )


# ─── Data Loading (cached) ────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def load_generation(gen_type, solar_frac, capacity_mw, state, city, coupling, nrel_key):
    if gen_type == "Solar":
        # Try live PVWatts if key provided
        if nrel_key and nrel_key != "DEMO_KEY":
            result = fetch_pvwatts(city, capacity_mw * 1_000, api_key=nrel_key)
            if result:
                gen_mwh = result["ac_kwh"] / 1_000   # kWh → MWh per hour
                return {
                    "generation_mwh": gen_mwh,
                    "clipped_mwh": np.zeros(8760),
                    "bess_dc_avail_mwh": np.zeros(8760),
                    "annual_cf": float(gen_mwh.sum() / (capacity_mw * 8760)),
                    "source": result["source"],
                    "live": True,
                }
        return synthetic_solar_profile(capacity_mw, state, city, coupling)
    elif gen_type == "Wind":
        return synthetic_wind_profile(capacity_mw, state)
    else:  # Hybrid
        wind_frac = 1.0 - solar_frac
        solar = synthetic_solar_profile(capacity_mw * solar_frac, state, city, coupling)
        wind  = synthetic_wind_profile(capacity_mw * wind_frac, state)
        blended = solar["generation_mwh"] + wind["generation_mwh"]
        blended_cf = float(blended.sum() / (capacity_mw * 8760))
        return {
            "generation_mwh":    blended,
            "clipped_mwh":       solar["clipped_mwh"] + wind.get("clipped_mwh", np.zeros(8760)),
            "bess_dc_avail_mwh": solar.get("bess_dc_avail_mwh", np.zeros(8760)),
            "annual_cf":         blended_cf,
            "source":            f"Hybrid ({int(solar_frac*100)}% Solar + {int(wind_frac*100)}% Wind) synthetic profile",
            "live":              False,
        }


@st.cache_data(show_spinner=False, ttl=3600)
def load_lmp(iso, gen_type, gridstatus_key=""):
    if gridstatus_key:
        live = load_lmp_gridstatus(iso, gridstatus_key)
        if live is not None:
            return live
    return synthetic_lmp_profile(iso, gen_type)


# ─── BESS Pack Recommendation ────────────────────────────────────────────────

def bess_pack_rationale(iso, gen_type, solar_frac, ancillary_premium, bess_n, preset):
    """
    Build a markdown explanation of why the selected BESS pack count/type
    is appropriate for this ISO, generation type, and market conditions.

    Scoring: Pack 1 (2hr/high-power) vs Pack 2 (4hr/arbitrage duration)
    Drivers: ancillary premium, price spread, gen shape, negative-price frequency.
    """
    lmp_stats   = HISTORICAL_LMP.get(iso, HISTORICAL_LMP["PJM"])
    spread      = lmp_stats.get("spread", 0)       # peak – offpeak $/MWh
    neg_pct     = lmp_stats.get("negative_pct", 0) # % of hours negative

    p1_score, p2_score = 0, 0
    p1_drivers, p2_drivers = [], []

    # ── Ancillary premium ────────────────────────────────────────────────
    if ancillary_premium >= 18:
        p1_score += 3
        p1_drivers.append(
            f"**{iso} ancillary premium: ${ancillary_premium:.0f}/MWh** (top tier nationally) — "
            "frequency regulation and fast-frequency response (FFR/ECRS) programs strongly reward "
            "high-power, fast-cycling assets; 2-hour packs maximise registration capacity in these programmes"
        )
    elif ancillary_premium >= 14:
        p1_score += 1
        p1_drivers.append(
            f"**{iso} ancillary premium: ${ancillary_premium:.0f}/MWh** (solid) — "
            "spinning reserve and regulation markets add meaningful $/MWh uplift to shorter, high-power cycles"
        )
    elif ancillary_premium >= 10:
        p2_score += 1
        p2_drivers.append(
            f"**{iso} ancillary premium: ${ancillary_premium:.0f}/MWh** (moderate) — "
            "energy arbitrage is more dominant than ancillary income; duration adds more value than peak power"
        )
    else:
        p2_score += 2
        p2_drivers.append(
            f"**{iso} ancillary premium: ${ancillary_premium:.0f}/MWh** (low) — "
            "mostly bilateral contracts with limited real-time ancillary market; "
            "4-hour duration captures more of the daily price spread"
        )

    # ── Price spread (peak – offpeak) ────────────────────────────────────
    if spread >= 60:
        p2_score += 3
        p2_drivers.append(
            f"**{iso} peak/off-peak spread: ${spread:.0f}/MWh** (wide) — "
            "large price differential persists over 3-5 hours; 4-hour packs capture the full "
            "morning-peak and evening-peak windows without truncation"
        )
    elif spread >= 45:
        p2_score += 1
        p2_drivers.append(
            f"**{iso} spread: ${spread:.0f}/MWh** (medium) — "
            "4-hour duration adds marginal arbitrage upside over the 2-hour alternative"
        )
    else:
        p1_score += 1
        p1_drivers.append(
            f"**{iso} spread: ${spread:.0f}/MWh** (narrow) — "
            "short, sharp price spikes dominate over sustained differentials; "
            "high-power 2hr packs respond faster and earn more per MWh on brief peaks"
        )

    # ── Generation shape ─────────────────────────────────────────────────
    if gen_type == "Solar":
        p1_score += 2
        p1_drivers.append(
            "**Solar generation profile** — the 'Duck Curve' creates a 2–3 hour discharge window "
            "at sunset when net load spikes; 2hr/high-power packs are optimally sized for this "
            "predictable daily pattern and capture clipped inverter energy during midday peak"
        )
    elif gen_type == "Wind":
        p2_score += 2
        p2_drivers.append(
            "**Wind generation profile** — overnight low-price curtailment windows extend 4–8 hours; "
            "4hr packs absorb more curtailed energy and discharge across a broader morning/evening "
            "demand window, reducing the number of partial cycles"
        )
    else:  # Hybrid
        if solar_frac >= 0.6:
            p1_score += 1
            p1_drivers.append(
                f"**Hybrid profile ({int(solar_frac*100)}% solar-dominant)** — "
                "solar duck-curve shape slightly favours 2hr high-power discharge"
            )
        elif solar_frac <= 0.4:
            p2_score += 1
            p2_drivers.append(
                f"**Hybrid profile ({int((1-solar_frac)*100)}% wind-dominant)** — "
                "wind overnight curtailment slightly favours 4hr duration"
            )
        else:
            p2_drivers.append(
                f"**Hybrid profile (50/50 mix)** — balanced generation shape; "
                "4hr duration provides flexibility across both solar and wind dispatch windows"
            )
            p2_score += 1

    # ── Negative-price frequency ─────────────────────────────────────────
    if neg_pct >= 6:
        p1_score += 2
        p1_drivers.append(
            f"**Negative LMP frequency: {neg_pct:.1f}% of hours** — high cycling environment; "
            "2hr high-power packs charge quickly during negative-price events and discharge "
            "rapidly at the next peak, completing more profitable full cycles per year"
        )
    elif neg_pct >= 4:
        p1_score += 1
        p1_drivers.append(
            f"**Negative LMP frequency: {neg_pct:.1f}% of hours** — moderate cycling; "
            "some benefit to high-power fast-charge capability"
        )
    else:
        p2_score += 1
        p2_drivers.append(
            f"**Negative LMP frequency: {neg_pct:.1f}% of hours** (low) — "
            "infrequent cycling means duration matters more than peak power per cycle"
        )

    # ── Determine recommended pack ───────────────────────────────────────
    rec_is_p1    = p1_score >= p2_score
    sel_is_p1    = preset["label"] == "Pack 1"
    is_optimal   = rec_is_p1 == sel_is_p1
    rec_label    = "Pack 1 — 1.9 MW / 2 hr (high-power)" if rec_is_p1 else "Pack 2 — 1.0 MW / 4 hr (long-duration)"
    winning_drivers = p1_drivers if rec_is_p1 else p2_drivers

    status_line = (
        f"✅ **{preset['label']} is the recommended configuration for {iso}**"
        if is_optimal else
        f"⚠️ **Consider switching to {rec_label}** — it scores higher for {iso} "
        f"(score: Pack 1 = {p1_score}, Pack 2 = {p2_score})"
    )

    lines = [
        f"**{bess_n} × Tesla Megapack {preset['label']}** "
        f"({preset['power_mw']} MW / {preset['duration_hr']} hr each · "
        f"{bess_n * preset['energy_mwh']:.1f} MWh total · "
        f"${bess_n * preset['cost_usd'] / 1e6:.2f}M deployed)",
        "",
        status_line,
        "",
        f"**Why {preset['label']} fits this site** *(score: Pack 1 = {p1_score}, Pack 2 = {p2_score})*:",
    ]
    for d in winning_drivers:
        lines.append(f"- {d}")

    return "\n".join(lines)


def grid_btm_insight(
    gen_type: str,
    solar_frac: float,
    grid_tied: bool,
    annual_cf: float,
    lmp_arr,
    be_price_mwh: float,
    total_annual_rev: float,
    annual_rev_mine: float,
    annual_rev_import: float,
    mining_util: float,
    bess_split: float,
    mine_split: float,
) -> str:
    """
    Generate a dynamic narrative comparing Grid-Tied vs BTM dispatch economics,
    tailored to the current gen type, mode, and live simulation outputs.
    """
    import numpy as np

    # ── Analytical counterfactual estimates ───────────────────────────────
    # Grid-Tied: miners run every hour LMP < break-even (estimated from LMP profile)
    gt_util_est  = float((np.asarray(lmp_arr) < be_price_mwh).mean())
    # BTM: miners limited to on-site generation hours ≈ capacity factor
    btm_util_est = annual_cf

    # Revenue uplift going from BTM → Grid-Tied (relative to GT potential)
    btm_hit_pct  = max(0.0, (gt_util_est - btm_util_est) / max(gt_util_est, 0.001) * 100)

    bess_pct = int(round(bess_split * 100))
    mine_pct = int(round(mine_split * 100))

    # ── Gen-type labels ───────────────────────────────────────────────────
    if gen_type == "Hybrid":
        sol_pct_int  = int(round(solar_frac * 100))
        wind_pct_int = 100 - sol_pct_int
        gen_label    = f"{sol_pct_int}% Solar / {wind_pct_int}% Wind Hybrid"
        gen_shape    = "mixed day-and-night"
    elif gen_type == "Wind":
        gen_label = "Wind"
        gen_shape = "round-the-clock (day & night)"
    else:
        gen_label = "Solar"
        gen_shape = "daytime-only"

    mode_str  = "Grid-Tied" if grid_tied else "Behind-the-Meter (BTM)"
    idle_pct  = (1.0 - mining_util) * 100

    lines = []

    # ── 1. Current mode headline ──────────────────────────────────────────
    lines.append(f"#### {mode_str} · {gen_label}")
    lines.append("")

    if grid_tied:
        lines.append(
            f"Miners are running **{mining_util:.0%}** of all hours — the grid connection "
            f"allows importing power whenever LMP < break-even (${be_price_mwh:.0f}/MWh), "
            f"keeping miners active well beyond the site's **{annual_cf:.0%}** capacity factor."
        )
        if annual_rev_import > 0:
            lines.append(
                f"Grid import net P&L: **${annual_rev_import:,.0f}** earned — "
                f"negative-LMP windows paid the site to consume power, running miners at zero "
                f"(or negative) fuel cost."
            )
        elif annual_rev_import < 0:
            lines.append(
                f"Grid import cost: **${abs(annual_rev_import):,.0f}** — cheap off-peak power "
                f"purchased to run miners profitably overnight (cost < mining profit)."
            )
    else:
        lines.append(
            f"Miners are running **{mining_util:.0%}** of all hours — BTM limits operation "
            f"to on-site generation only ({gen_shape}, CF **{annual_cf:.0%}**). "
            f"Miners sit idle **{idle_pct:.0f}%** of the year with no grid import available."
        )

    lines.append("")

    # ── 2. Grid-Tied vs BTM impact (gen-type specific) ────────────────────
    lines.append("**Grid-Tied vs BTM Impact**")
    lines.append("")

    if gen_type == "Solar":
        solar_btm_idle = (1.0 - btm_util_est) * 100
        lines.append(
            f"Solar is the most BTM-sensitive resource: its **{annual_cf:.0%} CF** means miners "
            f"would sit idle ~{solar_btm_idle:.0f}% of the year in BTM mode. "
            f"Grid-Tied miners can run ~{gt_util_est:.0%} of hours — a "
            f"**~{btm_hit_pct:.0f}% mining revenue uplift** vs BTM."
        )
        lines.append(
            f"The **{bess_pct}% BESS / {mine_pct}% Miners** split leans into BESS because "
            f"solar's midday Duck Curve creates a predictable arbitrage window: "
            f"charge at noon, discharge at the 4–8 pm evening price spike."
        )

    elif gen_type == "Wind":
        wind_btm_idle = (1.0 - btm_util_est) * 100
        lines.append(
            f"Wind's {gen_shape} profile (CF **{annual_cf:.0%}**) means miners stay productive "
            f"overnight even in BTM — idle only ~{wind_btm_idle:.0f}% of the year. "
            f"Grid-Tied miners can run ~{gt_util_est:.0%} of hours — a "
            f"**~{btm_hit_pct:.0f}% mining revenue uplift** vs BTM."
        )
        lines.append(
            f"The **{mine_pct}% Miners / {bess_pct}% BESS** split favours miners heavily because "
            f"wind curtails overnight when prices are already low — miners are the perfect "
            f"flexible load to absorb every curtailed MWh. "
            f"BESS arbitrage value is lower without a daily Duck Curve signal."
        )

    else:  # Hybrid
        sol_pct_i = int(round(solar_frac * 100))
        wnd_pct_i = 100 - sol_pct_i
        lines.append(
            f"The {sol_pct_i}/{wnd_pct_i} Solar/Wind blend achieves **{annual_cf:.0%} CF**, "
            f"spreading generation across more hours than pure solar and smoothing overnight "
            f"curtailment vs pure wind. "
            f"Grid-Tied miners can run ~{gt_util_est:.0%} of hours — "
            f"a **~{btm_hit_pct:.0f}% mining revenue uplift** vs BTM."
        )
        lines.append(
            f"Capital split **{bess_pct}% BESS / {mine_pct}% Miners** blends both strategies: "
            f"BESS handles the solar Duck Curve portion; miners absorb the wind overnight curtailment."
        )

    lines.append("")

    # ── 3. Contextual call-out ────────────────────────────────────────────
    if grid_tied and gen_type == "Wind":
        lines.append(
            f"**Wind + Grid-Tied is the strongest miner configuration**: "
            f"overnight negative-LMP windows let the grid *pay you* to run miners, "
            f"while daytime exports capture peak prices wind naturally misses at night."
        )
    elif grid_tied and gen_type == "Solar":
        lines.append(
            f"**Grid-Tied Solar adds overnight mining**: BESS captures midday solar for "
            f"evening arbitrage while the grid connection lets miners run all night on cheap "
            f"off-peak power — miner utilisation rises from ~{annual_cf:.0%} to ~{mining_util:.0%}."
        )
    elif not grid_tied and gen_type == "Wind":
        lines.append(
            f"**BTM Wind is still competitive**: wind's **{annual_cf:.0%} CF** means miners "
            f"run {mining_util:.0%} of the year even without the grid — comparable to a "
            f"Grid-Tied Solar site. Grid-Tied would push miner uptime to ~{gt_util_est:.0%}."
        )
    elif not grid_tied and gen_type == "Solar":
        lines.append(
            f"**BTM Solar trades revenue for simplicity**: no interconnection costs or grid "
            f"exposure, but miners only run when the sun shines ({mining_util:.0%} utilisation). "
            f"Switching to Grid-Tied could unlock ~{btm_hit_pct:.0f}% more mining revenue."
        )
    elif gen_type == "Hybrid":
        if grid_tied:
            lines.append(
                f"**Hybrid + Grid-Tied maximises flexibility**: solar provides the BESS arbitrage "
                f"signal; wind extends mining hours overnight; the grid fills remaining gaps — "
                f"miners run {mining_util:.0%} of all hours."
            )
        else:
            lines.append(
                f"**Hybrid BTM smooths the BTM penalty**: the wind component keeps miners running "
                f"overnight even without grid import, softening the revenue hit vs pure solar BTM. "
                f"Grid-Tied would push uptime from {mining_util:.0%} to ~{gt_util_est:.0%}."
            )

    # Escape $ so Streamlit doesn't treat monetary values as LaTeX math delimiters
    import re
    result = "\n".join(lines)
    result = re.sub(r'\$(-?[\d,])', r'\\$\1', result)
    return result


# ─── Helper Functions ─────────────────────────────────────────────────────────

def fmt_irr(irr_val):
    """Format an IRR value for display."""
    if irr_val is None:
        return "N/A"
    return f"{irr_val * 100:.1f}%"


def render_bess_inputs() -> dict:
    """Render BESS configuration widgets (placed inline in Dispatch tab)."""
    st.markdown("##### BESS Configuration (Tesla Megapack)")
    col_pack, col_n = st.columns(2)
    with col_pack:
        pack_key = st.selectbox(
            "Megapack Preset",
            options=list(MEGAPACK_PRESETS.keys()),
            index=0,
        )
    with col_n:
        n_packs_manual = st.number_input(
            "Number of Packs (manual)", min_value=0, max_value=500,
            value=0, step=1,
            help="Set to 0 to use the auto capital-allocation calculator.",
        )
    return {"pack_key": pack_key, "n_packs_manual": n_packs_manual}


def render_financial_inputs() -> dict:
    """Render ITC and Capital Budget widgets (placed inline in Financials tab)."""
    col_itc, col_budget = st.columns(2)

    with col_itc:
        st.markdown("##### Investment Tax Credit (ITC)")
        itc_base = st.checkbox("30% Base ITC (Section 48E)", value=True, disabled=True)
        itc_domestic = st.checkbox("+ 10% Domestic Content Adder", value=True)
        underserved_label = st.radio(
            "Underserved Community Adder",
            options=list(UNDERSERVED_OPTIONS.keys()),
            index=0,
        )
        underserved_rate = UNDERSERVED_OPTIONS[underserved_label]
        itc_rate = 0.30 + (0.10 if itc_domestic else 0.0) + underserved_rate
        st.info(f"**Total ITC: {itc_rate:.0%}** (Base 30% + Adders)")

    with col_budget:
        st.markdown("##### Capital Budget")
        budget_m = st.number_input(
            "Total Investment Budget ($M)", min_value=0.5, max_value=500.0,
            value=10.0, step=0.5,
        )
        budget = budget_m * 1_000_000

    return {"itc_rate": itc_rate, "budget": budget}


# ─── PDF Export ──────────────────────────────────────────────────────────────

def generate_executive_pdf(inp, iso, hybrid_irr, total_annual_rev,
                           rec_text, bess_n, preset, bess_cost,
                           miner_budget, mining_th, itc_rate,
                           itc_savings_bess, budget, irr_str,
                           bess_power_mw, bess_energy) -> bytes:
    """Generate a 1-page executive summary PDF and return raw bytes."""
    def _ascii(text: str) -> str:
        """Replace common Unicode chars with ASCII for Helvetica compatibility."""
        return (text
                .replace("\u2014", "--")   # em-dash
                .replace("\u2013", "-")    # en-dash
                .replace("\u2018", "'")    # left single quote
                .replace("\u2019", "'")    # right single quote
                .replace("\u201c", '"')    # left double quote
                .replace("\u201d", '"')    # right double quote
                .replace("\u2026", "...")  # ellipsis
                .replace("\u00b7", "-")    # middle dot
                .replace("\u2022", "-")    # bullet
                .replace("\u00d7", "x")    # multiplication sign
                .replace("\u2248", "~")    # approx
                )

    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Colors ──
    DARK = (14, 17, 23)
    ACCENT = (14, 165, 233)
    WHITE = (232, 234, 240)
    MUTED = (148, 163, 184)
    CARD_BG = (22, 27, 46)

    # ── Background ──
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 216, 280, "F")

    # ── Header ──
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 10, "GRIDSTACK OS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    _conn = "Grid-Tied" if inp["grid_tied"] else "BTM"
    pdf.cell(0, 5,
             _ascii(f"Executive Summary  |  {inp['city']}, {inp['state']}  |  "
                    f"{inp['capacity_mw']} MW {inp['gen_type']}  |  {_conn}  |  {iso}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Generated {_date.today().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── Divider ──
    def draw_divider():
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 206, pdf.get_y())
        pdf.ln(4)

    draw_divider()

    # ── Section helper ──
    def section_title(title):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACCENT)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ── KEY METRICS ──
    section_title("KEY METRICS")
    kpi_w = 47
    kpi_h = 16

    irr_val = hybrid_irr.get("irr")
    payback = hybrid_irr.get("payback_years", "N/A")
    npv = hybrid_irr.get("npv_8pct", 0)

    kpis = [
        ("Blended IRR", irr_str),
        ("Payback Period", f"{payback} yrs" if isinstance(payback, (int, float)) else str(payback)),
        ("Annual Revenue", f"${total_annual_rev:,.0f}"),
        ("NPV @ 8%", f"${npv / 1e6:.2f}M"),
    ]

    for label, value in kpis:
        pdf.set_fill_color(*CARD_BG)
        pdf.set_draw_color(30, 42, 69)
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        pdf.rect(x0, y0, kpi_w, kpi_h, "DF")
        pdf.set_xy(x0 + 3, y0 + 2)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.cell(kpi_w - 6, 4, label)
        pdf.set_xy(x0 + 3, y0 + 7)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*WHITE)
        pdf.cell(kpi_w - 6, 7, value)
        pdf.set_xy(x0 + kpi_w + 1, y0)

    pdf.ln(kpi_h + 4)
    draw_divider()

    # ── RECOMMENDED STRATEGY ──
    section_title("RECOMMENDED STRATEGY")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*WHITE)
    # Strip markdown bold markers and sanitize for PDF
    clean_rec = _ascii(rec_text.replace("**", "").replace("*", ""))
    pdf.multi_cell(0, 5, clean_rec)
    pdf.ln(3)
    draw_divider()

    # ── CAPITAL ALLOCATION ──
    section_title("CAPITAL ALLOCATION")
    bess_pct = bess_cost / budget * 100 if budget > 0 else 0
    miner_pct = miner_budget / budget * 100 if budget > 0 else 0

    alloc_data = [
        ("BESS (Megapacks)", f"${bess_cost / 1e6:.2f}M", f"{bess_pct:.1f}%"),
        ("BTC Miners", f"${miner_budget / 1e6:.2f}M", f"{miner_pct:.1f}%"),
        ("ITC Savings", f"${itc_savings_bess / 1e6:.2f}M", f"{itc_rate:.0%} rate"),
    ]
    col_widths = [70, 40, 40]
    # Header row
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.set_fill_color(*CARD_BG)
    for w, h in zip(col_widths, ["Category", "Amount", "Share"]):
        pdf.cell(w, 6, h, border=0, fill=True)
    pdf.ln()
    # Data rows
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*WHITE)
    for cat, amt, share in alloc_data:
        pdf.cell(col_widths[0], 6, cat, border=0)
        pdf.cell(col_widths[1], 6, amt, border=0)
        pdf.cell(col_widths[2], 6, share, border=0)
        pdf.ln()

    pdf.ln(3)
    draw_divider()

    # ── DEPLOYMENT SUMMARY ──
    section_title("DEPLOYMENT SUMMARY")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*WHITE)
    lines = [
        f"Total Budget: ${budget / 1e6:.1f}M across a {inp['gen_type']} hybrid site",
        f"BESS: {bess_n} x {preset['label']} Megapacks ({bess_power_mw:.1f} MW / {bess_energy:.1f} MWh) -- ${bess_cost / 1e6:.2f}M",
        f"Mining: {mining_th:,.0f} TH at {inp['efficiency_jth']} J/TH -- ${miner_budget / 1e6:.2f}M",
        f"ITC: {itc_rate:.0%} reduces effective BESS CapEx by ${itc_savings_bess / 1e6:.2f}M",
        f"Projected Blended IRR: {irr_str} | Annual Revenue: ${total_annual_rev:,.0f}",
    ]
    for line in lines:
        pdf.cell(0, 5.5, _ascii(line), new_x="LMARGIN", new_y="NEXT")

    # ── Footer ──
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, f"GridStack OS v1.0.0  |  Generated {_date.today().isoformat()}", align="C")

    return bytes(pdf.output())


# ─── Sensitivity Engine ──────────────────────────────────────────────────────

def run_sensitivity(inp, iso, gen_mwh, lmp_mwh, gen_data, lmp_data,
                    budget, itc_rate, pack_key, bess_split,
                    ancillary_premium, dsumm, bess_n, preset,
                    bess_cost, miner_budget, mining_th, mine_power,
                    be_price_mwh, annual_rev_grid, annual_rev_bess,
                    annual_rev_anc, annual_rev_import, hybrid_irr_base):
    """
    Run IRR sensitivity across 8 key variables.
    Returns list of dicts for the tornado chart.
    """
    base_irr = hybrid_irr_base.get("irr") or 0

    def _irr_for_financial(hp=None, hw=None, bgt=None, itc=None,
                           eff=None, rev_bess_mult=1.0, anc_mult=1.0):
        """Re-run financial model with overridden parameters."""
        _hp  = hp  if hp  is not None else inp["hashprice"]
        _hw  = hw  if hw  is not None else inp["hw_cost_per_th"]
        _bgt = bgt if bgt is not None else budget
        _itc = itc if itc is not None else itc_rate
        _eff = eff if eff is not None else inp["efficiency_jth"]

        # Re-allocate capital if budget or hw changed
        _alloc = allocate_capital(
            _bgt, inp["gen_type"], pack_key, _hw, _eff, _hp, _itc, bess_split,
        )
        _bess_n = _alloc["n_packs"]
        _bess_cost = _alloc["bess_cost"]
        _miner_budget = _alloc["mining_cost"]
        _mining_th = _miner_budget / _hw if _hw > 0 else 0
        _preset = MEGAPACK_PRESETS[pack_key]

        # Scale dispatch-dependent revenues
        _rev_bess = annual_rev_bess * rev_bess_mult
        _rev_anc  = annual_rev_anc * anc_mult
        _rev_mine = mining_revenue_annual(_mining_th, _hp) * dsumm["mining_utilization"]

        _cfs = build_annual_cashflows(
            gen_type=inp["gen_type"],
            solar_frac=inp["solar_frac"],
            capacity_mw=inp["capacity_mw"],
            hashrate_th=_mining_th,
            hashprice_per_th_day=_hp,
            efficiency_jth=_eff,
            bess_packs=_bess_n,
            pack_preset=_preset,
            ancillary_premium=ancillary_premium * anc_mult,
            annual_rev_grid=annual_rev_grid,
            annual_rev_bess=_rev_bess,
            annual_rev_ancillary=_rev_anc,
            annual_rev_import=annual_rev_import,
            itc_rate=_itc,
        )
        result = compute_irr_roi(_bgt, _cfs["hybrid_cfs"], _itc)
        return result.get("irr") or 0

    # Define sensitivity sweeps
    hp = inp["hashprice"]
    bgt = budget
    itc = itc_rate
    hw = inp["hw_cost_per_th"]
    eff = inp["efficiency_jth"]

    sweeps = [
        {
            "name": "Hashprice ($/TH/day)",
            "low_irr":  _irr_for_financial(hp=hp * 0.70),
            "high_irr": _irr_for_financial(hp=hp * 1.30),
        },
        {
            "name": "Total Budget ($M)",
            "low_irr":  _irr_for_financial(bgt=bgt * 0.70),
            "high_irr": _irr_for_financial(bgt=bgt * 1.30),
        },
        {
            "name": "ITC Rate (%)",
            "low_irr":  _irr_for_financial(itc=max(0, itc - 0.10)),
            "high_irr": _irr_for_financial(itc=min(0.60, itc + 0.10)),
        },
        {
            "name": "Hardware Cost ($/TH)",
            "low_irr":  _irr_for_financial(hw=hw * 1.25),   # higher cost = worse
            "high_irr": _irr_for_financial(hw=hw * 0.75),   # lower cost = better
        },
        {
            "name": "Miner Efficiency (J/TH)",
            "low_irr":  _irr_for_financial(eff=eff * 1.15),  # worse efficiency
            "high_irr": _irr_for_financial(eff=eff * 0.85),  # better efficiency
        },
        {
            "name": "BESS Arb. Revenue",
            "low_irr":  _irr_for_financial(rev_bess_mult=0.75),
            "high_irr": _irr_for_financial(rev_bess_mult=1.25),
        },
        {
            "name": "Ancillary Premium ($/MWh)",
            "low_irr":  _irr_for_financial(anc_mult=0.60),
            "high_irr": _irr_for_financial(anc_mult=1.40),
        },
        {
            "name": "Generation Capacity (MW)",
            "low_irr":  _irr_for_financial(bgt=bgt * 0.80),  # proxy: smaller site
            "high_irr": _irr_for_financial(bgt=bgt * 1.20),  # proxy: larger site
        },
    ]

    return sweeps, base_irr


# ─── Main App ─────────────────────────────────────────────────────────────────

def main():
    # ── Portfolio session state ───────────────────────────────────────────
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = []

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1: Sidebar inputs (slim)
    # ══════════════════════════════════════════════════════════════════════
    inp = render_sidebar()

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: Data loading (only needs sidebar inputs)
    # ══════════════════════════════════════════════════════════════════════
    with st.spinner("Fetching generation & pricing data…"):
        gen_data = load_generation(
            inp["gen_type"], inp["solar_frac"], inp["capacity_mw"], inp["state"],
            inp["city"], inp["coupling"], inp["nrel_key"],
        )
        lmp_data = load_lmp(inp["iso"], inp["gen_type"], inp.get("gridstatus_key", ""))

    gen_mwh  = gen_data["generation_mwh"]
    lmp_mwh  = lmp_data["lmp_mwh"]
    iso      = inp["iso"]

    # Derived quantities that only need sidebar inputs
    ancillary_premium = ANCILLARY_PREMIUMS.get(iso, 10.0)
    be_price_kwh      = mining_break_even_price(inp["efficiency_jth"], inp["hashprice"])
    be_price_mwh      = be_price_kwh * 1_000

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3: Header + Data Disclosure
    # ══════════════════════════════════════════════════════════════════════
    _badge_cls = "solar" if inp["gen_type"] == "Solar" else ("wind" if inp["gen_type"] == "Wind" else "hybrid")
    _badge_lbl = inp["gen_type"] if inp["gen_type"] != "Hybrid" else f"Hybrid {int(inp['solar_frac']*100)}S / {int((1-inp['solar_frac'])*100)}W"
    gen_badge = f'<span class="badge badge-{_badge_cls}">{_badge_lbl}</span>'
    _conn = "Grid-Tied" if inp["grid_tied"] else "BTM"
    st.markdown(
        f'<h1 style="margin-bottom:2px;font-weight:700;letter-spacing:-0.02em">'
        f'<span style="color:#0EA5E9">Grid</span>Stack OS '
        f'{gen_badge}</h1>'
        f'<div class="context-bar">'
        f'{inp["city"]}, {inp["state"]}'
        f'<span class="sep">/</span>'
        f'{inp["capacity_mw"]} MW {inp["gen_type"]}'
        f'<span class="sep">/</span>'
        f'{_conn}'
        f'<span class="sep">/</span>'
        f'{iso}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── How It Works — onboarding guide for new users ─────────────────────
    with st.expander("How It Works — New User Guide", expanded=False):
        st.markdown("""
**What is GridStack OS?**

GridStack OS models the economics of co-locating **solar or wind generation** with
**Bitcoin miners** and **battery storage (BESS)** at a single site. Instead of
selling all your power to the grid at volatile wholesale prices, the app
simulates a *synergy dispatch* strategy that stacks **four revenue streams**:

1. **Grid Export** — sell surplus generation at market price (LMP)
2. **BTC Mining** — convert cheap or curtailed electricity into Bitcoin
3. **BESS Arbitrage** — charge batteries when prices are low, discharge when high
4. **Ancillary Services** — earn standby revenue from frequency regulation markets

The model runs an **8,760-hour dispatch simulation** (one full year, hour-by-hour)
to calculate blended IRR, payback period, and total annual revenue for your
specific site configuration.

---

**Getting Started**

1. **Configure your site** in the left sidebar — pick a state & city, choose
   solar/wind/hybrid, set capacity, and enter your miner hardware specs.
   The budget slider controls how capital is split between BESS and miners.
2. **Review the Executive Summary** (Tab 1) for headline financials — IRR,
   payback period, total revenue, and the recommended BESS/miner split.
3. **Explore the other tabs** for deeper analysis — generation profiles,
   hourly dispatch operations, financial breakdowns, sensitivity, and
   multi-site portfolio comparison.

---

**What Each Tab Shows**

| Tab | What It Shows | Key Metric |
|-----|--------------|------------|
| **Executive Summary** | Top-line financials, recommended strategy, capital allocation | Blended IRR, Payback Period |
| **Site & Generation** | Solar/wind generation profile, LMP heatmap, hourly revenue | Capacity Factor, Avg LMP |
| **Dispatch & Operations** | BESS config, dispatch rules, hourly operational data, 7/30-day performance | Hybrid Uplift vs generation-only |
| **Financials & Allocation** | ITC tax credits, budget split, 25-year cashflows, ancillary revenue | Net BESS CapEx after ITC |
| **Sensitivity** | Tornado chart — which inputs move IRR the most | Top 3 IRR drivers |
| **Portfolio** | Save & compare up to 3 site configurations side by side | Best IRR across sites |

---

**Key Terms**

| Term | Definition |
|------|-----------|
| **LMP** | Locational Marginal Price — the wholesale electricity price at a specific grid node, updated hourly |
| **BESS** | Battery Energy Storage System — grid-scale lithium-ion batteries (Tesla Megapack in this model) |
| **BTM** | Behind-the-Meter — site is not connected to the grid; all power consumed on-site |
| **Grid-Tied** | Site can import from and export to the grid — enables 24/7 mining and grid arbitrage |
| **ITC** | Investment Tax Credit — 30%+ federal tax credit for solar + storage under IRA Section 48E |
| **Synergy Dispatch** | The hour-by-hour algorithm that decides whether to export, mine, charge BESS, or curtail |
| **Ancillary Services** | Revenue from providing grid stability (frequency regulation, spinning reserves) |
| **Hashprice** | Bitcoin mining revenue per terahash per day ($/TH/day) — tracks mining profitability |
| **J/TH** | Joules per Terahash — miner energy efficiency (lower = more efficient; S21 XP ≈ 13.5) |
| **Capacity Factor** | Fraction of time a generator produces at full output (solar ≈ 20-30%, wind ≈ 25-45%) |
| **Megapack** | Tesla's utility-scale battery product — comes in 2hr and 4hr duration configurations |
| **IRR** | Internal Rate of Return — the annualised return on invested capital over the project life |
""")

    _lmp_is_live = lmp_data.get("source", "").startswith("gridstatus.io")
    if _lmp_is_live:
        _lmp_method = (
            "Live day-ahead hourly LMP fetched from gridstatus.io API. "
            "Data covers the trailing 12 months for the selected ISO hub."
        )
        _lmp_ref = f"gridstatus.io ({iso} market data); verified against ISO public dashboards."
    else:
        _lmp_method = (
            "Synthetic hourly LMP profile modelled from ISO-level historical averages, "
            "peak/off-peak ratios, negative-price frequency, and scarcity-spike distributions."
        )
        _lmp_ref = f"EIA Electric Power Monthly (2022–2023); {iso} annual market reports."

    with st.expander("Data Sources & Disclosure", expanded=False):
        st.markdown(f"""
**Electricity Pricing Data**
- Source: {lmp_data['source']}
- Methodology: {_lmp_method}
- Reference: {_lmp_ref}

**Solar/Wind Generation Data**
- Source: {gen_data['source']}
- Methodology: {'Live NREL PVWatts V8 API (NSRDB PSM3 TMY)' if gen_data.get('live') else 'Synthetic physics-based profile calibrated to NREL state-level capacity factors.'}
- Reference: NREL National Solar Radiation Database (NSRDB); NREL Wind Toolkit (WTK).

**Bitcoin Network Data**
- Hashprice: User-supplied (${inp['hashprice']:.3f}/TH/day). Track live at hashrateindex.com.
- Miner efficiency: User-supplied ({inp['efficiency_jth']} J/TH).

**BESS & ITC**
- Megapack specs: Tesla public filings (Pack 1: 1.9 MW/2hr, Pack 2: 1.0 MW/4hr).
- ITC: 30% base rate (IRA Section 48E) + domestic content and energy community adders.
- Ancillary premium: {iso} FERC/ISO market reports (2022–2023 average).

**Disclaimer:** All revenue projections are estimates based on {'live market data' if _lmp_is_live else 'historical data'} and model assumptions.
{'Live LMP data reflects recent market conditions but does not guarantee future prices.' if _lmp_is_live else 'Past LMP patterns do not guarantee future results.'} This tool does not constitute financial or tax advice.
        """)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 4: Create 6 tabs
    # ══════════════════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Executive Summary",
        "Site & Generation",
        "Dispatch & Operations",
        "Financials & Allocation",
        "Sensitivity",
        "Portfolio",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 5: Collect in-tab inputs (before computation pipeline)
    # ══════════════════════════════════════════════════════════════════════
    with tab3:
        bess_inputs = render_bess_inputs()
        st.markdown("---")

    with tab4:
        fin_inputs = render_financial_inputs()
        st.markdown("---")

    pack_key       = bess_inputs["pack_key"]
    n_packs_manual = bess_inputs["n_packs_manual"]
    itc_rate       = fin_inputs["itc_rate"]
    budget         = fin_inputs["budget"]

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 6: Full computation pipeline
    # ══════════════════════════════════════════════════════════════════════

    # Capital allocation
    bess_split, mine_split, rec_text = recommended_split(
        inp["gen_type"], inp["solar_frac"],
        be_price_mwh=be_price_mwh,
        avg_lmp=lmp_data["avg_lmp"],
    )
    alloc = allocate_capital(
        budget=budget,
        gen_type=inp["gen_type"],
        pack_key=pack_key,
        hw_cost_per_th=inp["hw_cost_per_th"],
        efficiency_jth=inp["efficiency_jth"],
        hashprice_per_th_day=inp["hashprice"],
        itc_rate=itc_rate,
        recommended_bess_split=bess_split,
    )

    # Allow manual pack override
    if n_packs_manual > 0:
        preset = MEGAPACK_PRESETS[pack_key]
        bess_n        = n_packs_manual
        bess_power_mw = bess_n * preset["power_mw"]
        bess_energy   = bess_n * preset["energy_mwh"]
        bess_cost     = bess_n * preset["cost_usd"]
        miner_budget  = max(0, budget - bess_cost)
    else:
        preset        = MEGAPACK_PRESETS[pack_key]
        bess_n        = alloc["n_packs"]
        bess_power_mw = alloc["pack_power_mw"]
        bess_energy   = alloc["pack_energy_mwh"]
        bess_cost     = alloc["bess_cost"]
        miner_budget  = alloc["mining_cost"]

    mining_th    = miner_budget / inp["hw_cost_per_th"] if inp["hw_cost_per_th"] > 0 else 0
    mine_power   = mining_power_mw(mining_th, inp["efficiency_jth"])

    # Run dispatch simulation
    with st.spinner("Running synergy dispatch simulation (8760 hours)…"):
        dispatch_df = simulate_synergy_dispatch(
            gen_mwh=gen_mwh,
            lmp_mwh=lmp_mwh,
            break_even_mwh=be_price_mwh,
            bess_power_mw=bess_power_mw,
            bess_energy_mwh=bess_energy,
            mining_power_mw=mine_power,
            interconnection_mw=inp["interconnection_mw"],
            ancillary_premium=ancillary_premium,
            rte=BESS_RTE,
            dc_avail_mwh=gen_data.get("bess_dc_avail_mwh"),
            grid_tied=inp["grid_tied"],
        )
        # Backfill hourly mining revenue (hashrate × hashprice prorated by utilisation)
        if mine_power > 0 and mining_th > 0:
            _hourly_hp = inp["hashprice"] / 24.0          # $/TH per hour
            _frac = dispatch_df["mining_mw"] / mine_power  # fraction of fleet running
            dispatch_df["rev_mining"] = _frac * mining_th * _hourly_hp
        dsumm = dispatch_summary(dispatch_df)

    annual_rev_grid = dsumm["total_rev_grid"]
    annual_rev_bess = dsumm["total_rev_bess"]
    annual_rev_anc  = dsumm["total_rev_ancillary"]
    annual_rev_mine = mining_revenue_annual(mining_th, inp["hashprice"]) * dsumm["mining_utilization"]
    annual_rev_import = dsumm["net_import_revenue"]
    total_annual_rev = annual_rev_grid + annual_rev_bess + annual_rev_anc + annual_rev_mine + annual_rev_import

    # Financial model
    cfs = build_annual_cashflows(
        gen_type=inp["gen_type"],
        solar_frac=inp["solar_frac"],
        capacity_mw=inp["capacity_mw"],
        hashrate_th=mining_th,
        hashprice_per_th_day=inp["hashprice"],
        efficiency_jth=inp["efficiency_jth"],
        bess_packs=bess_n,
        pack_preset=preset,
        ancillary_premium=ancillary_premium,
        annual_rev_grid=annual_rev_grid,
        annual_rev_bess=annual_rev_bess,
        annual_rev_ancillary=annual_rev_anc,
        annual_rev_import=annual_rev_import,
        itc_rate=itc_rate,
    )

    miners_irr  = compute_irr_roi(miner_budget, cfs["miners_cfs"], 0.0)
    bess_irr    = compute_irr_roi(bess_cost,    cfs["bess_cfs"],   itc_rate)
    hybrid_irr  = compute_irr_roi(budget,       cfs["hybrid_cfs"], itc_rate)

    rev_table = generation_revenue_table(gen_mwh, lmp_mwh, inp["grid_tied"])

    ev_table = electron_value_table(
        avg_lmp=lmp_data["avg_lmp"],
        peak_lmp=lmp_data["peak_lmp"],
        break_even_price_kwh=be_price_kwh,
        ancillary_premium_mwh=ancillary_premium,
    )

    # Pre-compute shared values
    itc_savings_bess = bess_cost * itc_rate
    pack_rationale = bess_pack_rationale(
        iso, inp["gen_type"], inp["solar_frac"],
        ancillary_premium, bess_n, preset,
    )

    # Revenue scenario data (used in Tab 1 and Tab 4)
    rev_scenario = {
        "Miners Only": {
            "Grid Export": annual_rev_grid * mine_split,
            "BTC Mining":  annual_rev_mine,
            "BESS Arb.":   0,
            "Ancillary":   0,
        },
        "BESS Only": {
            "Grid Export": annual_rev_grid,
            "BTC Mining":  0,
            "BESS Arb.":   annual_rev_bess,
            "Ancillary":   annual_rev_anc,
        },
        "Hybrid": {
            "Grid Export": annual_rev_grid,
            "BTC Mining":  annual_rev_mine,
            "BESS Arb.":   annual_rev_bess,
            "Ancillary":   annual_rev_anc,
        },
    }

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 7: Populate all tabs with results
    # ══════════════════════════════════════════════════════════════════════

    # ── TAB 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    with tab1:
        # Scenario context bar + download button
        grid_mode = "Grid-Tied" if inp["grid_tied"] else "BTM"
        _ctx_col, _dl_col = st.columns([5, 1])
        with _ctx_col:
            st.markdown(
                f"**{inp['city']}, {inp['state']}** · {inp['capacity_mw']} MW {inp['gen_type']} · "
                f"{grid_mode} · ${budget / 1e6:.1f}M Budget"
            )
        with _dl_col:
            _pdf_bytes = generate_executive_pdf(
                inp=inp, iso=iso, hybrid_irr=hybrid_irr,
                total_annual_rev=total_annual_rev, rec_text=rec_text,
                bess_n=bess_n, preset=preset, bess_cost=bess_cost,
                miner_budget=miner_budget, mining_th=mining_th,
                itc_rate=itc_rate, itc_savings_bess=itc_savings_bess,
                budget=budget, irr_str=fmt_irr(hybrid_irr["irr"]),
                bess_power_mw=bess_power_mw, bess_energy=bess_energy,
            )
            st.download_button(
                "Download PDF",
                data=_pdf_bytes,
                file_name="gridstack-executive-summary.pdf",
                mime="application/pdf",
            )

        # Top KPI row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Blended IRR (Hybrid)", fmt_irr(hybrid_irr["irr"]),
                  help="Internal rate of return on combined investment with ITC.")
        c2.metric("Payback Period", f"{hybrid_irr['payback_years'] or 'N/A'} yrs",
                  help="Years to recover net investment after ITC.")
        c3.metric("Total Annual Revenue", f"${total_annual_rev:,.0f}",
                  help="Grid + Mining + BESS + Ancillary.")
        c4.metric("NPV @ 8%", f"${hybrid_irr['npv_8pct'] / 1e6:.2f}M",
                  help="Net present value at 8% discount rate.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Recommended Strategy
        st.subheader("Recommended Strategy")
        import re as _re
        _safe_rec = _re.sub(r'\$(-?[\d,])', r'&#36;\1', rec_text)
        st.markdown(f'<div class="rec-box">{_safe_rec}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Two-column: Capital allocation pie | Electron value chart
        col_pie, col_ev = st.columns(2)
        with col_pie:
            st.subheader("Capital Allocation")
            st.plotly_chart(
                chart_capital_allocation(bess_cost, miner_budget),
                use_container_width=True, key="exec_cap_alloc",
            )
        with col_ev:
            st.subheader("Highest Value of an Electron")
            st.plotly_chart(chart_electron_value(ev_table), use_container_width=True)

        # Revenue Stack comparison
        st.subheader("Revenue Comparison by Strategy")
        st.plotly_chart(chart_revenue_comparison(rev_scenario), use_container_width=True, key="exec_rev_comp")

        # Condensed recommendation
        hybrid_irr_val = hybrid_irr["irr"]
        irr_str = f"{hybrid_irr_val * 100:.1f}%" if hybrid_irr_val else "N/A"
        st.markdown(f"""
<div class="rec-box">
<h4 style="color:#0EA5E9;margin-top:0">Deployment Summary</h4>
<b>${budget / 1e6:.1f}M</b> across a <b>{inp['gen_type']}</b> site →
<b>{bess_n} × {preset['label']} Megapacks</b> (${bess_cost / 1e6:.2f}M) +
<b>{mining_th:,.0f} TH</b> mining (${miner_budget / 1e6:.2f}M).
ITC saves ${itc_savings_bess / 1e6:.2f}M.
<b>Blended IRR: {irr_str}</b> · Annual revenue: <b>${total_annual_rev:,.0f}</b>.
</div>
        """, unsafe_allow_html=True)

        # ── Model Confidence & Methodology ───────────────────────────────
        lmp_is_live = lmp_data.get("source", "").startswith("gridstatus.io")
        lmp_conf = "High" if lmp_is_live else "Medium"
        lmp_src = "gridstatus.io live ISO data" if lmp_is_live else "Synthetic model calibrated to EIA 2022-2023"
        with st.expander("Model Confidence & Methodology", expanded=False):
            st.markdown(f"""
| Input | Confidence | Source |
|-------|-----------|--------|
| Solar/Wind Capacity Factor | High | NREL PVWatts / Wind Toolkit |
| LMP Profile | {lmp_conf} | {lmp_src} |
| Bitcoin Hashprice | High | User-supplied, verifiable at Hashrate Index |
| Megapack Specs & Cost | High | Tesla public filings |
| ITC Rate (30% + adders) | High | IRA Section 48E statutory rate |
| Miner Efficiency / Cost | High | User-supplied hardware spec |
| Ancillary Service Premium | Medium | FERC/ISO market reports (2022-2023 avg) |
| BESS Arbitrage Dispatch | Medium | Deterministic rule-based model |
| 25-Year Flat Cashflows | Low | No escalation, degradation simplified |
| Grid Export Revenue | Medium | Assumes merchant pricing, no PPA |

**High** = verifiable from a named public source.
**Medium** = calibrated to public data but uses modeled assumptions.
**Low** = simplifying assumption that may diverge from reality.
            """)

    # ── TAB 2: SITE & GENERATION ─────────────────────────────────────────
    with tab2:
        # Generation Profile vs. LMP
        st.subheader("Generation Profile vs. LMP")
        season_map = {"Spring (Apr)": 24*90, "Summer (Jul)": 24*180,
                      "Autumn (Oct)": 24*270, "Winter (Jan)": 0}
        season_sel = st.radio("Sample Window", list(season_map.keys()),
                              horizontal=True, index=1)
        start_h = season_map[season_sel]
        st.plotly_chart(
            chart_gen_lmp(gen_mwh, lmp_mwh, inp["gen_type"],
                          inp["capacity_mw"], start_h),
            use_container_width=True,
        )

        # Duration curve + Negative price risk
        col_dc, col_pc = st.columns(2)
        with col_dc:
            st.plotly_chart(
                chart_duration_curve(lmp_mwh, be_price_kwh),
                use_container_width=True,
            )
        with col_pc:
            st.subheader("Negative-Price Risk")
            n_neg = int((lmp_mwh < 0).sum())
            rev_lost = float(
                (gen_mwh[lmp_mwh < 0] * np.abs(lmp_mwh[lmp_mwh < 0])).sum()
            )
            st.metric("Negative LMP Hours / Year", f"{n_neg:,}")
            st.metric("Revenue at Risk (grid-tied)", f"${rev_lost:,.0f}")
            st.metric("Mining / BESS as Negative-Price Hedge",
                      f"${rev_lost * 0.85:,.0f} recoverable",
                      help="~85% of negative-price revenue is recoverable by diverting to miners/BESS.")

        st.markdown("---")

        # Generation-only revenue table
        st.subheader("Generation-Only Revenue Table")
        st.caption(
            "Pure generation scenario — no storage or mining. "
            "Revenue reflects spot LMP only; negative-price hours are curtailed."
        )
        styled = rev_table.style.format({
            "Generation (MWh)":                  "{:,.1f}",
            "Revenue ($)":                        "${:,.0f}",
            "Avg LMP ($/MWh)":                   "${:.2f}",
            "Hours Curtailed":                    "{:,}",
            "Revenue Lost — Neg. Pricing ($)":    "${:,.0f}",
        }).background_gradient(
            subset=["Revenue ($)"], cmap="Greens"
        ).background_gradient(
            subset=["Revenue Lost — Neg. Pricing ($)"], cmap="Reds"
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Annual Heatmap (reference view)
        with st.expander("Annual Heatmap (hour × day)", expanded=False):
            heatmap_choice = st.radio(
                "View", ["Generation (MWh)", "LMP ($/MWh)"],
                horizontal=True, label_visibility="collapsed",
            )
            if heatmap_choice == "Generation (MWh)":
                color = "YlOrRd" if inp["gen_type"] == "Solar" else ("Purples" if inp["gen_type"] == "Hybrid" else "Blues")
                fig_hm = chart_annual_heatmap(gen_mwh, "Generation Heatmap (MWh/hour)", color, "MWh")
            else:
                fig_hm = chart_annual_heatmap(lmp_mwh, f"{iso} LMP Heatmap ($/MWh)", "RdYlGn", "$/MWh")
            st.plotly_chart(fig_hm, use_container_width=True)

    # ── TAB 3: DISPATCH & OPERATIONS ─────────────────────────────────────
    # (BESS inputs were already rendered in Phase 5 above the ---  divider)
    with tab3:
        # Grid Connection & Dispatch Insight (prominent, expanded by default)
        insight_md = grid_btm_insight(
            gen_type=inp["gen_type"],
            solar_frac=inp["solar_frac"],
            grid_tied=inp["grid_tied"],
            annual_cf=gen_data["annual_cf"],
            lmp_arr=lmp_mwh,
            be_price_mwh=be_price_mwh,
            total_annual_rev=total_annual_rev,
            annual_rev_mine=annual_rev_mine,
            annual_rev_import=annual_rev_import,
            mining_util=dsumm["mining_utilization"],
            bess_split=bess_split,
            mine_split=mine_split,
        )
        with st.expander("Grid Connection & Dispatch Insight", expanded=True):
            st.markdown(insight_md)

        # BESS Pack Rationale
        with st.expander("BESS Pack Selection — why this config?", expanded=False):
            st.markdown(pack_rationale)

        # Dispatch rules
        st.subheader("Synergy Priority Dispatch Simulation")
        with st.expander("Dispatch Rules Applied", expanded=True):
            st.markdown(f"""
| Priority | Condition | Action |
|----------|-----------|--------|
| **1 — Negative LMP** | LMP < $0/MWh | Charge BESS → Mine remainder |
| **2a — Below Break-Even (charge)** | LMP < ${be_price_mwh:.0f}/MWh & SoC < 80% & forecast ↑ | Charge BESS → Mine remainder |
| **2b — Below Break-Even (mine)** | LMP < ${be_price_mwh:.0f}/MWh & SoC ≥ 80% | Mine full generation |
| **3 — Above Break-Even** | LMP ≥ ${be_price_mwh:.0f}/MWh | Discharge BESS → Export up to {inp["interconnection_mw"]} MW → Mine surplus only |

**Ancillary Service Premium:** ${ancillary_premium:.2f}/MWh when BESS SoC > 20% — {iso} market.
            """)

        # Dispatch window
        window_start = st.slider(
            "Dispatch Window Start (day of year)", 1, 340, 180, step=1,
        )
        st.plotly_chart(
            chart_dispatch_stacked(dispatch_df, start_hour=window_start * 24),
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("Annual Dispatch Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hours: Grid Export Mode",  f"{dsumm['hours_mode_export']:,}")
        c2.metric("Hours: Mining Mode",        f"{dsumm['hours_mode_mine']:,}")
        c3.metric("Hours: BESS Charging",      f"{dsumm['hours_mode_charge']:,}")
        c4.metric("Hours: Negative LMP Mode",  f"{dsumm['hours_mode_neg']:,}")

        c1b, c2b, c3b, c4b = st.columns(4)
        c1b.metric("Total Exported (MWh)",     f"{dsumm['total_grid_export_mwh']:,.0f}")
        c2b.metric(
            "Total Mining (MWh equiv)",
            f"{dsumm['total_mining_mwh']:,.0f}",
            delta=f"{dsumm['mining_utilization']:.0%} of capacity",
        )
        c3b.metric("BESS Charged (MWh)",       f"{dsumm['total_bess_charge_mwh']:,.0f}")
        c4b.metric("BESS Discharged (MWh)",    f"{dsumm['total_bess_disc_mwh']:,.0f}")

        if inp["grid_tied"] and dsumm["total_grid_import_mwh"] > 0:
            ci1, ci2, ci3 = st.columns(3)
            ci1.metric(
                "Grid Imported (MWh)",
                f"{dsumm['total_grid_import_mwh']:,.0f}",
                help="Power imported from the grid to run miners when LMP < break-even.",
            )
            net = dsumm["net_import_revenue"]
            ci2.metric(
                "Import Net P&L",
                f"${net:,.0f}",
                delta="income" if net >= 0 else "cost",
                delta_color="normal" if net >= 0 else "inverse",
                help="Positive = grid paid you (negative LMP hours). Negative = you paid for cheap grid power to mine.",
            )
            ci3.metric(
                "Connection Mode",
                "Grid-Tied",
                delta="Night mining enabled",
                help="Grid import allows miners to run 24/7 whenever LMP < mining break-even.",
            )
        elif not inp["grid_tied"]:
            st.info(
                "**Behind-the-Meter (BTM):** No grid import or export. Miners only run when on-site "
                f"generation is available — {dsumm['mining_utilization']:.0%} capacity utilisation. "
                "Switch to Grid-Tied to enable 24/7 mining from cheap grid power."
            )

        st.markdown("---")

        # ── Period summaries: 7-day and 30-day ──────────────────────────────
        def _period_stats(df, n_hours):
            """Compute summary stats for the last *n_hours* of dispatch_df."""
            chunk = df.tail(n_hours)
            total_rev = (
                chunk["rev_grid"].sum()
                + chunk["rev_bess"].sum()
                + chunk["rev_ancillary"].sum()
                + chunk["rev_mining"].sum()
                + chunk["rev_import"].sum()
            )
            # Baseline: generation-only (sell all power at LMP, curtail at neg prices)
            _gen_x_lmp = chunk["generation_mwh"] * chunk["lmp"]
            baseline_rev = float(_gen_x_lmp[_gen_x_lmp > 0].sum())
            return {
                "gen":       chunk["generation_mwh"].sum(),
                "avg_lmp":   chunk["lmp"].mean(),
                "grid_exp":  chunk["grid_export_mwh"].sum(),
                "grid_imp":  chunk["grid_import_mwh"].sum(),
                "mining":    chunk["rev_mining"].sum(),
                "bess":      chunk["rev_bess"].sum(),
                "ancillary": chunk["rev_ancillary"].sum(),
                "total_rev": total_rev,
                "baseline":  baseline_rev,
                "delta":     total_rev - baseline_rev,
            }

        _s7  = _period_stats(dispatch_df, 168)   # 7 days
        _s30 = _period_stats(dispatch_df, 720)   # 30 days

        st.subheader("Dispatch Performance")

        def _render_period(label, s):
            st.markdown(f"##### {label}")
            _a1, _a2, _a3 = st.columns(3)
            _a1.metric("Hybrid Revenue",        f"${s['total_rev']:,.0f}")
            _a2.metric("Generation-Only Rev",   f"${s['baseline']:,.0f}",
                        help="Baseline: sell all generation at LMP, curtail during negative prices. No BESS, no miners.")
            _delta_pct = (s['delta'] / s['baseline'] * 100) if s['baseline'] > 0 else 0
            _a3.metric("Hybrid Uplift",         f"${s['delta']:,.0f}",
                        delta=f"+{_delta_pct:,.0f}%")
            _b1, _b2, _b3, _b4, _b5 = st.columns(5)
            _b1.metric("Mining Rev",          f"${s['mining']:,.0f}")
            _b2.metric("BESS Rev",            f"${s['bess']:,.0f}")
            _b3.metric("Ancillary Rev",       f"${s['ancillary']:,.0f}")
            _b4.metric("Avg LMP ($/MWh)",     f"${s['avg_lmp']:.2f}")
            _b5.metric("Generation (MWh)",    f"{s['gen']:,.0f}")

        _render_period("Previous 7 Days (168 h)", _s7)
        _render_period("Previous 30 Days (720 h)", _s30)

        # ── Raw table (last 168 hours) ──────────────────────────────────────
        st.markdown("---")
        st.subheader("Raw Dispatch Data (Last 168 Hours)")
        _cols = ["hour", "generation_mwh", "lmp", "grid_export_mwh", "grid_import_mwh",
                 "mining_mw", "bess_charge_mwh", "bess_discharge_mwh",
                 "bess_soc_mwh", "rev_mining", "rev_grid", "rev_import", "rev_bess", "rev_ancillary",
                 "dispatch_mode"]
        disp_display = dispatch_df.tail(168)[_cols].copy()
        # Map timestamps: last 168 hours ending at current hour
        _now = pd.Timestamp.now().floor("h")
        _start = _now - pd.Timedelta(hours=167)
        disp_display.insert(0, "timestamp", pd.date_range(_start, _now, freq="h").values)
        disp_display.drop(columns=["hour"], inplace=True)
        _nice_cols = [
            "Timestamp", "Gen (MWh)", "LMP ($/MWh)", "Grid Exp (MWh)", "Grid Imp (MWh)",
            "Mining (MW)", "BESS Chg (MWh)", "BESS Dis (MWh)",
            "SoC (MWh)", "Rev Mine ($)", "Rev Grid ($)", "Rev Import ($)", "Rev BESS ($)", "Rev Anc ($)",
            "Mode",
        ]
        disp_display.columns = _nice_cols
        # Totals row
        _num_cols = [c for c in _nice_cols if c not in ("Timestamp", "Mode", "LMP ($/MWh)", "SoC (MWh)")]
        _totals = {c: disp_display[c].sum() for c in _num_cols}
        _totals["Timestamp"] = "TOTAL (168 h)"
        _totals["Mode"] = ""
        _totals["LMP ($/MWh)"] = disp_display["LMP ($/MWh)"].mean()
        _totals["SoC (MWh)"] = disp_display["SoC (MWh)"].mean()
        totals_row = pd.DataFrame([_totals], columns=_nice_cols)
        disp_display = pd.concat([disp_display, totals_row], ignore_index=True)

        def color_mode(val):
            colors_map = {
                "Negative LMP": "color: #F87171",
                "BESS": "color: #A78BFA",
                "Mine": "color: #FF8C42",
                "Export": "color: #7EE8A2",
            }
            for k, v in colors_map.items():
                if k in str(val):
                    return v
            return ""

        def _fmt_ts(x):
            if isinstance(x, str):
                return x
            return x.strftime("%b %d %H:%M")

        st.dataframe(
            disp_display.style.format({
                "Timestamp": _fmt_ts,
                "Gen (MWh)": "{:.3f}", "LMP ($/MWh)": "${:.2f}",
                "Grid Exp (MWh)": "{:.3f}", "Grid Imp (MWh)": "{:.3f}",
                "Mining (MW)": "{:.3f}",
                "BESS Chg (MWh)": "{:.3f}", "BESS Dis (MWh)": "{:.3f}",
                "SoC (MWh)": "{:.3f}", "Rev Mine ($)": "${:.1f}",
                "Rev Import ($)": "${:.1f}",
                "Rev Grid ($)": "${:.1f}", "Rev BESS ($)": "${:.1f}",
                "Rev Anc ($)": "${:.2f}",
            }).applymap(color_mode, subset=["Mode"]),
            use_container_width=True,
            height=400,
        )

    # ── TAB 4: FINANCIALS & ALLOCATION ───────────────────────────────────
    # (ITC + Budget inputs were already rendered in Phase 5 above the --- divider)
    with tab4:
        # ITC summary metrics
        st.subheader("Financial Analysis & ITC Impact")
        col_itc1, col_itc2, col_itc3 = st.columns(3)
        col_itc1.metric("Total ITC Rate",   f"{itc_rate:.0%}")
        col_itc2.metric("BESS ITC Savings", f"${itc_savings_bess:,.0f}",
                        help="Applied against BESS CapEx in year 1.")
        col_itc3.metric("Net BESS CapEx After ITC",
                        f"${bess_cost * (1 - itc_rate):,.0f}")

        st.markdown("---")

        # IRR / ROI table
        st.subheader("IRR · NPV · ROI by Scenario")

        def fmt_irr_val(v):
            return f"{v * 100:.2f}%" if v is not None else "< 0% (loss)"

        scenario_data = {
            "Scenario": [
                "Miners Only (no ITC)",
                "BESS Only (with ITC)",
                "Hybrid Combined (with ITC)",
            ],
            "CapEx ($)": [
                f"${miner_budget:,.0f}",
                f"${bess_cost:,.0f}",
                f"${budget:,.0f}",
            ],
            "ITC Credit ($)": [
                "$0",
                f"${itc_savings_bess:,.0f}",
                f"${itc_savings_bess:,.0f}",
            ],
            "Net CapEx ($)": [
                f"${miners_irr['net_capex']:,.0f}",
                f"${bess_irr['net_capex']:,.0f}",
                f"${hybrid_irr['net_capex']:,.0f}",
            ],
            "IRR": [
                fmt_irr_val(miners_irr["irr"]),
                fmt_irr_val(bess_irr["irr"]),
                fmt_irr_val(hybrid_irr["irr"]),
            ],
            "NPV @ 8% ($)": [
                f"${miners_irr['npv_8pct']:,.0f}",
                f"${bess_irr['npv_8pct']:,.0f}",
                f"${hybrid_irr['npv_8pct']:,.0f}",
            ],
            "Simple ROI": [
                f"{miners_irr['roi']:.1%}",
                f"{bess_irr['roi']:.1%}",
                f"{hybrid_irr['roi']:.1%}",
            ],
            "Payback (yrs)": [
                str(miners_irr["payback_years"] or "N/A"),
                str(bess_irr["payback_years"] or "N/A"),
                str(hybrid_irr["payback_years"] or "N/A"),
            ],
        }
        st.dataframe(pd.DataFrame(scenario_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # IRR comparison + Cumulative cashflow charts
        col_irr, col_ccf = st.columns(2)
        with col_irr:
            irr_chart_data = {
                "Miners": miners_irr["irr"],
                "BESS (ITC)": bess_irr["irr"],
                "Hybrid (ITC)": hybrid_irr["irr"],
            }
            st.plotly_chart(chart_irr_comparison(irr_chart_data), use_container_width=True)
        with col_ccf:
            st.plotly_chart(
                chart_cumulative_cashflow(
                    miners_cfs=cfs["miners_cfs"],
                    bess_cfs=cfs["bess_cfs"],
                    hybrid_cfs=cfs["hybrid_cfs"],
                    miners_capex=miner_budget,
                    bess_capex=bess_cost,
                    hybrid_capex=budget,
                    itc_rate=itc_rate,
                ),
                use_container_width=True,
            )

        st.markdown("---")

        # Capital allocation table
        st.subheader("Capital Allocation")
        st.markdown(
            f"**Total Budget:** ${budget / 1e6:.1f}M  ·  "
            f"**Strategy:** {inp['gen_type']} site → "
            f"{int(bess_split * 100)}% BESS / {int(mine_split * 100)}% Miners"
        )

        alloc_rows = [
            {
                "Asset":              f"Tesla Megapack {preset['label']}",
                "Qty":                f"{bess_n} packs",
                "Unit Cost":          f"${preset['cost_usd']:,.0f}",
                "Total Cost":         f"${bess_cost:,.0f}",
                "Power Capacity":     f"{bess_power_mw:.1f} MW",
                "Energy / Hash Cap.": f"{bess_energy:.1f} MWh",
                "ITC Offset":         f"${itc_savings_bess:,.0f}",
            },
            {
                "Asset":              f"BTC Miners ({inp['efficiency_jth']} J/TH)",
                "Qty":                f"{mining_th:,.0f} TH",
                "Unit Cost":          f"${inp['hw_cost_per_th']:.2f}/TH",
                "Total Cost":         f"${miner_budget:,.0f}",
                "Power Capacity":     f"{mine_power:.2f} MW",
                "Energy / Hash Cap.": f"{mining_th:,.0f} TH",
                "ITC Offset":         "$0",
            },
            {
                "Asset":              "TOTAL",
                "Qty":                "—",
                "Unit Cost":          "—",
                "Total Cost":         f"${bess_cost + miner_budget:,.0f}",
                "Power Capacity":     f"{bess_power_mw + mine_power:.2f} MW",
                "Energy / Hash Cap.": "—",
                "ITC Offset":         f"${itc_savings_bess:,.0f}",
            },
        ]
        st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True, hide_index=True)

        if alloc.get("remaining", 0) > 1_000:
            st.info(
                f"Unallocated budget: **${alloc['remaining']:,.0f}** "
                "(fractional pack not purchased — consider adding miners or increasing budget)."
            )

        # Capital pie + KPIs
        col_pie, col_kpi = st.columns([1, 1.5])
        with col_pie:
            st.plotly_chart(
                chart_capital_allocation(bess_cost, miner_budget),
                use_container_width=True,
            )
        with col_kpi:
            st.subheader("Blended Investment KPIs")
            k1, k2 = st.columns(2)
            k1.metric("Blended IRR (Hybrid + ITC)", fmt_irr(hybrid_irr["irr"]))
            k2.metric("NPV @ 8% Discount Rate",     f"${hybrid_irr['npv_8pct'] / 1e6:.2f}M")
            k1.metric("Payback Period",     f"{hybrid_irr['payback_years'] or 'N/A'} yrs")
            k2.metric("ITC Savings (total)", f"${itc_savings_bess:,.0f}")
            k1.metric("Mining TH Deployed", f"{mining_th:,.0f} TH")
            k2.metric("Megapacks Deployed", f"{bess_n} × {preset['label']}")

        st.markdown("---")

        # Revenue Stack vs. Budget
        st.subheader("Revenue Stack vs. Budget")
        st.plotly_chart(chart_revenue_comparison(rev_scenario), use_container_width=True)

        # Final recommendation box
        st.markdown(f"""
<div class="rec-box">
<h4 style="color:#0EA5E9;margin-top:0">Final Recommendation</h4>

Deploy <b>${budget / 1e6:.1f}M</b> across a <b>{inp['gen_type']}</b> hybrid site:

- **{bess_n} × {preset['label']} Megapacks** ({bess_power_mw:.1f} MW / {bess_energy:.1f} MWh) — ${bess_cost / 1e6:.2f}M
- **{mining_th:,.0f} TH** of BTC mining capacity at {inp['efficiency_jth']} J/TH — ${miner_budget / 1e6:.2f}M
- **{itc_rate:.0%} ITC** reduces effective BESS CapEx by ${itc_savings_bess / 1e6:.2f}M

Projected **Blended IRR: {irr_str}** over {PROJECT_LIFE_YEARS}-year project life.
Total annual revenue estimate: **${total_annual_rev:,.0f}**.

*Grid Export drives baseline returns. Miners monetise curtailed MWh. BESS captures peak spreads and
unlocks {iso} ancillary service revenue (${ancillary_premium:.2f}/MWh premium).*
</div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Ancillary Services Revenue
        st.subheader("Ancillary Services Revenue")
        st.markdown(f"""
| ISO | Premium | Service Type | Notes |
|-----|---------|--------------|-------|
| **{iso}** | **${ancillary_premium:.2f}/MWh** | Freq. Regulation + Reserve | Applied when BESS SoC > 20% |

Annual ancillary revenue estimate: **${annual_rev_anc:,.0f}**
*(= {bess_power_mw:.1f} MW × ${ancillary_premium:.2f}/MWh × 8,760 h × SoC availability factor)*
        """)

    # ── TAB 5: SENSITIVITY ANALYSIS ──────────────────────────────────────
    with tab5:
        st.subheader("Sensitivity Analysis")
        st.caption("How much does each input variable move the Blended IRR?")

        with st.spinner("Running sensitivity sweeps (8 variables)..."):
            sens_results, sens_base_irr = run_sensitivity(
                inp=inp, iso=iso, gen_mwh=gen_mwh, lmp_mwh=lmp_mwh,
                gen_data=gen_data, lmp_data=lmp_data,
                budget=budget, itc_rate=itc_rate,
                pack_key=pack_key, bess_split=bess_split,
                ancillary_premium=ancillary_premium,
                dsumm=dsumm, bess_n=bess_n, preset=preset,
                bess_cost=bess_cost, miner_budget=miner_budget,
                mining_th=mining_th, mine_power=mine_power,
                be_price_mwh=be_price_mwh,
                annual_rev_grid=annual_rev_grid,
                annual_rev_bess=annual_rev_bess,
                annual_rev_anc=annual_rev_anc,
                annual_rev_import=annual_rev_import,
                hybrid_irr_base=hybrid_irr,
            )

        st.plotly_chart(chart_tornado(sens_results, sens_base_irr),
                        use_container_width=True)

        st.markdown("---")
        st.subheader("Sensitivity Detail")

        sens_rows = []
        for s in sorted(sens_results, key=lambda x: abs(x["high_irr"] - x["low_irr"]), reverse=True):
            spread = abs(s["high_irr"] - s["low_irr"])
            sens_rows.append({
                "Variable": s["name"],
                "Downside IRR": f"{s['low_irr'] * 100:.2f}%" if s["low_irr"] else "< 0%",
                "Base IRR": f"{sens_base_irr * 100:.2f}%" if sens_base_irr else "N/A",
                "Upside IRR": f"{s['high_irr'] * 100:.2f}%" if s["high_irr"] else "< 0%",
                "Spread (pp)": f"{spread * 100:.1f}",
            })
        st.dataframe(pd.DataFrame(sens_rows), use_container_width=True, hide_index=True)

        st.info(
            "Variables are perturbed independently (one-at-a-time). "
            "Sorted by total IRR spread. "
            "Hashprice and hardware cost typically dominate for mining-heavy allocations."
        )

    # ── TAB 6: MULTI-SITE PORTFOLIO ──────────────────────────────────────
    with tab6:
        st.subheader("Multi-Site Portfolio")
        st.caption("Save up to 3 site configurations and compare aggregate returns.")

        # ── Save current site ────────────────────────────────────────────
        portfolio = st.session_state.portfolio
        can_save = len(portfolio) < 3

        site_name_default = (
            f"{inp['city']} {inp['gen_type']} {inp['capacity_mw']}MW"
        )
        col_name, col_btn = st.columns([3, 1])
        with col_name:
            site_label = st.text_input(
                "Site name", value=site_name_default, key="portfolio_site_name",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "Save Current Site" if can_save else "Portfolio Full (3/3)",
                disabled=not can_save, use_container_width=True,
            ):
                site_dict = {
                    "name": site_label,
                    "inp": dict(inp),
                    "pack_key": pack_key,
                    "bess_split": bess_split,
                    "itc_rate": itc_rate,
                    "budget": budget,
                    "results": {
                        "hybrid_irr": dict(hybrid_irr),
                        "total_annual_rev": total_annual_rev,
                        "budget": budget,
                        "bess_cost": bess_cost,
                        "miner_budget": miner_budget,
                        "mining_th": mining_th,
                        "bess_n": bess_n,
                        "irr_str": fmt_irr(hybrid_irr["irr"]),
                        "npv": hybrid_irr["npv_8pct"],
                        "payback": hybrid_irr["payback_years"],
                        "annual_rev_grid": annual_rev_grid,
                        "annual_rev_mine": annual_rev_mine,
                        "annual_rev_bess": annual_rev_bess,
                        "annual_rev_anc": annual_rev_anc,
                    },
                }
                st.session_state.portfolio.append(site_dict)
                st.rerun()

        if not portfolio:
            st.info(
                "No sites saved yet. Configure a site using the sidebar, "
                "then click **Save Current Site** to add it to the portfolio."
            )
        else:
            st.markdown("---")

            # ── Portfolio summary metrics ────────────────────────────────
            total_capex = sum(s["results"]["budget"] for s in portfolio)
            total_rev   = sum(s["results"]["total_annual_rev"] for s in portfolio)
            # Weighted-average IRR by budget
            irr_vals = []
            for s in portfolio:
                v = s["results"]["hybrid_irr"].get("irr")
                if v is not None:
                    irr_vals.append((v, s["results"]["budget"]))
            if irr_vals:
                wavg_irr = sum(v * w for v, w in irr_vals) / sum(w for _, w in irr_vals)
                wavg_str = f"{wavg_irr * 100:.2f}%"
            else:
                wavg_str = "N/A"

            pm1, pm2, pm3, pm4 = st.columns(4)
            pm1.metric("Sites", f"{len(portfolio)} / 3")
            pm2.metric("Total CapEx", f"${total_capex / 1e6:.1f}M")
            pm3.metric("Wtd-Avg IRR", wavg_str)
            pm4.metric("Total Annual Rev", f"${total_rev:,.0f}")

            st.markdown("---")

            # ── Site comparison table ────────────────────────────────────
            st.subheader("Site Comparison")
            comp_rows = []
            for i, s in enumerate(portfolio):
                r = s["results"]
                comp_rows.append({
                    "Site": s["name"],
                    "Gen Type": s["inp"]["gen_type"],
                    "Capacity (MW)": s["inp"]["capacity_mw"],
                    "Budget ($M)": f"${r['budget'] / 1e6:.1f}M",
                    "IRR": r["irr_str"],
                    "NPV @ 8%": f"${r['npv']:,.0f}",
                    "Payback (yrs)": str(r["payback"] or "N/A"),
                    "Annual Rev": f"${r['total_annual_rev']:,.0f}",
                    "Megapacks": r["bess_n"],
                    "Mining TH": f"{r['mining_th']:,.0f}",
                })
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

            # ── Remove buttons ───────────────────────────────────────────
            st.caption("Remove a site:")
            rm_cols = st.columns(len(portfolio))
            for i, s in enumerate(portfolio):
                with rm_cols[i]:
                    if st.button(f"Remove: {s['name']}", key=f"rm_site_{i}"):
                        st.session_state.portfolio.pop(i)
                        st.rerun()

            # ── Comparison charts ────────────────────────────────────────
            if len(portfolio) >= 2:
                st.markdown("---")
                # Flatten for chart functions
                irr_data = [
                    {"name": s["name"], "irr": s["results"]["hybrid_irr"].get("irr")}
                    for s in portfolio
                ]
                rev_data = [
                    {
                        "name": s["name"],
                        "rev_grid": s["results"].get("annual_rev_grid", 0),
                        "rev_mining": s["results"].get("annual_rev_mine", 0),
                        "rev_bess": s["results"].get("annual_rev_bess", 0),
                        "rev_ancillary": s["results"].get("annual_rev_anc", 0),
                    }
                    for s in portfolio
                ]
                col_pirr, col_prev = st.columns(2)
                with col_pirr:
                    st.plotly_chart(
                        chart_portfolio_irr(irr_data),
                        use_container_width=True,
                    )
                with col_prev:
                    st.plotly_chart(
                        chart_portfolio_revenue(rev_data),
                        use_container_width=True,
                    )


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
