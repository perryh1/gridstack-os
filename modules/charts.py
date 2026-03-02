"""
Plotly chart builders for the GridStack OS dashboard.
All charts use the dark industrial palette defined in .streamlit/config.toml.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ─── Palette ─────────────────────────────────────────────────────────────────
C_SOLAR   = "#FFD700"   # gold
C_WIND    = "#00D4FF"   # cyan
C_GRID    = "#7EE8A2"   # green
C_MINE    = "#FF8C42"   # amber/orange
C_BESS    = "#A78BFA"   # violet
C_LMP     = "#F87171"   # red
C_NEG     = "#EF4444"
C_ANC     = "#34D399"   # emerald
BG        = "#0E1117"
BG2       = "#161B2E"
GRID_CLR  = "#2D3556"
TEXT_CLR  = "#E8EAF0"


def _base_layout(title: str, height: int = 420) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=TEXT_CLR, size=15)),
        paper_bgcolor=BG2,
        plot_bgcolor=BG,
        font=dict(color=TEXT_CLR, size=12),
        height=height,
        margin=dict(l=50, r=20, t=50, b=40),
        xaxis=dict(gridcolor=GRID_CLR, zerolinecolor=GRID_CLR),
        yaxis=dict(gridcolor=GRID_CLR, zerolinecolor=GRID_CLR),
        legend=dict(
            bgcolor="rgba(0,0,0,0.4)",
            bordercolor=GRID_CLR,
            borderwidth=1,
        ),
    )


# ─── 1. 72-Hour Generation + LMP Overlay ─────────────────────────────────────

def chart_gen_lmp(
    gen_mwh: np.ndarray,
    lmp_mwh: np.ndarray,
    gen_type: str,
    capacity_mw: float,
    start_hour: int = 24 * 90,   # default: start of April
) -> go.Figure:
    """72-hour dual-axis chart: generation profile + LMP price curve."""
    h = slice(start_hour, start_hour + 72)
    hours = np.arange(72)
    gen   = gen_mwh[h]
    lmp   = lmp_mwh[h]

    gen_color = C_SOLAR if gen_type == "Solar" else C_WIND
    label = f"{gen_type} Generation (MWh)"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=hours, y=gen, name=label,
            marker_color=gen_color, opacity=0.8,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=hours, y=lmp, name="LMP ($/MWh)",
            line=dict(color=C_LMP, width=2),
            mode="lines",
        ),
        secondary_y=True,
    )
    # Shade negative LMP hours
    neg_mask = lmp < 0
    if neg_mask.any():
        for i in range(len(hours)):
            if neg_mask[i]:
                fig.add_vrect(
                    x0=i - 0.5, x1=i + 0.5,
                    fillcolor=C_NEG, opacity=0.15,
                    line_width=0,
                )

    layout = _base_layout(f"72-Hour Generation & LMP Snapshot", height=400)
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="Generation (MWh)", secondary_y=False, gridcolor=GRID_CLR)
    fig.update_yaxes(title_text="LMP ($/MWh)", secondary_y=True, gridcolor=GRID_CLR)
    fig.update_xaxes(title_text="Hour Offset", gridcolor=GRID_CLR)
    return fig


# ─── 2. Annual Heatmap ────────────────────────────────────────────────────────

def chart_annual_heatmap(
    data: np.ndarray,
    title: str,
    colorscale: str = "Viridis",
    unit: str = "MWh",
) -> go.Figure:
    """
    Reshape 8760-hour array into (365 days × 24 hours) heatmap.
    Clamps to 8760 data points.
    """
    n = min(len(data), 8760)
    matrix = data[:n].reshape(n // 24, 24).T  # shape (24, 365)

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=list(range(matrix.shape[1])),
        y=list(range(24)),
        colorscale=colorscale,
        colorbar=dict(title=unit),
    ))
    layout = _base_layout(title, height=360)
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="Day of Year")
    fig.update_yaxes(title_text="Hour of Day")
    return fig


# ─── 3. Dispatch Stacked Area ─────────────────────────────────────────────────

def chart_dispatch_stacked(
    df: pd.DataFrame,
    start_hour: int = 24 * 180,
    window: int = 96,
) -> go.Figure:
    """
    96-hour stacked area chart showing how each electron is dispatched:
    grid export, mining load, BESS charge, BESS discharge.
    """
    h = slice(start_hour, start_hour + window)
    d = df.iloc[h].copy()
    x = list(range(window))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=d["grid_export_mwh"].values,
        name="Grid Export", fill="tozeroy",
        line=dict(color=C_GRID, width=1), fillcolor=f"rgba(126,232,162,0.4)",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=d["mining_mw"].values,
        name="Mining Load (MW)", fill="tozeroy",
        line=dict(color=C_MINE, width=1), fillcolor=f"rgba(255,140,66,0.4)",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=d["bess_charge_mwh"].values,
        name="BESS Charging", fill="tozeroy",
        line=dict(color=C_BESS, width=1), fillcolor=f"rgba(167,139,250,0.35)",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=-d["bess_discharge_mwh"].values,
        name="BESS Discharging", fill="tozeroy",
        line=dict(color=C_ANC, width=1),
        fillcolor=f"rgba(52,211,153,0.35)",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=d["bess_soc_mwh"].values,
        name="BESS SoC (MWh)", mode="lines",
        line=dict(color="#FCD34D", width=2, dash="dot"),
        yaxis="y2",
    ))

    layout = _base_layout("96-Hour Synergy Dispatch", height=440)
    fig.update_layout(
        **layout,
        yaxis2=dict(
            title="SoC (MWh)", overlaying="y", side="right",
            gridcolor=GRID_CLR, showgrid=False,
        ),
    )
    fig.update_xaxes(title_text="Hour Offset")
    fig.update_yaxes(title_text="MWh / MW")
    return fig


# ─── 4. Revenue Comparison Bar ────────────────────────────────────────────────

def chart_revenue_comparison(rev_dict: dict) -> go.Figure:
    """
    Grouped bar chart comparing annual revenue sources across three scenarios.
    rev_dict: {scenario: {source: value}}
    """
    scenarios  = list(rev_dict.keys())
    sources    = list(next(iter(rev_dict.values())).keys())
    colors     = [C_GRID, C_MINE, C_BESS, C_ANC]

    fig = go.Figure()
    for i, src in enumerate(sources):
        fig.add_trace(go.Bar(
            name=src,
            x=scenarios,
            y=[rev_dict[s].get(src, 0) / 1_000 for s in scenarios],
            marker_color=colors[i % len(colors)],
        ))

    layout = _base_layout("Annual Revenue by Scenario ($K)", height=380)
    fig.update_layout(**layout, barmode="stack")
    fig.update_yaxes(title_text="Revenue ($K)")
    return fig


# ─── 5. IRR Comparison Chart ──────────────────────────────────────────────────

def chart_irr_comparison(irr_data: dict) -> go.Figure:
    """
    Horizontal bar chart: Miners / BESS / Hybrid IRR (w/ and w/o ITC).
    irr_data: {label: irr_pct}  e.g. {"Miners (no ITC)": 0.12, ...}
    """
    labels = list(irr_data.keys())
    values = [v * 100 if v is not None else 0 for v in irr_data.values()]
    colors = [
        C_MINE if "Miner" in l else C_BESS if "BESS" in l else C_GRID
        for l in labels
    ]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
    ))
    layout = _base_layout("Blended IRR by Scenario", height=360)
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="IRR (%)")
    fig.add_vline(x=8, line_dash="dash", line_color="#94A3B8",
                  annotation_text="8% hurdle", annotation_position="top right")
    return fig


# ─── 6. Capital Allocation Donut ─────────────────────────────────────────────

def chart_capital_allocation(bess_cost: float, mine_cost: float) -> go.Figure:
    """Donut chart showing BESS vs Miner capital split."""
    fig = go.Figure(go.Pie(
        labels=["Megapacks (BESS)", "BTC Miners"],
        values=[bess_cost, mine_cost],
        hole=0.55,
        marker=dict(colors=[C_BESS, C_MINE]),
        textinfo="label+percent",
        textfont=dict(color=TEXT_CLR, size=13),
        hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
    ))
    layout = _base_layout("Capital Allocation", height=340)
    fig.update_layout(**layout)
    return fig


# ─── 7. LMP Duration Curve ───────────────────────────────────────────────────

def chart_duration_curve(lmp_mwh: np.ndarray, break_even_kwh: float) -> go.Figure:
    """Price duration curve with break-even overlay."""
    sorted_lmp = np.sort(lmp_mwh)[::-1]
    pct        = np.linspace(0, 100, len(sorted_lmp))
    be_mwh     = break_even_kwh * 1_000

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pct, y=sorted_lmp,
        mode="lines", name="LMP Duration Curve",
        line=dict(color=C_LMP, width=2),
        fill="tozeroy", fillcolor="rgba(248,113,113,0.15)",
    ))
    fig.add_hline(
        y=be_mwh, line_dash="dash", line_color=C_MINE,
        annotation_text=f"Mining Break-Even: ${be_mwh:.0f}/MWh",
        annotation_font_color=C_MINE,
    )
    fig.add_hline(y=0, line_color=GRID_CLR, line_width=1)

    layout = _base_layout("Price Duration Curve — Hours vs LMP", height=380)
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="% of Hours (100% = highest price)")
    fig.update_yaxes(title_text="LMP ($/MWh)")
    return fig


# ─── 8. Electron Value Comparison ────────────────────────────────────────────

def chart_electron_value(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar for the highest-value-of-an-electron table."""
    colors = []
    for _, row in df.iterrows():
        if row["Highest Value?"] == "★ Best":
            colors.append(C_GRID)
        elif "Mining" in row["Use Case"]:
            colors.append(C_MINE)
        else:
            colors.append(C_BESS)

    fig = go.Figure(go.Bar(
        x=df["Value ($/MWh)"].values,
        y=df["Use Case"].values,
        orientation="h",
        marker_color=colors,
        text=[f"${v:,.1f}" for v in df["Value ($/MWh)"].values],
        textposition="outside",
    ))
    layout = _base_layout("Highest Value of an Electron ($/MWh)", height=280)
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="Value ($/MWh)")
    return fig


# ─── 9. Cumulative Cash Flow Curves ──────────────────────────────────────────

def chart_cumulative_cashflow(
    miners_cfs: list,
    bess_cfs: list,
    hybrid_cfs: list,
    miners_capex: float,
    bess_capex: float,
    hybrid_capex: float,
    itc_rate: float,
) -> go.Figure:
    """
    Show cumulative net cash position over the project life for all three scenarios.
    """
    years = list(range(len(miners_cfs) + 1))

    def cumulative(capex, cfs, itc):
        net_capex = capex * (1 - itc)
        cum = [-net_capex]
        running = -net_capex
        for cf in cfs:
            running += cf
            cum.append(running)
        return cum

    m_cum = cumulative(miners_capex, miners_cfs, 0)
    b_cum = cumulative(bess_capex,   bess_cfs,   itc_rate)
    h_cum = cumulative(hybrid_capex, hybrid_cfs, itc_rate)

    fig = go.Figure()
    for cum, name, color in [
        (m_cum, "Miners", C_MINE),
        (b_cum, "BESS",   C_BESS),
        (h_cum, "Hybrid", C_GRID),
    ]:
        fig.add_trace(go.Scatter(
            x=years, y=[v / 1e6 for v in cum],
            name=name, mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#94A3B8", line_width=1)
    layout = _base_layout("Cumulative Net Cash Position ($M) — 25-Year Horizon", height=420)
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(title_text="Cumulative Net ($M)")
    return fig


def chart_tornado(sensitivity_results: list, base_irr: float) -> go.Figure:
    """
    Horizontal tornado chart showing IRR sensitivity to each variable.

    sensitivity_results: list of dicts with keys:
        name, low_irr, high_irr, low_label, high_label
    base_irr: the base-case IRR (float, e.g. 0.527 = 52.7%)
    """
    # Sort by total spread (most sensitive at top)
    results = sorted(sensitivity_results, key=lambda r: abs(r["high_irr"] - r["low_irr"]))
    names = [r["name"] for r in results]
    base_pct = base_irr * 100

    low_deltas = [(r["low_irr"] * 100) - base_pct for r in results]
    high_deltas = [(r["high_irr"] * 100) - base_pct for r in results]

    fig = go.Figure()

    # Downside bars (left of base)
    fig.add_trace(go.Bar(
        y=names,
        x=low_deltas,
        orientation="h",
        name="Downside",
        marker_color="#EF4444",
        text=[f"{(r['low_irr'] * 100):.1f}%" for r in results],
        textposition="outside",
        textfont=dict(color="#EF4444", size=10),
        hovertemplate="%{y}: %{text}<extra>Low case</extra>",
    ))

    # Upside bars (right of base)
    fig.add_trace(go.Bar(
        y=names,
        x=high_deltas,
        orientation="h",
        name="Upside",
        marker_color="#34D399",
        text=[f"{(r['high_irr'] * 100):.1f}%" for r in results],
        textposition="outside",
        textfont=dict(color="#34D399", size=10),
        hovertemplate="%{y}: %{text}<extra>High case</extra>",
    ))

    # Base-case reference line
    fig.add_vline(x=0, line_dash="dash", line_color="#94A3B8", line_width=1,
                  annotation_text=f"Base: {base_pct:.1f}%",
                  annotation_position="top",
                  annotation_font_color="#94A3B8")

    layout = _base_layout("IRR Sensitivity — Tornado Chart", height=max(350, len(results) * 50))
    layout["barmode"] = "overlay"
    layout["showlegend"] = True
    layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(color=TEXT_CLR),
    )
    fig.update_layout(**layout)
    fig.update_xaxes(title_text="Change in IRR (percentage points)", zeroline=True,
                     zerolinecolor="#94A3B8", zerolinewidth=1)
    fig.update_yaxes(title_text="")
    return fig


def chart_portfolio_irr(sites: list) -> go.Figure:
    """
    Grouped bar chart comparing IRR across portfolio sites.

    sites: list of dicts with keys: name, irr, npv, budget
    """
    names = [s["name"] for s in sites]
    irrs = [s["irr"] * 100 if s["irr"] else 0 for s in sites]

    fig = go.Figure()
    colors = [C_GRID, C_MINE, C_BESS]

    for i, (name, irr_val) in enumerate(zip(names, irrs)):
        fig.add_trace(go.Bar(
            x=[name], y=[irr_val],
            name=name,
            marker_color=colors[i % len(colors)],
            text=[f"{irr_val:.1f}%"],
            textposition="outside",
            textfont=dict(color=TEXT_CLR),
        ))

    # 8% hurdle line
    fig.add_hline(y=8, line_dash="dash", line_color="#94A3B8", line_width=1,
                  annotation_text="8% hurdle",
                  annotation_position="top right",
                  annotation_font_color="#94A3B8")

    layout = _base_layout("Blended IRR by Site", height=350)
    layout["showlegend"] = False
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="IRR (%)")
    return fig


def chart_portfolio_revenue(sites: list) -> go.Figure:
    """
    Stacked bar chart comparing revenue streams across portfolio sites.

    sites: list of dicts with keys: name, rev_grid, rev_mining, rev_bess, rev_ancillary
    """
    names = [s["name"] for s in sites]

    sources = [
        ("Grid Export", "rev_grid", C_GRID),
        ("BTC Mining", "rev_mining", C_MINE),
        ("BESS Arb.", "rev_bess", C_BESS),
        ("Ancillary", "rev_ancillary", C_ANC),
    ]

    fig = go.Figure()
    for label, key, color in sources:
        vals = [s.get(key, 0) / 1e3 for s in sites]  # convert to $K
        fig.add_trace(go.Bar(
            x=names, y=vals,
            name=label,
            marker_color=color,
        ))

    layout = _base_layout("Annual Revenue by Site ($K)", height=380)
    layout["barmode"] = "stack"
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="Revenue ($K)")
    return fig
