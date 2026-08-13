"""
内置自动化规则引擎。

核心逻辑：
  人体传感器检测到人 → 开灯 → 延时 N 秒后关灯（受门磁约束）。

门磁约束场景（典型：卫生间/卧室）：
  1. 进门：门磁从关→开，如果灯亮着（说明人刚出去），则关灯 + 设置 cooldown
     （防止门关上后人体传感器再次触发又把灯打开）
  2. 关门：门磁从开→关，清除 cooldown，允许后续触发
  3. 延时关灯时：如果门关着（人还在里面），保持亮灯等门开，不执行关灯
  4. 门关着时触发：取消已有定时器，保持亮灯（等人开门出来）
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class TriggerEngine:
    """
    内置自动化规则引擎。

    支持的规则字段：
      name:      规则名称（用于日志）
      match:     触发条件 {sid, attr, equals}
      target:    控制目标 {sid, attr}
      onValue:   触发时写入的值
      offValue:  延时到期后写入的值（需配合 delay）
      delay:     延时秒数，到期后写入 offValue
      doorGuard: 门磁设备 SID，关联门磁实现"进门开灯、关门保持、开门关灯"
      condition: 前置条件，格式 {sid, attr, equals}，仅在条件满足时才触发
    """

    def __init__(self, hub_getter, gateways: list, rules: list[dict], config):
        """
        初始化规则引擎。

        Args:
            hub_getter: 返回 Hub 实例的可调用对象（延迟获取，避免循环引用）
            gateways: 网关配置列表
            rules: 规则列表
            config: 全局配置对象
        """
        # Hub 延迟获取器（因为 Hub 可能在重连时重建）
        self._hub = hub_getter
        self._gateways = gateways
        self._rules = rules
        self._config = config

        # 定时器字典: rule_key -> asyncio.Task
        # 用于管理每条规则的延时关灯任务
        self._timers: dict[str, asyncio.Task] = {}

        # 门磁保持状态: doorGuard_sid -> bool
        # True 表示该门磁关联的规则正在"保持亮灯等门开"状态
        self._held_by_door: dict[str, bool] = {}

        # 门磁开关状态: door_sid -> bool
        # True=门开, False=门关
        self._door_states: dict[str, bool] = {}

        # 门磁 cooldown 时间戳: door_sid -> 到期时间(ms)
        # 门从关→开后，短时间内抑制人体触发，防止人出门后立即被再次触发
        self._door_open_cooldown: dict[str, float] = {}

        # cooldown 时长(ms)，默认 5000ms
        self._door_open_cooldown_ms = (
                    config.doorOpenCooldownMs if config.doorOpenCooldownMs > 0 else 5000
        )

        # 每个网关上次刷新 token 的时间戳
        # 控制设备前需要先刷新 token（超过 10s 则重新获取）
        self._last_token_refresh: dict[str, float] = {}

        # 事件循环（用于 call_later 延时控制）
        self._loop = asyncio.get_running_loop()

        # 刚开门离开的设备 SID
        # 用于标记"刚开门出去"的人体传感器，跳过下次触发
        self._just_exited: str | None = None

        # 人体传感器最后一次检测到活动的时间戳(ms)
        self._last_motion: dict[str, float] = {}

    @property
    def hub(self):
        """获取当前的 Hub 实例（延迟解引用）。"""
        return self._hub()

    def _get_val(self, obj, attr: str):
        """
        安全获取对象属性值。

        用于从传感器对象读取当前状态值，不存在则返回 None。
        """
        if obj is not None and hasattr(obj, attr):
            return getattr(obj, attr)
        return None

    def _rule_key(self, rule: dict) -> str:
        """
        生成规则的唯一标识符。

        优先使用规则的 name 字段，否则用 target.sid + "/" + target.attr 组合。
        用于定时器字典的 key。
        """
        return rule.get("name") or (rule["target"]["sid"] + "/" + rule["target"]["attr"])

    def _check_condition(self, rule: dict) -> bool:
        """
        检查规则的前置条件是否满足。

        如果规则没有 condition 字段，默认通过。
        如果有，则读取条件设备的当前状态，与 equals 值比较。
        例如：condition: {sid: "灯SID", attr: "channel_0", equals: false}
        表示"仅在灯关闭时"才触发。
        """
        cond = rule.get("condition")
        if not cond:
            return True
        sensor = self.hub.get_sensor(cond["sid"])
        if not sensor:
            return False
        cur = self._get_val(sensor, cond["attr"])
        return str(cur) == str(cond["equals"])

    @staticmethod
    def _is_time_inactive(rule: dict) -> bool:
        """检查当前时间是否在规则指定的不执行时段内.

        规则字段: timeInactive: {"start": "22:00", "end": "06:00"}
        支持跨午夜时段 (start > end 表示跨天).
        """
        ti = rule.get("timeInactive")
        if not ti:
            return False
        start = ti.get("start")
        end = ti.get("end")
        if not start or not end:
            return False
        try:
            h, m = start.split(":")
            start_min = int(h) * 60 + int(m)
            h, m = end.split(":")
            end_min = int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return False
        now = time.localtime()
        now_min = now.tm_hour * 60 + now.tm_min
        if start_min <= end_min:
            return start_min <= now_min < end_min
        else:
            return now_min >= start_min or now_min < end_min

    def _apply_control(self, rule: dict, value):
        """
        向目标设备发送控制指令。

        流程：
          1. 查找目标设备
          2. 检查是否需要刷新网关 token（超过 10s 未刷新则先发 get_id_list）
          3. 调用设备的 control() 方法

        Args:
            rule: 规则配置
            value: 要写入的值（onValue 或 offValue）
        """
        sensor = self.hub.get_sensor(rule["target"]["sid"])
        if not sensor:
            logger.error(f"[trigger] 目标设备不存在: {rule['target']['sid']}")
            return
        if not hasattr(sensor, "control"):
            logger.error(f"[trigger] {rule['target']['sid']} 不支持 Control")
            return

        # 获取网关 IP (用于 token 刷新; 未配置时跳过刷新)
        gw_ip = self._gateways[0].ip if self._gateways else None
        now = time.monotonic()
        last_refresh = self._last_token_refresh.get(gw_ip, 0) if gw_ip else 0
        token_age = now - last_refresh

        def do_control():
            try:
                sensor.control(rule["target"]["attr"], value)
            except Exception as e:
                logger.error(f"[trigger] Control 失败: {e}")

        # 如果距离上次刷新 token 超过 10 秒，先刷新 token 再控制
        if token_age > 10 and gw_ip:
            try:
                # 发送 get_id_list 命令触发网关返回 token
                self.hub.send_message({"cmd": "get_id_list"}, gw_ip)
            except Exception:
                pass
            self._last_token_refresh[gw_ip] = now
            # 延迟 0.5s 等待 token 响应
            self._loop.call_later(0.5, do_control)
        else:
            do_control()

    def _cancel_all_timers(self, dg: str):
        """
        取消指定门磁关联的所有定时器。

        当门被打开或关闭时，需要取消所有关联的延时关灯定时器。
        """
        for rule in self._rules:
            if rule.get("doorGuard") != dg:
                continue
            key = self._rule_key(rule)
            if key in self._timers:
                self._timers[key].cancel()
                del self._timers[key]

    def cancel_all(self):
        """取消全部定时器 (规则热重载/重连时调用, 防止旧规则继续控制设备)."""
        for task in self._timers.values():
            task.cancel()
        self._timers.clear()

    async def _start_timer(self, rule: dict, delay_ms: int):
        """
        异步延时任务：等待 delay_ms 毫秒后执行关灯逻辑。

        关灯前的判断逻辑：
          1. 如果门磁处于"保持"状态（held_by_door=True），不关灯，等门开
          2. 如果门关着，且最近有活动（last_motion 在延时窗口内），则进入保持状态
          3. 如果门关着，且最近无活动，执行关灯
          4. 如果门开着，直接执行关灯
        """
        key = self._rule_key(rule)
        # 等待延时到期
        await asyncio.sleep(delay_ms / 1000)

        dg = rule.get("doorGuard")

        if dg and self._held_by_door.get(dg):
            # 情况1: 已处于保持状态，不关灯
            logger.info(
                f"[trigger] {rule.get('name', '')}: 保持亮灯等门开"
            )
        elif dg and self._door_states.get(dg) is False:
            # 情况2: 门关着，检查最近是否有活动
            last_motion = self._last_motion.get(rule["match"]["sid"], 0)
            if (time.time() * 1000 - last_motion) <= delay_ms + 2000:
                # 在延时窗口内还有人活动，进入保持状态
                self._held_by_door[dg] = True
                logger.info(
                    f"[trigger] {rule.get('name', '')}: "
                    f"门关着且最近{int((time.time() * 1000 - last_motion) / 1000)}s内有活动, 保持亮灯等门开"
                )
            else:
                # 最近无活动，执行关灯
                self._apply_control(rule, rule["offValue"])
                logger.info(
                    f"[trigger] {rule.get('name', '')}: "
                    f"{delay_ms / 1000}s -> offValue={rule['offValue']} (门关)"
                )
        else:
            # 情况3/4: 无门磁约束，或门开着，直接关灯
            self._apply_control(rule, rule["offValue"])
            logger.info(
                f"[trigger] {rule.get('name', '')}: "
                f"{delay_ms / 1000}s -> offValue={rule['offValue']}"
                + (f" (门{'开' if self._door_states.get(dg) else '关'})" if dg else "")
            )

        # 清理定时器
        self._timers.pop(key, None)

    def _schedule_off(self, rule: dict):
        """
        安排延时关灯任务。

        1. 如果有关联门磁，先重置保持状态
        2. 取消已有的定时器（重置延时）
        3. 创建新的异步延时任务
        """
        if rule.get("doorGuard"):
            self._held_by_door[rule["doorGuard"]] = False
        delay = (rule.get("delay") or 30) * 1000
        key = self._rule_key(rule)
        if key in self._timers:
            self._timers[key].cancel()
        self._timers[key] = asyncio.ensure_future(self._start_timer(rule, delay))

    def _is_suppressed_by_door(self, rule: dict) -> bool:
        """
        检查是否因门磁 cooldown 而被抑制。

        当门从关→开（人出门）时，会设置一个短暂的 cooldown 窗口。
        在此期间，该门磁关联的人体传感器触发被跳过，
        防止人刚出门、门关上后人体传感器立即再次触发把灯打开。
        """
        dg = rule.get("doorGuard")
        if not dg:
            return False
        cooldown_until = self._door_open_cooldown.get(dg, 0)
        return time.time() * 1000 < cooldown_until

    # ==================== 公共入口方法 ====================

    def on_data(self, sid: str, data: dict):
        """
        处理传感器数据上报，匹配规则并触发。

        这是规则引擎的主入口，每当传感器上报数据时调用。
        遍历所有规则，检查是否匹配触发条件。

        跳过触发的场景：
          - just_exited: 刚开门离开，跳过本次触发
          - condition 不满足: 前置条件未达成
          - cooldown 中: 门磁 cooldown 窗口内
          - held_by_door: 已在保持状态，跳过重复触发

        定时器处理：
          - 如果已有定时器 + 门关着: 取消定时器，保持亮灯（等人出门）
          - 如果已有定时器 + 门开着: 重置定时器（重新计时）
          - 关联门磁: 先取消关联的所有定时器，再执行开灯
        """
        if self._config.enable_triggers is False:
            return

        for rule in self._rules:
            # 检查是否匹配触发条件
            if not rule.get("match") or rule["match"]["sid"] != sid:
                continue
            v = data.get(rule["match"]["attr"])
            if v is None:
                continue
            if str(v) != str(rule["match"]["equals"]):
                continue

            dg = rule.get("doorGuard")
            key = self._rule_key(rule)

            # 记录人体传感器最后活动时间（用于延时关灯时的判断）
            match_sensor = self.hub.get_sensor(rule["match"]["sid"])
            if dg and match_sensor and hasattr(match_sensor, "no_motion"):
                self._last_motion[sid] = time.time() * 1000

            # 跳过：规则被禁用
            if rule.get("enabled") is False:
                continue

            # 跳过：刚开门离开（门磁 on_door 中设置的标记）
            if self._just_exited == sid:
                self._just_exited = None
                logger.info(f"[trigger] {rule.get('name', '')}: 刚开门离开, 跳过")
                continue

            # 跳过：前置条件不满足
            if not self._check_condition(rule):
                logger.info(f"[trigger] {rule.get('name', '')}: 条件不满足, 跳过")
                continue

            # 跳过：不在允许的时间段内
            if self._is_time_inactive(rule):
                logger.info(
                    f"[trigger] {rule.get('name', '')}: 当前时间在不执行时段内, 跳过"
                )
                continue

            # 跳过：门磁 cooldown 窗口内
            if self._is_suppressed_by_door(rule):
                logger.info(f"[trigger] {rule.get('name', '')}: cooldown中, 跳过")
                continue

            # 已在保持状态：人还在活动，重置定时器，继续等门开
            if dg and self._held_by_door.get(dg):
                self._schedule_off(rule)
                logger.info(f"[trigger] {rule.get('name', '')}: 已在保持状态, 重置定时器")
                continue

            # 处理已有定时器
            if key in self._timers:
                if dg and self._door_states.get(dg) is False:
                    # 门关着，取消定时器，保持亮灯等门开
                    self._cancel_all_timers(dg)
                    self._held_by_door[dg] = True
                    logger.info(
                        f"[trigger] {rule.get('name', '')}: 门关着, 取消定时, 保持亮灯等门开"
                    )
                    continue
                # 门开着，重置定时器
                logger.info(f"[trigger] {rule.get('name', '')}: 门开着, 重置定时器")

            # 取消该门磁关联的所有定时器
            if dg:
                self._cancel_all_timers(dg)

            # 执行开灯
            self._apply_control(rule, rule["onValue"])
            logger.info(f"[trigger] {rule.get('name', '')}: 命中 -> onValue={rule['onValue']}")

            # 如果设置了延时，安排关灯
            if rule.get("delay"):
                self._schedule_off(rule)

    def on_door(self, sid: str, data: dict):
        """
        处理门磁传感器事件。

        两个核心场景：

        1. 门从关→开（人推门出去）:
           - 检查关联的灯是否亮着
           - 如果亮着：立即关灯 + 设置 cooldown + 标记 just_exited
           - 这样门关上后，传感器不会立即重新触发开灯

        2. 门从开→关（人进门后关门）:
           - 清除 cooldown 和 held 状态
           - 重置最后活动时间
           - 允许后续人体传感器触发
        """
        if self._config.enable_triggers is False:
            return

        st = data.get("state")
        if st is None:
            return

        # 记录门磁状态变化前的值
        was_closed = self._door_states.get(sid) is False
        was_open = self._door_states.get(sid) is True
        self._door_states[sid] = bool(st)

        # ---- 场景1: 门从关→开（推门出去） ----
        if st is True and was_closed:
            # 检查该门磁关联的规则中，是否有灯处于开启状态
            any_light_on = False
            for rule in self._rules:
                if rule.get("doorGuard") != sid:
                    continue
                sensor = self.hub.get_sensor(rule["target"]["sid"])
                if sensor and self._get_val(sensor, rule["target"]["attr"]) == rule["onValue"]:
                    any_light_on = True
                    break

            if any_light_on:
                # 标记刚离开的设备，防止门关上后立即重新触发
                self._just_exited = sid
                # 设置 cooldown 窗口，短时间内抑制人体触发
                self._door_open_cooldown[sid] = (
                    time.time() * 1000 + self._door_open_cooldown_ms
                )
                # 取消所有关联的定时器
                self._cancel_all_timers(sid)
                # 关闭所有关联的灯
                for rule in self._rules:
                    if rule.get("doorGuard") != sid:
                        continue
                    self._apply_control(rule, rule["offValue"])
                    logger.info(
                        f"[trigger] {sid}, {rule.get('name', '')} -> offValue={rule['offValue']}"
                    )
                self._held_by_door[sid] = False

        # ---- 场景2: 门从开→关（进门后关门） ----
        if st is False and was_open:
            # 清除 cooldown，允许后续触发
            self._door_open_cooldown.pop(sid, None)
            self._held_by_door[sid] = False
            # 重置最后活动时间，避免延时关灯时误判为"最近有活动"
            for rule in self._rules:
                if rule.get("doorGuard") != sid:
                    continue
                self._last_motion[rule["match"]["sid"]] = 0