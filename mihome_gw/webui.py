"""简易 WebUI: 查看/编辑自动化规则和配置, 实时热重载."""
import json
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mihome-gw 配置</title>
<style>
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#222}
header{background:#2b3a4a;color:#fff;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;margin:0}
main{max-width:960px;margin:20px auto;padding:0 16px}
.card{background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.12);margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
th{background:#fafafa;font-weight:600}
input,select{padding:6px 8px;border:1px solid #ccc;border-radius:4px;font-size:13px;width:100%;box-sizing:border-box}
button{padding:8px 14px;border:none;border-radius:4px;cursor:pointer;font-size:13px}
.btn-primary{background:#2b7de9;color:#fff}
.btn-success{background:#2e7d32;color:#fff}
.btn-danger{background:#d9534f;color:#fff}
.btn-ghost{background:#eee;color:#333}
.btn-sm{padding:4px 8px;font-size:12px}
.row{display:flex;gap:8px;margin-bottom:8px;align-items:center}
.row label{width:110px;flex-shrink:0;font-size:13px;color:#555}
.row input,.row select{flex:1}
.col2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:4px;display:none;font-size:14px;z-index:999}
.muted{color:#888;font-size:12px}
.devices{max-height:180px;overflow-y:auto;border:1px solid #eee;border-radius:4px;padding:4px 8px;font-size:12px}
.devices li{cursor:pointer;padding:2px 4px}
.devices li:hover{background:#f0f4ff}
code{background:#f4f4f4;padding:1px 4px;border-radius:3px;font-size:12px}
hr{border:none;border-top:1px solid #eee;margin:12px 0}
</style>
</head>
<body>
<header><h1>mihome-gw 配置</h1><span class="muted" id="status"></span></header>
<main>

<div class="card">
  <div class="row" style="justify-content:space-between">
    <label style="width:auto">自动化规则</label>
    <div>
      <button class="btn-primary btn-sm" onclick="addRule()">+ 新增</button>
      <button class="btn-ghost btn-sm" onclick="loadRules()">刷新</button>
    </div>
  </div>
<table id=\"rules\"><thead><tr>
    <th style=\"width:90px\">名称</th>
    <th style=\"width:170px\">触发</th>
    <th style=\"width:170px\">目标</th>
    <th style=\"width:90px\">动作</th>
    <th style=\"width:55px\">延时</th>
    <th style=\"width:100px\">门磁</th>
    <th style=\"width:130px\">不执行时段</th>
    <th style=\"width:40px\"></th>
  </tr></thead><tbody></tbody></table>
  <div style="margin-top:12px;text-align:right">
    <button class="btn-success btn-sm" onclick="saveRules()">保存规则</button>
  </div>
</div>

<div class="card">
  <div class="row" style="justify-content:space-between">
    <label style="width:auto">系统设置</label>
    <button class="btn-success btn-sm" onclick="saveConfig()">保存设置</button>
  </div>
  <div class="col2">
    <div class="row"><label>规则引擎</label>
      <select id="cfg_enable_triggers"><option value="true">启用</option><option value="false">停用</option></select></div>
    <div class="row"><label>门磁抑制(ms)</label>
      <input id="cfg_doorOpenCooldownMs" type="number" min="0" max="30000" step="500"></div>
    <div class="row"><label>心跳超时(s)</label>
      <input id="cfg_heartbeatTimeout" type="number" min="10" max="600" step="5"></div>
    <div class="row"><label>Rediscover(s)</label>
      <input id="cfg_rediscoverInterval" type="number" min="0" max="600" step="5"></div>
    <div class="row"><label>调试日志</label>
      <select id="cfg_debug"><option value="true">开启</option><option value="false">关闭</option></select></div>
    <div class="row"><label>Web 端口</label>
      <input id="cfg_web_port" type="number" min="1024" max="65535"></div>
  </div>
  <p class="muted">规则引擎/门磁抑制/调试日志 修改后立即生效；心跳/Rediscover/Web端口 需重启进程。</p>
</div>

<div class="card">
  <div class="row"><label style="width:auto">设备列表</label></div>
  <ul class="devices" id="devices"></ul>
  <p class="muted">点击设备 SID 复制到剪贴板。规则字段说明: match=触发条件, target=控制目标,
    onValue=触发写入, offValue=延时写入, doorGuard=门磁SID(进门保持/出门即关/cooldown 抑制)。</p>
</div>

</main>
<div id="toast"></div>

<script>
let rules=[];

function t(m,o){const d=document.getElementById('toast');d.textContent=m;d.style.background=o?'#2e7d32':'#d9534f';d.style.display='block';setTimeout(()=>d.style.display='none',2500)}

async function api(p,o){const r=await fetch(p,o);const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||r.status);return d}

async function loadRules(){try{
  const d=await api('/api/rules');
  rules=d.rules||[];
  document.getElementById('status').textContent='运行中 · '+(d.enable_triggers?'规则引擎已启用':'已停用');
  render();
  // 填充设置
  document.getElementById('cfg_enable_triggers').value=String(d.enable_triggers);
  document.getElementById('cfg_doorOpenCooldownMs').value=d.doorOpenCooldownMs;
  document.getElementById('cfg_heartbeatTimeout').value=d.heartbeatTimeout;
  document.getElementById('cfg_rediscoverInterval').value=d.rediscoverInterval;
  document.getElementById('cfg_debug').value=String(d.debug);
  document.getElementById('cfg_web_port').value=d.web_port;
}catch(e){t('加载失败: '+e.message,false)}}

async function loadDevices(){try{
  const d=await api('/api/devices');
  const ul=document.getElementById('devices');ul.innerHTML='';
  for(const dev of d.devices||[]){
    const li=document.createElement('li');
    li.textContent=dev.model+'  '+dev.sid+'  ('+dev.ip+')';
    li.onclick=()=>{navigator.clipboard.writeText(dev.sid);t('已复制: '+dev.sid)};
    ul.appendChild(li);
  }
}catch(e){}}

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function render(){
  const tb=document.querySelector('#rules tbody');tb.innerHTML='';
  if(!rules.length){tb.innerHTML='<tr><td colspan=\"8\" class=\"muted\">暂无规则</td></tr>';return}
  rules.forEach((r,i)=>{
    const m=r.match||{},t=r.target||{};
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td><input data-f="name" value="${esc(r.name)}" placeholder="名称"></td>
      <td><input data-f="match.sid" value="${esc(m.sid)}" placeholder="SID" style="margin-bottom:3px">
        <div style="display:flex;gap:3px">
          <input data-f="match.attr" value="${esc(m.attr)}" placeholder="attr" style="flex:1">
          <input data-f="match.equals" value="${esc(m.equals)}" placeholder="=" style="flex:1">
        </div></td>
      <td><input data-f="target.sid" value="${esc(t.sid)}" placeholder="SID" style="margin-bottom:3px">
        <input data-f="target.attr" value="${esc(t.attr)}" placeholder="attr"></td>
      <td><input data-f="onValue" value="${esc(r.onValue)}" placeholder="开" style="margin-bottom:3px">
        <input data-f="offValue" value="${esc(r.offValue)}" placeholder="关"></td>
      <td><input data-f="delay" value="${esc(r.delay)}" type="number" step="1" style="width:50px"></td>
      <td><input data-f="doorGuard" value="${esc(r.doorGuard)}" placeholder="门磁SID"></td>
      <td><div style="display:flex;gap:3px;align-items:center">
          <input data-f="timeInactive.start" value="${esc((r.timeInactive||{}).start)}" placeholder="22:00" style="flex:1;width:55px">
          <span>~</span>
          <input data-f="timeInactive.end" value="${esc((r.timeInactive||{}).end)}" placeholder="06:00" style="flex:1;width:55px">
        </div></td>
      <td><button class="btn-danger btn-sm" onclick="removeRule(${i})">×</button></td>`;
    tb.appendChild(tr);
  });
}

function collect(){
  const rows=document.querySelectorAll('#rules tbody tr');const out=[];
  rows.forEach(tr=>{
    const g=f=>tr.querySelector(`[data-f="${f}"]`);
    const r={name:g('name').value.trim(),match:{sid:g('match.sid').value.trim(),attr:g('match.attr').value.trim(),equals:n(g('match.equals').value)},target:{sid:g('target.sid').value.trim(),attr:g('target.attr').value.trim()},onValue:n(g('onValue').value),offValue:n(g('offValue').value)};
    const d=g('delay').value, dg=g('doorGuard').value.trim();
    if(d!=='')r.delay=parseInt(d,10);
    if(dg!=='')r.doorGuard=dg;
    const ts=g('timeInactive.start').value, te=g('timeInactive.end').value;
    if(ts||te)r.timeInactive={start:ts.trim(),end:te.trim()};
    if(r.name&&r.match.sid&&r.target.sid)out.push(r)});
  return out;
}

function n(v){const s=String(v).trim();if(s==='true')return true;if(s==='false')return false;if(s!==''&&!isNaN(Number(s)))return Number(s);return s}

function addRule(){rules.push({name:'',match:{sid:'',attr:'state',equals:true},target:{sid:'',attr:'channel_0'},onValue:true,offValue:false,delay:30});render()}
function removeRule(i){rules.splice(i,1);render()}

async function saveRules(){
  const nr=collect();
  try{const d=await api('/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rules:nr})});rules=d.rules;t('已保存 ('+rules.length+' 条规则)');render()}catch(e){t('保存失败: '+e.message,false)}
}

async function saveConfig(){
  const cfg={
    enable_triggers: document.getElementById('cfg_enable_triggers').value==='true',
    doorOpenCooldownMs: parseInt(document.getElementById('cfg_doorOpenCooldownMs').value,10)||5000,
    heartbeatTimeout: parseInt(document.getElementById('cfg_heartbeatTimeout').value,10)||120,
    rediscoverInterval: parseInt(document.getElementById('cfg_rediscoverInterval').value,10)||60,
    debug: document.getElementById('cfg_debug').value==='true',
    web_port: parseInt(document.getElementById('cfg_web_port').value,10)||8080,
  };
  try{const d=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});t('已保存'+(d.hot_reload?' (已生效)':' (部分需重启)'))}catch(e){t('保存失败: '+e.message,false)}
}

loadRules();loadDevices();
</script>
</body>
</html>"""


class WebUI:
    def __init__(self, app, config_path: str, port: int = 8080, bind: str = "0.0.0.0"):
        self._main = app
        self._config_path = config_path
        self._port = port
        self._bind = bind
        self._runner = None

    # ---- routes ----
    async def _index(self, request):
        return web.Response(text=HTML, content_type="text/html", charset="utf-8")

    async def _get_rules(self, request):
        cfg = self._main.config
        return web.json_response({
            "rules": cfg.rules,
            "enable_triggers": cfg.enable_triggers,
            "doorOpenCooldownMs": cfg.doorOpenCooldownMs,
            "heartbeatTimeout": cfg.heartbeatTimeout,
            "rediscoverInterval": cfg.rediscoverInterval,
            "debug": cfg.debug,
            "web_port": cfg.web_port,
            "gateways": [{"ip": g.ip, "sid": g.sid} for g in cfg.gateways],
            "output": cfg.output.type,
        })

    async def _post_rules(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)
        new_rules = body.get("rules")
        if not isinstance(new_rules, list):
            return web.json_response({"error": "rules 必须是数组"}, status=400)
        for i, r in enumerate(new_rules):
            if not r.get("match", {}).get("sid") or not r.get("target", {}).get("sid"):
                return web.json_response({"error": f"第 {i+1} 条缺少 sid"}, status=400)
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            data["rules"] = new_rules
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return web.json_response({"error": f"写文件失败: {e}"}, status=500)
        self._main.config.rules = new_rules
        try:
            self._main.setup_triggers()
            logger.info(f"[webui] 规则热重载 ({len(new_rules)} 条)")
        except Exception as e:
            return web.json_response({"error": f"规则已保存但重载失败: {e}"}, status=500)
        return web.json_response({"ok": True, "rules": new_rules})

    async def _get_config(self, request):
        # 返回完整配置（隐藏 key）
        cfg = self._main.config
        return web.json_response({
            "enable_triggers": cfg.enable_triggers,
            "doorOpenCooldownMs": cfg.doorOpenCooldownMs,
            "heartbeatTimeout": cfg.heartbeatTimeout,
            "rediscoverInterval": cfg.rediscoverInterval,
            "debug": cfg.debug,
            "web_enabled": cfg.web_enabled,
            "web_port": cfg.web_port,
            "web_bind": cfg.web_bind,
            "port": cfg.port,
            "bind": cfg.bind,
            "output_type": cfg.output.type,
            "gateways": [{"ip": g.ip, "sid": g.sid} for g in cfg.gateways],
        })

    async def _post_config(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)

        # 读当前文件, 更新可改字段
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            return web.json_response({"error": f"读配置失败: {e}"}, status=500)

        hot = {"enable_triggers": None, "doorOpenCooldownMs": None, "debug": None}
        for k in ("enable_triggers", "doorOpenCooldownMs", "heartbeatTimeout",
                  "rediscoverInterval", "debug", "web_port"):
            if k in body:
                data[k] = body[k]
                if k in hot:
                    hot[k] = body[k]

        try:
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return web.json_response({"error": f"写文件失败: {e}"}, status=500)

        # 热生效: 更新内存 config + 触发引擎
        cfg = self._main.config
        if hot["enable_triggers"] is not None:
            cfg.enable_triggers = hot["enable_triggers"]
        if hot["doorOpenCooldownMs"] is not None:
            cfg.doorOpenCooldownMs = hot["doorOpenCooldownMs"]
            if self._main.triggers:
                self._main.triggers._door_open_cooldown_ms = hot["doorOpenCooldownMs"]
        if hot["debug"] is not None:
            cfg.debug = hot["debug"]
        # 其余字段存进内存 (重启才生效)
        for k in ("heartbeatTimeout", "rediscoverInterval", "web_port"):
            if k in body:
                setattr(cfg, k, body[k])

        logger.info(f"[webui] 配置已更新")
        return web.json_response({"ok": True, "hot_reload": True})

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

    async def start(self):
        webapp = web.Application()
        webapp.router.add_get("/", self._index)
        webapp.router.add_get("/api/rules", self._get_rules)
        webapp.router.add_post("/api/rules", self._post_rules)
        webapp.router.add_get("/api/config", self._get_config)
        webapp.router.add_post("/api/config", self._post_config)
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