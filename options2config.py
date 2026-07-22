#!/usr/bin/env python3
"""Convert HA Supervisor options.json to config.json."""

import json
import os
import sys


def main():
    options_path = "/data/options.json"
    try:
        with open(options_path, "r") as f:
            opt = json.load(f)
    except Exception as e:
        print(f"[options2config] 无法读取 {options_path}: {e}", file=sys.stderr)
        sys.exit(1)

    door_cooldown = int(opt.get("doorOpenCooldownMs", 0))
    if door_cooldown <= 0:
        door_cooldown = 3000

    mqtt_user = opt.get("mqtt_user", "")
    mqtt_password = opt.get("mqtt_password", "")
    mqtt_server = opt.get("mqtt_server", "core-mosquitto")
    mqtt_port = opt.get("mqtt_port", 1883)

    mqtt_url = f"mqtt://{mqtt_user}:{mqtt_password}@{mqtt_server}:{mqtt_port}"

    config = {
        "port": 9898,
        "bind": "0.0.0.0",
        "debug": bool(opt.get("debug", False)),
        "enable_triggers": opt.get("enable_triggers", True) is not False,
        "doorOpenCooldownMs": door_cooldown,
        "gateways": [
            {"ip": opt["gateway_ip"], "key": opt["gateway_key"], "sid": ""}
        ],
        "output": {
            "type": "mqtt",
            "url": mqtt_url,
            "prefix": "mihome/",
        },
        "rules": opt.get("rules", []),
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("[options2config] config.json 已生成")


if __name__ == "__main__":
    main()