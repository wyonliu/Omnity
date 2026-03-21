/**
 * SOAP-View — Vite 入口
 * UI 壳层：GenerativeAgentsCN 同源 Bootstrap 3 + jQuery + game-container（Apache-2.0 见 public/vendor/generative-agents-cn/）
 * 地图：Phaser 3 · 关系图：vis-network
 */
import "vis-network/styles/vis-network.min.css";
import { Network } from "vis-network";
import { computeMapPayload, REALITY_COLORS } from "./soap-layout.js";
import { mountPixelMall } from "./pixel-mall.js";
import "./style.css";

let scene = null;
let metaPath = "";
let rolesPayload = [];
let roleVisibleIds = null;
let selectedId = null;
let network = null;
let pixelApi = null;

function ensurePixelMount() {
  const el = document.getElementById("game-container");
  if (!el) return;
  if (!pixelApi) {
    el.innerHTML = "";
    pixelApi = mountPixelMall("game-container", {
      onSelect: (id) => selectObject(id),
    });
  }
}

function renderMap() {
  if (!scene || !scene.objects) return;
  ensurePixelMount();
  const base = computeMapPayload(scene);
  pixelApi?.refresh({
    ...base,
    roleVisibleIds,
    selectedId,
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/** 条带高亮颜色与 GenerativeAgentsCN 回放选中一致 */
const STRIP_HIGHLIGHT = "#ABFF84";

function renderEntityStrip() {
  const inner = document.getElementById("entityStripInner");
  if (!inner || !scene?.objects) return;
  inner.innerHTML = "";
  for (const o of scene.objects) {
    const col = REALITY_COLORS[o.reality] || REALITY_COLORS.default;
    const wrap = document.createElement("div");
    wrap.style.cssText = "text-align: center; margin: 0.5em;";
    const a = document.createElement("a");
    a.href = "javascript:void(0);";
    a.dataset.objId = o.id;
    a.innerHTML = `<div class="entity-thumb-wrap" style="padding:0;border-radius:10px;display:inline-block;">
        <div class="entity-thumb" data-bg="${col}" style="width:32px;height:32px;margin:0 auto;background:${col};border-radius:4px;border:1px solid #333;"></div>
        <br><span class="entity-id" style="font-size:12px">${escapeHtml(o.id)}</span>
      </div>`;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      selectObject(o.id);
    });
    wrap.appendChild(a);
    inner.appendChild(wrap);
  }
  updateStripHighlight(selectedId);
}

function updateStripHighlight(id) {
  document.querySelectorAll("#entityStripInner a").forEach((a) => {
    const thumb = a.querySelector(".entity-thumb");
    const wrap = a.querySelector(".entity-thumb-wrap");
    const oid = a.dataset.objId;
    const bg = thumb?.getAttribute("data-bg") || "#ccc";
    if (oid === id) {
      wrap.style.backgroundColor = STRIP_HIGHLIGHT;
      wrap.style.fontWeight = "900";
    } else {
      wrap.style.backgroundColor = "white";
      wrap.style.fontWeight = "500";
      thumb.style.background = bg;
    }
  });
}

function buildGraphData() {
  const nodes = [];
  const edges = [];
  const objects = scene.objects || [];
  const regions = scene.regions || [];
  for (const r of regions) {
    nodes.push({
      id: `region:${r.id}`,
      label: `📍 ${r.name || r.id}`,
      group: "region",
      color: { background: "#e8daef", border: "#7d3c98" },
      font: { color: "#1a1a1a", size: 13 },
      title: r.uri,
    });
    for (const oid of r.contained_object_ids || []) {
      if (!objects.some((x) => x.id === oid)) continue;
      edges.push({
        from: `region:${r.id}`,
        to: `obj:${oid}`,
        label: "contains",
        color: { color: "#884ea0", opacity: 0.7 },
        dashes: true,
      });
    }
  }
  for (const o of objects) {
    const col = REALITY_COLORS[o.reality] || REALITY_COLORS.default;
    nodes.push({
      id: `obj:${o.id}`,
      label: o.id,
      group: o.reality || "default",
      color: {
        background: col,
        border: "#333",
        highlight: { background: STRIP_HIGHLIGHT, border: "#000" },
      },
      font: { color: "#111", size: 11, face: "monospace" },
      title: `${o.type}\n${o.uri}`,
    });
  }
  for (const rel of scene.relations || []) {
    edges.push({
      from: `obj:${rel.from_id}`,
      to: `obj:${rel.to_id}`,
      label: rel.relation,
      arrows: "to",
      color: { color: "#2874a6" },
    });
  }
  return { nodes, edges };
}

function renderGraph() {
  const mount = document.getElementById("graphMount");
  mount.innerHTML = "";
  if (!scene) return;
  const { nodes, edges } = buildGraphData();
  const data = { nodes, edges };
  const options = {
    physics: {
      enabled: true,
      barnesHut: { gravitationalConstant: -2600, springLength: 130 },
      stabilization: { iterations: 140 },
    },
    nodes: {
      shape: "box",
      margin: 10,
      borderWidth: 2,
      shadow: false,
    },
    edges: {
      font: { size: 10, color: "#555", strokeWidth: 0 },
      smooth: { type: "cubicBezier" },
    },
    layout: { improvedLayout: true },
  };
  network = new Network(mount, data, options);
  network.on("click", (p) => {
    if (p.nodes.length) {
      const nid = p.nodes[0];
      if (nid.startsWith("obj:")) selectObject(nid.slice(4));
    }
  });
}

function selectObject(id) {
  selectedId = id;
  const o = (scene.objects || []).find((x) => x.id === id);
  const init = document.getElementById("detailInit");
  const panel = document.getElementById("detailPanel");
  const pre = document.getElementById("detailJson");
  if (init) init.style.display = "none";
  if (panel) panel.style.display = "block";
  if (pre) pre.textContent = o ? JSON.stringify(o, null, 2) : id;
  updateStripHighlight(id);
  renderMap();
}

function fillRoleSelect() {
  const sel = document.getElementById("roleSelect");
  while (sel.options.length > 1) sel.remove(1);
  for (const r of rolesPayload) {
    const opt = document.createElement("option");
    opt.value = r.key;
    opt.textContent = r.name;
    sel.appendChild(opt);
  }
}

function applyRole(key) {
  const desc = document.getElementById("roleDesc");
  const ul = document.getElementById("roleActions");
  const ins = document.getElementById("roleInsight");
  ul.innerHTML = "";
  if (!key) {
    roleVisibleIds = null;
    desc.textContent = "选择「角色视角」以高亮其在 SOAP 中可见的实体。";
    ins.textContent = "";
    renderMap();
    return;
  }
  const r = rolesPayload.find((x) => x.key === key);
  if (!r) return;
  roleVisibleIds = new Set(r.visible_object_ids);
  desc.textContent = r.desc;
  for (const a of r.actions || []) {
    const li = document.createElement("li");
    li.textContent = a;
    ul.appendChild(li);
  }
  ins.textContent = r.insight || "";
  renderMap();
}

async function loadAll() {
  selectedId = null;
  const init = document.getElementById("detailInit");
  const panel = document.getElementById("detailPanel");
  if (init) init.style.display = "block";
  if (panel) panel.style.display = "none";

  const [scRes, roRes] = await Promise.all([fetch("/api/scene"), fetch("/api/roles")]);
  const sc = await scRes.json();
  const ro = await roRes.json();
  if (sc.error) throw new Error(sc.detail || sc.error);
  if (ro.error) throw new Error(ro.detail || ro.error);
  scene = sc.scene;
  metaPath = (sc.meta && sc.meta.scene_path) || "";
  rolesPayload = ro.roles || [];
  const titleEl = document.getElementById("sceneTitle");
  if (titleEl) titleEl.textContent = scene.title || "SOAP-View";
  const metaEl = document.getElementById("sceneMeta");
  if (metaEl) metaEl.textContent = `${scene.space_id || ""} · ${metaPath}`;
  fillRoleSelect();
  renderEntityStrip();
  const rs = document.getElementById("roleSelect").value;
  if (rs) applyRole(rs);
  else {
    roleVisibleIds = null;
    renderMap();
  }
  renderGraph();
}

document.getElementById("roleSelect").addEventListener("change", (e) => {
  applyRole(e.target.value);
});

document.getElementById("btnReload").addEventListener("click", () => {
  loadAll().catch((err) => {
    const m = document.getElementById("sceneMeta");
    if (m) m.textContent = `加载失败: ${err.message}`;
  });
});

loadAll().catch((err) => {
  const m = document.getElementById("sceneMeta");
  if (m) m.textContent = `加载失败: ${err.message}`;
});
