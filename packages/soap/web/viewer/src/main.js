/**
 * SOAP-View — 空间 Agent 可视化 + 自主智能体演示
 */
import { computeMapPayload, REALITY_COLORS } from "./soap-layout.js";
import { mountPixelMall } from "./pixel-mall.js";

let scene = null, rolesPayload = [], roleVisibleIds = null, selectedId = null, pixelApi = null;
const agentState = {};
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ── 地图 ───────────────────────────────────────────────────────

function ensureMount() {
  if (pixelApi) return;
  const el = $("game-container");
  if (!el || el.clientWidth < 20) return;
  el.innerHTML = "";
  pixelApi = mountPixelMall("game-container", { onSelect: selectObject });
}

function renderMap() {
  if (!scene?.objects) return;
  ensureMount();
  pixelApi?.refresh({ ...computeMapPayload(scene), roleVisibleIds, selectedId, agents: agentState });
}

function playAction(verb, agentId, targetId) {
  return new Promise(resolve => {
    if (!pixelApi) { resolve(); return; }
    pixelApi.action(verb, agentId, targetId, resolve);
  });
}

// ── 实体条带 ───────────────────────────────────────────────────

function renderEntityBar() {
  const el = $("entityBar");
  if (!el || !scene?.objects) return;
  el.innerHTML = "";
  for (const o of scene.objects) {
    const col = REALITY_COLORS[o.reality] || REALITY_COLORS.default;
    const d = document.createElement("div");
    d.className = "chip" + (o.id === selectedId ? " sel" : "");
    d.dataset.oid = o.id;
    d.innerHTML = `<span class="dot" style="background:${col}"></span>${esc(o.id)}`;
    d.onclick = () => selectObject(o.id);
    el.appendChild(d);
  }
}

function selectObject(id) {
  selectedId = id;
  const o = scene?.objects?.find((x) => x.id === id);
  $("detailEmpty").style.display = "none";
  const pre = $("detailJson");
  pre.style.display = "block";
  pre.textContent = o ? JSON.stringify(o, null, 2) : id;
  $("detailId").textContent = id;
  document.querySelectorAll(".chip").forEach(c => c.classList.toggle("sel", c.dataset.oid === id));
  renderMap();
}

// ── 角色视角 ───────────────────────────────────────────────────

function fillRoleSelect() {
  const sel = $("roleSelect");
  while (sel.options.length > 1) sel.remove(1);
  for (const r of rolesPayload) {
    const opt = document.createElement("option");
    opt.value = r.key; opt.textContent = r.name;
    sel.appendChild(opt);
  }
}

// ── 控制台 ─────────────────────────────────────────────────────

function fillTargets(extraAgents) {
  const sel = $("ctrlTarget");
  sel.innerHTML = "";
  if (extraAgents?.length) {
    for (const a of extraAgents) {
      const opt = document.createElement("option"); opt.value = a.id;
      opt.textContent = `🤖 ${a.id} (HP=${a.hp ?? "?"})`;
      sel.appendChild(opt);
    }
  }
  for (const r of scene?.regions || []) {
    const opt = document.createElement("option"); opt.value = r.id;
    opt.textContent = `📍 ${r.name || r.id}`; sel.appendChild(opt);
  }
  for (const o of scene?.objects || []) {
    const opt = document.createElement("option"); opt.value = o.id;
    opt.textContent = o.id; sel.appendChild(opt);
  }
}

function fillNavTargets() {
  const sel = $("ctrlNavUri");
  sel.innerHTML = "";
  for (const o of scene?.objects || []) {
    if (!o.uri) continue;
    const opt = document.createElement("option"); opt.value = o.uri;
    opt.textContent = `${o.id} → ${o.uri}`; sel.appendChild(opt);
  }
  for (const r of scene?.regions || []) {
    if (!r.uri) continue;
    const opt = document.createElement("option"); opt.value = r.uri;
    opt.textContent = `📍 ${r.name || r.id} → ${r.uri}`; sel.appendChild(opt);
  }
}

function syncParams() {
  const v = $("ctrlVerb").value;
  $("paramObserve").style.display = v === "OBSERVE" ? "" : "none";
  $("paramNavigate").style.display = v === "NAVIGATE" ? "" : "none";
  $("paramManipulate").style.display = v === "MANIPULATE" ? "" : "none";
}

function clearActionUI() {
  $("actionStatus").textContent = ""; $("actionStatus").className = "status";
  const r = $("actionResult"); r.textContent = ""; r.style.display = "none";
}

// ── 执行单个动作（带平滑动画） ─────────────────────────────────

async function executeAction(agentId, verb, targetId, params = {}) {
  const res = await fetch("/api/act", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, verb, target_id: targetId, params }),
  });
  const data = await res.json();
  renderMap();
  await playAction(verb, agentId, targetId);
  if (data.ok) {
    agentState[agentId] = { ...agentState[agentId], nearTarget: targetId };
    renderMap();
  }
  await pollEvents();
  return data;
}

// ── 手动发送动作 ───────────────────────────────────────────────

async function sendAction() {
  clearActionUI();
  pixelApi?.clearTrail();
  const agentId = $("ctrlAgent").value || "anon";
  const verb = $("ctrlVerb").value;
  const targetId = $("ctrlTarget").value;
  const params = {};
  if (verb === "NAVIGATE") params.target_uri = $("ctrlNavUri").value;
  if (verb === "MANIPULATE") {
    params.action = $("ctrlAction").value;
    const msg = $("ctrlMsg").value.trim();
    if (msg) {
      const n = Number(msg);
      if (!isNaN(n) && params.action === "attack_target") params.damage = n;
      else params.message = msg;
    }
  }
  $("actionStatus").textContent = "⏳ 发送中…"; $("actionStatus").className = "status sending";
  if (!agentState[agentId]) agentState[agentId] = { nearTarget: "atrium" };
  try {
    const data = await executeAction(agentId, verb, targetId, params);
    $("actionStatus").textContent = data.ok ? "✓ 成功" : "✗ 失败";
    $("actionStatus").className = data.ok ? "status ok" : "status fail";
    const r = $("actionResult"); r.style.display = "block"; r.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("actionStatus").textContent = "✗ " + e.message; $("actionStatus").className = "status fail";
  }
}

// ── 自主智能体 ─────────────────────────────────────────────────

const DEMO_PLAN = [
  { thought: "初来乍到，先观察中庭的环境", verb: "OBSERVE", target: "atrium",
    think: 1200, pause: 1800 },
  { thought: "看看喷泉附近有什么有趣的东西", verb: "OBSERVE", target: "fountain_center",
    think: 1000, pause: 1500 },
  { thought: "去102号店铺逛逛吧", verb: "NAVIGATE", target: "store_102",
    params: { target_uri: "soap://mall_01/store_102" }, think: 1200, pause: 1500 },
  { thought: "看看货架上有什么好东西", verb: "OBSERVE", target: "store_102_shelf_a",
    think: 800, pause: 1500 },
  { thought: "跟 AI 店员聊聊，问问推荐", verb: "MANIPULATE", target: "store_102_ai_clerk",
    params: { action: "speak", message: "你好！有什么推荐的商品吗？" }, think: 1200, pause: 2500 },
  { thought: "去二楼咖啡店休息一下", verb: "NAVIGATE", target: "cafe_201",
    params: { target_uri: "soap://mall_01/cafe_201" }, think: 1000, pause: 1500 },
  { thought: "来杯拿铁", verb: "MANIPULATE", target: "cafe_201_counter",
    params: { action: "speak", message: "来杯拿铁，谢谢" }, think: 800, pause: 2500 },
  { thought: "好奇后场通道是什么样子", verb: "NAVIGATE", target: "service_lane",
    params: { target_uri: "soap://mall_01/service_lane" }, think: 1000, pause: 1500 },
  { thought: "这里有配送机器人，看看在忙什么", verb: "OBSERVE", target: "robot_unit_d",
    think: 800, pause: 2000 },
  { thought: "回中庭看看传送门！", verb: "NAVIGATE", target: "atrium",
    params: { target_uri: "soap://mall_01/atrium" }, think: 1000, pause: 1500 },
  { thought: "传送门后面有怪物？试试挑战！", verb: "MANIPULATE", target: "game_monster_01",
    params: { action: "attack_target", damage: 50 }, think: 1200, pause: 2500 },
  { thought: "再攻击一次，把它打倒！", verb: "MANIPULATE", target: "game_monster_01",
    params: { action: "attack_target", damage: 80 }, think: 800, pause: 2000 },
];

let demoRunning = false;
let demoAbort = false;
let demoInterrupted = false;
let demoResolveWait = null;

function handleAgentInterrupted(targetAgentId, attackerId, data) {
  if (targetAgentId === "explorer" && demoRunning) {
    demoInterrupted = true;
    const hp = data.hp_remaining ?? "?";
    const action = data.action || "attack";
    logThought("explorer", `被 ${attackerId} 打断了！(${action}, HP=${hp}) 需要重新规划…`);
    agentState["explorer"] = {
      ...agentState["explorer"],
      thought: `被 ${attackerId} 打断了！HP=${hp}`,
      hp,
    };
    renderMap();
    if (demoResolveWait) demoResolveWait();
  }
}

function logThought(agentId, text) {
  const log = $("eventLog");
  if (log.querySelector(".log-empty")) log.innerHTML = "";
  const t = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  log.insertAdjacentHTML("beforeend",
    `<div class="ev thought"><span class="ts">${t}</span> <b style="color:#00e676">${esc(agentId)}</b> <span style="color:#aaa">💭 ${esc(text)}</span></div>`);
  log.scrollTop = log.scrollHeight;
}

function interruptibleSleep(ms) {
  return new Promise(resolve => {
    demoResolveWait = resolve;
    const timer = setTimeout(() => { demoResolveWait = null; resolve(); }, ms);
    const orig = demoResolveWait;
    demoResolveWait = () => { clearTimeout(timer); demoResolveWait = null; resolve(); };
  });
}

async function runDemoAgent() {
  if (demoRunning) { demoAbort = true; return; }
  demoRunning = true; demoAbort = false; demoInterrupted = false;
  const btn = $("qDemo");
  btn.textContent = "⏹ 停止"; btn.style.borderColor = "var(--accent)";

  const agentId = "explorer";
  agentState[agentId] = { nearTarget: "atrium", thought: null, hp: 100 };
  renderMap();
  await sleep(500);

  for (const step of DEMO_PLAN) {
    if (demoAbort) break;

    if (demoInterrupted) {
      demoInterrupted = false;
      agentState[agentId].thought = "呃……让我缓一下……";
      renderMap();
      logThought(agentId, "被打断后需要恢复，稍等片刻…");
      await interruptibleSleep(3000);
      if (demoAbort) break;
      const hp = agentState[agentId].hp ?? 100;
      if (hp <= 0) {
        agentState[agentId].thought = "我被击败了……";
        renderMap();
        logThought(agentId, "HP归零，巡游终止。");
        await sleep(2000);
        break;
      }
      agentState[agentId].thought = "好吧，继续探索！";
      renderMap();
      logThought(agentId, "恢复完毕，继续巡游。");
      await sleep(1500);
    }

    agentState[agentId].thought = step.thought;
    renderMap();
    logThought(agentId, step.thought);
    await interruptibleSleep(step.think || 1000);
    if (demoAbort) break;
    if (demoInterrupted) continue;
    await executeAction(agentId, step.verb, step.target, step.params || {});
    agentState[agentId].thought = null;
    renderMap();
    await interruptibleSleep(step.pause || 1500);
  }

  if (!demoAbort) {
    agentState[agentId].thought = "巡游结束，今天很开心！";
    renderMap();
    await sleep(3000);
  }
  agentState[agentId].thought = null;
  renderMap();
  demoRunning = false;
  btn.textContent = "🤖 巡游"; btn.style.borderColor = "";
}

// ── 加载 ───────────────────────────────────────────────────────

async function loadAll() {
  selectedId = null;
  const [scRes, roRes] = await Promise.all([fetch("/api/scene"), fetch("/api/roles")]);
  const sc = await scRes.json(), ro = await roRes.json();
  if (sc.error) throw new Error(sc.detail || sc.error);
  scene = sc.scene; rolesPayload = ro.roles || [];
  $("sceneTitle").textContent = scene.title || "";
  $("sceneMeta").textContent = `${scene.space_id || ""}`;
  fillRoleSelect(); fillTargets(); fillNavTargets();
  renderEntityBar(); roleVisibleIds = null; renderMap();
}

// ── 事件轮询 ───────────────────────────────────────────────────

let lastSeq = 0;
const VC = { OBSERVE: "#42a5f5", NAVIGATE: "#ffa726", MANIPULATE: "#ec407a" };
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

function evHTML(ev) {
  const t = new Date(ev.ts * 1000).toLocaleTimeString("zh-CN", { hour12: false });
  const ok = ev.result?.ok, col = VC[ev.verb] || "#999";
  let extra = "";
  const d = ev.result?.data;
  if (d?.reply) extra = `<div class="extra">💬 ${esc(d.reply)}</div>`;
  if (d?.hp_remaining != null) extra = `<div class="extra">HP=${d.hp_remaining}${d.defeated ? " 💀 击败!" : ""}</div>`;
  if (d?.digital_twin_url) extra = `<div class="extra">🔗 ${esc(d.digital_twin_url)}</div>`;
  return `<div class="ev ${ev.verb}">
    <span class="ts">${t}</span> <b style="color:${col}">${ev.verb}</b>
    <b>${esc(ev.target_id)}</b> <span style="opacity:.5">← ${esc(ev.agent_id)}</span>
    <span style="color:${ok ? "var(--success)" : "var(--fail)"}">${ok ? "✓" : "✗"}</span>${extra}
  </div>`;
}

async function pollEvents() {
  try {
    const [evRes, agRes] = await Promise.all([
      fetch(`/api/events?after=${lastSeq}`),
      fetch("/api/agents"),
    ]);
    const data = await evRes.json();
    const agData = await agRes.json();
    const serverAgents = agData.agents || [];

    const prevSel = $("ctrlTarget").value;
    fillTargets(serverAgents);
    if (prevSel) $("ctrlTarget").value = prevSel;

    for (const sa of serverAgents) {
      if (!agentState[sa.id]) agentState[sa.id] = {};
      agentState[sa.id].hp = sa.hp;
      agentState[sa.id].serverStatus = sa.status;
      if (sa.near_target) agentState[sa.id].nearTarget = sa.near_target;
    }

    const events = data.events || [];
    if (events.length > 0) {
      const log = $("eventLog");
      if (lastSeq === 0 && log.querySelector(".log-empty")) log.innerHTML = "";
      for (const ev of events) {
        log.insertAdjacentHTML("beforeend", evHTML(ev));
        if (ev.result?.ok && ev.agent_id) {
          if (!agentState[ev.agent_id]) agentState[ev.agent_id] = {};
          agentState[ev.agent_id].nearTarget = ev.target_id;
        }
        if (ev.result?.data?.interrupted && ev.result?.data?.is_agent) {
          handleAgentInterrupted(ev.target_id, ev.agent_id, ev.result.data);
        }
      }
      log.scrollTop = log.scrollHeight;
      lastSeq = data.latest_seq;
      $("eventCount").textContent = String(lastSeq);
      const scRes = await fetch("/api/scene");
      const sc = await scRes.json();
      if (!sc.error) {
        scene = sc.scene; renderMap(); renderEntityBar();
        if (selectedId) {
          const o = scene.objects?.find(x => x.id === selectedId);
          if (o) $("detailJson").textContent = JSON.stringify(o, null, 2);
        }
      }
    }
  } catch { /* ignore */ }
}

// ── 快捷按钮 ──────────────────────────────────────────────────

$("qObserve").addEventListener("click", () => { $("ctrlVerb").value = "OBSERVE"; syncParams(); sendAction(); });
$("qSpeak").addEventListener("click", () => {
  $("ctrlVerb").value = "MANIPULATE"; syncParams();
  $("ctrlAction").value = "speak"; $("ctrlMsg").value = $("ctrlMsg").value || "你好"; $("ctrlMsg").focus();
});
$("qAttack").addEventListener("click", () => {
  $("ctrlVerb").value = "MANIPULATE"; syncParams();
  $("ctrlAction").value = "attack_target"; $("ctrlMsg").value = "50"; sendAction();
});
$("qNav").addEventListener("click", () => { $("ctrlVerb").value = "NAVIGATE"; syncParams(); });
$("qDemo").addEventListener("click", runDemoAgent);

// ── 绑定 ──────────────────────────────────────────────────────

$("roleSelect").addEventListener("change", (e) => {
  if (!e.target.value) { roleVisibleIds = null; renderMap(); return; }
  const r = rolesPayload.find(x => x.key === e.target.value);
  if (r) { roleVisibleIds = new Set(r.visible_object_ids); renderMap(); }
});
$("ctrlVerb").addEventListener("change", () => { syncParams(); clearActionUI(); });
$("btnSend").addEventListener("click", sendAction);
$("btnReload").addEventListener("click", () => {
  if (pixelApi) { pixelApi.destroy(); pixelApi = null; }
  loadAll().catch(e => { $("sceneTitle").textContent = `加载失败: ${e.message}`; });
});

syncParams();
loadAll().then(() => setInterval(pollEvents, 2000)).catch(e => {
  $("sceneTitle").textContent = `加载失败: ${e.message}`;
});
