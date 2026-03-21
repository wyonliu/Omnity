"""Mindos Dashboard — local web UI for browsing the soul."""

from __future__ import annotations

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from mindos.core import Mindos

_mindos: "Mindos | None" = None

_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Mindos Dashboard — 灵魂面板</title>
<style>
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --orange: #d29922; --red: #f85149;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, 'Segoe UI', sans-serif; padding: 24px; }
h1 { font-size: 1.6em; margin-bottom: 4px; }
h2 { font-size: 1.1em; color: var(--accent); margin: 16px 0 8px; }
.subtitle { color: var(--dim); font-size: .85em; margin-bottom: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.stat { font-size: 2em; font-weight: 700; color: var(--accent); }
.stat-label { color: var(--dim); font-size: .8em; }
.tag { display: inline-block; background: #1f6feb33; color: var(--accent); padding: 2px 8px; border-radius: 4px; font-size: .8em; margin: 2px; }
.mem-list { max-height: 420px; overflow-y: auto; }
.mem-item { padding: 8px 0; border-bottom: 1px solid var(--border); font-size: .85em; }
.mem-type { display: inline-block; min-width: 72px; padding: 1px 6px; border-radius: 3px; font-size: .75em; text-transform: uppercase; }
.mem-type.fact { background: #1f6feb33; color: var(--accent); }
.mem-type.episode { background: #3fb95033; color: var(--green); }
.mem-type.preference { background: #d2992233; color: var(--orange); }
.mem-type.skill { background: #f8514933; color: var(--red); }
.mem-type.relation { background: #a371f733; color: #a371f7; }
.confidence { float: right; color: var(--dim); font-size: .75em; }
.source { color: var(--dim); font-size: .75em; margin-left: 8px; }
.triple { font-size: .85em; padding: 4px 0; }
.triple em { color: var(--accent); }
.actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
button { background: var(--accent); color: #fff; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: .85em; }
button:hover { opacity: .85; }
button.secondary { background: var(--border); color: var(--text); }
input[type=text] { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 6px 12px; border-radius: 6px; font-size: .85em; width: 240px; }
#commitArea { width: 100%; min-height: 80px; background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 8px; border-radius: 6px; font-size: .85em; resize: vertical; }
.toast { position: fixed; top: 20px; right: 20px; background: var(--green); color: #fff; padding: 10px 20px; border-radius: 8px; font-size: .9em; opacity: 0; transition: opacity .3s; pointer-events: none; }
.toast.show { opacity: 1; }
</style>
</head>
<body>

<h1>🧠 Mindos Dashboard</h1>
<p class="subtitle">Portable Digital Soul Protocol — <span id="soulName">loading...</span></p>

<div class="grid">
  <div class="card">
    <div class="stat" id="memCount">-</div>
    <div class="stat-label">记忆总量</div>
  </div>
  <div class="card">
    <div class="stat" id="kgCount">-</div>
    <div class="stat-label">知识图谱三元组</div>
  </div>
  <div class="card">
    <div class="stat" id="soulAge">-</div>
    <div class="stat-label">灵魂年龄</div>
  </div>
  <div class="card">
    <div id="traits"></div>
    <div class="stat-label" style="margin-top:4px">人格特征</div>
  </div>
</div>

<h2>快速操作</h2>
<div class="card">
  <div class="actions">
    <input type="text" id="hydrateInput" placeholder="输入场景，如：讨论旅行计划">
    <button onclick="doHydrate()">💧 hydrate</button>
    <button class="secondary" onclick="doCommitUI()">📝 commit 对话</button>
    <input type="text" id="forgetInput" placeholder="要遗忘的关键词">
    <button style="background:var(--red)" onclick="doForget()">🗑 forget</button>
  </div>
  <pre id="hydrateResult" style="margin-top:12px;font-size:.8em;color:var(--dim);white-space:pre-wrap;display:none"></pre>
  <div id="commitUI" style="display:none;margin-top:12px">
    <textarea id="commitArea" placeholder="粘贴对话内容（JSON 格式 [{role, content}, ...]）"></textarea>
    <div style="margin-top:8px"><button onclick="doCommit()">提交 commit</button></div>
  </div>
</div>

<h2>记忆浏览器</h2>
<div class="card">
  <div class="actions" style="margin-top:0;margin-bottom:12px">
    <input type="text" id="searchInput" placeholder="搜索记忆..." oninput="loadMemories()">
  </div>
  <div id="memList" class="mem-list"></div>
</div>

<h2>知识图谱</h2>
<div class="card" id="kgCard">
  <div id="kgList"></div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
async function api(path, opts) {
  const r = await fetch(API + path, opts);
  return r.json();
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

async function loadStatus() {
  const s = await api('/api/status');
  document.getElementById('soulName').textContent = s.name;
  document.getElementById('memCount').textContent = s.total_memories;
  document.getElementById('kgCount').textContent = s.knowledge_graph_triples;
  document.getElementById('soulAge').textContent = s.soul_age;
  const traits = document.getElementById('traits');
  traits.innerHTML = (s.personality || []).map(t => `<span class="tag">${t}</span>`).join('') || '<span style="color:var(--dim)">(未设定)</span>';
}

async function loadMemories() {
  const q = document.getElementById('searchInput').value;
  const url = q ? `/api/memories?q=${encodeURIComponent(q)}` : '/api/memories';
  const data = await api(url);
  const list = document.getElementById('memList');
  if (!data.memories || !data.memories.length) {
    list.innerHTML = '<div style="color:var(--dim);padding:16px">暂无记忆</div>';
    return;
  }
  list.innerHTML = data.memories.map(m => {
    const date = new Date(m.created_at * 1000).toLocaleString('zh-CN');
    return `<div class="mem-item">
      <span class="mem-type ${m.type}">${m.type}</span>
      ${m.content}
      <span class="confidence">置信度 ${(m.confidence*100).toFixed(0)}%</span>
      <br><span class="source">${m.source} · ${date}</span>
    </div>`;
  }).join('');
}

async function loadKG() {
  const data = await api('/api/knowledge_graph');
  const el = document.getElementById('kgList');
  if (!data.triples || !data.triples.length) {
    el.innerHTML = '<div style="color:var(--dim)">暂无知识图谱数据</div>';
    return;
  }
  el.innerHTML = data.triples.slice(0, 50).map(t =>
    `<div class="triple"><em>${t.subject}</em> → ${t.predicate} → <em>${t.object}</em></div>`
  ).join('');
}

async function doHydrate() {
  const situation = document.getElementById('hydrateInput').value || '一般对话';
  const data = await api('/api/hydrate', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({situation, max_tokens: 2000})
  });
  const el = document.getElementById('hydrateResult');
  el.style.display = 'block';
  el.textContent = data.context || '(空)';
  toast('hydrate 完成');
}

function doCommitUI() {
  const el = document.getElementById('commitUI');
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

async function doCommit() {
  const raw = document.getElementById('commitArea').value;
  let messages;
  try {
    messages = JSON.parse(raw);
  } catch {
    messages = [{role: 'user', content: raw}];
  }
  const data = await api('/api/commit', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({messages, source: 'dashboard'})
  });
  toast(`commit 完成：新增 ${data.memories_added} 条记忆`);
  document.getElementById('commitUI').style.display = 'none';
  loadStatus(); loadMemories();
}

async function doForget() {
  const pattern = document.getElementById('forgetInput').value;
  if (!pattern) return;
  if (!confirm(`确定要永久擦除所有包含「${pattern}」的记忆？此操作不可撤销。`)) return;
  const data = await api('/api/forget', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({pattern})
  });
  toast(`已擦除 ${data.deleted} 条记忆`);
  document.getElementById('forgetInput').value = '';
  loadStatus(); loadMemories(); loadKG();
}

loadStatus(); loadMemories(); loadKG();
setInterval(loadStatus, 5000);
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass  # quiet

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        assert _mindos is not None
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/status":
            self._json(_mindos.status())
            return

        if path == "/api/memories":
            q = qs.get("q", [""])[0]
            if q:
                mems = _mindos.store.search_text(q, limit=50)
            else:
                mems = _mindos.store.list_recent(limit=50)
            self._json({"memories": [
                {"id": m.id, "type": m.type, "content": m.content,
                 "source": m.source, "confidence": m.confidence,
                 "created_at": m.created_at}
                for m in mems
            ]})
            return

        if path == "/api/knowledge_graph":
            triples = _mindos.store.triples()
            self._json({"triples": [
                {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                for t in triples
            ]})
            return

        self.send_error(404)

    def do_POST(self):
        assert _mindos is not None
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/hydrate":
            body = self._read_body()
            ctx = _mindos.hydrate(
                situation=body.get("situation", ""),
                max_tokens=body.get("max_tokens", 2000),
            )
            self._json({"context": ctx})
            return

        if path == "/api/commit":
            body = self._read_body()
            result = _mindos.commit(
                messages=body.get("messages", []),
                source=body.get("source", "api"),
            )
            self._json(result)
            return

        if path == "/api/forget":
            body = self._read_body()
            count = _mindos.forget(body.get("pattern", ""), scope=body.get("scope", "all"))
            self._json({"deleted": count})
            return

        self.send_error(404)


def run_dashboard(mindos_instance: "Mindos", port: int = 3456) -> None:
    global _mindos
    _mindos = mindos_instance
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"🧠 Mindos Dashboard 运行在 http://localhost:{port}")
    print(f"   数据目录：{mindos_instance.root}")
    print(f"   按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Dashboard 已停止")
        server.server_close()
