"""Device type registry — maps Xiaomi model strings to sensor classes."""

from .sensors.gateway import Gateway
from .sensors.th_sensor import THSensor
from .sensors.door_sensor import DoorSensor
from .sensors.motion_sensor import MotionSensor
from .sensors.plug import Plug
from .sensors.button import Button
from .sensors.cube import Cube
from .sensors.alarm import Alarm
from .sensors.curtain import Curtain
from .sensors.lock import Lock
from .sensors.vibration_sensor import VibrationSensor
from .sensors.water_sensor import WaterSensor
from .sensors.wall_buttons import WallButtons
from .sensors.wall_wired_switch import WallWiredSwitch
from .sensors.relay import Relay

# Device registry: key -> {type, fullName, ClassName}
DEVICES = {
    "gateway":                   {"type": "gateway",          "fullName": "Xiaomi RGB Gateway", "ClassName": Gateway},
    "acpartner3":                {"type": "acpartner.v3",     "fullName": "Xiaomi Aqara AC partner Gateway", "ClassName": Gateway},
    "th":                        {"type": "sensor_ht",        "fullName": "Xiaomi Temperature/Humidity", "ClassName": THSensor},
    "weather":                   {"type": "weather.v1",       "fullName": "Xiaomi Temperature/Humidity/Pressure", "ClassName": THSensor},
    "weather0":                  {"type": "weather",          "fullName": "Xiaomi Temperature/Humidity/Pressure", "ClassName": THSensor},
    "button":                    {"type": "switch",           "fullName": "Xiaomi Wireless Switch", "ClassName": Button},
    "sensor_switch":             {"type": "sensor_switch",    "fullName": "Xiaomi Wireless Switch", "ClassName": Button},
    "button2":                   {"type": "sensor_switch.aq2","fullName": "Xiaomi Wireless Switch Sensor", "ClassName": Button},
    "button3":                   {"type": "sensor_switch.aq3","fullName": "Xiaomi Wireless Switch Sensor", "ClassName": Button},
    "button4":                   {"type": "remote.b1acn01",   "fullName": "Xiaomi Aqara Smart Wireless Switch", "ClassName": Button},
    "plug":                      {"type": "plug",             "fullName": "Xiaomi Smart Plug", "ClassName": Plug},
    "plug86":                    {"type": "86plug",           "fullName": "Xiaomi Smart Wall Plug", "ClassName": Plug},
    "remote_b286acn01":          {"type": "remote.b286acn01", "fullName": "Xiaomi Aqara Wireless Remote Switch (Double Rocker)", "ClassName": WallButtons},
    "remote_b286acn02":          {"type": "remote.b286acn02", "fullName": "Xiaomi Aqara Wireless Remote Switch D1 (Double Rocker)", "ClassName": WallButtons},
    "remote_b186acn01":          {"type": "remote.b186acn01", "fullName": "Xiaomi Aqara Wireless Remote Switch (Single Rocker)", "ClassName": WallButtons},
    "remote_b186acn02":          {"type": "remote.b186acn02", "fullName": "Xiaomi Aqara Wireless Remote Switch D1 (Single Rocker)", "ClassName": WallButtons},
    "aqara_relay":               {"type": "relay.c2acn01",    "fullName": "Aqara Two-channel Relay", "ClassName": Relay},
    "sw2_86":                    {"type": "86sw2",            "fullName": "Xiaomi Wireless Dual Wall Switch", "ClassName": WallButtons},
    "sw1_86":                    {"type": "86sw1",            "fullName": "Xiaomi Wireless Single Wall Switch", "ClassName": WallButtons},
    "sensor_sw2_86":             {"type": "sensor_86sw2",     "fullName": "Xiaomi Wireless Dual Wall Switch", "ClassName": WallButtons},
    "sensor_sw1_86":             {"type": "sensor_86sw1",     "fullName": "Xiaomi Wireless Single Wall Switch", "ClassName": WallButtons},
    "natgas":                    {"type": "natgas",           "fullName": "Xiaomi Mijia Honeywell Gas Alarm Detector", "ClassName": Alarm},
    "smoke":                     {"type": "smoke",            "fullName": "Xiaomi Mijia Honeywell Fire Alarm Detector", "ClassName": Alarm},
    "ctrl_ln1":                  {"type": "ctrl_ln1",         "fullName": "Xiaomi Aqara 86 Fire Wall Switch One Button", "ClassName": WallWiredSwitch},
    "ctrl_ln1_aq1":              {"type": "ctrl_ln1.aq1",     "fullName": "Xiaomi Aqara Wall Switch LN", "ClassName": WallWiredSwitch},
    "ctrl_ln2":                  {"type": "ctrl_ln2",         "fullName": "Xiaomi 86 zero fire wall switch double key", "ClassName": WallWiredSwitch},
    "ctrl_ln2_aq1":              {"type": "ctrl_ln2.aq1",     "fullName": "Xiaomi Aqara Wall Switch LN double key", "ClassName": WallWiredSwitch},
    "ctrl_86plug":               {"type": "ctrl_86plug",      "fullName": "Xiaomi Aqara Wall Socket", "ClassName": Plug},
    "ctrl_86plug_aq1":           {"type": "ctrl_86plug.aq1",  "fullName": "Xiaomi Aqara Wall Socket", "ClassName": Plug},
    "ctrl_neutral2":             {"type": "ctrl_neutral2",    "fullName": "Xiaomi Wired Dual Wall Switch", "ClassName": WallWiredSwitch},
    "ctrl_neutral1":             {"type": "ctrl_neutral1",    "fullName": "Xiaomi Wired Single Wall Switch", "ClassName": WallWiredSwitch},
    "ctrl_neutral2_b2nacn02p1":  {"type": "switch_b2nacn02",  "fullName": "Aqara D1 2 gang smart wall switch", "ClassName": WallWiredSwitch},
    "ctrl_neutral2_b2nacn02p2":  {"type": "switch.b2nacn02",  "fullName": "Aqara D1 2 gang smart wall switch", "ClassName": WallWiredSwitch},
    "cube":                      {"type": "cube",             "fullName": "Xiaomi Cube", "ClassName": Cube},
    "cube2":                     {"type": "sensor_cube.aqgl01","fullName": "Xiaomi Cube 01", "ClassName": Cube},
    "magnet":                    {"type": "magnet",           "fullName": "Xiaomi Door Sensor", "ClassName": DoorSensor},
    "sensor_magnet":             {"type": "sensor_magnet",    "fullName": "Xiaomi Door Sensor", "ClassName": DoorSensor},
    "magnet2":                   {"type": "sensor_magnet.aq2","fullName": "Xiaomi Door Sensor", "ClassName": DoorSensor},
    "curtain":                   {"type": "curtain",          "fullName": "Xiaomi Aqara Smart Curtain", "ClassName": Curtain},
    "motion":                    {"type": "motion",           "fullName": "Xiaomi Motion Sensor", "ClassName": MotionSensor},
    "sensor_motion":             {"type": "sensor_motion",    "fullName": "Xiaomi Motion Sensor", "ClassName": MotionSensor},
    "lock_aq1":                  {"type": "lock.aq1",         "fullName": "Xiaomi Lock", "ClassName": Lock},
    "lock_v1":                   {"type": "lock.v1",          "fullName": "Xiaomi Vima Smart Lock", "ClassName": Lock},
    "motion2":                   {"type": "sensor_motion.aq2","fullName": "Xiaomi Motion Sensor", "ClassName": MotionSensor},
    "vibration":                 {"type": "vibration",        "fullName": "Xiaomi Vibration Sensor", "ClassName": VibrationSensor},
    "wleak1":                    {"type": "sensor_wleak.aq1", "fullName": "Xiaomi Aqara Water Sensor", "ClassName": WaterSensor},
}


# Sensor type classification (used for MQTT discovery)
SENSOR_TYPES = {
    "temperature": ["sensor_ht", "weather.v1", "weather"],
    "door":        ["magnet", "sensor_magnet", "sensor_magnet.aq2"],
    "motion":      ["motion", "sensor_motion", "sensor_motion.aq2"],
    "switch_ctrl": ["plug", "86plug", "ctrl_86plug", "ctrl_86plug.aq1",
                    "ctrl_ln1", "ctrl_ln1.aq1", "ctrl_ln2", "ctrl_ln2.aq1",
                    "ctrl_neutral1", "ctrl_neutral2", "switch_b2nacn02", "switch.b2nacn02"],
    "gateway":     ["gateway", "acpartner.v3"],
    "button":      ["switch", "sensor_switch", "sensor_switch.aq2", "sensor_switch.aq3",
                    "remote.b1acn01", "remote.b186acn01", "remote.b186acn02",
                    "remote.b286acn01", "remote.b286acn02",
                    "86sw1", "86sw2", "sensor_86sw1", "sensor_86sw2"],
    "cube":        ["cube", "sensor_cube.aqgl01"],
    "alarm":       ["natgas", "smoke"],
    "curtain":     ["curtain"],
    "lock":        ["lock.aq1", "lock.v1"],
    "vibration":   ["vibration"],
    "water":       ["sensor_wleak.aq1"],
    "relay":       ["relay.c2acn01"],
}