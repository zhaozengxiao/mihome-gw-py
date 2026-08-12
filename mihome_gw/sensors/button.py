"""Wireless Button."""

import asyncio

from .base import BaseSensor


class Button(BaseSensor):
    """Xiaomi Wireless Button / Switch."""

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

        status = data.get("status")
        if status is not None:
            action = {
                "click": "danji",
                "double_click": "shuangji",
                "long_click_press": "changan",
                "long_click": "changan",
            }.get(status)
            if action:
                obj["action"] = action
                self._schedule_reset()
            new_data = True
        elif data.get("voltage") is not None:
            obj["action"] = "idle"
            new_data = True

        return obj if new_data else None
