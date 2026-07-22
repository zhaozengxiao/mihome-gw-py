"""Motion sensor."""

from .base import BaseSensor


class MotionSensor(BaseSensor):
    """Xiaomi Motion sensor."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: bool = False
        self.motion: bool = False
        self.no_motion: int | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        status = data.get("status")
        if status is not None:
            self.motion = status == "motion"
            obj["state"] = self.motion
            new_data = True

        no_motion = data.get("no_motion")
        if no_motion is not None and no_motion != self.no_motion:
            self.no_motion = no_motion
            obj["no_motion"] = self.no_motion
            new_data = True

        lux = data.get("lux")
        if lux is not None:
            obj["lux"] = int(lux)
            new_data = True

        return obj if new_data else None