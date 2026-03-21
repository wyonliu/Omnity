/**
 * SOAP 场景 → 平面图几何（与旧 SVG 逻辑一致，供 Phaser 像素视图复用）
 */

export const REALITY_COLORS = {
  physical: "#f2c94c",
  virtual: "#bb6bd9",
  mixed: "#56ccf2",
  default: "#7f8c8d",
};

export function byUri(objects) {
  const m = {};
  for (const o of objects) m[o.uri] = o;
  return m;
}

export function aabbXZ(b) {
  if (!b || b.type !== "aabb" || !b.min || !b.max) return null;
  return {
    xmin: b.min[0],
    zmin: b.min[2],
    xmax: b.max[0],
    zmax: b.max[2],
  };
}

export function aabbCenterXZ(b) {
  const xz = aabbXZ(b);
  if (!xz) return null;
  return { x: (xz.xmin + xz.xmax) / 2, z: (xz.zmin + xz.zmax) / 2 };
}

export function mergeBounds(a, b) {
  if (!a) return b;
  if (!b) return a;
  return {
    xmin: Math.min(a.xmin, b.xmin),
    zmin: Math.min(a.zmin, b.zmin),
    xmax: Math.max(a.xmax, b.xmax),
    zmax: Math.max(a.zmax, b.zmax),
  };
}

export function boundsFromObjects(objects) {
  let bb = null;
  for (const o of objects) {
    const xz = aabbXZ(o.bounds);
    if (xz) bb = mergeBounds(bb, xz);
  }
  return bb || { xmin: -2, zmin: -2, xmax: 35, zmax: 18 };
}

export function inferPosition(o, uriMap, bb) {
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

export function layoutUnplaced(unplaced, bb) {
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

/**
 * @param {object} soapScene - SOAP JSON
 * @returns {{ xmin,xmax,zmin,zmax, regions: Array, items: Array, objects: Array }}
 */
export function computeMapPayload(soapScene) {
  const objects = soapScene.objects || [];
  const regions = soapScene.regions || [];
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

  const regionRects = [];
  for (const r of regions) {
    const ids = r.contained_object_ids || [];
    let rb = null;
    for (const id of ids) {
      const o = objects.find((x) => x.id === id);
      if (!o) continue;
      const xz = aabbXZ(o.bounds);
      if (xz) rb = mergeBounds(rb, xz);
    }
    if (rb) regionRects.push({ id: r.id, name: r.name || r.id, rb });
  }

  // 注意：不可再写简写 `regions`，否则会覆盖上面的几何包络数组
  return {
    xmin,
    xmax,
    zmin,
    zmax,
    regionBounds: regionRects,
    items,
    objects,
    soapRegions: regions,
  };
}
