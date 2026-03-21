"""Mindos Dashboard — local web UI for browsing the soul."""

from __future__ import annotations

import json
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from mindos.core import Mindos

_mindos: "Mindos | None" = None
_serve_port: int = 3456

_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Mindos Dashboard</title>
<style>
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --orange: #d29922; --red: #f85149; --purple: #a371f7;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, 'Segoe UI', sans-serif; padding: 24px; max-width: 1200px; margin: 0 auto; }
h1 { font-size: 1.6em; margin-bottom: 4px; }
h2 { font-size: 1.1em; color: var(--accent); margin: 20px 0 8px; cursor: pointer; }
h2:hover { opacity: .85; }
.subtitle { color: var(--dim); font-size: .85em; margin-bottom: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.stat { font-size: 2em; font-weight: 700; color: var(--accent); }
.stat-label { color: var(--dim); font-size: .8em; }
.tag { display: inline-block; background: #1f6feb33; color: var(--accent); padding: 2px 8px; border-radius: 4px; font-size: .8em; margin: 2px; }
.mem-list { max-height: 500px; overflow-y: auto; }
.mem-item { padding: 8px 0; border-bottom: 1px solid var(--border); font-size: .85em; }
.mem-type { display: inline-block; min-width: 72px; padding: 1px 6px; border-radius: 3px; font-size: .75em; text-transform: uppercase; }
.mem-type.fact { background: #1f6feb33; color: var(--accent); }
.mem-type.episode { background: #3fb95033; color: var(--green); }
.mem-type.preference { background: #d2992233; color: var(--orange); }
.mem-type.skill { background: #f8514933; color: var(--red); }
.mem-type.relation { background: #a371f733; color: var(--purple); }
.confidence { float: right; color: var(--dim); font-size: .75em; }
.source { color: var(--dim); font-size: .75em; margin-left: 8px; }
.triple { font-size: .85em; padding: 4px 0; }
.triple em { color: var(--accent); }
.actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
button { background: var(--accent); color: #fff; border: none; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: .85em; }
button:hover { opacity: .85; }
button.secondary { background: var(--border); color: var(--text); }
button.danger { background: var(--red); }
input[type=text] { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 6px 12px; border-radius: 6px; font-size: .85em; width: 240px; }
textarea { width: 100%; min-height: 80px; background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 8px; border-radius: 6px; font-size: .85em; resize: vertical; }
pre { margin-top: 12px; font-size: .8em; color: var(--dim); white-space: pre-wrap; }
.toast { position: fixed; top: 20px; right: 20px; background: var(--green); color: #fff; padding: 10px 20px; border-radius: 8px; font-size: .9em; opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 100; }
.toast.show { opacity: 1; }
.mood-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: .8em; }
.mood-badge.neutral { background: #30363d; }
.mood-badge.engaged { background: #1f6feb33; color: var(--accent); }
.mood-badge.creative { background: #a371f733; color: var(--purple); }
.collapsible { overflow: hidden; transition: max-height .3s; }
</style>
</head>
<body>

<h1>Mindos Dashboard</h1>
<p class="subtitle">Portable Digital Soul Protocol — <span id="soulName">loading...</span><br>
<span id="serveInfo" style="opacity:.75"></span></p>

<div class="grid">
  <div class="card"><div class="stat" id="memCount">-</div><div class="stat-label">Memories</div></div>
  <div class="card"><div class="stat" id="kgCount">-</div><div class="stat-label">KG Triples</div></div>
  <div class="card"><div class="stat" id="soulAge">-</div><div class="stat-label">Soul Age</div></div>
  <div class="card"><div id="moodBadge" class="mood-badge neutral">neutral</div><div class="stat-label" style="margin-top:4px">Mood</div></div>
  <div class="card"><div id="traits"></div><div class="stat-label" style="margin-top:4px">Traits</div></div>
</div>

<h2 onclick="toggle('actionsPanel')">Operations</h2>
<div class="card" id="actionsPanel">
  <div class="actions">
    <input type="text" id="hydrateInput" placeholder="Context for hydrate...">
    <button onclick="doHydrate()">hydrate</button>
    <button class="secondary" onclick="toggle('commitUI')">commit</button>
    <button class="secondary" onclick="toggle('recallUI')">recall</button>
    <input type="text" id="forgetInput" placeholder="Keyword to forget">
    <button class="danger" onclick="doForget()">forget</button>
    <button class="secondary" onclick="doReflect()">reflect</button>
  </div>
  <pre id="opResult" style="display:none"></pre>
  <div id="commitUI" style="display:none;margin-top:12px">
    <textarea id="commitArea" placeholder="Paste conversation text..."></textarea>
    <div style="margin-top:8px;display:flex;gap:8px;align-items:center">
      <input type="text" id="commitSource" placeholder="source (e.g. claude)" value="dashboard" style="width:140px">
      <button onclick="doCommit()">Submit</button>
    </div>
  </div>
  <div id="recallUI" style="display:none;margin-top:12px">
    <div class="actions" style="margin-top:0"><input type="text" id="recallQuery" placeholder="Recall query..." style="width:300px"><button onclick="doRecall()">Search</button></div>
    <div id="recallResults" style="margin-top:8px"></div>
  </div>
</div>

<h2 onclick="toggle('memPanel')">Memory Browser</h2>
<div class="card" id="memPanel">
  <div class="actions" style="margin-top:0;margin-bottom:12px">
    <input type="text" id="searchInput" placeholder="Search memories..." oninput="loadMemories()">
  </div>
  <div id="memList" class="mem-list"></div>
</div>

<h2 onclick="toggle('kgPanel')">Knowledge Graph</h2>
<div class="card" id="kgPanel">
  <div id="kgList"></div>
</div>

<div class="toast" id="toast"></div>

<script>
function toggle(id) { const el = document.getElementById(id); el.style.display = el.style.display === 'none' ? 'block' : 'none'; }

async function api(path, opts) { const r = await fetch(path, opts); return r.json(); }

function toast(msg, bg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.background = bg || 'var(--green)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

async function loadConfig() {
  try { const c = await api('/api/config'); document.getElementById('serveInfo').textContent = `http://127.0.0.1:${c.port} · v${c.version} · ${c.data_root}`; } catch {}
}

async function loadStatus() {
  const s = await api('/api/status');
  const ident = s.identity || {};
  const mem = s.memory || {};
  const emotion = s.emotion || {};
  document.getElementById('soulName').textContent = ident.name || '?';
  document.getElementById('memCount').textContent = mem.total_memories || 0;
  document.getElementById('kgCount').textContent = mem.knowledge_graph_triples || 0;
  document.getElementById('soulAge').textContent = s.soul_age || '?';
  const mb = document.getElementById('moodBadge');
  mb.textContent = `${emotion.mood || 'neutral'} (${Math.round((emotion.energy||0)*100)}%)`;
  mb.className = 'mood-badge ' + (emotion.mood || 'neutral');
  document.getElementById('traits').innerHTML = (ident.traits || []).map(t => `<span class="tag">${t}</span>`).join('') || '<span style="color:var(--dim)">(empty)</span>';
}

async function loadMemories() {
  const q = document.getElementById('searchInput').value;
  const url = q ? `/api/memories?q=${encodeURIComponent(q)}` : '/api/memories';
  const data = await api(url);
  const list = document.getElementById('memList');
  if (!data.memories || !data.memories.length) { list.innerHTML = '<div style="color:var(--dim);padding:16px">No memories</div>'; return; }
  list.innerHTML = data.memories.map(m => {
    const date = new Date(m.created_at * 1000).toLocaleString();
    return `<div class="mem-item"><span class="mem-type ${m.type}">${m.type}</span> ${m.content}<span class="confidence">${(m.confidence*100).toFixed(0)}%</span><br><span class="source">${m.source} · ${date}</span></div>`;
  }).join('');
}

async function loadKG() {
  const data = await api('/api/knowledge_graph');
  const el = document.getElementById('kgList');
  if (!data.triples || !data.triples.length) { el.innerHTML = '<div style="color:var(--dim)">No triples</div>'; return; }
  el.innerHTML = data.triples.slice(0,50).map(t => `<div class="triple"><em>${t.subject}</em> → ${t.predicate} → <em>${t.object}</em></div>`).join('');
}

async function doHydrate() {
  const ctx = document.getElementById('hydrateInput').value || '';
  const data = await api('/api/hydrate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({context:ctx, max_tokens:2000}) });
  const el = document.getElementById('opResult'); el.style.display='block'; el.textContent = data.context || '(empty)';
  toast('hydrate done');
}

async function doCommit() {
  const raw = document.getElementById('commitArea').value;
  const source = document.getElementById('commitSource').value || 'dashboard';
  const data = await api('/api/commit', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({conversation:raw, source}) });
  let msg = `Added ${data.facts_added||0} facts, ${data.triples_added||0} triples`;
  if (data.skipped_duplicate) msg += `, ${data.skipped_duplicate} dup`;
  if (data.skipped_sensitive) msg += `, ${data.skipped_sensitive} sensitive`;
  msg += ` (${data.method})`;
  toast(msg);
  document.getElementById('commitUI').style.display='none';
  loadStatus(); loadMemories(); loadKG();
}

async function doRecall() {
  const q = document.getElementById('recallQuery').value;
  if (!q) return;
  const data = await api('/api/recall', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q, top_k:10}) });
  const el = document.getElementById('recallResults');
  if (!data.results || !data.results.length) { el.innerHTML = '<div style="color:var(--dim)">No results</div>'; return; }
  el.innerHTML = data.results.map(r => `<div class="mem-item"><span class="mem-type ${r.type}">${r.type}</span> ${r.content} <span class="confidence">${(r.confidence*100).toFixed(0)}%</span></div>`).join('');
  toast(`Found ${data.results.length} memories`);
}

async function doForget() {
  const p = document.getElementById('forgetInput').value;
  if (!p) return;
  if (!confirm(`Permanently erase all memories containing "${p}"? This cannot be undone.`)) return;
  const data = await api('/api/forget', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pattern:p}) });
  toast(`Erased ${data.deleted} memories`, 'var(--red)');
  document.getElementById('forgetInput').value='';
  loadStatus(); loadMemories(); loadKG();
}

async function doReflect() {
  toast('Running reflection...', 'var(--orange)');
  const data = await api('/api/reflect', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({}) });
  const el = document.getElementById('opResult'); el.style.display='block';
  el.textContent = JSON.stringify(data, null, 2);
  toast('Reflection complete');
}

loadConfig(); loadStatus(); loadMemories(); loadKG();
setInterval(loadStatus, 5000);
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        assert _mindos is not None
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/config":
            from mindos import __version__
            self._json({"port": _serve_port, "version": __version__, "data_root": str(_mindos.root)})
            return

        if path == "/api/status":
            self._json(_mindos.status())
            return

        if path == "/api/memories":
            q = qs.get("q", [""])[0]
            mems = _mindos.store.search_text(q, limit=50) if q else _mindos.store.list_recent(limit=50)
            self._json({"memories": [
                {"id": m.id, "type": m.type, "content": m.content,
                 "source": m.source, "confidence": m.confidence, "created_at": m.created_at}
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
            ctx = _mindos.hydrate(context=body.get("context", ""), max_tokens=body.get("max_tokens", 2000))
            self._json({"context": ctx})
            return

        if path == "/api/commit":
            body = self._read_body()
            conv = body.get("conversation", "")
            if not conv and body.get("messages"):
                conv = "\n".join(f"{m.get('role','?')}: {m.get('content','')}" for m in body["messages"])
            result = _mindos.commit(conv, source=body.get("source", "dashboard"))
            self._json(result)
            return

        if path == "/api/recall":
            body = self._read_body()
            results = _mindos.recall(body.get("query", ""), top_k=body.get("top_k", 10))
            self._json({"results": results})
            return

        if path == "/api/forget":
            body = self._read_body()
            result = _mindos.forget(body.get("pattern", ""), scope=body.get("scope", "all"))
            self._json(result)
            return

        if path == "/api/reflect":
            result = _mindos.reflect()
            self._json(result or {"message": "No episodes to reflect on"})
            return

        self.send_error(404)


def _pick_port(preferred: int = 3456, max_attempts: int = 32) -> int:
    for p in range(preferred, preferred + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise OSError(f"Cannot bind port {preferred}-{preferred + max_attempts - 1}")


def run_dashboard(mindos_instance: "Mindos", port: int = 3456) -> None:
    global _mindos, _serve_port
    _mindos = mindos_instance
    actual = _pick_port(port)
    _serve_port = actual
    if actual != port:
        print(f"Port {port} busy, using {actual}")
    server = HTTPServer(("127.0.0.1", actual), DashboardHandler)
    print(f"Mindos Dashboard: http://localhost:{actual}")
    print(f"Data: {mindos_instance.root}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped")
        server.server_close()
