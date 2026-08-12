"""Smart Lock."""

import asyncio

from .base import BaseSensor


class Lock(BaseSensor):
    """Xiaomi Smart Lock."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)

    def _schedule_reset(self):
        """0.5s 后发布 idle, 复位动作状态."""
        asyncio.get_running_loop().call_later(
            0.5, lambda: self.hub.emit("data", self.sid, self.className, {"action": "idle"})
        )

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        for key, action in (
            ("fing_verified", "finger"),
            ("psw_verified", "password"),
            ("card_verified", "card"),
            ("verified_wrong", "wrong"),
        ):
            val = data.get(key)
            if val is not None:
                obj["action"] = action
                self._schedule_reset()
                new_data = True

        return obj if new_data else None
