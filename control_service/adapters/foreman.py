"""
Foreman Mining fleet management adapter.

Integrates with the Foreman REST API (https://foreman.mn) for controlling
miner power states: High (full power), Low (reduced), Sleep (shutdown).

Authentication uses client_id + API key passed as an Authorization header.
"""

import logging
from datetime import datetime, timezone

import httpx

from .base import MinerAdapter
from ..models import MinerStatus

logger = logging.getLogger(__name__)


class ForemanAdapter(MinerAdapter):
    """Controls miners via the Foreman.mn Power Control API."""

    def __init__(self, api_url: str, client_id: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"{self.client_id}:{self.api_key}"},
            timeout=10.0,
        )
        self._connected = await self.health_check()
        if self._connected:
            logger.info("Foreman adapter connected to %s", self.api_url)
        else:
            logger.warning("Foreman adapter failed health check at %s", self.api_url)
        return self._connected

    async def get_status(self) -> MinerStatus:
        if not self._client:
            return MinerStatus()
        try:
            resp = await self._client.get("/miners")
            resp.raise_for_status()
            data = resp.json()
            # Foreman returns a list of miners; aggregate fleet status
            total_power = 0.0
            total_hashrate = 0.0
            modes = set()
            for miner in data.get("miners", data if isinstance(data, list) else []):
                total_power += miner.get("power", 0) / 1_000_000  # W → MW
                total_hashrate += miner.get("hashrate", 0) / 1_000  # GH → TH
                modes.add(miner.get("powerMode", "unknown").lower())

            # Determine fleet-level mode
            if modes == {"sleep"} or not modes:
                fleet_mode = "sleep"
            elif "high" in modes:
                fleet_mode = "high"
            elif "low" in modes:
                fleet_mode = "low"
            else:
                fleet_mode = "unknown"

            return MinerStatus(
                online=True,
                power_mode=fleet_mode,
                power_mw=total_power,
                hashrate_th=total_hashrate,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("Foreman get_status error: %s", e)
            return MinerStatus(online=False)

    async def set_power_mode(self, mode: str) -> bool:
        """
        Set power mode for all miners.

        Foreman Power Control API:
          POST /actions/power
          Body: {"mode": "high"|"low"|"sleep"}
        """
        if not self._client:
            return False
        try:
            resp = await self._client.post(
                "/actions/power",
                json={"mode": mode},
            )
            resp.raise_for_status()
            logger.info("Foreman: set fleet to %s mode (HTTP %d)", mode, resp.status_code)
            return True
        except Exception as e:
            logger.error("Foreman set_power_mode(%s) failed: %s", mode, e)
            return False

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get("/ping")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
