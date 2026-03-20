/**
 * SOAP-View — Vite 入口
 * UI：Bootstrap 5（MIT）· 图：vis-network（MIT & Apache-2.0）
 */
import "bootstrap/dist/css/bootstrap.min.css";
import "vis-network/styles/vis-network.min.css";
import { Network } from "vis-network";
import "./style.css";

const REALITY_COLORS = {
  physical: "#eab308",
  virtual: "#a855f7",
  mixed: "#2dd4bf",
  default: "#94a3b8",
};

let scene = null;
let metaPath = "";
let rolesPayload = [];
let roleVisibleIds = null;
let selectedId = null;
let network = null;

function byUri(objects) {
  const m = {};
  for (const o of objects) m[o.uri] = o;
  return m;
}

function aabbXZ(b) {
  if (!b || b.type !== "aabb" || !b.min || !b.max) return null;
  return {
    xmin: b.min[0],
    zmin: b.min[2],
    xmax: b.max[0],
    zmax: b.max[2],
  };
}

function aabbCenterXZ(b) {
  const xz = aabbXZ(b);
  if (!xz) return null;
  return { x: (xz.xmin + xz.xmax) / 2, z: (xz.zmin + xz.zmax) / 2 };
}

function mergeBounds(a, b) {
  if (!a) return b;
  if (!b) return a;
  return {
    xmin: Math.min(a.xmin, b.xmin),
    zmin: Math.min(a.zmin, b.zmin),
    xmax: Math.max(a.xmax, b.xmax),
    zmax: Math.max(a.zmax, b.zmax),
  };
}

function boundsFromObjects(objects) {
  let bb = null;
  for (const o of objects) {
    const xz = aabbXZ(o.bounds);
    if (xz) bb = mergeBounds(bb, xz);
  }
  return bb || { xmin: -2, zmin: -2, xmax: 35, zmax: 18 };
}

function inferPosition(o, uriMap, bb) {
  const direct = aabbXZ(o.bounds);
  if (direct) {
    return { kind: "aabb", xz: direct, o };
  }
  const bind = o.bindings || {};
  const anchorU = bind.twin_anchor_uri || bind.anchor_physical_uri;
  if (anchorU && uriMap[anchorU]) {
    const anchor = uriMap[anchorU];
    const ac = aabbCenterXZ(anchor.bounds);
    if (ac) return { kind: "anchor", x: ac.x + 0.35, z: ac.z + 0.35, o };
    const axz = aabbXZ(anchor.bounds);
    if (axz) {
      return {
        kind: "anchor",
        x: (axz.xmin + axz.xmax) / 2 + 0.35,
        z: (axz.zmin + axz.zmax) / 2 + 0.35,
        o,
      };
    }
  }
  return { kind: "unplaced", o };
}

function layoutUnplaced(unplaced, bb) {
  const pad = 2;
  const xmax = bb.xmax + pad;
  const zstart = bb.zmin;
  unplaced.forEach((item, i) => {
    const col = i % 5;
    const row = Math.floor(i / 5);
    item.x = xmax + 1.2 + col * 1.1;
    item.z = zstart + row * 1.4;
  });
}

function renderMap() {
  const wrap = document.getElementById("mapWrap");
  wrap.innerHTML = "";
  if (!scene || !scene.objects) return;

  const objects = scene.objects;
  const regions = scene.regions || [];
  const uriMap = byUri(objects);
  const bb = boundsFromObjects(objects);

  const items = objects.map((o) => {
    const p = inferPosition(o, uriMap, bb);
    return { ...p, o };
  });
  const unplaced = items.filter((i) => i.kind === "unplaced");
  layoutUnplaced(unplaced, bb);

  let xmin = bb.xmin - 1;
  let zmin = bb.zmin - 1;
  let xmax = bb.xmax + 1;
  let zmax = bb.zmax + 1;
  for (const it of items) {
    if (it.kind === "aabb") {
      xmin = Math.min(xmin, it.xz.xmin);
      zmin = Math.min(zmin, it.xz.zmin);
      xmax = Math.max(xmax, it.xz.xmax);
      zmax = Math.max(zmax, it.xz.zmax);
    } else if (it.x != null) {
      xmin = Math.min(xmin, it.x - 0.4);
      zmin = Math.min(zmin, it.z - 0.4);
      xmax = Math.max(xmax, it.x + 0.4);
      zmax = Math.max(zmax, it.z + 0.4);
    }
  }

  const w = xmax - xmin;
  const h = zmax - zmin;
  const pad = Math.max(w, h) * 0.06;
  xmin -= pad;
  zmin -= pad;
  xmax += pad;
  zmax += pad;

  const svgW = 900;
  const svgH = Math.max(360, (svgW * (zmax - zmin)) / (xmax - xmin));

  const sx = (x) => ((x - xmin) / (xmax - xmin)) * svgW;
  const sy = (z) => svgH - ((z - zmin) / (zmax - zmin)) * svgH;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${svgW} ${svgH}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  for (const r of regions) {
    const ids = r.contained_object_ids || [];
    let rb = null;
    for (const id of ids) {
      const o = objects.find((x) => x.id === id);
      if (!o) continue;
      const xz = aabbXZ(o.bounds);
      if (xz) rb = mergeBounds(rb, xz);
    }
    if (!rb) continue;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "region-rect");
    rect.setAttribute("x", sx(rb.xmin));
    rect.setAttribute("y", sy(rb.zmax));
    rect.setAttribute("width", sx(rb.xmax) - sx(rb.xmin));
    rect.setAttribute("height", sy(rb.zmin) - sy(rb.zmax));
    svg.appendChild(rect);
  }

  for (const it of items) {
    const o = it.o;
    const col = REALITY_COLORS[o.reality] || REALITY_COLORS.default;
    const dim = roleVisibleIds && !roleVisibleIds.has(o.id) ? " dim" : "";
    const sel = selectedId === o.id ? " selected" : "";

    if (it.kind === "aabb") {
      const xz = it.xz;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", `obj-rect${dim}${sel}`);
      rect.setAttribute("x", sx(xz.xmin));
      rect.setAttribute("y", sy(xz.zmax));
      rect.setAttribute("width", Math.max(2, sx(xz.xmax) - sx(xz.xmin)));
      rect.setAttribute("height", Math.max(2, sy(xz.zmin) - sy(xz.zmax)));
      rect.setAttribute("fill", col);
      rect.setAttribute("fill-opacity", "0.35");
      rect.setAttribute("stroke", col);
      rect.dataset.id = o.id;
      rect.addEventListener("click", () => selectObject(o.id));
      svg.appendChild(rect);
    } else if (it.x != null) {
      const cx = sx(it.x);
      const cy = sy(it.z);
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("class", `obj-dot${dim}${sel}`);
      circle.setAttribute("cx", cx);
      circle.setAttribute("cy", cy);
      circle.setAttribute("r", 7);
      circle.setAttribute("fill", col);
      circle.setAttribute("stroke", "#0d1117");
      circle.dataset.id = o.id;
      circle.addEventListener("click", () => selectObject(o.id));
      svg.appendChild(circle);
    }

    let lx;
    let ly;
    if (it.kind === "aabb") {
      lx = sx((it.xz.xmin + it.xz.xmax) / 2);
      ly = sy((it.xz.zmin + it.xz.zmax) / 2) - 4;
    } else if (it.x != null) {
      lx = sx(it.x);
      ly = sy(it.z) - 12;
    } else continue;

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("class", "obj-label");
    text.setAttribute("x", lx);
    text.setAttribute("y", ly);
    text.setAttribute("text-anchor", "middle");
    text.textContent = o.id.length > 18 ? o.id.slice(0, 16) + "…" : o.id;
    svg.appendChild(text);
  }

  wrap.appendChild(svg);
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
      title: r.uri,
    });
    for (const oid of r.contained_object_ids || []) {
      if (!objects.some((x) => x.id === oid)) continue;
      edges.push({
        from: `region:${r.id}`,
        to: `obj:${oid}`,
        label: "contains",
        color: { color: "#475569" },
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
      color: col,
      font: { color: "#e6edf3", size: 13 },
      title: `${o.type}\n${o.uri}`,
    });
  }
  for (const rel of scene.relations || []) {
    edges.push({
      from: `obj:${rel.from_id}`,
      to: `obj:${rel.to_id}`,
      label: rel.relation,
      arrows: "to",
      color: { color: "#38bdf8" },
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
      barnesHut: { gravitationalConstant: -3500, springLength: 120 },
      stabilization: { iterations: 120 },
    },
    nodes: { shape: "box", margin: 10, borderWidth: 1 },
    edges: { font: { size: 10, color: "#8b949e" }, smooth: { type: "cubicBezier" } },
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
    desc.textContent = "选择导航栏中的角色以高亮可见物体。";
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
