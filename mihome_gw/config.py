"""Configuration loading and defaults."""

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GatewayConfig:
    ip: str
    key: str
    sid: str = ""


@dataclass
class OutputConfig:
    type: str = "console"
    url: str = ""
    prefix: str = "mihome/"


@dataclass
class RuleConfig:
    name: str = ""
    match: dict | None = None
    target: dict | None = None
    onValue: Any = None
    offValue: Any = None
    delay: int | None = None
    doorGuard: str | None = None
    condition: dict | None = None


@dataclass
class Config:
    port: int = 9898
    bind: str = "0.0.0.0"
    debug: bool = False
    enable_triggers: bool = True
    doorOpenCooldownMs: int = 5000
    heartbeatTimeout: int = 120
    rediscoverInterval: int = 60
    gateways: list[GatewayConfig] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
    rules: list[dict] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "Config":
        with open(path, "r") as f:
            data = json.load(f)

        config = cls()
        config.port = data.get("port", 9898)
        config.bind = data.get("bind", "0.0.0.0")
        config.debug = data.get("debug", False)
        config.enable_triggers = data.get("enable_triggers", True)
        config.doorOpenCooldownMs = int(data.get("doorOpenCooldownMs", 5000))
        config.heartbeatTimeout = data.get("heartbeatTimeout", 120)
        config.rediscoverInterval = data.get("rediscoverInterval", 60)

        config.gateways = [
            GatewayConfig(ip=g["ip"], key=g["key"], sid=g.get("sid", ""))
            for g in data.get("gateways", [])
        ]

        output = data.get("output", {})
        config.output = OutputConfig(
            type=output.get("type", "console"),
            url=output.get("url", ""),
            prefix=output.get("prefix", "mihome/"),
        )

        config.rules = data.get("rules", [])
        return config

    @classmethod
    def from_options(cls, options_path: str = "/data/options.json") -> "Config":
        """Convert HA Supervisor options.json to Config."""
        with open(options_path, "r") as f:
            opt = json.load(f)

        door_cooldown = int(opt.get("doorOpenCooldownMs", 0))
        if door_cooldown <= 0:
            door_cooldown = 5000

        mqtt_user = opt.get("mqtt_user", "")
        mqtt_password = opt.get("mqtt_password", "")
        mqtt_server = opt.get("mqtt_server", "core-mosquitto")
        mqtt_port = opt.get("mqtt_port", 1883)

        mqtt_url = f"mqtt://{mqtt_user}:{mqtt_password}@{mqtt_server}:{mqtt_port}"

        config = cls()
        config.gateways = [
            GatewayConfig(ip=opt["gateway_ip"], key=opt["gateway_key"])
        ]
        config.output = OutputConfig(type="mqtt", url=mqtt_url, prefix="mihome/")
        config.debug = bool(opt.get("debug", False))
        config.enable_triggers = opt.get("enable_triggers", True) is not False
        config.doorOpenCooldownMs = door_cooldown
        config.rules = opt.get("rules", [])
        return config