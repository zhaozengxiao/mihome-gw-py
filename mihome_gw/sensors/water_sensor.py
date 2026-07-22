"""Water leak sensor."""

from .base import BaseSensor


class WaterSensor(BaseSensor):
    """Xiaomi Aqara Water Sensor."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: bool = False

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        status = data.get("status")
        if status is not None:
            self.state = status in ("leak", "true", True)
            obj["state"] = self.state
            new_data = True

        return obj if new_data else None