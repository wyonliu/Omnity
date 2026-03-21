/**
 * SOAP-View — Vite 入口
 * UI：Bootstrap 5 · 像素地图：Phaser 3 · 关系图：vis-network
 */
import "bootstrap/dist/css/bootstrap.min.css";
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
  const wrap = document.getElementById("mapWrap");
  if (!document.getElementById("phaserMount")) {
    wrap.innerHTML = `
      <div id="phaserMount" class="soap-phaser-root"></div>
      <p class="soap-pixel-hint">↑↓←→ 或 <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 漫游 · 点击色块查看 JSON</p>`;
    pixelApi = mountPixelMall("phaserMount", {
      onSelect: (id) => selectObject(id),
    });
  }
}

function renderMap() {
  if (!scene || !scene.objects) return;
  ensurePixelMount();
  const base = computeMapPayload(scene);
  pixelApi.refresh({
    ...base,
    roleVisibleIds,
    selectedId,
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
      color: { background: "#6c3483", border: "#d7bde2" },
      font: { color: "#f5eef8", size: 13 },
      title: r.uri,
    });
    for (const oid of r.contained_object_ids || []) {
      if (!objects.some((x) => x.id === oid)) continue;
      edges.push({
        from: `region:${r.id}`,
        to: `obj:${oid}`,
        label: "contains",
        color: { color: "#a569bd", opacity: 0.65 },
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
        border: "#2c1a4a",
        highlight: { background: "#f39c12", border: "#fff" },
      },
      font: { color: "#1a0a1f", size: 12, face: "monospace" },
      title: `${o.type}\n${o.uri}`,
    });
  }
  for (const rel of scene.relations || []) {
    edges.push({
      from: `obj:${rel.from_id}`,
      to: `obj:${rel.to_id}`,
      label: rel.relation,
      arrows: "to",
      color: { color: "#5dade2" },
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
      barnesHut: { gravitationalConstant: -2800, springLength: 130 },
      stabilization: { iterations: 140 },
    },
    nodes: {
      shape: "box",
      margin: 12,
      borderWidth: 2,
      shadow: true,
    },
    edges: {
      font: { size: 11, color: "#c39bd3", strokeWidth: 0 },
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
  document.getElementById("detailJson").textContent = o
    ? JSON.stringify(o, null, 2)
    : id;
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
    desc.textContent = "选择角色以高亮其在 SOAP 中「可见」的实体。";
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
  const [scRes, roRes] = await Promise.all([fetch("/api/scene"), fetch("/api/roles")]);
  const sc = await scRes.json();
  const ro = await roRes.json();
  if (sc.error) throw new Error(sc.detail || sc.error);
  if (ro.error) throw new Error(ro.detail || ro.error);
  scene = sc.scene;
  metaPath = (sc.meta && sc.meta.scene_path) || "";
  rolesPayload = ro.roles || [];
  document.getElementById("sceneTitle").textContent = scene.title || "SOAP-View";
  document.getElementById("sceneMeta").textContent = `${scene.space_id || ""} · ${metaPath}`;
  fillRoleSelect();
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
    document.getElementById("sceneMeta").textContent = `加载失败: ${err.message}`;
  });
});

loadAll().catch((err) => {
  document.getElementById("sceneMeta").textContent = `加载失败: ${err.message}`;
});
