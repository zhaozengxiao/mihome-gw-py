"""Vibration sensor."""

from .base import BaseSensor


class VibrationSensor(BaseSensor):
    """Xiaomi Vibration sensor."""

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
            self.state = status in ("vibrate", "true")
            obj["state"] = self.state
            new_data = True

        for key in ("tilt_angle", "orientationX", "orientationY", "orientationZ", "bed_activity"):
            val = data.get(key)
            if val is not None:
                obj[key] = float(val)
                new_data = True

        return obj if new_data else None