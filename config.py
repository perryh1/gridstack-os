"""
Configuration constants for GridStack OS.
"""

# ─── Megapack Presets ─────────────────────────────────────────────────────────
MEGAPACK_PRESETS = {
    "Pack 1 — 1.9 MW / 2 hr  ($1,058,140)": {
        "label": "Pack 1",
        "power_mw": 1.9,
        "duration_hr": 2,
        "energy_mwh": 3.8,
        "cost_usd": 1_058_140,
    },
    "Pack 2 — 1.0 MW / 4 hr  ($991,910)": {
        "label": "Pack 2",
        "power_mw": 1.0,
        "duration_hr": 4,
        "energy_mwh": 4.0,
        "cost_usd": 991_910,
    },
}

# ─── US States + Major Cities ─────────────────────────────────────────────────
STATE_CITIES = {
    "Alabama": ["Birmingham", "Huntsville", "Mobile", "Montgomery"],
    "Alaska": ["Anchorage", "Fairbanks", "Juneau"],
    "Arizona": ["Flagstaff", "Mesa", "Phoenix", "Scottsdale", "Tucson", "Yuma"],
    "Arkansas": ["Fayetteville", "Fort Smith", "Little Rock"],
    "California": ["Bakersfield", "Fresno", "Los Angeles", "Riverside", "Sacramento", "San Diego", "San Francisco", "San Jose", "Stockton"],
    "Colorado": ["Aurora", "Colorado Springs", "Denver", "Fort Collins", "Grand Junction"],
    "Connecticut": ["Bridgeport", "Hartford", "New Haven"],
    "Delaware": ["Dover", "Newark", "Wilmington"],
    "Florida": ["Jacksonville", "Miami", "Orlando", "Tampa", "Tallahassee"],
    "Georgia": ["Atlanta", "Augusta", "Columbus", "Savannah"],
    "Hawaii": ["Hilo", "Honolulu", "Kailua"],
    "Idaho": ["Boise", "Idaho Falls", "Meridian", "Nampa"],
    "Illinois": ["Chicago", "Peoria", "Rockford", "Springfield"],
    "Indiana": ["Evansville", "Fort Wayne", "Indianapolis"],
    "Iowa": ["Cedar Rapids", "Davenport", "Des Moines"],
    "Kansas": ["Kansas City", "Overland Park", "Wichita"],
    "Kentucky": ["Bowling Green", "Lexington", "Louisville"],
    "Louisiana": ["Baton Rouge", "New Orleans", "Shreveport"],
    "Maine": ["Augusta", "Bangor", "Portland"],
    "Maryland": ["Annapolis", "Baltimore", "Frederick"],
    "Massachusetts": ["Boston", "Springfield", "Worcester"],
    "Michigan": ["Ann Arbor", "Detroit", "Grand Rapids", "Lansing"],
    "Minnesota": ["Minneapolis", "Rochester", "Saint Paul"],
    "Mississippi": ["Biloxi", "Gulfport", "Jackson"],
    "Missouri": ["Kansas City", "Saint Louis", "Springfield"],
    "Montana": ["Billings", "Great Falls", "Missoula"],
    "Nebraska": ["Bellevue", "Lincoln", "Omaha"],
    "Nevada": ["Henderson", "Las Vegas", "Reno"],
    "New Hampshire": ["Concord", "Manchester", "Nashua"],
    "New Jersey": ["Jersey City", "Newark", "Trenton"],
    "New Mexico": ["Albuquerque", "Las Cruces", "Santa Fe"],
    "New York": ["Albany", "Buffalo", "New York City", "Rochester", "Syracuse"],
    "North Carolina": ["Charlotte", "Durham", "Greensboro", "Raleigh"],
    "North Dakota": ["Bismarck", "Fargo", "Grand Forks"],
    "Ohio": ["Cincinnati", "Cleveland", "Columbus", "Toledo"],
    "Oklahoma": ["Norman", "Oklahoma City", "Tulsa"],
    "Oregon": ["Eugene", "Portland", "Salem"],
    "Pennsylvania": ["Allentown", "Erie", "Philadelphia", "Pittsburgh"],
    "Rhode Island": ["Cranston", "Providence", "Warwick"],
    "South Carolina": ["Charleston", "Columbia", "Greenville"],
    "South Dakota": ["Aberdeen", "Rapid City", "Sioux Falls"],
    "Tennessee": ["Chattanooga", "Knoxville", "Memphis", "Nashville"],
    "Texas": ["Austin", "Dallas", "El Paso", "Fort Worth", "Houston", "Lubbock", "Midland", "San Antonio"],
    "Utah": ["Provo", "Salt Lake City", "West Valley City"],
    "Vermont": ["Burlington", "Montpelier", "Rutland"],
    "Virginia": ["Arlington", "Norfolk", "Richmond", "Virginia Beach"],
    "Washington": ["Olympia", "Seattle", "Spokane", "Tacoma"],
    "West Virginia": ["Charleston", "Huntington", "Morgantown"],
    "Wisconsin": ["Green Bay", "Madison", "Milwaukee"],
    "Wyoming": ["Casper", "Cheyenne", "Laramie"],
}

# ─── State → ISO/RTO Mapping ──────────────────────────────────────────────────
STATE_ISO = {
    "California": "CAISO",
    "Texas": "ERCOT",
    "New York": "NYISO",
    "Massachusetts": "ISO-NE", "Connecticut": "ISO-NE", "Rhode Island": "ISO-NE",
    "Vermont": "ISO-NE", "New Hampshire": "ISO-NE", "Maine": "ISO-NE",
    "Illinois": "PJM", "Indiana": "PJM", "Maryland": "PJM",
    "New Jersey": "PJM", "North Carolina": "PJM", "Ohio": "PJM",
    "Pennsylvania": "PJM", "Virginia": "PJM", "West Virginia": "PJM",
    "Delaware": "PJM",
    "Minnesota": "MISO", "Iowa": "MISO", "Missouri": "MISO",
    "Wisconsin": "MISO", "Michigan": "MISO", "Arkansas": "MISO",
    "Louisiana": "MISO", "Mississippi": "MISO", "Montana": "MISO",
    "North Dakota": "MISO", "South Dakota": "MISO",
    "Kansas": "SPP", "Oklahoma": "SPP", "Nebraska": "SPP",
    "New Mexico": "WECC", "Arizona": "WECC", "Nevada": "WECC",
    "Colorado": "WECC", "Utah": "WECC", "Wyoming": "WECC",
    "Oregon": "WECC", "Washington": "WECC", "Idaho": "WECC",
    "Alabama": "SERC", "Georgia": "SERC", "Florida": "SERC",
    "South Carolina": "SERC", "Tennessee": "SERC", "Kentucky": "SERC",
    "Hawaii": "HIISO", "Alaska": "AKGRID",
}

# ─── Ancillary Services Premium by ISO ($/MWh) ───────────────────────────────
# Sources: FERC eLibrary market reports, ISO ancillary service data 2022-2023
ANCILLARY_PREMIUMS = {
    "CAISO":  18.50,   # Frequency Regulation + Spinning Reserve + RA credits
    "ERCOT":  22.00,   # FFR + ECRS + Responsive Reserve (ERCOT most valuable)
    "PJM":    15.75,   # Regulation D market + Synchronized Reserve
    "MISO":   12.00,   # Regulation market + Spinning Reserve
    "SPP":    10.50,   # Less liquid bilateral + Reg market
    "NYISO":  16.25,   # Regulation/Spinning Reserve
    "ISO-NE": 14.50,   # Regulation market
    "WECC":    8.00,   # Mostly bilateral contracts
    "SERC":    7.00,   # Largely bilateral, no centralized market
    "HIISO":  28.00,   # Hawaii island grid — highest premium
    "AKGRID":  9.00,   # Alaska isolated grids
}

# ─── Historical Average LMP by ISO ($/MWh, 2022-2023 averages) ───────────────
# Sources: EIA Electric Power Monthly, ISO annual reports
HISTORICAL_LMP = {
    "CAISO":  {"avg": 52.3, "peak": 95.4,  "offpeak": 28.1, "negative_pct": 8.2,  "spread": 67.3},
    "ERCOT":  {"avg": 44.7, "peak": 78.2,  "offpeak": 21.5, "negative_pct": 5.1,  "spread": 56.7},
    "PJM":    {"avg": 38.9, "peak": 68.4,  "offpeak": 20.2, "negative_pct": 3.4,  "spread": 48.2},
    "MISO":   {"avg": 35.2, "peak": 62.1,  "offpeak": 18.8, "negative_pct": 4.8,  "spread": 43.3},
    "SPP":    {"avg": 32.6, "peak": 58.9,  "offpeak": 16.3, "negative_pct": 6.2,  "spread": 42.6},
    "NYISO":  {"avg": 55.1, "peak": 98.7,  "offpeak": 31.4, "negative_pct": 2.1,  "spread": 67.3},
    "ISO-NE": {"avg": 48.6, "peak": 88.2,  "offpeak": 27.9, "negative_pct": 1.8,  "spread": 60.3},
    "WECC":   {"avg": 41.2, "peak": 72.6,  "offpeak": 22.4, "negative_pct": 5.5,  "spread": 50.2},
    "SERC":   {"avg": 34.8, "peak": 61.3,  "offpeak": 18.1, "negative_pct": 2.9,  "spread": 43.2},
    "HIISO":  {"avg": 95.0, "peak": 160.0, "offpeak": 60.0, "negative_pct": 1.0,  "spread": 100.0},
    "AKGRID": {"avg": 72.0, "peak": 120.0, "offpeak": 45.0, "negative_pct": 0.5,  "spread": 75.0},
}

# ─── GridStatus.io Hub Mapping (for live LMP) ───────────────────────────────
# Maps ISO to gridstatusio dataset parameters. Only the 7 major ISOs are
# supported; others (WECC, SERC, HIISO, AKGRID) fall back to synthetic.
GRIDSTATUS_HUB_MAP = {
    "CAISO":  {"dataset": "caiso_lmp_day_ahead_hourly",  "hub": "TH_NP15_GEN-APND", "price_col": "lmp"},
    "ERCOT":  {"dataset": "ercot_spp_day_ahead_hourly",  "hub": "HB_HUBAVG",        "price_col": "spp"},
    "PJM":    {"dataset": "pjm_lmp_day_ahead_hourly",    "hub": "WESTERN HUB",       "price_col": "lmp"},
    "MISO":   {"dataset": "miso_lmp_day_ahead_hourly",   "hub": "ILLINOIS.HUB",      "price_col": "lmp"},
    "SPP":    {"dataset": "spp_lmp_day_ahead_hourly",    "hub": "GSEC_SPS",          "price_col": "lmp"},
    "NYISO":  {"dataset": "nyiso_lmp_day_ahead_hourly",  "hub": "CAPITL",            "price_col": "lmp"},
    "ISO-NE": {"dataset": "isone_lmp_day_ahead_hourly",  "hub": ".H.INTERNAL_HUB",   "price_col": "lmp"},
}

# ─── Solar Capacity Factors by State (annual average fraction) ────────────────
# Source: NREL PVWatts atlas, fixed-tilt south-facing arrays
SOLAR_CF = {
    "Alabama": 0.220, "Alaska": 0.140, "Arizona": 0.290, "Arkansas": 0.215,
    "California": 0.275, "Colorado": 0.260, "Connecticut": 0.175, "Delaware": 0.195,
    "Florida": 0.245, "Georgia": 0.225, "Hawaii": 0.280, "Idaho": 0.220,
    "Illinois": 0.185, "Indiana": 0.195, "Iowa": 0.195, "Kansas": 0.220,
    "Kentucky": 0.200, "Louisiana": 0.220, "Maine": 0.175, "Maryland": 0.200,
    "Massachusetts": 0.175, "Michigan": 0.175, "Minnesota": 0.180, "Mississippi": 0.225,
    "Missouri": 0.205, "Montana": 0.215, "Nebraska": 0.220, "Nevada": 0.280,
    "New Hampshire": 0.175, "New Jersey": 0.185, "New Mexico": 0.285, "New York": 0.175,
    "North Carolina": 0.220, "North Dakota": 0.210, "Ohio": 0.180, "Oklahoma": 0.225,
    "Oregon": 0.180, "Pennsylvania": 0.185, "Rhode Island": 0.170, "South Carolina": 0.225,
    "South Dakota": 0.215, "Tennessee": 0.215, "Texas": 0.255, "Utah": 0.265,
    "Vermont": 0.175, "Virginia": 0.215, "Washington": 0.170, "West Virginia": 0.190,
    "Wisconsin": 0.180, "Wyoming": 0.230,
}

# ─── Wind Capacity Factors by State ──────────────────────────────────────────
# Source: NREL Wind Toolkit 100m hub height, class 3+ wind resources
WIND_CF = {
    "Alabama": 0.255, "Alaska": 0.350, "Arizona": 0.310, "Arkansas": 0.285,
    "California": 0.290, "Colorado": 0.360, "Connecticut": 0.265, "Delaware": 0.265,
    "Florida": 0.235, "Georgia": 0.245, "Hawaii": 0.330, "Idaho": 0.305,
    "Illinois": 0.330, "Indiana": 0.310, "Iowa": 0.420, "Kansas": 0.400,
    "Kentucky": 0.265, "Louisiana": 0.260, "Maine": 0.320, "Maryland": 0.270,
    "Massachusetts": 0.295, "Michigan": 0.290, "Minnesota": 0.370, "Mississippi": 0.250,
    "Missouri": 0.315, "Montana": 0.375, "Nebraska": 0.385, "Nevada": 0.315,
    "New Hampshire": 0.285, "New Jersey": 0.270, "New Mexico": 0.360, "New York": 0.285,
    "North Carolina": 0.290, "North Dakota": 0.410, "Ohio": 0.275, "Oklahoma": 0.395,
    "Oregon": 0.320, "Pennsylvania": 0.280, "Rhode Island": 0.280, "South Carolina": 0.255,
    "South Dakota": 0.390, "Tennessee": 0.260, "Texas": 0.380, "Utah": 0.320,
    "Vermont": 0.280, "Virginia": 0.285, "Washington": 0.310, "West Virginia": 0.295,
    "Wisconsin": 0.305, "Wyoming": 0.395,
}

# ─── City Coordinates (lat, lon) ─────────────────────────────────────────────
CITY_COORDS = {
    "Albuquerque": (35.0844, -106.6504), "Anchorage": (61.2181, -149.9003),
    "Annapolis": (38.9784, -76.4922), "Arlington": (38.8816, -77.0910),
    "Atlanta": (33.7490, -84.3880), "Augusta": (33.4735, -82.0105),
    "Austin": (30.2672, -97.7431), "Bakersfield": (35.3733, -119.0187),
    "Baltimore": (39.2904, -76.6122), "Baton Rouge": (30.4515, -91.1871),
    "Billings": (45.7833, -108.5007), "Bismarck": (46.8083, -100.7837),
    "Boise": (43.6150, -116.2023), "Boston": (42.3601, -71.0589),
    "Bowling Green": (36.9685, -86.4808), "Buffalo": (42.8864, -78.8784),
    "Burlington": (44.4759, -73.2121), "Casper": (42.8501, -106.3252),
    "Cedar Rapids": (41.9779, -91.6656), "Charleston": (32.7765, -79.9311),
    "Charlotte": (35.2271, -80.8431), "Chattanooga": (35.0456, -85.3097),
    "Cheyenne": (41.1400, -104.8202), "Chicago": (41.8781, -87.6298),
    "Cincinnati": (39.1031, -84.5120), "Cleveland": (41.4993, -81.6944),
    "Colorado Springs": (38.8339, -104.8214), "Columbia": (34.0007, -81.0348),
    "Columbus": (39.9612, -82.9988), "Concord": (43.2081, -71.5376),
    "Dallas": (32.7767, -96.7970), "Davenport": (41.5236, -90.5776),
    "Denver": (39.7392, -104.9903), "Des Moines": (41.5868, -93.6250),
    "Detroit": (42.3314, -83.0458), "Dover": (39.1582, -75.5244),
    "Durham": (35.9940, -78.8986), "El Paso": (31.7619, -106.4850),
    "Eugene": (44.0521, -123.0868), "Evansville": (37.9716, -87.5711),
    "Fargo": (46.8772, -96.7898), "Fayetteville": (36.0626, -94.1574),
    "Flagstaff": (35.1983, -111.6513), "Fort Collins": (40.5853, -105.0844),
    "Fort Smith": (35.3859, -94.3985), "Fort Worth": (32.7555, -97.3308),
    "Fresno": (36.7378, -119.7871), "Grand Forks": (47.9253, -97.0329),
    "Grand Junction": (39.0639, -108.5506), "Grand Rapids": (42.9634, -85.6681),
    "Great Falls": (47.4999, -111.3009), "Green Bay": (44.5133, -88.0133),
    "Greenville": (34.8526, -82.3940), "Gulfport": (30.3674, -89.0928),
    "Hartford": (41.7658, -72.6851), "Henderson": (36.0395, -114.9817),
    "Hilo": (19.7297, -155.0900), "Honolulu": (21.3069, -157.8583),
    "Houston": (29.7604, -95.3698), "Huntington": (38.4192, -82.4452),
    "Huntsville": (34.7304, -86.5861), "Idaho Falls": (43.4917, -112.0408),
    "Indianapolis": (39.7684, -86.1581), "Jackson": (32.2988, -90.1848),
    "Jacksonville": (30.3322, -81.6557), "Jersey City": (40.7178, -74.0431),
    "Juneau": (58.3005, -134.4197), "Kailua": (21.4022, -157.7394),
    "Kansas City": (39.0997, -94.5786), "Knoxville": (35.9606, -83.9207),
    "Lansing": (42.7325, -84.5555), "Laramie": (41.3114, -105.5911),
    "Las Cruces": (32.3199, -106.7637), "Las Vegas": (36.1699, -115.1398),
    "Lexington": (38.0406, -84.5037), "Lincoln": (40.8136, -96.7026),
    "Little Rock": (34.7465, -92.2896), "Los Angeles": (34.0522, -118.2437),
    "Louisville": (38.2527, -85.7585), "Lubbock": (33.5779, -101.8552),
    "Madison": (43.0731, -89.4012), "Manchester": (42.9956, -71.4548),
    "Memphis": (35.1495, -90.0490), "Meridian": (43.6135, -116.3918),
    "Mesa": (33.4152, -111.8315), "Miami": (25.7617, -80.1918),
    "Midland": (31.9974, -102.0779), "Milwaukee": (43.0389, -87.9065),
    "Minneapolis": (44.9778, -93.2650), "Missoula": (46.8721, -113.9940),
    "Mobile": (30.6954, -88.0399), "Montgomery": (32.3668, -86.3000),
    "Montpelier": (44.2601, -72.5754), "Nashville": (36.1627, -86.7816),
    "Nampa": (43.5407, -116.5635), "Nashua": (42.7654, -71.4676),
    "New Haven": (41.3083, -72.9279), "New Orleans": (29.9511, -90.0715),
    "New York City": (40.7128, -74.0060), "Newark": (40.7357, -74.1724),
    "Norfolk": (36.8508, -76.2859), "Norman": (35.2226, -97.4395),
    "Olympia": (47.0379, -122.9007), "Omaha": (41.2565, -95.9345),
    "Orlando": (28.5383, -81.3792), "Overland Park": (38.9822, -94.6708),
    "Philadelphia": (39.9526, -75.1652), "Phoenix": (33.4484, -112.0740),
    "Pittsburgh": (40.4406, -79.9959), "Portland": (45.5231, -122.6765),
    "Providence": (41.8240, -71.4128), "Provo": (40.2338, -111.6585),
    "Raleigh": (35.7796, -78.6382), "Rapid City": (44.0805, -103.2310),
    "Reno": (39.5296, -119.8138), "Richmond": (37.5407, -77.4360),
    "Riverside": (33.9806, -117.3755), "Rochester": (43.1566, -77.6088),
    "Rockford": (42.2711, -89.0940), "Sacramento": (38.5816, -121.4944),
    "Saint Louis": (38.6270, -90.1994), "Saint Paul": (44.9537, -93.0900),
    "Salem": (44.9429, -123.0351), "Salt Lake City": (40.7608, -111.8910),
    "San Antonio": (29.4241, -98.4936), "San Diego": (32.7157, -117.1611),
    "San Francisco": (37.7749, -122.4194), "San Jose": (37.3382, -121.8863),
    "Santa Fe": (35.6870, -105.9378), "Savannah": (32.0835, -81.0998),
    "Scottsdale": (33.4942, -111.9261), "Seattle": (47.6062, -122.3321),
    "Shreveport": (32.5252, -93.7502), "Sioux Falls": (43.5446, -96.7311),
    "Spokane": (47.6588, -117.4260), "Springfield": (37.2090, -93.2923),
    "Stockton": (37.9577, -121.2908), "Syracuse": (43.0481, -76.1474),
    "Tacoma": (47.2529, -122.4443), "Tallahassee": (30.4518, -84.2807),
    "Tampa": (27.9506, -82.4572), "Toledo": (41.6639, -83.5552),
    "Trenton": (40.2171, -74.7429), "Tucson": (32.2226, -110.9747),
    "Tulsa": (36.1540, -95.9928), "Virginia Beach": (36.8529, -75.9780),
    "Warwick": (41.7001, -71.4162), "Washington": (38.9072, -77.0369),
    "West Valley City": (40.6916, -112.0011), "Wichita": (37.6872, -97.3301),
    "Wilmington": (39.7447, -75.5483), "Worcester": (42.2626, -71.8023),
    "Yuma": (32.6927, -114.6277),
}

# ─── ITC / Tax Credit Settings ───────────────────────────────────────────────
ITC_BASE_RATE = 0.30           # 30% base ITC (IRA Section 48E)
ITC_DOMESTIC_CONTENT = 0.10   # +10% domestic content adder
UNDERSERVED_OPTIONS = {
    "None (0%)": 0.00,
    "Low-Income Community — §45D  (+10%)": 0.10,
    "Energy Community (coal/oil closure)  (+20%)": 0.20,
}

# ─── BESS Physical Parameters ─────────────────────────────────────────────────
BESS_RTE = 0.92                # Round-trip efficiency (Megapack spec)
BESS_CYCLES_PER_YEAR = 300     # Typical grid-arbitrage cycling
BESS_OM_PER_MWH_YEAR = 8_000   # $/MWh·yr O&M
BESS_DEGRADATION = 0.02        # 2% capacity fade per year
BESS_AUGMENTATION_YEAR = 10    # Augment at year 10 to restore to 80%

# ─── Generation Asset Parameters ─────────────────────────────────────────────
SOLAR_OM_PER_MW_YEAR = 17_000   # $/MW·yr fixed O&M
WIND_OM_PER_MW_YEAR  = 35_000   # $/MW·yr fixed O&M
SOLAR_DEGRADATION = 0.005       # 0.5%/yr module degradation
WIND_DEGRADATION  = 0.003       # 0.3%/yr turbine output degradation

# ─── Mining Parameters ────────────────────────────────────────────────────────
MINER_OM_RATE = 0.02            # 2% of hardware cost per year
DC_AC_RATIO_SOLAR = 1.25        # Typical solar DC/AC oversizing
PROJECT_LIFE_YEARS = 25

# ─── Control Service Defaults ────────────────────────────────────────────────
CONTROL_SERVICE_PORT = 8400
DISPATCH_INTERVAL_SECONDS = 300         # 5 minutes
SAFETY_MAX_CONSECUTIVE_FAILURES = 3
SAFETY_FAILSAFE_MINER_MODE = "sleep"
SAFETY_FAILSAFE_BESS_MODE = "idle"
