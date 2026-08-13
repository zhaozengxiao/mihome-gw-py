"""MQTT output backend."""

import json
import logging
import asyncio

import paho.mqtt.client as mqtt

from .discovery import build_discovery

logger = logging.getLogger(__name__)


class MqttOutput:
    """MQTT output backend for publishing to Home Assistant."""

    def __init__(self, url: str, prefix: str = "mihome/", command_handler=None):
        self.url = url
        self.prefix = prefix
        self.command_handler = command_handler
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.discovered: set[str] = set()
        self.discovery_messages: list[dict] = []
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected = True
            logger.info("[mqtt] connected")
            client.subscribe(self.prefix + "cmd/#")
            for message in self.discovery_messages:
                client.publish(
                    message["topic"],
                    json.dumps(message["payload"]),
                    qos=0,
                    retain=True,
                )
        else:
            logger.error(f"[mqtt] connect failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        logger.warning(f"[mqtt] disconnected: {reason_code}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = msg.payload.decode()
        except UnicodeDecodeError:
            logger.warning(f"[mqtt] 忽略非 UTF-8 消息: {topic}")
            return
        if self.command_handler:
            self.command_handler(topic, payload)

    def connect(self):
        """Parse MQTT URL and connect."""
        # Format: mqtt://user:pass@host:port | mqtt://host:port | mqtts://...
        url = self.url
        use_tls = False
        if url.startswith("mqtt://"):
            url = url[7:]
        elif url.startswith("mqtts://"):
            url = url[8:]
            use_tls = True

        # 仅当存在 "@" 时才拆分认证段 (无认证 URL 不能误当作 user:pass)
        if "@" in url:
            auth, _, hostpart = url.partition("@")
            if ":" in auth:
                user, password = auth.split(":", 1)
                self.client.username_pw_set(user, password)
        else:
            hostpart = url

        host, _, port_str = hostpart.partition(":")
        port = int(port_str) if port_str else (8883 if use_tls else 1883)

        if use_tls:
            self.client.tls_set()
        self.client.connect_async(host, port, 60)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()

    def send(self, topic: str, payload: dict | str):
        """Publish a message to MQTT."""
        full_topic = self.prefix + topic
        data = json.dumps(payload) if isinstance(payload, dict) else payload
        if not self._connected:
            # broker 不可达时丢弃, 避免 paho 无限内存队列
            logger.warning(f"[mqtt] 未连接, 丢弃消息: {full_topic}")
            return
        self.client.publish(full_topic, data, qos=0)

    def discover(self, sid: str, model: str, data: dict | None = None):
        """Publish HA MQTT discovery messages."""
        key = sid + model
        if key in self.discovered:
            return
        self.discovered.add(key)
        msgs = build_discovery(sid, model, self.prefix)
        self.discovery_messages.extend(msgs)
        for m in msgs:
            if self._connected:
                self.client.publish(
                    m["topic"], json.dumps(m["payload"]), qos=0, retain=True
                )
            logger.info(f"[mqtt] discovery: {m['topic']}")


class ConsoleOutput:
    """Simple console output for debugging."""

    def send(self, topic: str, payload: dict | str):
        print(json.dumps({"topic": topic, "payload": payload}))

    def discover(self, sid: str, model: str, data: dict | None = None):
        pass


class WebhookOutput:
    """HTTP webhook output (标准库 urllib 实现, 同步接口)."""

    def __init__(self, url: str):
        self.url = url

    def send(self, topic: str, payload: dict | str):
        import urllib.request

        data = json.dumps({"topic": topic, "payload": payload}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
        except Exception as e:
            logger.error(f"[webhook] error: {e}")

    def discover(self, sid: str, model: str, data: dict | None = None):
        pass