"""UDP multicast Hub — listens to Xiaomi Gateway messages."""

import asyncio
import json
import logging
import os
import socket
import struct
import sys

if sys.platform == "linux":
    import fcntl
else:
    fcntl = None

from Crypto.Cipher import AES

from .devices import DEVICES

logger = logging.getLogger(__name__)

MULTICAST_ADDR = "224.0.0.50"
MULTICAST_PORT = 4321
GATEWAY_PORT = 9898
IV = bytes([0x17, 0x99, 0x6d, 0x09, 0x3d, 0x28, 0xdd, 0xb3, 0xba, 0x69, 0x5a, 0x2e, 0x6f, 0x58, 0x56, 0x2e])


class Hub:
    """UDP multicast hub for Xiaomi Gateway communication."""

    def __init__(self, keys: list[dict], port: int = 9898, bind: str = "0.0.0.0"):
        self.keys: dict[str, str] = {k["ip"]: k["key"] for k in keys}
        self.key = keys[0]["key"] if keys else None
        self.sids: dict[str, str] = {}
        self.token: dict[str, str] = {}
        self.proto_ver: dict[str, list[str]] = {}
        self.sensors: dict[str, object] = {}
        self.port = port
        self.bind = bind
        self._state = "INIT"
        self._transport: asyncio.DatagramTransport | None = None
        self._listeners: dict[str, list] = {}
        self._loop = asyncio.get_running_loop()

    def on(self, event: str, callback):
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def emit(self, event: str, *args):
        for cb in self._listeners.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                logger.error(f"[hub] event handler error: {e}")

    def proto_major(self, ip: str) -> str:
        if ip not in self.proto_ver:
            return "1"
        return self.proto_ver[ip][0]

    def _params2data(self, params: list) -> dict:
        data = {}
        for p in params:
            for key, val in p.items():
                if key == "battery_voltage":
                    data["voltage"] = val
                elif key == "energy_consumed":
                    data["power_consumed"] = val / 1000.0
                elif key == "button_0":
                    data["channel_0"] = val
                elif key == "button_1":
                    data["channel_1"] = val
                elif key == "dual_channel":
                    if val == "click":
                        data["dual_channel"] = "both_click"
                else:
                    data[key] = val
        return data

    def _data2params(self, data: dict) -> list:
        return [{k: v} for k, v in data.items()]

    async def start(self):
        """Start listening for UDP multicast messages."""

        class HubProtocol(asyncio.DatagramProtocol):
            def __init__(self, hub):
                self.hub = hub
                self.transport = None

            def connection_made(self, transport):
                self.transport = transport
                self.hub._transport = transport
                self.hub._state = "CONNECTED"

                # Enable broadcast
                sock = transport.get_extra_info("socket")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 128)

                # Join multicast group
                if self.hub.bind != "0.0.0.0":
                    mreq = struct.pack("4s4s", socket.inet_aton(MULTICAST_ADDR),
                                       socket.inet_aton(self.hub.bind))
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                    logger.info(f"[hub] addMembership {MULTICAST_ADDR} on {self.hub.bind}")
                else:
                    joined = False
                    # Enumerate all non-loopback IPv4 interfaces via ioctl
                    try:
                        if fcntl is None:
                            raise OSError("interface ioctl is unavailable on this platform")
                        SIOCGIFADDR = 0x8915
                        SIOCGIFFLAGS = 0x8913
                        IFF_LOOPBACK = 0x8
                        IFF_UP = 0x1

                        # Get interface list from /proc/net/dev (Linux)
                        with open("/proc/net/dev", "r") as f:
                            lines = f.readlines()[2:]  # skip header
                        ifaces = [line.split(":")[0].strip() for line in lines]

                        for iface in ifaces:
                            try:
                                ifreq = struct.pack("256s", iface[:15].encode())
                                flags = struct.unpack("H", fcntl.ioctl(
                                    sock.fileno(), SIOCGIFFLAGS, ifreq)[16:18])[0]
                                if flags & IFF_LOOPBACK or not (flags & IFF_UP):
                                    continue
                                addr = socket.inet_ntoa(fcntl.ioctl(
                                    sock.fileno(), SIOCGIFADDR, ifreq)[20:24])
                                mreq = struct.pack("4s4s", socket.inet_aton(MULTICAST_ADDR),
                                                   socket.inet_aton(addr))
                                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                                joined = True
                                logger.info(f"[hub] addMembership {MULTICAST_ADDR} on {iface}({addr})")
                            except Exception:
                                pass
                    except Exception:
                        pass

                    if not joined:
                        # Fallback: join with INADDR_ANY
                        mreq = struct.pack("4s4s", socket.inet_aton(MULTICAST_ADDR),
                                           socket.inet_aton("0.0.0.0"))
                        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                        logger.info(f"[hub] addMembership {MULTICAST_ADDR} (INADDR_ANY)")

                # Send whois
                whois = b'{"cmd": "whois"}'
                self.transport.sendto(whois, (MULTICAST_ADDR, MULTICAST_PORT))
                logger.info("[hub] listening")

            def datagram_received(self, data, addr):
                self.hub._on_message(data, addr)

            def error_received(self, exc):
                logger.error(f"[hub] error: {exc}")
                self.hub.emit("error", exc)

            def connection_lost(self, exc):
                self.hub._state = "CLOSED"

        loop = asyncio.get_running_loop()
        endpoint_options = {}
        if sys.platform != "win32":
            endpoint_options["reuse_port"] = True
        transport, _ = await loop.create_datagram_endpoint(
            lambda: HubProtocol(self),
            local_addr=(self.bind, self.port),
            **endpoint_options,
        )
        return transport

    async def stop(self):
        if self._state == "CLOSED":
            return
        self._state = "CLOSED"
        if self._transport:
            self._transport.close()
            self._transport = None

    def send_message(self, message: dict, ip: str | None = None):
        """Send a JSON message to a gateway."""
        if self._state == "CLOSED" or not self._transport:
            return

        proto = self.proto_major(ip) if ip else "1"
        if proto == "2":
            message.pop("short_id", None)
            if "data" in message:
                if "key" in message["data"]:
                    message["key"] = message["data"].pop("key")
                message["params"] = self._data2params(message.pop("data"))

        data = json.dumps(message).encode()
        dest = (ip or MULTICAST_ADDR, GATEWAY_PORT)
        logger.info(f"[hub] SEND -> {dest[0]}:{dest[1]} {data.decode()}")
        self._transport.sendto(data, dest)

    def _on_message(self, msg_buffer: bytes, rinfo):
        if self._state == "CLOSED":
            return

        try:
            msg = json.loads(msg_buffer.decode())
        except json.JSONDecodeError:
            return

        ip = rinfo[0]
        model = msg.get("model")
        sid = msg.get("sid", "")

        # Fix gateway SID with missing leading zeros
        if model in ("gateway", "acpartner.v3") and sid and len(sid) < 12:
            msg["sid"] = sid.zfill(12)
            sid = msg["sid"]

        if msg.get("proto_version"):
            self.proto_ver[ip] = msg["proto_version"].split(".")

        if msg.get("params") and self.proto_major(ip) == "2":
            msg["data"] = self._params2data(msg["params"])

        sensor = self.get_sensor(sid)

        if not model and sid:
            model = self.sids.get(sid)
            if model:
                msg["model"] = model

        if not sensor:
            if not model:
                return
            try:
                sensor = self._sensor_factory(sid, model, ip, msg.get("name"))
            except Exception as e:
                self.emit("warning", f"Could not add new sensor: {e}")
                return

        if sensor:
            if isinstance(msg.get("data"), str):
                try:
                    msg["data"] = json.loads(msg["data"])
                except json.JSONDecodeError:
                    self.emit("warning", f"Could not parse: {msg['data']}")
                    msg["data"] = None

            if msg.get("token"):
                self.token[ip] = msg["token"]

            if msg.get("cmd") == "heartbeat":
                sensor.heart_beat(msg.get("token"), msg.get("data"))
            else:
                sensor.heart_beat()

            if self.proto_major(ip) == "2":
                if msg.get("cmd") == "read_rsp":
                    msg["cmd"] = "read_ack"
                if msg.get("cmd") == "write_rsp":
                    msg["cmd"] = "write_ack"
                if msg.get("cmd") == "discovery_rsp":
                    sids = [d["sid"] for d in msg.get("dev_list", [])]
                    msg["data"] = sids
                    msg["cmd"] = "get_id_list_ack"

            if msg.get("data") and (msg.get("cmd") == "report" or msg.get("cmd", "").endswith("_ack")):
                if msg.get("cmd") == "write_ack":
                    logger.info(f"[hub] WRITE_ACK from {ip}: {json.dumps(msg['data'])}")
                sensor.on_message(msg)

        self.emit("message", msg)

    def get_key(self, ip: str) -> str | None:
        """Generate encrypted key for gateway communication."""
        token = self.token.get(ip)
        if not token:
            return None
        try:
            key = self.keys.get(ip) or self.key
            cipher = AES.new(key.encode(), AES.MODE_CBC, iv=IV)
            encrypted = cipher.encrypt(token.encode("ascii"))
            result = encrypted.hex()
            logger.info(f"[hub] getKey ip={ip} token={token} -> {result}")
            return result
        except Exception as e:
            self.emit("error", f"Cannot get Key for {ip}: {e}")
            return None

    def get_sensor(self, sid: str):
        return self.sensors.get(sid)

    def _sensor_factory(self, sid: str, model: str, ip: str, name: str | None = None):
        if self._state == "CLOSED":
            return None

        dev = next((d for d in DEVICES.values() if d["type"] == model), None)
        if not dev:
            raise ValueError(f'Type "{model}" is not valid')

        sensor = dev["ClassName"](sid, ip, self, model)
        self.sensors[sid] = sensor
        self.emit("device", sensor, name)
        return sensor


def create_hub(keys: list[dict], port: int = 9898, bind: str = "0.0.0.0") -> Hub:
    """Factory function to create a Hub instance."""
    return Hub(keys, port, bind)