"""Rule engine for built-in automations (motion -> light, door guard)."""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class TriggerEngine:
    """Built-in automation rule engine."""

    def __init__(self, hub_getter, gateways: list, rules: list[dict], config):
        self._hub = hub_getter
        self._gateways = gateways
        self._rules = rules
        self._config = config
        self._timers: dict[str, asyncio.Task] = {}
        self._held_by_door: dict[str, bool] = {}
        self._door_states: dict[str, bool] = {}
        self._door_open_cooldown: dict[str, float] = {}
        self._door_open_cooldown_ms = config.doorOpenCooldownMs if config.doorOpenCooldownMs > 0 else 3000
        self._last_token_refresh: dict[str, float] = {}
        self._just_exited: str | None = None
        self._last_motion: dict[str, float] = {}

    @property
    def hub(self):
        return self._hub()

    def _get_val(self, obj, attr: str):
        if obj is not None and hasattr(obj, attr):
            return getattr(obj, attr)
        return None

    def _rule_key(self, rule: dict) -> str:
        return rule.get("name") or (rule["target"]["sid"] + "/" + rule["target"]["attr"])

    def _check_condition(self, rule: dict) -> bool:
        cond = rule.get("condition")
        if not cond:
            return True
        sensor = self.hub.get_sensor(cond["sid"])
        if not sensor:
            return False
        cur = self._get_val(sensor, cond["attr"])
        return str(cur) == str(cond["equals"])

    def _apply_control(self, rule: dict, value):
        sensor = self.hub.get_sensor(rule["target"]["sid"])
        if not sensor:
            logger.error(f"[trigger] target device not found: {rule['target']['sid']}")
            return
        if not hasattr(sensor, "control"):
            logger.error(f"[trigger] {rule['target']['sid']} has no Control")
            return

        gw_ip = self._gateways[0].ip if self._gateways else "192.168.50.115"
        now = time.monotonic()
        last_refresh = self._last_token_refresh.get(gw_ip, 0)
        token_age = now - last_refresh

        def do_control():
            try:
                sensor.control(rule["target"]["attr"], value)
            except Exception as e:
                logger.error(f"[trigger] Control failed: {e}")

        if token_age > 10:
            try:
                self.hub.send_message({"cmd": "get_id_list"}, gw_ip)
            except Exception:
                pass
            self._last_token_refresh[gw_ip] = now
            asyncio.get_event_loop().call_later(0.5, do_control)
        else:
            do_control()

    def _cancel_all_timers(self, dg: str):
        for rule in self._rules:
            if rule.get("doorGuard") != dg:
                continue
            key = self._rule_key(rule)
            if key in self._timers:
                self._timers[key].cancel()
                del self._timers[key]

    async def _start_timer(self, rule: dict, delay_ms: int):
        key = self._rule_key(rule)
        await asyncio.sleep(delay_ms / 1000)
        dg = rule.get("doorGuard")
        if dg and self._held_by_door.get(dg):
            logger.info(f"[trigger] {rule.get('name', '')}: keep light on, waiting for door open")
        elif dg and self._door_states.get(dg) is False:
            last_motion = self._last_motion.get(rule["match"]["sid"], 0)
            if (time.time() * 1000 - last_motion) <= delay_ms + 2000:
                self._held_by_door[dg] = True
                logger.info(f"[trigger] {rule.get('name', '')}: door closed, recent motion, keep light on")
            else:
                self._apply_control(rule, rule["offValue"])
                logger.info(f"[trigger] {rule.get('name', '')}: {delay_ms / 1000}s -> offValue={rule['offValue']} (door closed)")
        else:
            self._apply_control(rule, rule["offValue"])
            logger.info(f"[trigger] {rule.get('name', '')}: {delay_ms / 1000}s -> offValue={rule['offValue']}")
        self._timers.pop(key, None)

    def _schedule_off(self, rule: dict):
        if rule.get("doorGuard"):
            self._held_by_door[rule["doorGuard"]] = False
        delay = (rule.get("delay") or 10) * 1000
        key = self._rule_key(rule)
        if key in self._timers:
            self._timers[key].cancel()
        self._timers[key] = asyncio.ensure_future(self._start_timer(rule, delay))

    def _is_suppressed_by_door(self, rule: dict) -> bool:
        dg = rule.get("doorGuard")
        if not dg:
            return False
        cooldown_until = self._door_open_cooldown.get(dg, 0)
        return time.time() * 1000 < cooldown_until

    def on_data(self, sid: str, data: dict):
        """Process incoming data against rules."""
        if self._config.enable_triggers is False:
            return

        for rule in self._rules:
            if not rule.get("match") or rule["match"]["sid"] != sid:
                continue
            v = data.get(rule["match"]["attr"])
            if v is None:
                continue
            if str(v) != str(rule["match"]["equals"]):
                continue

            dg = rule.get("doorGuard")
            key = self._rule_key(rule)

            match_sensor = self.hub.get_sensor(rule["match"]["sid"])
            if dg and match_sensor and hasattr(match_sensor, "no_motion"):
                self._last_motion[sid] = time.time() * 1000

            if self._just_exited == sid:
                self._just_exited = None
                logger.info(f"[trigger] {rule.get('name', '')}: just exited, skip")
                continue

            if not self._check_condition(rule):
                logger.info(f"[trigger] {rule.get('name', '')}: condition not met, skip")
                continue

            if self._is_suppressed_by_door(rule):
                logger.info(f"[trigger] {rule.get('name', '')}: in cooldown, skip")
                continue

            if dg and self._held_by_door.get(dg):
                logger.info(f"[trigger] {rule.get('name', '')}: already held, skip")
                continue

            if key in self._timers:
                if dg and self._door_states.get(dg) is False:
                    self._cancel_all_timers(dg)
                    self._held_by_door[dg] = True
                    logger.info(f"[trigger] {rule.get('name', '')}: door closed, cancel timer, hold light")
                    continue
                logger.info(f"[trigger] {rule.get('name', '')}: door open, reset timer")

            if dg:
                self._cancel_all_timers(dg)

            self._apply_control(rule, rule["onValue"])
            logger.info(f"[trigger] {rule.get('name', '')}: hit -> onValue={rule['onValue']}")

            if rule.get("delay"):
                self._schedule_off(rule)

    def on_door(self, sid: str, data: dict):
        """Process door sensor events."""
        if self._config.enable_triggers is False:
            return

        st = data.get("state")
        if st is None:
            return

        was_closed = self._door_states.get(sid) is False
        was_open = self._door_states.get(sid) is True
        self._door_states[sid] = bool(st)

        if st is True and was_closed:
            any_light_on = False
            for rule in self._rules:
                if rule.get("doorGuard") != sid:
                    continue
                sensor = self.hub.get_sensor(rule["target"]["sid"])
                if sensor and self._get_val(sensor, rule["target"]["attr"]) == rule["onValue"]:
                    any_light_on = True
                    break

            if any_light_on:
                self._just_exited = sid
                self._door_open_cooldown[sid] = time.time() * 1000 + self._door_open_cooldown_ms
                self._cancel_all_timers(sid)
                for rule in self._rules:
                    if rule.get("doorGuard") != sid:
                        continue
                    self._apply_control(rule, rule["offValue"])
                    logger.info(f"[trigger] {sid}, {rule.get('name', '')} -> offValue={rule['offValue']}")
                self._held_by_door[sid] = False

        if st is False and was_open:
            self._door_open_cooldown.pop(sid, None)
            self._held_by_door[sid] = False
            for rule in self._rules:
                if rule.get("doorGuard") != sid:
                    continue
                self._last_motion[rule["match"]["sid"]] = 0