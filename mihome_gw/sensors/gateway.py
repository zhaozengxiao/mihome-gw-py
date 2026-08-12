"""Gateway sensor (Xiaomi RGB Gateway / AC Partner)."""

import asyncio
import logging

from .base import BaseSensor

logger = logging.getLogger(__name__)


class Gateway(BaseSensor):
    """Xiaomi RGB Gateway / Aqara AC Partner."""

    def __init__(self, sid: str, ip: str, hub, model: str):
        super().__init__(sid, ip, hub, model)
        self._loop = asyncio.get_running_loop()
        if "acpartner" in model:
            self.type = model
        else:
            self.type = "gateway"

        self.token: str | None = None
        self.illumination: float | None = None
        self.protoVersion: str = ""
        self.acPower: float | None = None
        self.onOffCfg: str | None = None
        self.modeCfg: str | None = None
        self.wsCfg: str | None = None
        self.swingCfg: str | None = None
        self.tempCfg: float | None = None
        self.relayStatus: str | None = None
        self.connected: bool = False

        self.lastValues = {"rgb": "#FFFFFF", "dimmer": 100}
        self.rgb: str | None = None
        self.dimmer: int | None = None
        self.on: bool | None = None
        self.mid: int | None = None
        self.timeout_handle = None

        if hub.proto_major(self.ip) == "2":
            hub.send_message({"cmd": "discovery", "sid": sid}, self.ip)
        else:
            hub.send_message({"cmd": "get_id_list", "sid": sid}, self.ip)

    def _schedule_timeout(self):
        timeout = 130000 if self.hub.proto_major(self.ip) == "2" else 20000
        if self.timeout_handle:
            self.timeout_handle.cancel()
        self.timeout_handle = self._loop.call_later(
            timeout / 1000,
            lambda: self.hub.emit("data", self.sid, self.type, {"connected": False}),
        )

    def get_data(self, data: dict) -> dict | None:
        new_data = False
        obj = {}

        if data.get("proto_version") is not None and data["proto_version"] != self.protoVersion:
            self.protoVersion = data["proto_version"]
            obj["proto_version"] = self.protoVersion
            new_data = True

        for attr_key, attr_name in [
            ("on_off_cfg", "onOffCfg"), ("mode_cfg", "modeCfg"),
            ("ws_cfg", "wsCfg"), ("swing_cfg", "swingCfg"),
            ("relay_status", "relayStatus"), ("ac_power", "acPower"),
        ]:
            val = data.get(attr_key)
            if val is not None and val != getattr(self, attr_name):
                setattr(self, attr_name, val)
                obj[attr_key] = val
                new_data = True

        if data.get("temp_cfg") is not None and data["temp_cfg"] != self.tempCfg:
            self.tempCfg = data["temp_cfg"]
            obj["temp_cfg"] = self.tempCfg
            new_data = True

        if data.get("illumination") is not None:
            self.illumination = float(data["illumination"])
            obj["illumination"] = self.illumination
            new_data = True

        if not self.connected:
            self.connected = True
            obj["connected"] = True
            new_data = True

        self._schedule_timeout()

        if data.get("rgb") is not None:
            rgb = int(data["rgb"])
            if not rgb:
                self.rgb = "#000000"
                self.dimmer = 0
                self.on = False
            else:
                rgb_hex = rgb.to_bytes(4, "big").hex()
                self.dimmer = int(rgb_hex[:2], 16)
                self.rgb = "#" + rgb_hex[2:].upper()
                self.on = True

            obj["on"] = self.on
            obj["dimmer"] = self.dimmer
            obj["rgb"] = self.rgb

            if obj["dimmer"]:
                self.lastValues["dimmer"] = obj["dimmer"]
            if int(obj["rgb"].replace("#", ""), 16):
                self.lastValues["rgb"] = obj["rgb"]
            new_data = True

        return obj if new_data else None

    def heart_beat(self, token: str | None = None, data: dict | None = None) -> None:
        if token:
            self.token = token
            if data:
                obj = self.get_data(data)
                if obj:
                    self.hub.emit("data", self.sid, self.className, obj)

    def on_message(self, message: dict) -> None:
        cmd = message.get("cmd")
        if cmd == "get_id_list_ack":
            self._init_sensors(message.get("data", []))
        elif cmd == "write_ack":
            if message.get("data", {}).get("error"):
                self.hub.emit("error", message["data"]["error"])
            obj = self.get_data(message.get("data", {}))
            if obj:
                self.hub.emit("data", self.sid, self.className, obj)
        elif message.get("data"):
            obj = self.get_data(message["data"])
            if obj:
                self.hub.emit("data", self.sid, self.className, obj)

    def _init_sensors(self, sids: list):
        self.hub.send_message({"cmd": "read", "sid": self.sid}, self.ip)
        for sid in sids:
            self.hub.send_message({"cmd": "read", "sid": sid}, self.ip)

    def control(self, attr: str, value) -> None:
        if attr in ("on", "dimmer", "rgb"):
            if self.dimmer is None:
                self.dimmer = self.lastValues["dimmer"]
            if self.rgb is None:
                self.rgb = self.lastValues["rgb"]
            if self.on is None:
                self.on = True

            if attr == "on":
                self.on = bool(value)
                if self.on:
                    if not int(self.rgb.replace("#", ""), 16):
                        self.rgb = self.lastValues["rgb"]
                    if not self.dimmer:
                        self.dimmer = self.lastValues["dimmer"]

            if attr == "dimmer":
                self.dimmer = max(0, min(100, value))
                if self.dimmer:
                    self.on = True
                    if not int(self.rgb.replace("#", ""), 16):
                        self.rgb = self.lastValues["rgb"]

            if attr == "rgb":
                self.rgb = str(value or "")
                if int(self.rgb.replace("#", ""), 16):
                    self.on = True
                    if not self.dimmer:
                        self.dimmer = self.lastValues["dimmer"]

            self._loop.call_later(0.2, self._send_rgb)

        elif attr == "volume":
            value = max(0, min(100, value))
            self.hub.send_message({
                "cmd": "write", "model": self.type, "sid": self.sid,
                "short_id": 0,
                "data": {"mid": self.mid or 999, "vol": value, "key": self.hub.get_key(self.ip)},
            }, self.ip)

        elif attr == "mid":
            self.mid = value
            self.hub.send_message({
                "cmd": "write", "model": self.type, "sid": self.sid,
                "short_id": 0,
                "data": {"mid": value, "key": self.hub.get_key(self.ip)},
            }, self.ip)

        elif attr in ("on_off_cfg", "mode_cfg", "ws_cfg", "swing_cfg", "relay_status",
                      "remove_device", "join_permission", "temp_cfg"):
            data = {attr: value, "key": self.hub.get_key(self.ip)}
            if attr == "temp_cfg":
                data["temp_cfg"] = int(value)
            self.hub.send_message({
                "cmd": "write", "model": self.type, "sid": self.sid,
                "short_id": 0, "data": data,
            }, self.ip)

        else:
            self.hub.emit("warning", f"Unknown attribute {attr}")

    def _send_rgb(self):
        if not self.on or not self.dimmer or self.rgb in ("000000", "#000000"):
            val = 0
        else:
            val = (self.dimmer << 24) | int(self.rgb.replace("#", ""), 16)

        self.hub.send_message({
            "cmd": "write", "model": self.type, "sid": self.sid,
            "short_id": 0,
            "data": {"rgb": val, "key": self.hub.get_key(self.ip)},
        }, self.ip)