# mihome-gw-py

米家网关（Xiaomi Gateway / Aqara Gateway）UDP 监听代理，Python asyncio 重写版。
监听网关组播消息，解析设备数据并通过 MQTT（含 Home Assistant MQTT Discovery）转发，
同时内置"人体感应开灯"规则引擎。

## 功能特性

- **组播监听**：加入 `224.0.0.50:4321` 组播组，自动发现网关及子设备（协议 v1/v2）
- **设备支持**：网关（RGB/AC partner）、温湿度、门磁、人体、插座、墙壁开关、无线开关、
  魔方、烟雾/燃气报警、窗帘、门锁、水浸、振动传感器等 40+ 型号
- **Home Assistant 接入**：自动发布 MQTT Discovery 配置（sensor / binary_sensor / switch /
  light / cover / lock），`mihome/cmd/<sid>/<attr>` 主题支持反向控制
- **内置规则引擎**：人体感应开灯 → 延时关灯，支持门磁联动防误触
  （进门保持、出门即关、cooldown 抑制重复触发）
- **输出后端**：MQTT / Webhook / Console
- **部署方式**：独立 Docker 容器（host 网络）或 HA Add-on

## 快速开始

### 方式一：Docker 独立运行

1. 准备配置（可复制 `config.example.json` 为 `data/options.json` 或直接使用 `config.json`）：

   ```bash
   mkdir -p data
   cp config.example.json data/options.json
   # 编辑 data/options.json：填入网关 IP 和密钥
   ```

2. 启动：

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

### 方式二：本地运行

```bash
pip install -r requirements.txt
cp config.example.json config.json   # 修改其中的网关 IP/密钥
python -m mihome_gw
```

## 配置说明

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `port` | `9898` | UDP 监听端口 |
| `bind` | `0.0.0.0` | 绑定地址 |
| `debug` | `false` | 打印原始上报消息 |
| `enable_triggers` | `true` | 是否启用内置规则引擎 |
| `doorOpenCooldownMs` | `5000` | 门磁开门后的触发抑制窗口（毫秒） |
| `heartbeatTimeout` | `120` | 无消息超时触发重连（秒） |
| `rediscoverInterval` | `60` | 周期性发送 `whois` 重新发现设备（秒） |
| `gateways` | - | 网关列表 `[{ip, key, sid}]`，key 为局域网通信密钥 |
| `output` | console | `{type: mqtt/webhook/console, url, prefix}` |
| `rules` | - | 内置规则引擎规则列表 |

### 规则引擎格式

```json
{
  "name": "人体开灯-30秒延时关",
  "match": {"sid": "158d000258361c", "attr": "state", "equals": true},
  "target": {"sid": "158d0002b062cd", "attr": "channel_0"},
  "onValue": true,
  "offValue": false,
  "delay": 30,
  "doorGuard": "158d00032b73ec"
}
```

- `match`：触发条件（人体传感器 `state` 为 true）
- `target`：控制目标（灯/插座/开关）
- `delay`：延时秒数，到期写入 `offValue`
- `doorGuard`：关联门磁 SID，实现"进门保持亮灯、出门立即关灯、关门抑制重复触发"
- `condition`：可选前置条件 `{sid, attr, equals}`，满足才触发

## Home Assistant 接入

1. 启用 HA 的 MQTT 集成（如 Mosquitto broker）
2. 配置 `output.type = "mqtt"`，`output.url = "mqtt://用户:密码@broker地址:1883"`
3. 设备上线后自动发布 discovery 配置，HA 中自动出现实体
4. 控制主题：`mihome/cmd/<sid>/<attr>`（如 `mihome/cmd/158d0002b062cd/channel_0` 发送 `on`/`off`）

## 目录结构

```
mihome_gw/
├── __main__.py       # 入口：App 生命周期、MQTT 命令处理、健康检查/重连
├── config.py         # 配置加载（config.json / options.json）
├── hub.py            # UDP 组播 Hub：设备发现、token/密钥、协议 v1/v2
├── devices.py        # 设备型号注册表 + 类型分类
├── discovery.py      # HA MQTT Discovery 配置生成
├── mqtt_output.py    # MQTT / Webhook / Console 输出后端
├── triggers.py       # 内置规则引擎（人体开灯 + 门磁联动）
└── sensors/          # 各设备型号解析与控制类
```

## 常见问题

- **收不到设备消息**：确认容器使用 `network_mode: host`（组播需要宿主机网络），
  网关与主机在同一网段，且已在米家 App 开启"局域网通信协议"
- **控制无响应**：控制前需要网关 token，程序会自动发送 `get_id_list` 刷新；
  确认网关密钥（`gateways[].key`）填写正确
