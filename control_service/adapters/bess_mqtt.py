"""
MQTT adapter for Battery Energy Storage Systems.

Publishes charge/discharge setpoints and subscribes to status updates.

Topics (configurable):
  Publish:   bess/command  → {"action": "charge", "power_mw": 1.5}
  Subscribe: bess/status   → {"soc_pct": 72, "soc_mwh": 2.74, "mode": "idle", "power_mw": 0}
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .base import BESSAdapter
from ..models import BESSStatus

logger = logging.getLogger(__name__)


class BESSMqttAdapter(BESSAdapter):
    """Controls a BESS via MQTT pub/sub."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        command_topic: str = "bess/command",
        status_topic: str = "bess/status",
        username: str = "",
        password: str = "",
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.command_topic = command_topic
        self.status_topic = status_topic
        self.username = username
        self.password = password
        self._client = None
        self._connected = False
        self._last_status: Optional[BESSStatus] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> bool:
        try:
            import paho.mqtt.client as mqtt

            self._loop = asyncio.get_running_loop()
            self._client = mqtt.Client(protocol=mqtt.MQTTv5)

            if self.username:
                self._client.username_pw_set(self.username, self.password)

            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message

            self._client.connect_async(self.broker_host, self.broker_port)
            self._client.loop_start()

            # Wait briefly for connection
            await asyncio.sleep(2)
            self._connected = self._client.is_connected()
            if self._connected:
                logger.info("BESS MQTT connected to %s:%d", self.broker_host, self.broker_port)
            return self._connected
        except Exception as e:
            logger.error("BESS MQTT connect failed: %s", e)
            return False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(self.status_topic)
            logger.info("BESS MQTT subscribed to %s", self.status_topic)
        else:
            logger.error("BESS MQTT connect returned code %d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            self._last_status = BESSStatus(
                online=True,
                mode=data.get("mode", "unknown"),
                soc_mwh=data.get("soc_mwh", 0.0),
                soc_pct=data.get("soc_pct", 0.0),
                power_mw=data.get("power_mw", 0.0),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("BESS MQTT message parse error: %s", e)

    async def get_status(self) -> BESSStatus:
        if self._last_status:
            return self._last_status
        return BESSStatus(online=self._connected)

    async def set_charge(self, power_mw: float) -> bool:
        return self._publish({"action": "charge", "power_mw": power_mw})

    async def set_discharge(self, power_mw: float) -> bool:
        return self._publish({"action": "discharge", "power_mw": power_mw})

    async def set_idle(self) -> bool:
        return self._publish({"action": "idle", "power_mw": 0.0})

    def _publish(self, payload: dict) -> bool:
        if not self._client or not self._connected:
            return False
        try:
            result = self._client.publish(
                self.command_topic,
                json.dumps(payload),
                qos=1,
            )
            success = result.rc == 0
            if success:
                logger.info("BESS MQTT published to %s: %s", self.command_topic, payload)
            return success
        except Exception as e:
            logger.error("BESS MQTT publish failed: %s", e)
            return False

    async def health_check(self) -> bool:
        return bool(self._client and self._connected)

    async def close(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
