"""Wall Wired Switch."""

from .base import BaseSensor


class WallWiredSwitch(BaseSensor):
    """Xiaomi Wired Wall Switch."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.channel_0: bool | None = None
        self.channel_1: bool | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        channel_0 = data.get("channel_0")
        if channel_0 is not None:
            self.channel_0 = channel_0 in ("on", True)
            obj["channel_0"] = self.channel_0
            new_data = True

        channel_1 = data.get("channel_1")
        if channel_1 is not None:
            self.channel_1 = channel_1 in ("on", True)
            obj["channel_1"] = self.channel_1
            new_data = True

        return obj if new_data else None

    def control(self, attr: str, value) -> None:
        message = {
            "cmd": "write", "model": self.className, "sid": self.sid,
            "short_id": 0, "data": {},
        }
        if attr == "channel_0":
            message["data"]["channel_0"] = "on" if value else "off"
        elif attr == "channel_1":
            message["data"]["channel_1"] = "on" if value else "off"
        message["data"]["key"] = self.hub.get_key(self.ip)
        self.hub.send_message(message, self.ip)