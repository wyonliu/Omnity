/**
 * SOAP 商场平面图 — Canvas 2D
 * 平滑移动 · 思维气泡 · 动作特效 · 自动追踪视口
 */
import { REALITY_COLORS } from "./soap-layout.js";

const PX = 24, WALL = 3;
const ROOM_STYLE = {
  atrium:       { fill: "#fdf6e3", wall: "#8d6e63", label: "#5d4037", name: "中庭 Atrium" },
  store_102:    { fill: "#e3f2fd", wall: "#5c6bc0", label: "#1a237e", name: "102号店铺" },
  cafe_201:     { fill: "#fce4ec", wall: "#e91e63", label: "#880e4f", name: "☕ 二楼咖啡店" },
  service_lane: { fill: "#eceff1", wall: "#78909c", label: "#37474f", name: "后场通道" },
  virtual_twin: { fill: "#ede7f6", wall: "#9575cd", label: "#4a148c", name: "🌐 虚拟商场" },
};
const ROOM_GEOM = {
  atrium:       { x: -4, z: -4, w: 24, h: 18 },
  store_102:    { x: 23, z: 2, w: 8, h: 8 },
  cafe_201:     { x: 28, z: 10, w: 8, h: 6 },
  service_lane: { x: -4, z: 15, w: 18, h: 4 },
  virtual_twin: { x: 23, z: -4, w: 13, h: 5 },
};
const TYPE_ICON = {
  "structure.column":"▮","decor.fountain":"⛲","mr_game.portal":"🌀","mr_game.creature":"👾",
  "retail.storefront":"🏪","retail.shelf":"🗄️","retail.counter":"☕","npc.store_clerk":"🧑‍💼",
  "npc.avatar":"🧑","robot.unit.delivery":"🤖","robot.unit.cleaning":"🧹",
  "facility.navigation_sign":"🪧","facility.escalator":"⬆️","furniture.bench":"🪑","iot.display_screen":"📺",
};
const REALITY_BORDER = { physical: "#d4a017", virtual: "#9b59b6", mixed: "#2980b9" };
const VERB_COLOR = { OBSERVE: "#42a5f5", NAVIGATE: "#ffa726", MANIPULATE: "#ec407a" };

function ease(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }

export function mountPixelMall(parentId, { onSelect }) {
  const parent = document.getElementById(parentId);
  if (!parent) return null;
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "display:block;width:100%;height:100%;cursor:grab;";
  parent.appendChild(canvas);
  const ctx = canvas.getContext("2d");

  let dpr = 1, W = 0, H = 0, ox = 60, oy = 60, zoom = 1;
  let items = [], payload = null;
  let anim = null;    // { type, agentId, targetId, fromXY, toXY, t, total, onDone }
  let trail = null;   // { type, targetId, fromXY, toXY, fade, totalFade }
  let running = false;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    W = parent.clientWidth; H = parent.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
  }
  function tx(m) { return (m * PX + ox) * zoom; }
  function ty(m) { return (m * PX + oy) * zoom; }
  function tw(m) { return m * PX * zoom; }

  function entityXY(id) {
    const it = items.find(i => i.o.id === id);
    return (it && it._cx != null) ? { x: it._cx, y: it._cy } : null;
  }
  function regionCenter(id) {
    const g = ROOM_GEOM[id];
    return g ? { x: tx(g.x + g.w / 2), y: ty(g.z + g.h / 2) } : null;
  }
  function resolveXY(id) { return entityXY(id) || regionCenter(id); }

  function agentBasePos(ag) {
    return ag?.nearTarget ? resolveXY(ag.nearTarget) : null;
  }

  // ── 视口平滑平移 ─────────────────────────────────────────────

  let panTgt = null, panFrames = 0;

  function panTo(sx, sy) {
    panTgt = { ox: ox + (W / 2 - sx) / zoom, oy: oy + (H / 2 - sy) / zoom };
    panFrames = 25;
  }
  function stepPan() {
    if (!panTgt || panFrames <= 0) { panTgt = null; return; }
    ox += (panTgt.ox - ox) * 0.14;
    oy += (panTgt.oy - oy) * 0.14;
    if (--panFrames <= 0) { ox = panTgt.ox; oy = panTgt.oy; panTgt = null; }
  }

  // ── 绘制主函数 ───────────────────────────────────────────────

  function draw() {
    if (!payload) return;
    resize();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#1e1e2e"; ctx.fillRect(0, 0, W, H);
    drawGrid(); drawRooms(); drawConnectors(); drawEntities();
    drawTrail(); drawActionFX(); drawAgents(); drawLegend();
  }

  function drawGrid() {
    ctx.strokeStyle = "rgba(255,255,255,0.04)"; ctx.lineWidth = 0.5;
    const s = PX * zoom;
    for (let x = (ox * zoom) % s; x < W; x += s) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = (oy * zoom) % s; y < H; y += s) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  }

  function drawRooms() {
    const hlId = anim?.targetId || trail?.targetId;
    for (const [id, g] of Object.entries(ROOM_GEOM)) {
      const st = ROOM_STYLE[id] || ROOM_STYLE.atrium;
      const rx = tx(g.x), ry = ty(g.z), rw = tw(g.w), rh = tw(g.h);
      const hl = id === hlId;
      ctx.fillStyle = st.fill; ctx.globalAlpha = hl ? 1 : 0.85;
      ctx.fillRect(rx, ry, rw, rh); ctx.globalAlpha = 1;
      if (hl) {
        ctx.save();
        ctx.shadowColor = VERB_COLOR[anim?.type || trail?.type] || "#ffa726";
        ctx.shadowBlur = 16 * zoom;
        ctx.strokeStyle = ctx.shadowColor; ctx.lineWidth = (WALL + 2) * zoom;
        ctx.strokeRect(rx, ry, rw, rh); ctx.restore();
      } else {
        ctx.strokeStyle = st.wall; ctx.lineWidth = WALL * zoom;
        ctx.strokeRect(rx, ry, rw, rh);
      }
      ctx.fillStyle = st.label;
      ctx.font = `bold ${Math.max(11, 13 * zoom)}px "PingFang SC","Noto Sans SC",system-ui,sans-serif`;
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillText(st.name || id, rx + 6 * zoom, ry + 5 * zoom);
    }
  }

  function drawConnectors() {
    ctx.strokeStyle = "rgba(255,255,255,0.12)"; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
    const a = ROOM_GEOM.atrium, s = ROOM_GEOM.store_102, c = ROOM_GEOM.cafe_201;
    ctx.beginPath(); ctx.moveTo(tx(a.x + a.w), ty(a.z + 6)); ctx.lineTo(tx(s.x), ty(s.z + 3)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(tx(a.x + a.w), ty(a.z + a.h - 2)); ctx.lineTo(tx(c.x), ty(c.z + 2)); ctx.stroke();
    ctx.setLineDash([]);
  }

  function drawEntities() {
    for (const it of items) {
      const o = it.o;
      const dim = payload.roleVisibleIds && !payload.roleVisibleIds.has(o.id);
      const sel = payload.selectedId === o.id;
      const hl = (anim?.targetId === o.id || trail?.targetId === o.id) && !ROOM_GEOM[o.id];
      let cx, cy, bw, bh;
      if (it.kind === "aabb") {
        const xz = it.xz;
        cx = tx((xz.xmin + xz.xmax) / 2); cy = ty((xz.zmin + xz.zmax) / 2);
        bw = Math.max(tw(xz.xmax - xz.xmin), 18 * zoom); bh = Math.max(tw(xz.zmax - xz.zmin), 18 * zoom);
      } else if (it.x != null) { cx = tx(it.x); cy = ty(it.z); bw = bh = 22 * zoom; }
      else continue;
      it._cx = cx; it._cy = cy; it._r = Math.max(bw, bh) / 2 + 6 * zoom;
      const alpha = dim ? 0.25 : 1, border = REALITY_BORDER[o.reality] || "#777";

      if (hl) {
        const col = VERB_COLOR[anim?.type || trail?.type] || "#ffa726";
        const pulse = anim ? 0.5 + 0.5 * Math.sin(anim.t * 0.4) : (trail ? trail.fade / trail.totalFade : 0.3);
        ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = 22 * zoom * pulse;
        ctx.strokeStyle = col; ctx.lineWidth = 3 * zoom;
        ctx.beginPath(); ctx.arc(cx, cy, it._r + 8 * zoom, 0, Math.PI * 2); ctx.stroke();
        ctx.globalAlpha = 0.15 * pulse; ctx.fillStyle = col; ctx.fill(); ctx.restore();
      }
      if (sel && !hl) {
        ctx.save(); ctx.shadowColor = "#4caf50"; ctx.shadowBlur = 14 * zoom;
        ctx.strokeStyle = "#4caf50"; ctx.lineWidth = 3 * zoom;
        ctx.beginPath(); ctx.arc(cx, cy, it._r + 4 * zoom, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
      }
      ctx.globalAlpha = alpha;
      ctx.fillStyle = "#fff"; ctx.strokeStyle = border; ctx.lineWidth = 2 * zoom;
      rr(ctx, cx - bw / 2, cy - bh / 2, bw, bh, 4 * zoom); ctx.fill(); ctx.stroke();
      ctx.font = `${Math.max(14, 16 * zoom)}px sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillStyle = dim ? "#ccc" : "#333"; ctx.fillText(TYPE_ICON[o.type] || "◆", cx, cy);
      ctx.font = `bold ${Math.max(9, 10 * zoom)}px "SF Mono","Noto Sans Mono",monospace`; ctx.textBaseline = "top";
      ctx.fillStyle = dim ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.9)";
      ctx.strokeStyle = "rgba(0,0,0,0.6)"; ctx.lineWidth = 2.5;
      const lb = o.id.length > 16 ? o.id.slice(0, 14) + "…" : o.id;
      ctx.strokeText(lb, cx, cy + bh / 2 + 3 * zoom); ctx.fillText(lb, cx, cy + bh / 2 + 3 * zoom);
      ctx.font = `${Math.max(8, 9 * zoom)}px monospace`;
      ctx.fillStyle = REALITY_COLORS[o.reality] || REALITY_COLORS.default;
      ctx.textBaseline = "bottom"; ctx.fillText(o.reality || "", cx, cy - bh / 2 - 2 * zoom);
      ctx.globalAlpha = 1;
    }
  }

  // ── Agent 头像 + 思维气泡 ─────────────────────────────────────

  function getAgentDrawPos(aid) {
    const agents = payload?.agents || {};
    const ag = agents[aid];
    let pos = agentBasePos(ag);
    if (!pos) return null;
    if (anim && anim.agentId === aid && anim.fromXY && anim.toXY) {
      const p = ease(Math.min(1, 1 - anim.t / anim.total));
      pos = { x: anim.fromXY.x + (anim.toXY.x - anim.fromXY.x) * p,
              y: anim.fromXY.y + (anim.toXY.y - anim.fromXY.y) * p };
    }
    return pos;
  }

  function drawAgents() {
    const agents = payload?.agents || {};
    for (const [aid, ag] of Object.entries(agents)) {
      const pos = getAgentDrawPos(aid);
      if (!pos) continue;
      const r = 16 * zoom;

      // 行走轨迹点
      if (anim && anim.agentId === aid && anim.fromXY && anim.toXY) {
        const prog = ease(Math.min(1, 1 - anim.t / anim.total));
        ctx.save();
        for (let i = 0; i < 6; i++) {
          const pp = Math.max(0, prog - i * 0.05);
          const dx = anim.fromXY.x + (anim.toXY.x - anim.fromXY.x) * pp;
          const dy = anim.fromXY.y + (anim.toXY.y - anim.fromXY.y) * pp;
          ctx.globalAlpha = 0.1 * (1 - i / 6);
          ctx.fillStyle = "#00e676";
          ctx.beginPath(); ctx.arc(dx, dy, 4 * zoom, 0, Math.PI * 2); ctx.fill();
        }
        ctx.restore();
      }

      // 头像
      ctx.save();
      ctx.shadowColor = "#00e676"; ctx.shadowBlur = 14 * zoom;
      ctx.beginPath(); ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
      const grd = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, r);
      grd.addColorStop(0, "#69f0ae"); grd.addColorStop(1, "#00c853");
      ctx.fillStyle = grd; ctx.fill();
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2.5 * zoom; ctx.stroke();
      ctx.restore();
      ctx.font = `${Math.max(13, 14 * zoom)}px sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillStyle = "#000"; ctx.fillText("🧑‍💻", pos.x, pos.y - 1);
      ctx.font = `bold ${Math.max(10, 11 * zoom)}px "SF Mono",monospace`;
      ctx.textBaseline = "top"; ctx.textAlign = "center";
      ctx.strokeStyle = "rgba(0,0,0,0.85)"; ctx.lineWidth = 3;
      ctx.strokeText(aid, pos.x, pos.y + r + 4 * zoom);
      ctx.fillStyle = "#00e676"; ctx.fillText(aid, pos.x, pos.y + r + 4 * zoom);

      // 思维气泡
      if (ag.thought) drawThought(pos, ag.thought, r);
    }
  }

  function drawThought(pos, text, agentR) {
    const fs = Math.max(10, 11 * zoom);
    ctx.font = `${fs}px "PingFang SC","Noto Sans SC",system-ui,sans-serif`;
    const display = text.length > 22 ? text.slice(0, 20) + "…" : text;
    const tm = ctx.measureText(display);
    const pad = 7 * zoom, bw = tm.width + pad * 2, bh = fs + pad * 2;
    const bx = pos.x - bw / 2, by = pos.y - agentR - bh - 14 * zoom;
    ctx.save();
    ctx.fillStyle = "rgba(20,20,40,0.92)"; rr(ctx, bx, by, bw, bh, 6 * zoom); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.15)"; ctx.lineWidth = 1; ctx.stroke();
    // 三角形
    ctx.beginPath();
    ctx.moveTo(pos.x - 5 * zoom, by + bh);
    ctx.lineTo(pos.x, by + bh + 7 * zoom);
    ctx.lineTo(pos.x + 5 * zoom, by + bh);
    ctx.closePath(); ctx.fillStyle = "rgba(20,20,40,0.92)"; ctx.fill();
    // 文字
    ctx.fillStyle = "#e0e0e0"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("💭 " + display, pos.x, by + bh / 2);
    ctx.restore();
  }

  // ── 动作特效 ─────────────────────────────────────────────────

  function drawActionFX() {
    if (!anim || anim.t <= 0) return;
    const { fromXY, toXY, type, t, total } = anim;
    const prog = 1 - t / total;

    if (type === "NAVIGATE" && fromXY && toXY) {
      ctx.save();
      ctx.setLineDash([10, 6]); ctx.lineDashOffset = -t * 2;
      ctx.strokeStyle = "#ffa726"; ctx.lineWidth = 3 * zoom; ctx.globalAlpha = 0.8;
      ctx.beginPath(); ctx.moveTo(fromXY.x, fromXY.y); ctx.lineTo(toXY.x, toXY.y); ctx.stroke();
      ctx.setLineDash([]);
      const a = Math.atan2(toXY.y - fromXY.y, toXY.x - fromXY.x);
      const ep = ease(prog);
      const tipX = fromXY.x + (toXY.x - fromXY.x) * ep;
      const tipY = fromXY.y + (toXY.y - fromXY.y) * ep;
      ctx.fillStyle = "#ffa726"; ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.moveTo(tipX + Math.cos(a) * 10 * zoom, tipY + Math.sin(a) * 10 * zoom);
      ctx.lineTo(tipX + Math.cos(a + 2.5) * 8 * zoom, tipY + Math.sin(a + 2.5) * 8 * zoom);
      ctx.lineTo(tipX + Math.cos(a - 2.5) * 8 * zoom, tipY + Math.sin(a - 2.5) * 8 * zoom);
      ctx.closePath(); ctx.fill(); ctx.restore();
    }

    if (type === "OBSERVE" && toXY) {
      for (let ring = 0; ring < 3; ring++) {
        const r = (20 + prog * 50 + ring * 18) * zoom;
        ctx.save(); ctx.globalAlpha = Math.max(0, (1 - prog - ring * 0.2)) * 0.5;
        ctx.strokeStyle = "#42a5f5"; ctx.lineWidth = 2 * zoom; ctx.setLineDash([8, 5]);
        ctx.beginPath(); ctx.arc(toXY.x, toXY.y, r, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]); ctx.restore();
      }
    }

    if (type === "MANIPULATE" && toXY) {
      const r = prog * 40 * zoom;
      ctx.save(); ctx.globalAlpha = (1 - prog) * 0.7;
      ctx.strokeStyle = "#ec407a"; ctx.lineWidth = 4 * zoom;
      ctx.beginPath(); ctx.arc(toXY.x, toXY.y, r, 0, Math.PI * 2); ctx.stroke();
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2 + t * 0.1;
        ctx.beginPath();
        ctx.moveTo(toXY.x + Math.cos(a) * r * 0.6, toXY.y + Math.sin(a) * r * 0.6);
        ctx.lineTo(toXY.x + Math.cos(a) * r * 1.3, toXY.y + Math.sin(a) * r * 1.3);
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  function drawTrail() {
    if (!trail || trail.fade <= 0) return;
    const a = trail.fade / trail.totalFade;
    if (trail.type === "NAVIGATE" && trail.fromXY && trail.toXY) {
      ctx.save(); ctx.globalAlpha = a * 0.35;
      ctx.setLineDash([8, 6]); ctx.strokeStyle = "#ffa726"; ctx.lineWidth = 2 * zoom;
      ctx.beginPath(); ctx.moveTo(trail.fromXY.x, trail.fromXY.y);
      ctx.lineTo(trail.toXY.x, trail.toXY.y); ctx.stroke();
      ctx.setLineDash([]); ctx.restore();
    }
  }

  function drawLegend() {
    const lx = 10, ly = H - 50;
    ctx.fillStyle = "rgba(0,0,0,0.6)"; rr(ctx, lx, ly, 280, 42, 6); ctx.fill();
    ctx.font = "bold 11px system-ui,sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    [{ c: "#d4a017", t: "physical" },{ c: "#9b59b6", t: "virtual" },{ c: "#2980b9", t: "mixed" },{ c: "#00e676", t: "agent" }].forEach((l, i) => {
      ctx.fillStyle = l.c; ctx.fillRect(lx + 8 + i * 66, ly + 8, 10, 10);
      ctx.fillStyle = "#ddd"; ctx.fillText(l.t, lx + 22 + i * 66, ly + 14);
    });
    ctx.fillStyle = "#777"; ctx.font = "10px monospace";
    ctx.fillText("滚轮缩放 · 右键/Shift拖拽平移 · 点击选中", lx + 8, ly + 32);
  }

  function rr(c, x, y, w, h, r) {
    c.beginPath(); c.moveTo(x + r, y);
    c.lineTo(x + w - r, y); c.quadraticCurveTo(x + w, y, x + w, y + r);
    c.lineTo(x + w, y + h - r); c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    c.lineTo(x + r, y + h); c.quadraticCurveTo(x, y + h, x, y + h - r);
    c.lineTo(x, y + r); c.quadraticCurveTo(x, y, x + r, y); c.closePath();
  }

  // ── 动画引擎 ─────────────────────────────────────────────────

  function startAction(type, agentId, targetId, onDone) {
    const agents = payload?.agents || {};
    const ag = agents[agentId];
    const fromXY = agentBasePos(ag);
    const toXY = resolveXY(targetId);
    const frames = 60; // ~1s at 60fps
    anim = { type, agentId, targetId, fromXY, toXY, t: frames, total: frames, onDone };
    if (toXY) panTo(toXY.x, toXY.y);
    if (!running) runLoop();
  }

  function runLoop() {
    running = true;
    function tick() {
      stepPan();
      if (anim) {
        anim.toXY = resolveXY(anim.targetId) || anim.toXY;
        if (anim.t > 0) { anim.t--; }
        else {
          const done = anim.onDone;
          trail = { type: anim.type, targetId: anim.targetId, fromXY: anim.fromXY, toXY: anim.toXY, fade: 120, totalFade: 120 };
          anim = null;
          if (done) done();
        }
      }
      if (trail) {
        if (trail.fade > 0) trail.fade--;
        else trail = null;
      }
      draw();
      if (anim || trail || panTgt) requestAnimationFrame(tick);
      else { running = false; draw(); }
    }
    requestAnimationFrame(tick);
  }

  // ── 交互 ─────────────────────────────────────────────────────

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const oldZ = zoom;
    zoom = Math.max(0.3, Math.min(4, zoom * (1 - e.deltaY * 0.001)));
    ox += (mx / zoom - mx / oldZ); oy += (my / zoom - my / oldZ);
    draw();
  }, { passive: false });

  let dragging = false, lastX = 0, lastY = 0;
  canvas.addEventListener("pointerdown", (e) => {
    if (e.button === 2 || e.shiftKey) {
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      canvas.style.cursor = "grabbing"; e.preventDefault();
    } else if (e.button === 0) {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      for (const it of items) {
        if (it._cx == null) continue;
        const dx = mx - it._cx, dy = my - it._cy;
        if (dx * dx + dy * dy < it._r * it._r) { onSelect(it.o.id); return; }
      }
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    ox += (e.clientX - lastX) / zoom; oy += (e.clientY - lastY) / zoom;
    lastX = e.clientX; lastY = e.clientY; draw();
  });
  canvas.addEventListener("pointerup", () => { dragging = false; canvas.style.cursor = "grab"; });
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  return {
    refresh(p) { payload = p; items = p.items || []; draw(); },
    action(type, agentId, targetId, onDone) { startAction(type, agentId, targetId, onDone); },
    clearTrail() { trail = null; anim = null; draw(); },
    destroy() { canvas.remove(); },
  };
}
