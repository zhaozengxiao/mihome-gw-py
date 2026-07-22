"""Home Assistant MQTT Discovery payload builder."""

from .devices import SENSOR_TYPES


def _device_name(sid: str, model: str) -> str:
    return (model + "_" + sid)[:32]


def _base_device(sid: str, model: str) -> dict:
    return {
        "identifiers": [f"mihome_{sid}"],
        "name": f"{model} {sid}",
        "manufacturer": "Xiaomi",
        "model": model,
    }


def build_discovery(sid: str, model: str, prefix: str = "mihome/") -> list[dict]:
    """Build list of {topic, payload} for HA MQTT auto-discovery."""
    state_topic = f"{prefix}state/{sid}/{model}"
    cmd_topic = f"{prefix}cmd/{sid}"
    dev = _base_device(sid, model)
    msgs = []

    # Temperature/Humidity sensor
    if model in SENSOR_TYPES["temperature"]:
        msgs += [
            {"topic": f"homeassistant/sensor/{sid}_temp/config", "payload": {
                "name": f"Temp {sid}", "device_class": "temperature", "unit_of_measurement": "°C",
                "state_topic": state_topic, "value_template": "{{ value_json.temperature }}",
                "unique_id": f"{sid}_temp", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_hum/config", "payload": {
                "name": f"Hum {sid}", "device_class": "humidity", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.humidity }}",
                "unique_id": f"{sid}_hum", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        if model in ("weather.v1", "weather"):
            msgs.append({"topic": f"homeassistant/sensor/{sid}_pres/config", "payload": {
                "name": f"Pressure {sid}", "device_class": "atmospheric_pressure", "unit_of_measurement": "hPa",
                "state_topic": state_topic, "value_template": "{{ value_json.pressure }}",
                "unique_id": f"{sid}_pres", "device": dev,
            }})
        return msgs

    # Door sensor
    if model in SENSOR_TYPES["door"]:
        msgs += [
            {"topic": f"homeassistant/binary_sensor/{sid}/config", "payload": {
                "name": _device_name(sid, model), "device_class": "door",
                "state_topic": state_topic, "value_template": "{{ value_json.state }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": sid, "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Motion sensor
    if model in SENSOR_TYPES["motion"]:
        msgs += [
            {"topic": f"homeassistant/binary_sensor/{sid}/config", "payload": {
                "name": _device_name(sid, model), "device_class": "motion",
                "state_topic": state_topic, "value_template": "{{ value_json.state }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": sid, "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_no_motion/config", "payload": {
                "name": f"No Motion {sid}", "unit_of_measurement": "s",
                "state_topic": state_topic, "value_template": "{{ value_json.no_motion }}",
                "unique_id": f"{sid}_no_motion", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        if model == "sensor_motion.aq2":
            msgs.append({"topic": f"homeassistant/sensor/{sid}_lux/config", "payload": {
                "name": f"Lux {sid}", "device_class": "illuminance", "unit_of_measurement": "lux",
                "state_topic": state_topic, "value_template": "{{ value_json.lux }}",
                "unique_id": f"{sid}_lux", "device": dev,
            }})
        return msgs

    # Switch (plug / wall switch)
    if model in SENSOR_TYPES["switch_ctrl"]:
        has_ch0 = model in ("plug", "86plug", "ctrl_86plug", "ctrl_86plug.aq1",
                            "ctrl_ln1", "ctrl_ln1.aq1", "ctrl_neutral1")
        is_plug = model in ("plug", "86plug", "ctrl_86plug", "ctrl_86plug.aq1")
        attr0 = "state" if is_plug else "channel_0"

        msgs.append({"topic": f"homeassistant/switch/{sid}_ch0/config", "payload": {
            "name": _device_name(sid, model) + " CH0",
            "state_topic": state_topic, "value_template": "{{{{ value_json.{0} }}}}".format(attr0),
            "command_topic": f"{cmd_topic}/{attr0}",
            "payload_on": "true", "payload_off": "false",
            "state_on": "true", "state_off": "false",
            "unique_id": f"{sid}_ch0", "device": dev,
        }})
        if not has_ch0:
            msgs.append({"topic": f"homeassistant/switch/{sid}_ch1/config", "payload": {
                "name": _device_name(sid, model) + " CH1",
                "state_topic": state_topic, "value_template": "{{ value_json.channel_1 }}",
                "command_topic": f"{cmd_topic}/channel_1",
                "payload_on": "true", "payload_off": "false",
                "state_on": "true", "state_off": "false",
                "unique_id": f"{sid}_ch1", "device": dev,
            }})
        if is_plug:
            msgs += [
                {"topic": f"homeassistant/sensor/{sid}_power/config", "payload": {
                    "name": f"Power {sid}", "device_class": "power", "unit_of_measurement": "W",
                    "state_topic": state_topic, "value_template": "{{ value_json.load_power }}",
                    "unique_id": f"{sid}_power", "device": dev,
                }},
                {"topic": f"homeassistant/sensor/{sid}_energy/config", "payload": {
                    "name": f"Energy {sid}", "device_class": "energy", "unit_of_measurement": "Wh",
                    "state_topic": state_topic, "value_template": "{{ value_json.power_consumed }}",
                    "unique_id": f"{sid}_energy", "device": dev,
                }},
            ]
        return msgs

    # Gateway
    if model in SENSOR_TYPES["gateway"]:
        msgs += [
            {"topic": f"homeassistant/sensor/{sid}_illum/config", "payload": {
                "name": f"Illum {sid}", "device_class": "illuminance", "unit_of_measurement": "lux",
                "state_topic": state_topic, "value_template": "{{ value_json.illumination }}",
                "unique_id": f"{sid}_illum", "device": dev,
            }},
            {"topic": f"homeassistant/light/{sid}/config", "payload": {
                "name": f"Gateway Light {sid}", "schema": "json",
                "state_topic": state_topic,
                "command_topic": f"{cmd_topic}/rgb",
                "brightness_state_topic": state_topic, "brightness_value_template": "{{ value_json.dimmer }}",
                "brightness_command_topic": f"{cmd_topic}/dimmer",
                "rgb_state_topic": state_topic, "rgb_value_template": "{{ value_json.rgb }}",
                "rgb_command_topic": f"{cmd_topic}/rgb",
                "unique_id": f"{sid}_light", "device": dev,
            }},
            {"topic": f"homeassistant/binary_sensor/{sid}_conn/config", "payload": {
                "name": f"Gateway {sid} connected", "device_class": "connectivity",
                "state_topic": state_topic, "value_template": "{{ value_json.connected }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": f"{sid}_conn", "device": dev,
            }},
        ]
        if model == "acpartner.v3":
            msgs.append({"topic": f"homeassistant/sensor/{sid}_ac_power/config", "payload": {
                "name": f"AC Power {sid}",
                "state_topic": state_topic, "value_template": "{{ value_json.ac_power }}",
                "unique_id": f"{sid}_ac_power", "device": dev,
            }})
        return msgs

    # Button
    if model in SENSOR_TYPES["button"]:
        msgs += [
            {"topic": f"homeassistant/sensor/{sid}_action/config", "payload": {
                "name": _device_name(sid, model),
                "state_topic": state_topic, "value_template": "{{ value_json | tojson }}",
                "unique_id": f"{sid}_action", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Cube
    if model in SENSOR_TYPES["cube"]:
        msgs += [
            {"topic": f"homeassistant/sensor/{sid}_action/config", "payload": {
                "name": _device_name(sid, model),
                "state_topic": state_topic, "value_template": "{{ value_json | tojson }}",
                "unique_id": f"{sid}_action", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Alarm
    if model in SENSOR_TYPES["alarm"]:
        dev_class = "gas" if model == "natgas" else "smoke"
        msgs += [
            {"topic": f"homeassistant/binary_sensor/{sid}/config", "payload": {
                "name": _device_name(sid, model), "device_class": dev_class,
                "state_topic": state_topic, "value_template": "{{ value_json.state }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": sid, "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Curtain
    if model in SENSOR_TYPES["curtain"]:
        msgs.append({"topic": f"homeassistant/cover/{sid}/config", "payload": {
            "name": _device_name(sid, model), "device_class": "curtain",
            "state_topic": state_topic, "position_template": "{{ value_json.curtain_level }}",
            "command_topic": f"{cmd_topic}/curtain_level",
            "set_position_topic": f"{cmd_topic}/curtain_level",
            "payload_open": "open", "payload_close": "close", "payload_stop": "stop",
            "unique_id": sid, "device": dev,
        }})
        return msgs

    # Lock
    if model in SENSOR_TYPES["lock"]:
        msgs += [
            {"topic": f"homeassistant/sensor/{sid}_action/config", "payload": {
                "name": _device_name(sid, model),
                "state_topic": state_topic, "value_template": "{{ value_json | tojson }}",
                "unique_id": f"{sid}_action", "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Vibration
    if model in SENSOR_TYPES["vibration"]:
        msgs += [
            {"topic": f"homeassistant/binary_sensor/{sid}/config", "payload": {
                "name": _device_name(sid, model), "device_class": "vibration",
                "state_topic": state_topic, "value_template": "{{ value_json.state }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": sid, "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Water sensor
    if model in SENSOR_TYPES["water"]:
        msgs += [
            {"topic": f"homeassistant/binary_sensor/{sid}/config", "payload": {
                "name": _device_name(sid, model), "device_class": "moisture",
                "state_topic": state_topic, "value_template": "{{ value_json.state }}",
                "payload_on": "true", "payload_off": "false",
                "unique_id": sid, "device": dev,
            }},
            {"topic": f"homeassistant/sensor/{sid}_bat/config", "payload": {
                "name": f"Battery {sid}", "device_class": "battery", "unit_of_measurement": "%",
                "state_topic": state_topic, "value_template": "{{ value_json.percent }}",
                "unique_id": f"{sid}_bat", "device": dev,
            }},
        ]
        return msgs

    # Relay
    if model in SENSOR_TYPES["relay"]:
        msgs += [
            {"topic": f"homeassistant/switch/{sid}_ch0/config", "payload": {
                "name": _device_name(sid, model) + " CH0",
                "state_topic": state_topic, "value_template": "{{ value_json.channel_0 }}",
                "command_topic": f"{cmd_topic}/channel_0",
                "payload_on": "true", "payload_off": "false",
                "state_on": "true", "state_off": "false",
                "unique_id": f"{sid}_ch0", "device": dev,
            }},
            {"topic": f"homeassistant/switch/{sid}_ch1/config", "payload": {
                "name": _device_name(sid, model) + " CH1",
                "state_topic": state_topic, "value_template": "{{ value_json.channel_1 }}",
                "command_topic": f"{cmd_topic}/channel_1",
                "payload_on": "true", "payload_off": "false",
                "state_on": "true", "state_off": "false",
                "unique_id": f"{sid}_ch1", "device": dev,
            }},
        ]
        return msgs

    # Default: generic sensor
    return [{"topic": f"homeassistant/sensor/{sid}_raw/config", "payload": {
        "name": _device_name(sid, model), "state_topic": state_topic,
        "value_template": "{{ value_json | tojson }}",
        "unique_id": f"{sid}_raw", "device": dev,
    }}]