"""Web 入口:零依赖 http.server,单页 + JSON API。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import agent, db, llm

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>纪要 · 会议转写整理</title>
<style>
  :root{--bg:#f6f8f7;--card:#fff;--ink:#243029;--muted:#6b7a71;--accent:#2f6b4f;--soft:#e3f0e9;
        --line:#e2eae5;--red:#b42318;--green:#067647;--amber:#b54708;--radius:16px}
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
  .wrap{max-width:1000px;margin:0 auto;padding:32px 20px 80px}
  h1{font-size:26px;margin:0 0 4px} header p{color:var(--muted);margin:0 0 22px}
  .badge{display:inline-block;font-size:12px;padding:3px 10px;border-radius:999px;background:var(--soft);color:var(--accent);margin-left:8px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;margin-bottom:18px;box-shadow:0 1px 2px rgba(36,48,41,.04)}
  label{display:block;font-size:13px;color:var(--muted);margin:0 0 6px}
  textarea,input{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font-size:14px;font-family:inherit;background:#fff}
  textarea{line-height:1.7}
  .row{display:flex;gap:12px;flex-wrap:wrap}.row>div{flex:1;min-width:160px}
  button{background:var(--accent);color:#fff;border:none;padding:12px 22px;border-radius:12px;font-size:15px;cursor:pointer}
  .hint{color:var(--muted);font-size:12px;margin-top:8px}
  .spin{display:inline-block;width:16px;height:16px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:sp .7s linear infinite}
  @keyframes sp{to{transform:rotate(360deg)}}
  .result{display:none}.result.show{display:block}
  h3{font-size:15px;color:var(--muted);margin:20px 0 8px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:600}
  .ok{color:var(--green)}.warn{color:var(--amber)}
  .box{background:#fafcfb;border-radius:10px;padding:12px 14px;margin:8px 0;font-size:14px;line-height:1.8;white-space:pre-wrap}
  .item{border-left:3px solid var(--accent);padding:4px 0 4px 12px;margin:8px 0;font-size:14px}
  ul{margin:6px 0 0 18px;padding:0}li{margin:6px 0;font-size:14px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>纪要 · 会议转写整理<span class="badge" id="badge">…</span></h1>
    <p>把转写原样粘进来:决议、待办、没人拍板的问题,外加一封能直接发的跟进邮件。</p>
  </header>
  <div class="card">
    <label>会议转写</label>
    <textarea id="text" rows="10" placeholder="会议: 产品周会 2026-11-24 参会: 张三,李四,王五&#10;张三: 登录改版这版就定了,按新稿上线。&#10;李四: 接口文档我明天发出来。"></textarea>
    <div style="margin-top:16px"><button id="btn">生成纪要</button></div>
    <div class="hint">日期、人名、数字由本地抽取;模型只负责措辞,邮件里的日期与金额会校验。</div>
  </div>
  <div class="result" id="res"></div>
</div>
<script>
const $=s=>document.querySelector(s);
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function load(btn,on){btn.disabled=on;if(on){btn.dataset.label=btn.dataset.label||btn.textContent.trim();btn.innerHTML='<span class="spin"></span>';}else{btn.innerHTML=btn.dataset.label||btn.textContent;}}
$('#btn').onclick=async()=>{
  const el=$('#res');el.classList.remove('show');load($('#btn'),true);
  try{
    const p=await fetch('/api/minutes',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:$('#text').value})});
    const r=await p.json(); if(r.error) throw new Error(r.error);
    let h='<div class="card"><div class="hint">'+(r.mode==='model'?'模型已连接':'离线模式')+(r.saved_id?' · 已入库 #'+r.saved_id:'')+'</div>';
    h+='<p><b>'+esc(r.topic)+'</b> · '+esc(r.date)+' · 模板 '+esc(r.template)+'</p>';
    if(r.summary){h+='<h3>摘要</h3><div class="box">'+esc(r.summary)+'</div>';}
    h+='<h3>决议</h3>';
    if(r.decisions.length){r.decisions.forEach(d=>{h+='<div class="item">'+esc(d.text)+'<div class="hint">发言:'+esc(d.speaker||'—')+'</div></div>';});}
    else{h+='<div class="hint">本次没有明确决议。</div>';}
    h+='<h3>待办</h3><table><tr><th>动作</th><th>负责人</th><th>截止</th><th>完整性</th></tr>';
    r.todos.forEach(t=>{h+='<tr><td>'+esc(t.action)+'</td><td>'+esc(t.owner)+'</td><td>'+esc(t.due||'待定')+'</td><td class="'+(t.complete?'ok':'warn')+'">'+(t.complete?'✅':'⚠️ 缺 '+esc(t.missing.join('、')))+'</td></tr>';});
    h+='</table>';
    h+='<h3>悬置问题</h3>';
    if(r.suspended.length){h+='<ul>';r.suspended.forEach(s=>h+='<li>'+esc(s.question)+' <span class="hint">('+esc(s.speaker||'—')+')</span></li>');h+='</ul>';}
    else{h+='<div class="hint">无</div>';}
    if(r.vague.length){h+='<h3>含糊词</h3><ul>';r.vague.forEach(v=>h+='<li>「'+esc(v.word)+'」× '+v.count+'</li>');h+='</ul>';}
    h+='<h3>下次议程</h3><ul>';r.agenda.forEach(a=>h+='<li>['+esc(a.type)+'] '+esc(a.text)+'</li>');h+='</ul>';
    if(r.risks.length){h+='<h3>风险</h3><ul>';r.risks.forEach(x=>h+='<li class="warn">'+esc(x)+'</li>');h+='</ul>';}
    h+='<h3>跟进邮件</h3><div class="box">'+esc(r.email)+'</div>';
    h+='<div class="hint">来源:'+(r.email_source==='model'?'模型草稿(已通过日期与数字校验)':'本地模板')+'</div></div>';
    el.innerHTML=h;
  }catch(e){el.innerHTML='<div class="card" style="color:#b42318">请求失败:'+esc(e.message)+'</div>';}
  el.classList.add('show');load($('#btn'),false);
};
fetch('/api/status').then(r=>r.json()).then(s=>{const b=$('#badge');
  if(s.mock){b.textContent='离线模式';b.style.background='#fee2e2';b.style.color='#b42318';}
  else{b.textContent=s.model||'模型已连接';b.style.background='#dcfce7';b.style.color='#067647';}
}).catch(()=>{});
</script>
</body></html>
"""


def _handler(cfg, force_mock, db_path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, ctype, status=200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _read(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            return json.loads(text) if text else {}

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/status":
                mock = force_mock or not cfg.get("api_key")
                self._json({"mock": mock, "model": None if mock else cfg.get("model")})
            elif path == "/api/history":
                db.use(db_path)
                self._json(db.meetings(10))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/minutes":
                self._json({"error": "not found"}, 404)
                return
            try:
                body = self._read()
                db.use(db_path)
                r = agent.analyze(body.get("text", ""), topic=body.get("topic"),
                                  meeting_date=body.get("date"), force_mock=force_mock)
                if body.get("save", True):
                    r["saved_id"] = db.save(r)
                self._json(r)
            except llm.LLMError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 500)

        def log_message(self, *args):
            pass

    return Handler


def serve(host="127.0.0.1", port=8000, db_path=None, force_mock=False):
    cfg = llm.default_config()
    httpd = ThreadingHTTPServer((host, port), _handler(cfg, force_mock, db_path))
    mode = "离线模式(未配置 key)" if (force_mock or not cfg.get("api_key")) else "模型:%s" % cfg.get("model")
    print("📝 纪要已启动:http://%s:%s  [%s]" % (host, port, mode))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
