"""Smart Lock."""

from .base import BaseSensor


class Lock(BaseSensor):
    """Xiaomi Smart Lock."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        for key in ("fing_verified", "psw_verified", "card_verified", "verified_wrong"):
            val = data.get(key)
            if val is not None:
                obj[key] = val
                new_data = True

        return obj if new_data else None