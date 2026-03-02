"""Control service configuration — loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings
from typing import Optional


class ControlSettings(BaseSettings):
    """All settings for the dispatch control service."""

    # ── Site parameters ──────────────────────────────────────────────────
    iso: str = "ERCOT"
    break_even_mwh: float = 85.0
    bess_power_mw: float = 1.9
    bess_energy_mwh: float = 3.8
    mining_power_mw: float = 15.0
    interconnection_mw: float = 100.0
    rte: float = 0.92
    grid_tied: bool = True
    ancillary_premium: float = 12.0       # $/MWh

    # ── Dispatch loop ────────────────────────────────────────────────────
    dispatch_interval_seconds: int = 300   # 5 minutes
    lmp_history_window: int = 72           # data points for future LMP avg

    # ── API keys ─────────────────────────────────────────────────────────
    gridstatus_api_key: str = ""

    # ── Foreman Mining ───────────────────────────────────────────────────
    foreman_api_url: str = "https://dashboard.foreman.mn/api"
    foreman_client_id: str = ""
    foreman_api_key: str = ""

    # ── BESS adapter ─────────────────────────────────────────────────────
    bess_adapter_type: str = "rest"        # "rest" or "mqtt"
    bess_rest_url: str = "http://localhost:8080"
    bess_rest_api_key: str = ""
    bess_mqtt_broker: str = "localhost"
    bess_mqtt_port: int = 1883
    bess_mqtt_username: str = ""
    bess_mqtt_password: str = ""
    bess_mqtt_command_topic: str = "bess/command"
    bess_mqtt_status_topic: str = "bess/status"

    # ── Safety ───────────────────────────────────────────────────────────
    safety_max_consecutive_failures: int = 3
    safety_failsafe_miner_mode: str = "sleep"
    safety_failsafe_bess_mode: str = "idle"
    safety_min_soc_pct: float = 5.0       # block discharge below this %
    safety_max_soc_pct: float = 98.0      # block charge above this %

    # ── Service ──────────────────────────────────────────────────────────
    service_port: int = 8400
    audit_db_path: str = "audit.db"

    model_config = {"env_prefix": "GRIDSTACK_", "env_file": ".env", "extra": "ignore"}
