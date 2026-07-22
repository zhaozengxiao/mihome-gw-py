"""Alarm sensor (Gas / Smoke)."""

from .base import BaseSensor


class Alarm(BaseSensor):
    """Xiaomi Gas / Smoke alarm sensor."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: bool = False
        self.desc: str | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        alarm = data.get("alarm")
        if alarm is not None:
            triggered = alarm in ("1", 1, True)
            self.state = triggered
            obj["state"] = self.state
            self.desc = "Alarm triggered" if triggered else "Normal"
            obj["description"] = self.desc
            new_data = True

        desc = data.get("desc")
        if desc is not None:
            self.desc = desc
            obj["description"] = self.desc
            new_data = True

        return obj if new_data else None