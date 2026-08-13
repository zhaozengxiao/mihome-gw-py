"""Cube controller."""

import asyncio

from .base import BaseSensor


class Cube(BaseSensor):
    """Xiaomi Cube controller."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: str | None = None
        self._reset_timer = None

    def _schedule_reset(self):
        """0.5s 后发布 idle, 复位动作状态 (新动作取消旧定时器)."""
        if self._reset_timer:
            self._reset_timer.cancel()
        self._reset_timer = asyncio.get_running_loop().call_later(
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
            obj["action"] = str(status).lower()
            self._schedule_reset()
            new_data = True

        rotate = data.get("rotate")
        if rotate is not None:
            obj["rotate"] = rotate
            new_data = True

        return obj if new_data else None
