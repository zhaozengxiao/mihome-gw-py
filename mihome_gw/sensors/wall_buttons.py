"""Wall Buttons (Wireless Remote Switch)."""

from .base import BaseSensor


class WallButtons(BaseSensor):
    """Xiaomi Wireless Remote Switch (Wall Buttons)."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        channel_0 = data.get("channel_0")
        if channel_0 is not None:
            obj["channel_0"] = channel_0 == "click"
            new_data = True

        channel_1 = data.get("channel_1")
        if channel_1 is not None:
            obj["channel_1"] = channel_1 == "click"
            new_data = True

        dual_channel = data.get("dual_channel")
        if dual_channel is not None:
            obj["dual_channel"] = dual_channel == "click"
            new_data = True

        status = data.get("status")
        if status is not None:
            obj["channel_0"] = status == "click"
            new_data = True

        return obj if new_data else None