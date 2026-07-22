"""Base sensor class for all Xiaomi devices."""

import logging

logger = logging.getLogger(__name__)


class BaseSensor:
    """Base class for all Xiaomi sensors."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        self.sid = sid
        self.ip = ip
        self.hub = hub
        self.className = model
        self.voltage: float | None = None
        self.percent: float | None = None

    def _parse_voltage(self, data: dict) -> dict:
        """Parse battery voltage and return voltage/percent dict if changed."""
        voltage_raw = data.get("voltage")
        if voltage_raw is None:
            return {}

        voltage = int(voltage_raw)
        new_voltage = voltage / 1000.0
        if new_voltage == self.voltage:
            return {}

        self.voltage = new_voltage
        self.percent = round(((voltage - 2655) / 3.45) * 10) / 10
        if self.percent > 100:
            self.percent = 100
        if self.percent < 0:
            self.percent = 0
        return {"voltage": self.voltage, "percent": self.percent}

    def get_data(self, data: dict) -> dict | None:
        """Parse incoming data. Returns dict of changed values, or None."""
        raise NotImplementedError

    def heart_beat(self, token: str | None = None, data: dict | None = None) -> None:
        """Handle heartbeat message."""
        if data:
            obj = self.get_data(data)
            if obj:
                self.hub.emit("data", self.sid, self.className, obj)

    def on_message(self, message: dict) -> None:
        """Handle incoming message."""
        if message.get("data"):
            obj = self.get_data(message["data"])
            if obj:
                self.hub.emit("data", self.sid, self.className, obj)

    def control(self, attr: str, value) -> None:
        """Control this device. Override in subclasses that support control."""
        pass