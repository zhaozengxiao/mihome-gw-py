"""Temperature/Humidity sensor."""

import time
import asyncio
import logging

from .base import BaseSensor

logger = logging.getLogger(__name__)


class THSensor(BaseSensor):
    """Xiaomi Temperature/Humidity sensor."""

    def __init__(self, sid: str, ip: str, hub, model: str, options=None):
        super().__init__(sid, ip, hub, model)
        self.interval = int((options or {}).get("interval", 5000)) or 0
        self.temperature: float | None = None
        self.humidity: float | None = None
        self.pressure: float | None = None
        self.lastData: float | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}
        ts = time.time() * 1000

        if self.interval and self.lastData is not None:
            diff = ts - self.lastData
            if 200 < diff < self.interval:
                obj["doublePress"] = True
                asyncio.get_event_loop().call_later(
                    0.3, lambda: self.hub.emit("data", self.sid, self.className, {"doublePress": False})
                )
                self.lastData = None
            else:
                self.lastData = ts
        else:
            self.lastData = ts

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        temp = data.get("temperature")
        if temp is not None:
            temp = int(temp)
            if temp == 10000:
                return None
            self.temperature = temp / 100.0
            obj["temperature"] = self.temperature
            new_data = True

        hum = data.get("humidity")
        if hum is not None:
            self.humidity = int(hum) / 100.0
            obj["humidity"] = self.humidity
            new_data = True

        pres = data.get("pressure")
        if pres is not None and pres != 0 and pres != "0":
            self.pressure = int(pres) / 100.0
            obj["pressure"] = self.pressure
            new_data = True

        return obj if new_data else None