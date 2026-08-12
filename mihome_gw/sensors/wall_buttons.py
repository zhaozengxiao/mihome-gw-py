"""Wall Buttons (Wireless Remote Switch)."""

import asyncio

from .base import BaseSensor

# remote.b186acn01 / b286acn01 等上报的 channel_* 动作值
_ACTION_MAP = {
    "click": "danji",
    "double_click": "shuangji",
    "long_click_press": "changan",
    "long_click": "changan",
}


class WallButtons(BaseSensor):
    """Xiaomi Wireless Remote Switch (Wall Buttons)."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)

    def _schedule_reset(self):
        """0.5s 后发布 idle, 复位动作状态."""
        asyncio.get_running_loop().call_later(
            0.5, lambda: self.hub.emit("data", self.sid, self.className, {"action": "idle"})
        )

    @staticmethod
    def _action_for(value) -> str:
        return _ACTION_MAP.get(str(value), str(value).lower())

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        channel_0 = data.get("channel_0")
        if channel_0 is not None:
            obj["action"] = self._action_for(channel_0)
            self._schedule_reset()
            new_data = True

        channel_1 = data.get("channel_1")
        if channel_1 is not None:
            obj["action"] = f"channel_1_{self._action_for(channel_1)}"
            self._schedule_reset()
            new_data = True

        dual_channel = data.get("dual_channel")
        if dual_channel is not None:
            obj["action"] = f"both_{self._action_for(dual_channel)}"
            self._schedule_reset()
            new_data = True

        status = data.get("status")
        if status is not None:
            obj["action"] = self._action_for(status)
            self._schedule_reset()
            new_data = True

        return obj if new_data else None
