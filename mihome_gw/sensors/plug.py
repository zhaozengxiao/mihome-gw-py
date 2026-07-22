"""Smart Plug."""

from .base import BaseSensor


class Plug(BaseSensor):
    """Xiaomi Smart Plug."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.state: bool | None = None
        self.load_power: float | None = None
        self.power_consumed: float | None = None
        self.inuse: bool | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        voltage_data = self._parse_voltage(data)
        if voltage_data:
            obj.update(voltage_data)
            new_data = True

        status = data.get("status")
        if status is not None:
            self.state = status == "on"
            obj["state"] = self.state
            new_data = True

        load_power = data.get("load_power")
        if load_power is not None:
            self.load_power = load_power
            obj["load_power"] = self.load_power
            new_data = True

        power_consumed = data.get("power_consumed")
        if power_consumed is not None:
            self.power_consumed = power_consumed
            obj["power_consumed"] = self.power_consumed
            new_data = True

        inuse = data.get("inuse")
        if inuse is not None:
            self.inuse = inuse in ("true", True)
            obj["inuse"] = self.inuse
            new_data = True

        channel_0 = data.get("channel_0")
        if channel_0 is not None:
            self.state = channel_0 in ("on", True)
            obj["state"] = self.state
            new_data = True

        return obj if new_data else None

    def control(self, attr: str, value) -> None:
        message = {
            "cmd": "write", "model": self.className, "sid": self.sid,
            "short_id": 0, "data": {"key": self.hub.get_key(self.ip)},
        }
        if attr == "channel_0":
            message["data"]["channel_0"] = "on" if value else "off"
        else:
            message["data"][attr] = "on" if value else "off"
        self.hub.send_message(message, self.ip)