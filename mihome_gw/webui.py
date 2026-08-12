"""简易 WebUI: 查看/编辑自动化规则, 实时热重载.

内置 aiohttp 服务, 与主程序同事件循环运行.
"""
import json
import logging

from aiohttp import web

logger = logging.getLogger(__name__)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mihome-gw 自动化配置</title>
<style>
  body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         margin: 0; background: #f5f6f8; color: #222; }
  header { background: #2b3a4a; color: #fff; padding: 14px 24px;
           display: flex; align-items: center; justify-content: space-between; }
  header h1 { font-size: 18px; margin: 0; }
  main { max-width: 960px; margin: 20px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 8px; padding: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,.12); margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left;
           vertical-align: top; }
  th { background: #fafafa; font-weight: 600; }
  input, select { padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px;
                  font-size: 13px; width: 100%; box-sizing: border-box; }
  button { padding: 8px 14px; border: none; border-radius: 4px; cursor: pointer;
           font-size: 13px; }
  .btn-primary { background: #2b7de9; color: #fff; }
  .btn-danger { background: #d9534f; color: #fff; }
  .btn-ghost { background: #eee; color: #333; }
  .btn-sm { padding: 4px 8px; font-size: 12px; }
  .row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
  .row label { width: 90px; flex-shrink: 0; font-size: 13px; color: #555; }
  .row input, .row select { flex: 1; }
  #toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
           background: #333; color: #fff; padding: 10px 20px; border-radius: 4px;
           display: none; font-size: 14px; }
  .muted { color: #888; font-size: 12px; }
  .devices { max-height: 180px; overflow-y: auto; border: 1px solid #eee;
             border-radius: 4px; padding: 4px 8px; font-size: 12px; }
  .devices li { cursor: pointer; padding: 2px 4px; }
  .devices li:hover { background: #f0f4ff; }
  code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px;
         font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>mihome-gw 自动化配置</h1>
  <span class="muted" id="status"></span>
</header>
<main>
  <div class="card">
    <div class="row">
      <label>规则列表</label>
      <button class="btn-primary" onclick="addRule()">+ 新增规则</button>
      <button class="btn-ghost" onclick="loadRules()">刷新</button>
    </div>
    <table id="rules">
      <thead><tr>
        <th style="width:110px">名称</th>
        <th style="width:190px">触发 (人体/传感器)</th>
        <th style="width:190px">目标 (灯/开关)</th>
        <th style="width:130px">动作</th>
        <th style="width:90px">延时(秒)</th>
        <th style="width:110px">门磁</th>
        <th style="width:60px"></th>
      </tr></thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:12px; text-align:right">
      <button class="btn-primary" onclick="saveRules()">保存并生效</button>
    </div>
  </div>

  <div class="card">
    <div class="row"><label>设备列表</label></div>
    <ul class="devices" id="devices"></ul>
    <p class="muted">点击设备可复制 SID 到规则中。规则说明: match=触发条件(sid/attr/equals),
      target=控制目标(sid/attr), onValue=触发时写入, offValue=延时后写入,
      delay=延时秒数, doorGuard=关联门磁 SID(进门保持/出门即关/cooldown 抑制)。</p>
  </div>
</main>
<div id="toast"></div>

<script>
let rules = [];

function toast(msg, ok = true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = ok ? '#2e7d32' : '#d9534f';
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2500);
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.status);
  return data;
}

async function loadRules() {
  try {
    const d = await api('/api/rules');
    rules = d.rules || [];
    document.getElementById('status').textContent = '运行中 · ' + (d.enable_triggers ? '规则引擎已启用' : '规则引擎已停用');
    render();
  } catch (e) { toast('加载失败: ' + e.message, false); }
}

async function loadDevices() {
  try {
    const d = await api('/api/devices');
    const ul = document.getElementById('devices');
    ul.innerHTML = '';
    for (const dev of d.devices || []) {
      const li = document.createElement('li');
      li.textContent = dev.model + '  ' + dev.sid + '  (' + dev.ip + ')';
      li.onclick = () => { navigator.clipboard.writeText(dev.sid); toast('已复制 SID: ' + dev.sid); };
      ul.appendChild(li);
    }
  } catch (e) { /* ignore */ }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function render() {
  const tb = document.querySelector('#rules tbody');
  tb.innerHTML = '';
  if (!rules.length) {
    tb.innerHTML = '<tr><td colspan="7" class="muted">暂无规则 — 点击"新增规则"创建</td></tr>';
    return;
  }
  rules.forEach((r, i) => {
    const m = r.match || {}, t = r.target || {};
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input data-f="name" value="${esc(r.name)}" placeholder="规则名称"></td>
      <td>
        <input data-f="match.sid" value="${esc(m.sid)}" placeholder="传感器SID" style="margin-bottom:4px">
        <div style="display:flex;gap:4px">
          <input data-f="match.attr" value="${esc(m.attr)}" placeholder="attr" style="flex:1">
          <input data-f="match.equals" value="${esc(m.equals)}" placeholder="等于" style="flex:1">
        </div>
      </td>
      <td>
        <input data-f="target.sid" value="${esc(t.sid)}" placeholder="目标SID" style="margin-bottom:4px">
        <input data-f="target.attr" value="${esc(t.attr)}" placeholder="attr (如 channel_0)">
      </td>
      <td>
        <input data-f="onValue" value="${esc(r.onValue)}" placeholder="开值" style="margin-bottom:4px">
        <input data-f="offValue" value="${esc(r.offValue)}" placeholder="关值">
      </td>
      <td><input data-f="delay" value="${esc(r.delay)}" placeholder="30" type="number"></td>
      <td><input data-f="doorGuard" value="${esc(r.doorGuard)}" placeholder="门磁SID"></td>
      <td><button class="btn-danger btn-sm" onclick="removeRule(${i})">删除</button></td>`;
    tb.appendChild(tr);
  });
}

function collect() {
  const rows = document.querySelectorAll('#rules tbody tr');
  const out = [];
  rows.forEach(tr => {
    const get = f => tr.querySelector(`[data-f="${f}"]`);
    const rule = {
      name: get('name').value.trim(),
      match: { sid: get('match.sid').value.trim(), attr: get('match.attr').value.trim(),
               equals: norm(get('match.equals').value) },
      target: { sid: get('target.sid').value.trim(), attr: get('target.attr').value.trim() },
      onValue: norm(get('onValue').value),
      offValue: norm(get('offValue').value),
    };
    const delay = get('delay').value, dg = get('doorGuard').value.trim();
    if (delay !== '') rule.delay = parseInt(delay, 10);
    if (dg !== '') rule.doorGuard = dg;
    if (rule.name && rule.match.sid && rule.target.sid) out.push(rule);
  });
  return out;
}

function norm(v) {
  const s = String(v).trim();
  if (s === 'true') return true;
  if (s === 'false') return false;
  if (s !== '' && !isNaN(Number(s))) return Number(s);
  return s;
}

function addRule() {
  rules.push({ name: '', match: { sid: '', attr: 'state', equals: true },
               target: { sid: '', attr: 'channel_0' }, onValue: true, offValue: false, delay: 30 });
  render();
}

function removeRule(i) { rules.splice(i, 1); render(); }

async function saveRules() {
  const newRules = collect();
  try {
    const d = await api('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules: newRules }),
    });
    rules = d.rules;
    toast('已保存并生效 (' + rules.length + ' 条规则)');
    render();
  } catch (e) { toast('保存失败: ' + e.message, false); }
}

loadRules();
loadDevices();
</script>
</body>
</html>
"""


class WebUI:
    """aiohttp Web 服务: 规则查看/编辑 + 热重载."""

    def __init__(self, app, config_path: str, port: int = 8080, bind: str = "0.0.0.0"):
        self._main = app
        self._config_path = config_path
        self._port = port
        self._bind = bind
        self._runner = None

    # ---- routes ----
    async def _index(self, request):
        return web.Response(text=HTML, content_type="text/html")

    async def _get_rules(self, request):
        cfg = self._main.config
        return web.json_response({
            "rules": cfg.rules,
            "enable_triggers": cfg.enable_triggers,
            "gateways": [{"ip": g.ip, "sid": g.sid} for g in cfg.gateways],
            "output": cfg.output.type,
        })

    async def _post_rules(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效的 JSON 请求体"}, status=400)

        new_rules = body.get("rules")
        if not isinstance(new_rules, list):
            return web.json_response({"error": "rules 必须是数组"}, status=400)

        # 校验必填字段
        for i, r in enumerate(new_rules):
            if not r.get("match", {}).get("sid") or not r.get("target", {}).get("sid"):
                return web.json_response(
                    {"error": f"第 {i + 1} 条规则缺少 match.sid 或 target.sid"}, status=400)

        # 写回 config.json (仅更新 rules 字段)
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            data["rules"] = new_rules
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[webui] 写配置失败: {e}")
            return web.json_response({"error": f"写配置文件失败: {e}"}, status=500)

        # 更新内存配置并热重载规则引擎
        self._main.config.rules = new_rules
        try:
            self._main.setup_triggers()
            logger.info(f"[webui] 规则已更新并热重载 ({len(new_rules)} 条)")
        except Exception as e:
            logger.error(f"[webui] 热重载失败: {e}")
            return web.json_response({"error": f"规则已保存但重载失败: {e}"}, status=500)

        return web.json_response({"ok": True, "rules": new_rules})

    async def _get_devices(self, request):
        devices = []
        hub = self._main.hub
        if hub:
            for sid, sensor in hub.sensors.items():
                devices.append({
                    "sid": sid,
                    "model": getattr(sensor, "className", ""),
                    "ip": getattr(sensor, "ip", ""),
                })
        devices.sort(key=lambda d: d["model"])
        return web.json_response({"devices": devices})

    # ---- lifecycle ----
    async def start(self):
        webapp = web.Application()
        webapp.router.add_get("/", self._index)
        webapp.router.add_get("/api/rules", self._get_rules)
        webapp.router.add_post("/api/rules", self._post_rules)
        webapp.router.add_get("/api/devices", self._get_devices)
        self._runner = web.AppRunner(webapp)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._bind, self._port)
        await site.start()
        logger.info(f"[webui] http://{self._bind}:{self._port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
