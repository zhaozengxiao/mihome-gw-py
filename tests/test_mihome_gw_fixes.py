"""Smoke tests for the mihome-gw-py fixes (run from repo root)."""
import asyncio
import json
import sys
import unittest

sys.path.insert(0, "/tmp/mihome-gw-py")

from mihome_gw.discovery import build_discovery
from mihome_gw.hub import Hub
from mihome_gw.config import Config
from mihome_gw.__main__ import App


class FakeTransport:
    def __init__(self):
        self.sent = []

    def sendto(self, data, dest):
        self.sent.append((data, dest))


class FakeHub(Hub):
    def __init__(self, loop):
        # bypass Hub.__init__ (needs running loop anyway, we're inside one)
        self.keys = {}
        self.key = "0123456789abcdef"
        self.sids = {}
        self.token = {"192.168.1.2": "m8EtWc0sXSnM1xJy"}
        self.proto_ver = {}
        self.sensors = {}
        self._state = "CONNECTED"
        self._transport = FakeTransport()
        self._listeners = {}
        self._loop = loop
        self.sent = self._transport.sent


class FakeSensor:
    def __init__(self):
        self.calls = []

    def control(self, attr, value):
        self.calls.append((attr, value))


class DiscoveryTests(unittest.TestCase):
    def test_gateway_light_template_schema(self):
        msgs = build_discovery("7811c3a1b2c3", "gateway", "mihome/")
        light = next(m for m in msgs if m["topic"] == f"homeassistant/light/7811c3a1b2c3/config")
        p = light["payload"]
        self.assertEqual(p["schema"], "template")
        self.assertEqual(p["command_topic"], "mihome/cmd/7811c3a1b2c3/on")
        self.assertEqual(p["brightness_command_topic"], "mihome/cmd/7811c3a1b2c3/dimmer")
        self.assertEqual(p["rgb_command_topic"], "mihome/cmd/7811c3a1b2c3/rgb")
        self.assertEqual(p["payload_on"], "true")
        self.assertEqual(p["payload_off"], "false")
        self.assertIn("state_value_template", p)
        self.assertIn("brightness_value_template", p)
        self.assertIn("rgb_value_template", p)

    def test_curtain_cover_topics(self):
        msgs = build_discovery("158d0002aaaa01", "curtain", "mihome/")
        cover = next(m for m in msgs if m["topic"] == f"homeassistant/cover/158d0002aaaa01/config")
        p = cover["payload"]
        self.assertEqual(p["command_topic"], "mihome/cmd/158d0002aaaa01/curtain_cmd")
        self.assertEqual(p["set_position_topic"], "mihome/cmd/158d0002aaaa01/curtain_level")
        self.assertNotIn("payload_stop", p)
        self.assertEqual(p["position_open"], 100)
        self.assertEqual(p["position_closed"], 0)
        self.assertEqual(p["payload_open"], "open")
        self.assertEqual(p["payload_close"], "close")


class GatewayControlTests(unittest.TestCase):
    def test_normalize_light_value(self):
        from mihome_gw.sensors.gateway import Gateway
        n = Gateway._normalize_light_value
        self.assertIs(n("on", "ON"), True)
        self.assertIs(n("on", "off"), False)
        self.assertIs(n("on", "true"), True)
        self.assertIs(n("on", 1), True)
        self.assertIs(n("on", 0), False)
        self.assertEqual(n("dimmer", "128"), 50)
        self.assertEqual(n("dimmer", "255"), 100)
        self.assertEqual(n("dimmer", "50"), 50)
        self.assertEqual(n("dimmer", "abc"), None)
        self.assertEqual(n("rgb", "255,0,128"), "#FF0080")
        self.assertEqual(n("rgb", "#00FF00"), "#00FF00")
        self.assertEqual(n("rgb", "x,y,z"), None)

    def test_control_sends_write_with_key(self):
        async def scenario():
            hub = FakeHub(asyncio.get_running_loop())
            from mihome_gw.sensors.gateway import Gateway
            gw = Gateway("7811c3a1b2c3", "192.168.1.2", hub, "gateway")
            gw._loop = asyncio.get_running_loop()
            gw.control("on", "ON")
            gw.control("dimmer", "128")
            gw.control("rgb", "255,0,128")
            await asyncio.sleep(0.3)  # let call_later(0.2) fire _send_rgb
            return hub.sent

        sent = asyncio.run(scenario())
        # rgb write must contain dimmer<<24 | hex value and key
        writes = [json.loads(d) for d, _ in sent if b"write" in d]
        rgb_writes = [w for w in writes if "rgb" in w["data"]]
        self.assertTrue(rgb_writes)
        last = rgb_writes[-1]
        # key = AES-CBC(PKCS7) 加密后的 32 位 hex
        self.assertIsInstance(last["data"]["key"], str)
        self.assertEqual(len(last["data"]["key"]), 32)
        # dimmer 50 -> val = (50<<24) | 0xFF0080
        self.assertEqual(last["data"]["rgb"], (50 << 24) | 0xFF0080)

    def test_write_retries_when_token_missing(self):
        async def scenario():
            hub = FakeHub(asyncio.get_running_loop())
            hub.token = {}  # no token yet
            from mihome_gw.sensors.gateway import Gateway
            gw = Gateway("7811c3a1b2c3", "192.168.1.2", hub, "gateway")
            gw._loop = asyncio.get_running_loop()
            gw._write({"rgb": 123})
            await asyncio.sleep(0.6)
            # first get_id_list request, then retry write (still no token -> key None)
            msgs = [json.loads(d) for d, _ in hub.sent]
            ids = [m for m in msgs if m["cmd"] == "get_id_list"]
            writes = [m for m in msgs if m["cmd"] == "write"]
            self.assertTrue(ids, "should request token before write")
            self.assertTrue(writes, "should retry write after token request")
            self.assertIsNone(writes[-1]["data"]["key"])
            # no crash on empty token path

        asyncio.run(scenario())


class CurtainControlTests(unittest.TestCase):
    def test_control(self):
        async def scenario():
            hub = FakeHub(asyncio.get_running_loop())
            from mihome_gw.sensors.curtain import Curtain
            c = Curtain("158d0002aaaa01", "192.168.1.2", hub, "curtain")
            c.control("curtain_cmd", "open")
            c.control("curtain_cmd", "close")
            c.control("curtain_cmd", "stop")  # ignored
            c.control("curtain_level", "50")
            return [json.loads(d) for d, _ in hub.sent]

        msgs = asyncio.run(scenario())
        levels = [m["data"]["curtain_level"] for m in msgs]
        self.assertEqual(levels, [100, 0, 50])


class HubMessageTests(unittest.TestCase):
    def _hub(self):
        return FakeHub(None)  # loop replaced below

    def test_report_creates_sensor_and_emits(self):
        async def scenario():
            hub = Hub([{"ip": "192.168.1.2", "key": "secret"}], port=0, bind="127.0.0.1")
            hub._loop = asyncio.get_running_loop()
            events = []
            hub.on("data", lambda sid, model, data: events.append((sid, model, data)))
            hub.on("device", lambda *a: None)
            msg = {"cmd": "report", "model": "sensor_motion", "sid": "158d0000000001",
                   "data": {"status": "motion", "voltage": "3000"}}
            hub._on_message(json.dumps(msg).encode(), ("192.168.1.2", 9898))
            self.assertIn("158d0000000001", hub.sensors)
            self.assertEqual(hub.sids["158d0000000001"], "sensor_motion")
            self.assertTrue(events)
            sid, model, data = events[0]
            self.assertEqual(sid, "158d0000000001")
            self.assertIs(data["state"], True)
            self.assertEqual(data["voltage"], 3.0)

        asyncio.run(scenario())

    def test_unknown_model_warns_not_crash(self):
        async def scenario():
            hub = Hub([{"ip": "192.168.1.2", "key": "secret"}], port=0, bind="127.0.0.1")
            hub._loop = asyncio.get_running_loop()
            hub.on("warning", lambda *a: None)
            msg = {"cmd": "report", "model": "no.such.model", "sid": "158d0000000009",
                   "data": {"status": "motion"}}
            hub._on_message(json.dumps(msg).encode(), ("192.168.1.2", 9898))
            self.assertNotIn("158d0000000009", hub.sensors)

        asyncio.run(scenario())

    def test_sid_fallback_resolves_model(self):
        async def scenario():
            hub = Hub([{"ip": "192.168.1.2", "key": "secret"}], port=0, bind="127.0.0.1")
            hub._loop = asyncio.get_running_loop()
            hub.on("device", lambda *a: None)
            hub.on("data", lambda *a: None)
            # first report with model -> factory records sids
            hub._on_message(json.dumps({"cmd": "report", "model": "sensor_ht",
                                        "sid": "158d0000000002",
                                        "data": {"temperature": "2100"}}).encode(),
                            ("192.168.1.2", 9898))
            # second message without model -> resolved from sids map
            hub._on_message(json.dumps({"cmd": "report", "sid": "158d0000000002",
                                        "data": {"humidity": "5200"}}).encode(),
                            ("192.168.1.2", 9898))
            self.assertEqual(hub.sensors["158d0000000002"].className, "sensor_ht")
            self.assertEqual(hub.sensors["158d0000000002"].humidity, 52.0)

        asyncio.run(scenario())


class KeyDerivationTests(unittest.TestCase):
    def test_get_key_16char_token_no_padding(self):
        async def scenario():
            hub = FakeHub(asyncio.get_running_loop())
            hub.token = {"192.168.1.2": "m8EtWc0sXSnM1xJy"}
            hub.errors = []
            hub.emit = lambda ev, *a: hub.errors.append(a) if ev == "error" else None
            key = hub.get_key("192.168.1.2")
            # 无填充: 16 字符 token -> 16 字节密文 -> 32 位 hex
            self.assertEqual(len(key), 32)
            self.assertEqual(hub.errors, [])

        asyncio.run(scenario())

    def test_get_key_non16_token_degrades_gracefully(self):
        async def scenario():
            hub = FakeHub(asyncio.get_running_loop())
            hub.token = {"192.168.1.2": "NXgY9M8f"}  # 8 chars
            hub.errors = []
            hub.emit = lambda ev, *a: hub.errors.append(a) if ev == "error" else None
            self.assertIsNone(hub.get_key("192.168.1.2"))  # 不崩溃, 返回 None
            self.assertEqual(hub.errors, [])

        asyncio.run(scenario())


class MqttCommandTests(unittest.TestCase):
    def test_value_normalization_and_no_gateway(self):
        async def scenario():
            config = Config(gateways=[], output=type("O", (), {"prefix": "mihome/"}))
            app = App(config)
            app._loop = asyncio.get_running_loop()
            app.hub = FakeHub(app._loop)
            sensor = FakeSensor()
            app.hub.get_sensor = lambda sid: sensor
            app._handle_mqtt_command("mihome/cmd/158d0002b062cd/state", "ON")
            app._handle_mqtt_command("mihome/cmd/158d0002b062cd/state", "OFF")
            app._handle_mqtt_command("mihome/cmd/158d0002b062cd/state", "False")
            app._handle_mqtt_command("mihome/cmd/158d0002b062cd/dimmer", "128")
            await asyncio.sleep(1.0)  # let call_later(0.5) fire
            return sensor.calls

        calls = asyncio.run(scenario())
        self.assertEqual(calls, [("state", True), ("state", False), ("state", False),
                                 ("dimmer", "128")])


class TriggerNoGatewayTests(unittest.TestCase):
    def test_apply_control_without_gateways(self):
        async def scenario():
            config = Config(gateways=[], enable_triggers=True)
            from mihome_gw.triggers import TriggerEngine
            hub = FakeHub(asyncio.get_running_loop())
            sensor = FakeSensor()
            hub.get_sensor = lambda sid: sensor
            rules = [{"name": "r1", "match": {"sid": "A", "attr": "state", "equals": True},
                      "target": {"sid": "B", "attr": "channel_0"},
                      "onValue": True, "offValue": False}]
            eng = TriggerEngine(lambda: hub, [], rules, config)
            eng._apply_control(rules[0], False)
            self.assertEqual(sensor.calls, [("channel_0", False)])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)
