"""Wireless Button."""

import asyncio

from .base import BaseSensor


class Button(BaseSensor):
    """Xiaomi Wireless Button / Switch."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.click: bool | None = None
        self.double: bool | None = None
        self.long: bool | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        status = data.get("status")
        if status is not None:
            obj["click"] = status == "click"
            obj["double"] = status == "double_click"
            obj["long"] = status == "long_click_press"
            if status == "click":
                asyncio.get_event_loop().call_later(
                    0.1, lambda: self.hub.emit("data", self.sid, self.className, {"click": False})
                )
            new_data = True
        elif data.get("voltage") is not None:
            obj["click"] = False
            obj["double"] = False
            obj["long"] = False
            new_data = True

        return obj if new_data else None