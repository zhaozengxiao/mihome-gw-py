"""Cube controller."""

from .base import BaseSensor


class Cube(BaseSensor):
    """Xiaomi Cube controller."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: str | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        status = data.get("status")
        if status is not None:
            obj[status] = True
            new_data = True

        rotate = data.get("rotate")
        if rotate is not None:
            obj["rotate"] = rotate
            new_data = True

        return obj if new_data else None