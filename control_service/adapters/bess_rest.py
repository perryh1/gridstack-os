"""
Generic REST adapter for Battery Energy Storage Systems.

Works with any BESS controller exposing a simple REST API:
  GET  /status  → {"soc_pct": 72, "soc_mwh": 2.74, "power_mw": 0, "mode": "idle"}
  POST /command → {"action": "charge"|"discharge"|"idle", "power_mw": 1.5}

Adapt the endpoint paths and payload format to match your specific BMS.
"""

import logging
from datetime import datetime, timezone

import httpx

from .base import BESSAdapter
from ..models import BESSStatus

logger = logging.getLogger(__name__)


class BESSRestAdapter(BESSAdapter):
    """Controls a BESS via a generic REST API."""

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    async def connect(self) -> bool:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=10.0,
        )
        self._connected = await self.health_check()
        if self._connected:
            logger.info("BESS REST adapter connected to %s", self.base_url)
        return self._connected

    async def get_status(self) -> BESSStatus:
        if not self._client:
            return BESSStatus()
        try:
            resp = await self._client.get("/status")
            resp.raise_for_status()
            data = resp.json()
            return BESSStatus(
                online=True,
                mode=data.get("mode", "unknown"),
                soc_mwh=data.get("soc_mwh", 0.0),
                soc_pct=data.get("soc_pct", 0.0),
                power_mw=data.get("power_mw", 0.0),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("BESS REST get_status error: %s", e)
            return BESSStatus(online=False)

    async def set_charge(self, power_mw: float) -> bool:
        return await self._send_command("charge", power_mw)

    async def set_discharge(self, power_mw: float) -> bool:
        return await self._send_command("discharge", power_mw)

    async def set_idle(self) -> bool:
        return await self._send_command("idle", 0.0)

    async def _send_command(self, action: str, power_mw: float) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.post(
                "/command",
                json={"action": action, "power_mw": power_mw},
            )
            resp.raise_for_status()
            logger.info("BESS REST: %s at %.2f MW (HTTP %d)", action, power_mw, resp.status_code)
            return True
        except Exception as e:
            logger.error("BESS REST %s failed: %s", action, e)
            return False

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get("/status")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
