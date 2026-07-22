"""Smart Curtain."""

from .base import BaseSensor


class Curtain(BaseSensor):
    """Xiaomi Aqara Smart Curtain."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self.curtain_level: int | None = None

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        curtain_level = data.get("curtain_level")
        if curtain_level is not None:
            self.curtain_level = int(curtain_level)
            obj["curtain_level"] = self.curtain_level
            new_data = True

        status = data.get("status")
        if status in ("open", "close", "stop"):
            obj[status] = True
            new_data = True

        return obj if new_data else None

    def control(self, attr: str, value) -> None:
        message = {
            "cmd": "write", "model": self.className, "sid": self.sid,
            "short_id": 0, "data": {},
        }
        if attr == "curtain_level":
            message["data"]["curtain_level"] = value
        message["data"]["key"] = self.hub.get_key(self.ip)
        self.hub.send_message(message, self.ip)