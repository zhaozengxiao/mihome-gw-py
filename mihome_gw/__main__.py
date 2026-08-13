"""Main entry point for mihome-gw-py."""

import asyncio
import json
import logging
import os
import signal
import sys
import time

from .config import Config
from .hub import Hub
from .mqtt_output import ConsoleOutput, MqttOutput, WebhookOutput
from .devices import SENSOR_TYPES
from .triggers import TriggerEngine

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mihome")

CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "..", "config.json"))


def load_config() -> Config:
    try:
        return Config.from_file(CONFIG_PATH)
    except Exception as e:
        logger.error(f"无法读取配置文件 {CONFIG_PATH}: {e}")
        sys.exit(1)


class App:
    """Main application."""

    def __init__(self, config: Config, config_path: str | None = None):
        self.config = config
        self.config_path = config_path or CONFIG_PATH
        self.hub: Hub | None = None
        self.triggers: TriggerEngine | None = None
        self.output = None
        self.mqtt_client = None
        self.webui = None
        self.last_message_time = time.time()
        self._shutdown = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def setup_output(self):
        """Initialize the output backend."""
        output_cfg = self.config.output

        if output_cfg.type == "mqtt":
            mqtt_out = MqttOutput(
                url=output_cfg.url,
                prefix=output_cfg.prefix,
                command_handler=self._handle_mqtt_command,
            )
            mqtt_out.connect()
            self.output = mqtt_out
            self.mqtt_client = mqtt_out
        elif output_cfg.type == "webhook":
            self.output = WebhookOutput(url=output_cfg.url)
        else:
            self.output = ConsoleOutput()

    def _handle_mqtt_command(self, topic: str, value: str):
        """Handle incoming MQTT command from Home Assistant."""
        prefix = self.config.output.prefix + "cmd/"
        if not topic.startswith(prefix):
            return
        rest = topic[len(prefix):]
        parts = rest.split("/")
        if len(parts) < 2:
            return
        sid, attr = parts[0], parts[1]

        sensor = self.hub.get_sensor(sid)
        if not sensor or not hasattr(sensor, "control"):
            logger.error(f"[mqtt] 控制目标不存在或无 Control: {sid}")
            return

        # Boolean conversion (兼容 HA 大小写: ON/OFF/True/False)
        v = value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "on", "1"):
                v = True
            elif v in ("false", "off", "0"):
                v = False

        logger.info(f"[mqtt] 收到控制指令 {sid} {attr} = {v}")

        # 刷新网关 token (未配置网关时跳过, 控制由设备自身 ip 完成)
        if self.config.gateways:
            try:
                self.hub.send_message({"cmd": "get_id_list"}, self.config.gateways[0].ip)
            except Exception:
                pass

        if self._loop is None or self._loop.is_closed():
            logger.error("[mqtt] 控制失败: 主事件循环不可用")
            return
        self._loop.call_soon_threadsafe(
            self._schedule_control, sensor, attr, v
        )

    def _schedule_control(self, sensor, attr: str, value):
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_later(0.5, self._do_control, sensor, attr, value)

    def _do_control(self, sensor, attr, value):
        try:
            sensor.control(attr, value)
        except Exception as e:
            logger.error(f"[mqtt] Control 失败: {e}")

    def setup_triggers(self):
        """Setup the rule engine."""
        # 取消旧引擎的定时器, 防止热重载后旧规则继续控制设备
        if self.triggers:
            try:
                self.triggers.cancel_all()
            except Exception:
                pass
        rules = self.config.rules
        if not rules:
            logger.info("[mihome] 未配置 rules, 规则引擎无规则可执行")
        self.triggers = TriggerEngine(
            lambda: self.hub,
            self.config.gateways,
            rules,
            self.config,
        )
        logger.info(f"[mihome] 规则已加载: {len(rules)} 条")

    def bind_events(self):
        """Bind hub events to output."""

        def on_message(msg):
            self.last_message_time = time.time()
            if self.config.debug:
                logger.info(f"[raw] {json.dumps(msg)}")

        def on_error(err):
            logger.error(f"[hub] error: {err}")

        def on_debug(msg):
            if self.config.debug:
                logger.debug(f"[hub] debug: {msg}")

        def on_warning(msg):
            logger.warning(f"[hub] warn: {msg}")

        def on_device(sensor, name):
            sid = sensor.sid
            model = sensor.className
            ip = sensor.ip
            logger.info(f"[device] {model} sid={sid} ip={ip}")
            if hasattr(self.output, "discover"):
                self.output.discover(sid, model, {})
            self.output.send(f"device/{sid}", {"event": "present", "type": model, "ip": ip})

        def on_data(sid, model, data):
            if not data:
                return
            self.last_message_time = time.time()
            if hasattr(self.output, "discover"):
                self.output.discover(sid, model, data)
            self.output.send(f"state/{sid}/{model}", data)

            # Door sensor triggers
            if model in SENSOR_TYPES["door"] and self.triggers:
                self.triggers.on_door(sid, data)
            if self.triggers:
                self.triggers.on_data(sid, data)

        self.hub.on("message", on_message)
        self.hub.on("error", on_error)
        self.hub.on("debug", on_debug)
        self.hub.on("warning", on_warning)
        self.hub.on("device", on_device)
        self.hub.on("data", on_data)

    async def _health_check(self):
        """Periodic health check and reconnect."""
        heartbeat_timeout = self.config.heartbeatTimeout
        rediscover_interval = self.config.rediscoverInterval

        # 心跳检查频率：每 min(30, heartbeatTimeout) 秒检查一次
        heartbeat_tick = min(30, heartbeat_timeout) if heartbeat_timeout > 0 else 30
        last_rediscover = time.time()

        while not self._shutdown:
            await asyncio.sleep(heartbeat_tick)

            # Health check
            elapsed = time.time() - self.last_message_time
            if elapsed > heartbeat_timeout:
                logger.warning(f"[hub] {int(elapsed)}s 无消息, 触发重连...")
                await self._reconnect()

            # Rediscover (按 rediscoverInterval 间隔发送 whois)
            if rediscover_interval > 0 and time.time() - last_rediscover >= rediscover_interval:
                last_rediscover = time.time()
                try:
                    if self.hub and self.hub.connected:
                        self.hub.send_raw(
                            b'{"cmd":"whois"}', ("224.0.0.50", 4321)
                        )
                except Exception:
                    pass

    async def _reconnect(self):
        if self.hub:
            await self.hub.stop()
        self.hub = None
        logger.info("[hub] 已停止, 3秒后重建...")
        await asyncio.sleep(3)

        self.hub = Hub(
            keys=[{"ip": g.ip, "key": g.key} for g in self.config.gateways],
            port=self.config.port,
            bind=self.config.bind,
        )
        self.setup_triggers()
        self.bind_events()
        await self.hub.start()
        self.last_message_time = time.time()
        logger.info("[hub] 重连完成")

    async def run(self):
        """Start the application."""
        self._loop = asyncio.get_running_loop()
        from .log_capture import install as install_log_capture
        install_log_capture()
        self.setup_output()

        self.hub = Hub(
            keys=[{"ip": g.ip, "key": g.key} for g in self.config.gateways],
            port=self.config.port,
            bind=self.config.bind,
        )

        self.setup_triggers()
        self.bind_events()
        await self.hub.start()

        logger.info(
            f"[mihome] started. listen={self.config.port} "
            f"bind={self.config.bind} gateways={len(self.config.gateways)} "
            f"output={self.config.output.type} rules={len(self.config.rules)} "
            f"heartbeatTimeout={self.config.heartbeatTimeout}s"
        )
        if not self.config.gateways:
            logger.warning("[mihome] 未配置网关 (gateways 为空), 仅能接收组播消息, 无法发送控制指令")

        # 启动 WebUI
        if self.config.web_enabled:
            try:
                from .webui import WebUI
                self.webui = WebUI(self, self.config_path,
                                   port=self.config.web_port,
                                   bind=self.config.web_bind)
                await self.webui.start()
            except Exception as e:
                logger.error(f"[webui] 启动失败: {e}")

        await self._health_check()

    async def shutdown(self):
        self._shutdown = True
        if self.webui:
            await self.webui.stop()
        if self.hub:
            await self.hub.stop()
        if self.mqtt_client:
            self.mqtt_client.stop()


def main():
    config = load_config()
    app = App(config, config_path=CONFIG_PATH)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    main_task = loop.create_task(app.run())

    def signal_handler():
        logger.info("Received shutdown signal")
        main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.run_until_complete(app.shutdown())
        loop.close()


if __name__ == "__main__":
    main()