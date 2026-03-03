# GridStack OS

**Hybrid BTC Mining + BESS Techno-Economic Modeling & Real-Time Control Platform**

---

## What Is GridStack OS?

GridStack OS is a production-grade platform for modeling and operating hybrid Bitcoin mining + battery energy storage (BESS) sites on deregulated electricity markets. It combines strategic financial planning with autonomous real-time hardware control.

The platform has two modes:
1. **Strategic Dashboard** - 8,760-hour dispatch simulations, three-scenario financial analysis, and multi-site portfolio comparison
2. **Live Control Service** - Autonomous 5-minute dispatch cycles with hardware integration, safety monitoring, and audit logging

---

## The Opportunity

Renewable generation assets (solar, wind, hybrid) produce power at variable rates. Wholesale electricity prices (LMP) fluctuate hourly, sometimes going negative when supply exceeds demand. Most operators either curtail generation or accept low prices during these periods.

GridStack OS optimizes revenue by dynamically routing each MWh to its highest-value use: grid export when prices are high, Bitcoin mining when power is cheap, and BESS arbitrage to capture price spreads.

---

## The GridStack Solution

### Bitcoin Mining
- Absorbs cheap and negative-price power that would otherwise be curtailed
- Scales instantly between sleep, low, and high power modes
- Profitable when electricity cost is below mining break-even price
- Converts stranded electrons into BTC revenue

### Battery Energy Storage (BESS)
- Charges when LMP is low, discharges at peak prices for arbitrage
- Earns ancillary service revenue (frequency regulation, spinning reserve)
- Provides grid services that support interconnection agreements
- Eligible for 30-60% federal Investment Tax Credit (ITC)

> **A note on BESS pricing:** This model uses Tesla Megapack pricing as a conservative benchmark since they are among the most expensive BESS options on the market. Megapacks are AC-coupled and grid-tied, which makes them less than ideal for behind-the-meter or DC-coupled applications. In a real deployment, purpose-built BESS solutions would likely be used at significantly lower cost, meaning actual returns should exceed what this model projects.

### Grid Export
- Sells surplus generation at wholesale market LMP
- Respects interconnection limits per grid agreement
- Supports both grid-tied and behind-the-meter configurations
- Revenue maximized during peak pricing hours

---

## Synergy Priority Logic (SPL)

The core dispatch engine applies a three-rule priority hierarchy each hour:

| LMP Condition | Action | Economic Logic |
|--------------|--------|----------------|
| **Negative** (LMP < $0) | Max charge BESS + max mine | Grid pays you to consume power |
| **Below break-even** (0 < LMP < BE) | Mine with cheap power, strategically charge BESS | Power costs less than mining revenue |
| **Above break-even** (LMP > BE) | Export generation + discharge BESS at peak | Selling power is more valuable than mining |

Within each rule, heuristics optimize BESS state-of-charge based on future LMP forecasts, SOC levels, and ancillary service availability.

---

## Generation Types Supported

| Type | Profile Characteristics | Best Market Fit |
|------|----------------------|-----------------|
| **Solar** | Peak midday production, zero at night | High-LMP daytime markets (CAISO, ERCOT) |
| **Wind** | Stronger at night, seasonal variation | Off-peak mining, portfolio diversification |
| **Hybrid** | Blended solar + wind with configurable mix | Smoother generation curve, higher capacity factor |

Coupling modes: **AC-Coupled** (generation clipped to inverter rating) or **DC-Coupled** (excess charges BESS directly). Grid connection: **Grid-Tied** (export allowed) or **Behind-the-Meter** (no export, on-site use only).

---

## Strategic Dashboard

### What It Does

The Streamlit dashboard runs a full 8,760-hour dispatch simulation and compares three deployment strategies over a 25-year project life:

**Miners Only** - All generation routed to mining, no BESS
- Lowest capex, highest exposure to hashprice volatility

**BESS Only** - All generation managed by BESS arbitrage and grid export
- Steady returns from price spreads and ancillary services
- ITC credit reduces effective capex by 30-60%

**Hybrid (GridStack)** - BESS + Mining optimized by SPL
- Highest total revenue capture across all market conditions
- Mining absorbs low-price hours, BESS captures high-price hours

### Financial Outputs

For each scenario:
- **IRR** (Internal Rate of Return) over 25 years
- **NPV** at 8% discount rate
- **Payback period** in years
- **Cumulative cash flow** year-by-year projection
- **Capital allocation** recommended BESS vs mining split

### Dashboard Tabs

| Tab | Purpose | Audience |
|-----|---------|----------|
| **Executive Summary** | Key metrics, recommended strategy, PDF export | Investors, executives |
| **Site & Generation** | 72-hour profiles, annual heatmaps, generation revenue table | Engineers, site planners |
| **Dispatch & Operations** | SPL simulation, dispatch mode breakdown, BESS cycling | Engineers, operators |
| **Financials & Allocation** | 3-scenario IRR/NPV, cash flow curves, capital split | Investors, finance |
| **Sensitivity** | Tornado chart of key variables vs Hybrid IRR | Analysts, risk teams |
| **Portfolio** | Save and compare multiple site configurations | BD, site selection |
| **Live Control** | Real-time dispatch service status, API docs | Operations, engineering |
| **How It Works** | Model methodology and assumptions | All audiences |

---

## Real-Time Control Service

### Architecture

A separate FastAPI service runs autonomous dispatch cycles independently of the dashboard:

```
Every 5 minutes:
  1. Fetch live LMP from GridStatus API
  2. Read hardware status (miners via Foreman, BESS via REST/MQTT)
  3. Run SPL dispatch decision
  4. Apply safety watchdog checks
  5. Send commands to hardware
  6. Log to SQLite audit trail
```

### Hardware Integration

| System | Adapter | Protocol | Capabilities |
|--------|---------|----------|-------------|
| **Mining Fleet** | Foreman.mn | REST API | Read fleet status, set power modes (sleep/low/high) |
| **BESS** | Generic REST | HTTP | Read SOC, send charge/discharge/idle commands |
| **BESS** | MQTT | MQTTv5 | Publish commands, subscribe to status updates |
| **LMP Feed** | GridStatus | REST API | Live day-ahead hourly prices for all major ISOs |

### Safety Monitoring

The safety watchdog tracks adapter health and enforces hard limits:

- **Adapter failure** (3 consecutive) - Miners sleep, BESS idle
- **SOC < 5%** - Block discharge commands
- **SOC > 98%** - Block charge commands
- **LMP unavailable** - Default to safe mode (miners sleep)

### Audit Trail

Every dispatch cycle is logged to SQLite with:
- Timestamp, LMP, generation level
- Mining and BESS commands sent
- Dispatch mode, BESS SOC
- Grid flows (import/export)
- Alerts and command success flags

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System status, adapter connectivity, uptime |
| `/state` | GET | Current dispatch mode, LMP, hardware status |
| `/history?hours=N` | GET | Dispatch history for charting |
| `/audit?limit=N` | GET | Recent audit log entries |
| `/override` | POST | Manual override (set miner/BESS modes) |
| `/start` | POST | Start dispatch loop |
| `/stop` | POST | Graceful shutdown |

---

## Key Parameters

### BESS Options (modeled with Tesla Megapack pricing)
- **Pack 1**: 1.9 MW / 2-hour duration ($1,058,140) - higher power, arbitrage focused
- **Pack 2**: 1.0 MW / 4-hour duration ($991,910) - longer duration, time-shifting focused
- *These represent a conservative upper bound on BESS capex. DC-coupled alternatives would reduce costs.*

### ITC Tax Credits
- Federal base rate: **30%**
- Domestic content bonus: **+10%** (>55% US manufacturing)
- Energy community bonus: **+20%** (coal/oil closure counties)
- Low-income community bonus: **+10%**
- Maximum blended rate: **60%**

### Coverage
- All 50 US states mapped to ISO/RTO regions
- ISO-specific LMP data: CAISO, ERCOT, PJM, MISO, SPP, NYISO, ISO-NE, WECC, SERC
- State-level solar and wind capacity factors
- Live data via NREL PVWatts (solar) and GridStatus (LMP) APIs

---

## Example Scenario

**50 MW Solar + 10 MW BESS + Mining in Texas (ERCOT)**

| Input | Value |
|-------|-------|
| Generation | 50 MW AC solar |
| BESS | 10 Megapacks (Pack 1, 1.9 MW each = 19 MW) |
| Mining | Remaining budget at 18 J/TH, $12/TH |
| Grid connection | Grid-tied, 50 MW interconnection |
| Hashprice | $0.045/TH/day |
| ITC | 40% (base + domestic content) |

**How SPL routes power:**
- **Midday (high LMP):** Export solar to grid at $70-100/MWh, discharge BESS
- **Afternoon (moderate LMP):** Export solar, idle BESS
- **Evening (low LMP):** Mine with remaining solar, charge BESS
- **Night (very low/negative LMP):** Mine at full capacity, charge BESS from grid
- **Negative price hours:** Max mine + max charge (grid pays you)

---

## Key Assumptions and Limitations

**Built into the model:**
- BESS round-trip efficiency: 92%
- BESS degradation: 2% per year (floor at 75%)
- Solar degradation: 0.5% per year
- Wind degradation: 0.3% per year
- Miner O&M: 2% of hardware cost annually
- Project life: 25 years
- Dispatch uses 72-point LMP history for future price averaging

**Not modeled:**
- ASIC hardware obsolescence or hashrate difficulty adjustments
- Interconnection queue timelines or curtailment orders
- Real-time grid congestion pricing
- Hashprice volatility over 25-year projection (held constant)
- Real utility rate escalation or PPA structures
- Permitting, land, or interconnection costs

---

## GridStack OS vs GridStack AI

| Aspect | GridStack OS | GridStack AI |
|--------|-------------|-------------|
| **Focus** | Renewable generation sites (solar/wind/hybrid) | AI data center load optimization |
| **Revenue Streams** | Grid export + mining + BESS arbitrage | Demand charge avoidance + mining + UPS replacement |
| **Dispatch Logic** | LMP-driven Synergy Priority Logic | Load-driven 5-step priority (peak shaving first) |
| **Real-Time Control** | Full hardware integration (Foreman, BESS adapters) | Dashboard only (no hardware integration) |
| **Generation** | Solar/wind/hybrid profiles | AI workload profiles (training/inference/mixed) |
| **Grid Connection** | Grid-tied or behind-the-meter | Behind-the-meter (data center) |

---

*Built with Streamlit + FastAPI | Python 3.11+ | Deployed on Snowflake Container Runtime & Render*
