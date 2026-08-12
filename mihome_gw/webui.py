"""WebUI: 规则编辑/设备状态/日志/测试/设置, 全功能版."""

import json
import logging
import time
from aiohttp import web

from .log_capture import get_logs, grep_logs

logger = logging.getLogger(__name__)

# ====================== HTML (模板内联) ======================
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>mihome-gw 配置</title>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#222;font-size:14px}
header{background:#2b3a4a;color:#fff;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px}
header h1{font-size:16px;margin:0}
#status{font-size:12px;color:#adb5bd}
.tabs{display:flex;background:#e9ecef;border-bottom:2px solid #dee2e6;overflow-x:auto}
.tab{padding:10px 18px;cursor:pointer;border:none;background:none;font-size:13px;color:#555;white-space:nowrap}
.tab.active{background:#fff;color:#2b7de9;border-bottom:2px solid #2b7de9;margin-bottom:-2px;font-weight:600}
.tab-content{display:none;padding:12px;max-width:1200px;margin:0 auto}
.tab-content.active{display:block}
.card{background:#fff;border-radius:6px;padding:12px;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:middle}
th{background:#f8f9fa;font-weight:600;white-space:nowrap}
input,select{padding:4px 6px;border:1px solid #ccc;border-radius:3px;font-size:12px;width:100%;box-sizing:border-box;background:#fff}
select{cursor:pointer}
input:focus,select:focus{outline:none;border-color:#2b7de9;box-shadow:0 0 0 2px rgba(43,125,233,.2)}
button{padding:6px 12px;border:none;border-radius:3px;cursor:pointer;font-size:12px;white-space:nowrap}
.btn-pri{background:#2b7de9;color:#fff}
.btn-suc{background:#2e7d32;color:#fff}
.btn-dan{background:#d9534f;color:#fff}
.btn-ghost{background:#e9ecef;color:#333}
.btn-sm{padding:3px 7px;font-size:11px}
.row{display:flex;gap:6px;margin-bottom:6px;align-items:center;flex-wrap:wrap}
.row label{font-size:12px;color:#555;flex-shrink:0;min-width:70px}
.row input,.row select{flex:1;min-width:60px}
.half{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media(max-width:640px){.half{grid-template-columns:1fr}}
.muted{color:#888;font-size:11px}

/* 设备面板 */
.states-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
.state-card{background:#fff;border:1px solid #eee;border-radius:6px;padding:8px 10px;position:relative}
.state-card .model{font-size:11px;color:#888}
.state-card .sid{font-size:11px;color:#aaa;cursor:pointer}
.state-card .sid:hover{color:#2b7de9}
.state-card .vals{font-size:13px;margin-top:4px;display:flex;flex-wrap:wrap;gap:4px}
.state-card .vals span{background:#f0f4ff;padding:1px 6px;border-radius:3px;font-size:11px;white-space:nowrap}
.state-card .offline{color:#d9534f;font-size:11px}
.state-card .online{color:#2e7d32}

/* 日志 */
.log-box{background:#1e1e1e;color:#d4d4d4;font-family:"Cascadia Code","Fira Code",monospace;font-size:12px;padding:8px;border-radius:4px;height:400px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;line-height:1.5}
.log-box .info{color:#6bc7f7}
.log-box .warn{color:#e8c547}
.log-box .error{color:#f44747}
.log-box .debug{color:#888}

/* toast */
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 16px;border-radius:4px;display:none;font-size:13px;z-index:9999;max-width:90%}

/* 开关样式 */
.toggle{width:36px;height:20px;background:#ccc;border-radius:10px;position:relative;cursor:pointer;display:inline-block;flex-shrink:0}
.toggle.on{background:#2e7d32}
.toggle::after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;background:#fff;border-radius:50%;transition:.15s}
.toggle.on::after{left:18px}
</style>
</head>
<body>

<header>
  <h1>mihome-gw 配置</h1>
  <span id="status"></span>
</header>

<div class="tabs" id="tabs">
  <button class="tab active" data-tab="rules">规则</button>
  <button class="tab" data-tab="devices">设备</button>
  <button class="tab" data-tab="logs">日志</button>
  <button class="tab" data-tab="test">测试</button>
  <button class="tab" data-tab="settings">设置</button>
</div>

<!-- ================ 规则 ================ -->
<div class="tab-content active" id="tab-rules">
  <div class="card">
    <div class="row" style="justify-content:space-between">
      <label style="min-width:auto;font-weight:600">自动化规则</label>
      <div style="display:flex;gap:4px;flex-wrap:wrap">
        <button class="btn-pri btn-sm" onclick="addRule()">+新增</button>
        <button class="btn-ghost btn-sm" onclick="refreshDevices();loadRules()">刷新</button>
        <button class="btn-ghost btn-sm" onclick="exportConfig()">导出</button>
        <button class="btn-ghost btn-sm" onclick="document.getElementById('importFile').click()">导入</button>
        <input type="file" id="importFile" accept=".json" style="display:none" onchange="importConfig(event)">
      </div>
    </div>
    <div style="overflow-x:auto">
    <table id="tbl-rules"><thead><tr>
      <th style="width:32px"><span class="muted">开</span></th>
      <th style="width:80px">名称</th>
      <th style="min-width:200px">触发 (传感器)</th>
      <th style="min-width:200px">目标 (设备)</th>
      <th style="min-width:140px">前置条件</th>
      <th style="width:80px">动作</th>
      <th style="width:50px">延时</th>
      <th style="width:100px">门磁</th>
      <th style="width:120px">不执行时段</th>
      <th style="width:36px"></th>
    </tr></thead>
    <tbody id="rules-body"></tbody></table>
    </div>
    <div style="margin-top:8px;text-align:right">
      <button class="btn-suc btn-sm" onclick="saveRules()">保存规则</button>
    </div>
  </div>
  <div class="card">
    <div class="row"><label style="min-width:auto;font-weight:600">设备列表 (点击 SID 填入规则)</label></div>
    <div id="device-list" style="max-height:180px;overflow-y:auto;font-size:12px"></div>
  </div>
</div>

<!-- ================ 设备 ================ -->
<div class="tab-content" id="tab-devices">
  <div class="card">
    <div class="row" style="justify-content:space-between">
      <label style="min-width:auto;font-weight:600">设备实时状态</label>
      <button class="btn-ghost btn-sm" onclick="loadStates()">刷新</button>
    </div>
    <div id="states-grid" class="states-grid"></div>
  </div>
</div>

<!-- ================ 日志 ================ -->
<div class="tab-content" id="tab-logs">
  <div class="card">
    <div class="row" style="justify-content:space-between">
      <label style="min-width:auto;font-weight:600">最近日志</label>
      <div style="display:flex;gap:4px">
        <input id="log-search" placeholder="过滤关键词" style="width:160px" oninput="loadLogs()">
        <button class="btn-ghost btn-sm" onclick="loadLogs()">刷新</button>
        <label class="toggle" id="log-auto-refresh" onclick="toggleLogAuto()"><span class="muted" style="position:absolute;left:40px;width:auto;white-space:nowrap">自动</span></label>
      </div>
    </div>
    <div class="log-box" id="log-box"></div>
  </div>
</div>

<!-- ================ 测试 ================ -->
<div class="tab-content" id="tab-test">
  <div class="half">
    <div class="card">
      <div class="row"><label style="min-width:auto;font-weight:600">MQTT 发布</label></div>
      <div class="row"><label>主题</label><input id="test-topic" placeholder="mihome/cmd/xxx/channel_0"></div>
      <div class="row"><label>内容</label><input id="test-payload" value="ON"></div>
      <button class="btn-pri btn-sm" onclick="testMqtt()">发送</button>
      <pre id="test-mqtt-result" class="muted" style="margin-top:6px;font-size:11px"></pre>
    </div>
    <div class="card">
      <div class="row"><label style="min-width:auto;font-weight:600">模拟规则触发</label></div>
      <div class="row"><label>SID</label><input id="test-trigger-sid" placeholder="158d000258361c"></div>
      <div class="row"><label>属性</label>
        <select id="test-trigger-attr"><option value="state">state</option><option value="channel_0">channel_0</option><option value="channel_1">channel_1</option></select>
      </div>
      <div class="row"><label>值</label>
        <select id="test-trigger-value"><option value="true">true</option><option value="false">false</option></select>
      </div>
      <button class="btn-pri btn-sm" onclick="testTrigger()">模拟触发</button>
      <pre id="test-trigger-result" class="muted" style="margin-top:6px;font-size:11px"></pre>
    </div>
  </div>
</div>

<!-- ================ 设置 ================ -->
<div class="tab-content" id="tab-settings">
  <div class="card">
    <div class="row" style="justify-content:space-between">
      <label style="min-width:auto;font-weight:600">系统设置</label>
      <button class="btn-suc btn-sm" onclick="saveSettings()">保存</button>
    </div>
    <div class="half">
      <div class="row"><label>规则引擎</label>
        <select id="s-enable-triggers"><option value="true">启用</option><option value="false">停用</option></select></div>
      <div class="row"><label>门磁抑制(ms)</label><input id="s-door-cooldown" type="number" min="0" max="30000" step="500"></div>
      <div class="row"><label>心跳超时(s)</label><input id="s-heartbeat" type="number" min="10" max="600" step="5"></div>
      <div class="row"><label>Rediscover(s)</label><input id="s-rediscover" type="number" min="0" max="600" step="5"></div>
      <div class="row"><label>调试日志</label>
        <select id="s-debug"><option value="true">开启</option><option value="false">关闭</option></select></div>
      <div class="row"><label>Web 端口</label><input id="s-web-port" type="number" min="1024" max="65535"></div>
    </div>
    <p class="muted">规则引擎/门磁抑制/调试日志 修改后立即生效；其余需重启进程。</p>
  </div>
</div>

<div id="toast"></div>

<script>
// ============== 工具函数 ==============
let rules = [], devices = [], logAutoTimer = null, statesTimer = null;

function toast(m,ok){
  const t=document.getElementById('toast');
  t.textContent=m;t.style.background=ok?'#2e7d32':'#d9534f';t.style.display='block';
  setTimeout(()=>t.style.display='none',2500);
}

async function api(p,o){
  const r=await fetch(p,o);
  const d=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(d.error||r.status);
  return d;
}

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

function norm(v){
  const s=String(v).trim();
  if(s==='true') return true; if(s==='false') return false;
  if(s!==''&&!isNaN(Number(s))) return Number(s);
  return s;
}

// ============== Tab 切换 ==============
document.querySelectorAll('.tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-'+tab.dataset.tab).classList.add('active');
  });
});

// ============== 设备列表下拉填充 ==============
async function refreshDevices(){
  try{
    const d=await api('/api/devices');
    devices=d.devices||[];
    const ul=document.getElementById('device-list');ul.innerHTML='';
    devices.forEach(dev=>{
      const span=document.createElement('span');
      span.style.cssText='display:inline-block;margin:2px 4px;padding:2px 6px;background:#f0f4ff;border-radius:3px;cursor:pointer;font-size:11px';
      span.textContent=dev.model+' '+dev.sid;
      span.title='IP: '+dev.ip+'\n点击复制 SID';
      span.onclick=()=>{navigator.clipboard.writeText(dev.sid);toast('已复制: '+dev.sid)};
      ul.appendChild(span);
    });
    // 填充所有下拉
    document.querySelectorAll('select.sid-sel').forEach(sel=>{
      const cur=sel.value;
      sel.innerHTML='<option value="">(选SID)</option>'+devices.map(d=>'<option value="'+esc(d.sid)+'">'+esc(d.model+' '+d.sid)+'</option>').join('');
      if(cur) sel.value=cur;
    });
  }catch(e){}
}

// ============== 规则 ==============
function renderRules(){
  const tb=document.getElementById('rules-body');tb.innerHTML='';
  if(!rules.length){tb.innerHTML='<tr><td colspan="10" class="muted">暂无规则</td></tr>';return}
  rules.forEach((r,i)=>{
    const m=r.match||{},t=r.target||{},c=r.condition||{},ti=r.timeInactive||{};
    const tr=document.createElement('tr');
    const enabled=r.enabled!==false;
    tr.innerHTML=
      '<td><div class="toggle'+(enabled?' on':'')+'" onclick="toggleRule('+i+')"></div></td>'+
      '<td><input data-f="name" value="'+esc(r.name)+'" placeholder="名称"></td>'+
      '<td><select class="sid-sel" data-f="match.sid" onchange="syncSid(this)"></select>'+
        '<div style="display:flex;gap:2px;margin-top:2px">'+
        '<select data-f="match.attr" style="flex:1"><option value="state"'+('state'==m.attr?' selected':'')+'>state</option><option value="channel_0"'+('channel_0'==m.attr?' selected':'')+'>ch0</option><option value="channel_1"'+('channel_1'==m.attr?' selected':'')+'>ch1</option></select>'+
        '<select data-f="match.equals" style="flex:1"><option value="true"'+('true'==String(m.equals)?' selected':'')+'>true</option><option value="false"'+('false'==String(m.equals)?' selected':'')+'>false</option></select></div></td>'+
      '<td><select class="sid-sel" data-f="target.sid" onchange="syncSid(this)"></select>'+
        '<select data-f="target.attr" style="margin-top:2px"><option value="channel_0"'+('channel_0'==t.attr?' selected':'')+'>channel_0</option><option value="channel_1"'+('channel_1'==t.attr?' selected':'')+'>channel_1</option><option value="state"'+('state'==t.attr?' selected':'')+'>state</option></select></td>'+
      '<td><select class="sid-sel" data-f="condition.sid" onchange="syncSid(this)"></select>'+
        '<div style="display:flex;gap:2px;margin-top:2px">'+
        '<select data-f="condition.attr" style="flex:1"><option value="">(attr)</option><option value="state"'+('state'==c.attr?' selected':'')+'>state</option><option value="channel_0"'+('channel_0'==c.attr?' selected':'')+'>ch0</option></select>'+
        '<select data-f="condition.equals" style="flex:1"><option value="">(=)</option><option value="true"'+('true'==String(c.equals)?' selected':'')+'>true</option><option value="false"'+('false'==String(c.equals)?' selected':'')+'>false</option></select></div></td>'+
      '<td><input data-f="onValue" value="'+esc(r.onValue)+'" placeholder="开" style="margin-bottom:2px">'+
        '<input data-f="offValue" value="'+esc(r.offValue)+'" placeholder="关"></td>'+
      '<td><input data-f="delay" value="'+esc(r.delay)+'" type="number" step="1" style="width:50px"></td>'+
      '<td><select class="sid-sel" data-f="doorGuard" onchange="syncSid(this)"></select></td>'+
      '<td><div style="display:flex;gap:2px;align-items:center">'+
        '<input data-f="tiStart" value="'+esc(ti.start||'')+'" placeholder="22:00" style="width:48px">'+
        '<span style="color:#888">~</span>'+
        '<input data-f="tiEnd" value="'+esc(ti.end||'')+'" placeholder="06:00" style="width:48px"></div></td>'+
      '<td><button class="btn-dan btn-sm" onclick="removeRule('+i+')">×</button></td>';
    tb.appendChild(tr);
  });
  refreshDevices(); // 填充所有下拉
}

function syncSid(el){/* 复制 SID 到剪贴板辅助 */}

function collectRules(){
  const rows=document.querySelectorAll('#rules-body tr');const out=[];
  rows.forEach(tr=>{
    const g=f=>tr.querySelector(`[data-f="${f}"]`);
    if(!g||!g('name')) return;
    const r={
      enabled: !tr.querySelector('.toggle')?.classList.contains('on')===false,
      name: g('name').value.trim(),
      match:{sid:g('match.sid').value.trim(),attr:g('match.attr').value,equals:norm(g('match.equals').value)},
      target:{sid:g('target.sid').value.trim(),attr:g('target.attr').value},
      onValue:norm(g('onValue').value),offValue:norm(g('offValue').value),
    };
    const d=g('delay').value; if(d!=='') r.delay=parseInt(d,10);
    const dg=g('doorGuard').value.trim(); if(dg!=='') r.doorGuard=dg;
    const cs=g('condition.sid').value.trim(),ca=g('condition.attr').value,ce=g('condition.equals').value;
    if(cs&&ca&&ce) r.condition={sid:cs,attr:ca,equals:norm(ce)};
    const ts=g('tiStart').value.trim(),te=g('tiEnd').value.trim();
    if(ts||te) r.timeInactive={start:ts,end:te};
    if(r.name&&r.match.sid&&r.target.sid) out.push(r);
  });
  return out;
}

function toggleRule(i){rules[i].enabled=!rules[i].enabled;renderRules()}
function addRule(){rules.push({name:'',match:{sid:'',attr:'state',equals:true},target:{sid:'',attr:'channel_0'},onValue:true,offValue:false,delay:30,enabled:true});renderRules()}
function removeRule(i){rules.splice(i,1);renderRules()}

async function loadRules(){
  try{
    const d=await api('/api/rules');
    rules=d.rules||[];
    document.getElementById('status').textContent='运行中 · '+(d.enable_triggers?'规则引擎已启用':'已停用')+' · '+rules.length+' 条规则';
    renderRules();
    // fill settings
    document.getElementById('s-enable-triggers').value=String(d.enable_triggers);
    document.getElementById('s-door-cooldown').value=d.doorOpenCooldownMs;
    document.getElementById('s-heartbeat').value=d.heartbeatTimeout;
    document.getElementById('s-rediscover').value=d.rediscoverInterval;
    document.getElementById('s-debug').value=String(d.debug);
    document.getElementById('s-web-port').value=d.web_port;
  }catch(e){toast('加载失败: '+e.message,false)}
}

async function saveRules(){
  const nr=collectRules();
  try{
    const d=await api('/api/rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rules:nr})});
    rules=d.rules;toast('已保存 ('+rules.length+' 条规则)');renderRules();
  }catch(e){toast('保存失败: '+e.message,false)}
}

// ============== 设备状态 ==============
async function loadStates(){
  try{
    const d=await api('/api/states');
    const grid=document.getElementById('states-grid');grid.innerHTML='';
    for(const s of d.states||[]){
      const card=document.createElement('div');card.className='state-card';
      const vals=Object.entries(s.vals||{}).filter(([k])=>!['voltage','percent'].includes(k));
      card.innerHTML=
        '<div class="model">'+esc(s.model)+'</div>'+
        '<div class="sid" onclick="navigator.clipboard.writeText(\''+esc(s.sid)+'\');toast(\'已复制: '+esc(s.sid)+'\')">'+esc(s.sid)+'</div>'+
        '<div class="vals">'+vals.map(([k,v])=>'<span>'+esc(k)+': '+esc(v)+'</span>').join('')+'</div>';
      grid.appendChild(card);
    }
  }catch(e){}
}

// ============== 日志 ==============
async function loadLogs(){
  try{
    const kw=document.getElementById('log-search').value.trim();
    const d=await api('/api/logs'+(kw?'?q='+encodeURIComponent(kw):''));
    const box=document.getElementById('log-box');
    box.innerHTML=d.logs.map(l=>{
      let cls='info';
      if(l.includes('WARNING')||l.includes('warn')) cls='warn';
      if(l.includes('ERROR')||l.includes('error')) cls='error';
      if(l.includes('DEBUG')||l.includes('debug')) cls='debug';
      return '<div class="'+cls+'">'+esc(l)+'</div>';
    }).join('');
    box.scrollTop=box.scrollHeight;
  }catch(e){}
}

function toggleLogAuto(){
  const el=document.getElementById('log-auto-refresh');
  if(logAutoTimer){clearInterval(logAutoTimer);logAutoTimer=null;el.classList.remove('on');}
  else{logAutoTimer=setInterval(loadLogs,3000);el.classList.add('on');}
}

// ============== 测试 ==============
async function testMqtt(){
  const topic=document.getElementById('test-topic').value.trim();
  const payload=document.getElementById('test-payload').value;
  if(!topic){toast('请输入主题',false);return}
  try{
    const d=await api('/api/test/mqtt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic,payload})});
    document.getElementById('test-mqtt-result').textContent='已发送 -> '+topic+' = '+payload;
    toast('MQTT 已发送');
  }catch(e){toast('MQTT 失败: '+e.message,false)}
}

async function testTrigger(){
  const sid=document.getElementById('test-trigger-sid').value.trim();
  const attr=document.getElementById('test-trigger-attr').value;
  const value=document.getElementById('test-trigger-value').value;
  if(!sid){toast('请输入 SID',false);return}
  try{
    const d=await api('/api/test/trigger',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sid,attr,value:norm(value)})});
    document.getElementById('test-trigger-result').textContent='已触发: '+sid+' '+attr+' = '+value;
    toast('已模拟触发');
  }catch(e){toast('触发失败: '+e.message,false)}
}

// ============== 配置导出导入 ==============
async function exportConfig(){
  try{
    const d=await api('/api/config/export');
    const blob=new Blob([JSON.stringify(d.config,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='mihome-gw-config.json';a.click();
    toast('已导出');
  }catch(e){toast('导出失败: '+e.message,false)}
}

async function importConfig(ev){
  const file=ev.target.files[0];if(!file)return;
  try{
    const text=await file.text();
    const d=await api('/api/config/import',{method:'POST',headers:{'Content-Type':'application/json'},body:text});
    toast('已导入 ('+d.rules.length+' 条规则)');
    loadRules();
  }catch(e){toast('导入失败: '+e.message,false)}
}

// ============== 设置 ==============
async function saveSettings(){
  const cfg={
    enable_triggers: document.getElementById('s-enable-triggers').value==='true',
    doorOpenCooldownMs: parseInt(document.getElementById('s-door-cooldown').value,10)||5000,
    heartbeatTimeout: parseInt(document.getElementById('s-heartbeat').value,10)||120,
    rediscoverInterval: parseInt(document.getElementById('s-rediscover').value,10)||60,
    debug: document.getElementById('s-debug').value==='true',
    web_port: parseInt(document.getElementById('s-web-port').value,10)||8080,
  };
  try{
    const d=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
    toast('已保存'+(d.hot_reload?' (已生效)':' (部分需重启)'));
  }catch(e){toast('保存失败: '+e.message,false)}
}

// ============== 初始化 ==============
refreshDevices();loadRules();
// 周期刷新状态
setInterval(()=>{if(document.getElementById('tab-devices').classList.contains('active'))loadStates()},5000);
loadLogs();
</script>
</body>
</html>
"""

# ====================== API 路由 ======================

class WebUI:
    def __init__(self, app, config_path: str, port: int = 8080, bind: str = "0.0.0.0"):
        self._main = app
        self._config_path = config_path
        self._port = port
        self._bind = bind
        self._runner = None

    async def _index(self, request):
        return web.Response(text=HTML, content_type="text/html", charset="utf-8")

    # ---- 规则 ----
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

    # ---- 设备实时状态 ----
    async def _get_states(self, request):
        states = []
        hub = self._main.hub
        if hub:
            for sid, sensor in hub.sensors.items():
                vals = {}
                for attr in ("state", "channel_0", "channel_1", "temperature",
                             "humidity", "pressure", "lux", "no_motion",
                             "load_power", "power_consumed", "illumination", "on",
                             "dimmer", "rgb", "curtain_level", "voltage", "percent",
                             "action", "connected"):
                    v = getattr(sensor, attr, None)
                    if v is not None:
                        vals[attr] = v
                states.append({
                    "sid": sid,
                    "model": getattr(sensor, "className", ""),
                    "ip": getattr(sensor, "ip", ""),
                    "vals": vals,
                })
        states.sort(key=lambda s: s["model"])
        return web.json_response({"states": states})

    # ---- 日志 ----
    async def _get_logs(self, request):
        q = request.query.get("q", "").strip()
        n = min(int(request.query.get("n", 100)), 200)
        logs = grep_logs(q, n) if q else get_logs(n)
        return web.json_response({"logs": logs})

    # ---- 测试 ----
    async def _post_test_mqtt(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)
        topic = body.get("topic", "")
        payload = body.get("payload", "")
        if not topic:
            return web.json_response({"error": "topic 必填"}, status=400)
        output = self._main.output
        if output and hasattr(output, "send"):
            try:
                output.send(topic, payload)
                logger.info(f"[webui-test] MQTT 测试: {topic} = {payload}")
                return web.json_response({"ok": True, "topic": topic, "payload": payload})
            except Exception as e:
                return web.json_response({"error": f"发送失败: {e}"}, status=500)
        return web.json_response({"error": "输出后端不可用"}, status=500)

    async def _post_test_trigger(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)
        sid = body.get("sid", "")
        attr = body.get("attr", "state")
        value = body.get("value")
        if not sid:
            return web.json_response({"error": "sid 必填"}, status=400)
        hub = self._main.hub
        if not hub:
            return web.json_response({"error": "hub 未就绪"}, status=500)
        sensor = hub.get_sensor(sid)
        if not sensor:
            return web.json_response({"error": f"传感器 {sid} 不存在"}, status=400)
        triggers = self._main.triggers
        if triggers:
            try:
                triggers.on_data(sid, {attr: value})
                logger.info(f"[webui-test] 模拟触发: {sid} {attr}={value}")
                return web.json_response({"ok": True, "sid": sid, "attr": attr, "value": value})
            except Exception as e:
                return web.json_response({"error": f"触发失败: {e}"}, status=500)
        return web.json_response({"error": "规则引擎未就绪"}, status=500)

    # ---- 配置导入导出 ----
    async def _get_export(self, request):
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
            # 脱敏 key
            for gw in data.get("gateways", []):
                if "key" in gw:
                    gw["key"] = gw["key"][:4] + "****" + gw["key"][-4:]
            return web.json_response({"config": data})
        except Exception as e:
            return web.json_response({"error": f"读配置失败: {e}"}, status=500)

    async def _post_import(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)
        if "rules" not in body or "gateways" not in body:
            return web.json_response({"error": "缺少 rules 或 gateways"}, status=400)
        try:
            with open(self._config_path, "w") as f:
                json.dump(body, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return web.json_response({"error": f"写文件失败: {e}"}, status=500)
        # 重新加载配置 (重启线程)
        logger.info("[webui] 配置已导入, 请重启进程生效")
        return web.json_response({"ok": True, "rules": body.get("rules", [])})

    # ---- 设备列表（供前端填充下拉）----
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

    # ---- 设置 ----
    async def _get_config(self, request):
        cfg = self._main.config
        return web.json_response({
            "enable_triggers": cfg.enable_triggers,
            "doorOpenCooldownMs": cfg.doorOpenCooldownMs,
            "heartbeatTimeout": cfg.heartbeatTimeout,
            "rediscoverInterval": cfg.rediscoverInterval,
            "debug": cfg.debug,
            "web_enabled": cfg.web_enabled,
            "web_port": cfg.web_port,
        })

    async def _post_config(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "无效 JSON"}, status=400)
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
        cfg = self._main.config
        if hot["enable_triggers"] is not None:
            cfg.enable_triggers = hot["enable_triggers"]
        if hot["doorOpenCooldownMs"] is not None:
            cfg.doorOpenCooldownMs = hot["doorOpenCooldownMs"]
            if self._main.triggers:
                self._main.triggers._door_open_cooldown_ms = hot["doorOpenCooldownMs"]
        if hot["debug"] is not None:
            cfg.debug = hot["debug"]
        for k in ("heartbeatTimeout", "rediscoverInterval", "web_port"):
            if k in body:
                setattr(cfg, k, body[k])
        logger.info("[webui] 配置已更新")
        return web.json_response({"ok": True, "hot_reload": True})

    # ---- 路由注册与生命周期 ----
    async def start(self):
        webapp = web.Application()
        routes = [
            ("/", ("GET", self._index)),
            ("/api/rules", ("GET", self._get_rules), ("POST", self._post_rules)),
            ("/api/devices", ("GET", self._get_devices)),
            ("/api/states", ("GET", self._get_states)),
            ("/api/logs", ("GET", self._get_logs)),
            ("/api/config", ("GET", self._get_config), ("POST", self._post_config)),
            ("/api/config/export", ("GET", self._get_export)),
            ("/api/config/import", ("POST", self._post_import)),
            ("/api/test/mqtt", ("POST", self._post_test_mqtt)),
            ("/api/test/trigger", ("POST", self._post_test_trigger)),
        ]
        for route in routes:
            path, methods = route[0], route[1:]
            for method, handler in methods:
                if method == "GET":
                    webapp.router.add_get(path, handler)
                elif method == "POST":
                    webapp.router.add_post(path, handler)
        self._runner = web.AppRunner(webapp)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._bind, self._port)
        await site.start()
        logger.info(f"[webui] http://{self._bind}:{self._port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None