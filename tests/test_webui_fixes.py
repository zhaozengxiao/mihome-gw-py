"""补充测试: H1 dual_channel 双重前缀 / H2 MQTT URL 解析 / M1 定时器取消."""
import asyncio
import sys
import unittest

sys.path.insert(0, "/tmp/mihome-gw-py")

from mihome_gw.hub import Hub
from mihome_gw.mqtt_output import MqttOutput
from mihome_gw.sensors.wall_buttons import WallButtons
from mihome_gw.sensors.button import Button


class FakeTransport:
    def __init__(self):
        self.sent = []

    def sendto(self, data, dest):
        self.sent.append((data, dest))


class FakeHub:
    def __init__(self):
        self._transport = FakeTransport()
        self._state = "CONNECTED"
        self.emitted = []
        self.proto_ver = {}

    def emit(self, event, *args):
        self.emitted.append((event,) + args)

    def get_key(self, ip):
        return "deadbeef"


class H1Tests(unittest.TestCase):
    def test_params2data_keeps_raw_dual_channel(self):
        """proto-2 网关上报 click 应保留原始值, 不预加 both_ 前缀."""

        async def scenario():
            hub = Hub([{"ip": "1.2.3.4", "key": "k" * 16}])
            hub.proto_ver["1.2.3.4"] = ["2"]
            return hub._params2data([{"dual_channel": "click"}])

        out = asyncio.run(scenario())
        self.assertEqual(out["dual_channel"], "click")

    def test_wallbuttons_single_prefix(self):
        """wall_buttons 双按输出 both_danji, 不能 both_both_click."""

        async def scenario():
            hub = FakeHub()
            wb = WallButtons("sid1", "1.2.3.4", hub, "remote.b286acn01")
            return wb.get_data({"dual_channel": "click"})

        out = asyncio.run(scenario())
        self.assertEqual(out["action"], "both_danji")


class H2Tests(unittest.TestCase):
    def _parse(self, url):
        out = {}
        m = MqttOutput(url, command_handler=lambda t, p: None)

        def fake_connect(host, port, keepalive):
            out["host"] = host
            out["port"] = port

        m.client.connect_async = fake_connect
        m.client.loop_start = lambda: None
        m.connect()
        out["username"] = m.client._username
        out["password"] = m.client._password
        return out

    def test_url_with_auth(self):
        r = self._parse("mqtt://user:pass@broker:1883")
        self.assertEqual(r["host"], "broker")
        self.assertEqual(r["port"], 1883)
        self.assertEqual(r["username"], b"user")
        self.assertEqual(r["password"], b"pass")

    def test_url_without_auth(self):
        """无认证 URL 不能被误当作 user:pass."""
        r = self._parse("mqtt://broker:1883")
        self.assertEqual(r["host"], "broker")
        self.assertEqual(r["port"], 1883)
        self.assertIsNone(r["username"])
        self.assertIsNone(r["password"])

    def test_url_default_port(self):
        r = self._parse("mqtt://broker")
        self.assertEqual(r["host"], "broker")
        self.assertEqual(r["port"], 1883)

    def test_mqtts_url(self):
        r = self._parse("mqtts://broker")
        self.assertEqual(r["port"], 8883)
        self.assertEqual(r["host"], "broker")


class M1Tests(unittest.TestCase):
    def test_reset_timer_cancelled_on_new_action(self):
        """快速连按: 第二次动作的 idle 定时器必须取消第一次的."""

        async def scenario():
            hub = FakeHub()
            btn = Button("sid1", "1.2.3.4", hub, "sensor_switch")
            btn.get_data({"status": "click"})
            t1 = btn._reset_timer
            btn.get_data({"status": "double_click"})
            t2 = btn._reset_timer
            return t1, t2

        t1, t2 = asyncio.run(scenario())
        self.assertIsNot(t1, t2)
        self.assertTrue(t1.cancelled())
        self.assertFalse(t2.cancelled())


if __name__ == "__main__":
    unittest.main(verbosity=2)