/**
 * Phaser 3 像素风俯视地图（范式参考 Stanford Generative Agents / [GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN)：
 * `pixelArt` + 键盘漫游；此处为程序生成地板与色块，不复制对方 tilemap / 精灵素材）
 */
import Phaser from "phaser";
import { REALITY_COLORS } from "./soap-layout.js";

const TILE = 22;

function hexToInt(h) {
  return parseInt(h.replace("#", ""), 16);
}

export function mountPixelMall(parentId, { onSelect }) {
  let game;

  class MallScene extends Phaser.Scene {
    constructor() {
      super({ key: "MallScene" });
    }

    create() {
      this.onSelectCb = onSelect;
      this.cursors = this.input.keyboard.createCursorKeys();
      this.wasd = this.input.keyboard.addKeys("W,S,A,D");
      this.cam = this.cameras.main;
      this.floorG = this.add.graphics().setDepth(0);
      this.regionG = this.add.graphics().setDepth(1);
      this.entityRoot = this.add.container(0, 0).setDepth(2);
      this.labelRoot = this.add.container(0, 0).setDepth(3);
      this.hudG = this.add.graphics().setDepth(10);
      this.cam._soapInit = false;
    }

    redraw(payload) {
      if (!payload) return;
      this.floorG.clear();
      this.regionG.clear();
      this.hudG.clear();
      this.entityRoot.removeAll(true);
      this.labelRoot.removeAll(true);

      const { xmin, xmax, zmin, zmax, regionBounds, items } = payload;
      const worldW = (xmax - xmin) * TILE;
      const worldH = (zmax - zmin) * TILE;

      this.cam.setBounds(0, 0, worldW, worldH);

      const c1 = 0x1a0f2e;
      const c2 = 0x251b3d;
      const grid = 0x2d1f45;
      const step = TILE;
      for (let px = 0; px < worldW; px += step) {
        for (let py = 0; py < worldH; py += step) {
          const cx = Math.floor(px / step) + Math.floor(py / step);
          this.floorG.fillStyle(cx % 2 === 0 ? c1 : c2, 1);
          this.floorG.fillRect(px, py, step, step);
        }
      }
      this.floorG.lineStyle(1, grid, 0.35);
      for (let x = 0; x <= worldW; x += step) {
        this.floorG.lineBetween(x, 0, x, worldH);
      }
      for (let y = 0; y <= worldH; y += step) {
        this.floorG.lineBetween(0, y, worldW, y);
      }

      this.regionG.lineStyle(2, 0x9b59b6, 0.55);
      for (const rr of regionBounds || []) {
        const b = rr.rb;
        const rx = (b.xmin - xmin) * TILE;
        const ry = (zmax - b.zmax) * TILE;
        const rw = (b.xmax - b.xmin) * TILE;
        const rh = (b.zmax - b.zmin) * TILE;
        this.regionG.strokeRect(rx + 1, ry + 1, Math.max(2, rw - 2), Math.max(2, rh - 2));
      }

      const { roleVisibleIds, selectedId } = payload;

      for (const it of items) {
        const o = it.o;
        const fillC = hexToInt(REALITY_COLORS[o.reality] || REALITY_COLORS.default);
        const dim = roleVisibleIds && !roleVisibleIds.has(o.id);
        const sel = selectedId === o.id;
        const alpha = dim ? 0.22 : 0.52;
        const strokeW = sel ? 4 : 2;
        const strokeC = sel ? 0xf39c12 : 0xffffff;

        if (it.kind === "aabb") {
          const xz = it.xz;
          const rx = (xz.xmin - xmin) * TILE;
          const ry = (zmax - xz.zmax) * TILE;
          const rw = Math.max(TILE * 0.45, (xz.xmax - xz.xmin) * TILE);
          const rh = Math.max(TILE * 0.45, (xz.zmax - xz.zmin) * TILE);
          const rect = this.add.rectangle(rx + rw / 2, ry + rh / 2, rw, rh, fillC, alpha);
          rect.setStrokeStyle(strokeW, strokeC);
          rect.setInteractive({ useHandCursor: true });
          rect.on("pointerdown", () => this.onSelectCb(o.id));
          this.entityRoot.add(rect);
          this._label(rx + 2, ry - 2, o.id, dim);
        } else if (it.x != null) {
          const cx = (it.x - xmin) * TILE;
          const cy = (zmax - it.z) * TILE;
          const dot = this.add.circle(cx, cy, Math.max(6, TILE * 0.35), fillC, alpha);
          dot.setStrokeStyle(strokeW, strokeC);
          dot.setInteractive({ useHandCursor: true });
          dot.on("pointerdown", () => this.onSelectCb(o.id));
          this.entityRoot.add(dot);
          const icon = this.add.text(cx - 6, cy - 18, this._typeIcon(o), {
            fontSize: "16px",
            color: "#ecf0f1",
          });
          this.labelRoot.add(icon);
          this._label(cx - 36, cy + 12, o.id, dim, 11);
        }
      }

      this.hudG.fillStyle(0x000000, 0.45);
      this.hudG.fillRect(8, 8, 218, 56);
      this.hudG.lineStyle(2, 0xf39c12, 0.95);
      this.hudG.strokeRect(8, 8, 218, 56);

      if (!this.cam._soapInit) {
        this.cam.centerOn(worldW / 2, worldH / 2);
        this.cam._soapInit = true;
      }
    }

    _label(x, y, id, dim, size = 12) {
      const t = id.length > 16 ? `${id.slice(0, 14)}…` : id;
      const txt = this.add.text(x, y, t, {
        fontFamily: '"VT323", "Courier New", monospace',
        fontSize: `${size}px`,
        color: dim ? "#5c6b7a" : "#ecf0f1",
        backgroundColor: "#000000aa",
        padding: { x: 4, y: 2 },
      });
      this.labelRoot.add(txt);
    }

    _typeIcon(o) {
      const t = o.type || "";
      if (t.startsWith("npc.")) return "◇";
      if (t.startsWith("robot.")) return "▣";
      if (t.startsWith("mr_game.")) return "✦";
      if (t.includes("store") || t.includes("retail")) return "⌂";
      return "·";
    }

    update() {
      const sp = 14;
      if (this.cursors.left.isDown || this.wasd.A?.isDown) this.cam.scrollX -= sp;
      if (this.cursors.right.isDown || this.wasd.D?.isDown) this.cam.scrollX += sp;
      if (this.cursors.up.isDown || this.wasd.W?.isDown) this.cam.scrollY -= sp;
      if (this.cursors.down.isDown || this.wasd.S?.isDown) this.cam.scrollY += sp;
    }
  }

  const parent = document.getElementById(parentId);
  const w = Math.min(960, parent?.clientWidth || 640);
  const h = 440;

  game = new Phaser.Game({
    type: Phaser.AUTO,
    parent: parentId,
    width: w,
    height: h,
    pixelArt: true,
    roundPixels: true,
    backgroundColor: "#0a0514",
    scene: MallScene,
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    banner: false,
    audio: { noAudio: true },
  });

  return {
    refresh(payload) {
      const tick = () => {
        const s = game?.scene?.getScene("MallScene");
        if (s?.scene?.isActive()) {
          s.redraw(payload);
        } else {
          requestAnimationFrame(tick);
        }
      };
      tick();
    },
    destroy() {
      game?.destroy(true);
      game = null;
    },
  };
}
