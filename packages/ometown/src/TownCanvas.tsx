import { useEffect, useRef } from 'react'
import { Application, Container, Graphics, Sprite, Text, TextStyle, Assets } from 'pixi.js'
import { worldToScreen, depthIndex, HALF_W, HALF_H, type CharacterData } from './iso'

/*
 * Kenney Isometric Tiles (CC0)
 * Ground: 132×83  (66px diamond + 17px depth)
 * Buildings: ~132×127 (taller)
 * Grid spacing: 132×66 (diamond face only)
 */

// ─── Tile registry ───
const TILES = {
  // Ground (132×83)
  grass_1:      'grass_1.png',
  grass_2:      'grass_2.png',
  grass_3:      'grass_3.png',
  dirt_1:       'dirt_1.png',
  water_1:      'water_1.png',
  water_2:      'water_2.png',
  water_3:      'water_3.png',
  road_cross:   'road_cross.png',
  road_side:    'road_side.png',
  road_corner:  'road_corner.png',
  fountain:     'fountain.png',
  // Buildings (132×127 or 99×85)
  shop_1:       'shop_1.png',
  shop_2:       'shop_2.png',
  shop_3:       'shop_3.png',
  cafe:         'cafe.png',
  store:        'store.png',
  house_1:      'house_1.png',
  house_2:      'house_2.png',
  city_house:   'city_house.png',
  pool:         'pool.png',
  // Nature
  hill_1:       'hill_1.png',
  river_1:      'river_1.png',
  river_2:      'river_2.png',
  dirt_water:   'dirt_water.png',
} as const

type TileKey = keyof typeof TILES

// ─── 14×14 Town Map ───
// G = grass, R = road, W = water, D = dirt
// Buildings/features are placed as overlays on grass tiles
const G1: TileKey = 'grass_1'
const G2: TileKey = 'grass_2'
const G3: TileKey = 'grass_3'
const RC: TileKey = 'road_cross'
const RS: TileKey = 'road_side'
const W1: TileKey = 'water_1'
const W2: TileKey = 'water_2'
const W3: TileKey = 'water_3'
const D1: TileKey = 'dirt_1'

const GROUND_MAP: TileKey[][] = [
  // 0    1    2    3    4    5    6    7    8    9   10   11
  [G1,  G2,  G3,  G1,  G2,  RS,  G1,  G2,  G3,  G1,  G2,  G3],  // 0
  [G2,  G1,  G3,  G2,  G1,  RS,  G2,  G1,  G3,  G2,  G1,  G2],  // 1
  [G3,  G2,  G1,  G3,  G2,  RS,  G3,  G1,  G2,  G3,  G2,  G1],  // 2
  [G1,  G3,  G2,  G1,  G3,  RS,  G1,  G3,  G2,  G1,  G3,  G2],  // 3
  [G2,  G1,  G3,  G2,  G1,  RS,  G2,  G1,  G3,  G2,  G1,  G3],  // 4
  [RS,  RS,  RS,  RS,  RS,  RC,  RS,  RS,  RS,  RS,  RS,  RS],  // 5  ← main road
  [G1,  G2,  G1,  G3,  G2,  RS,  G1,  G2,  G1,  G3,  G2,  G1],  // 6
  [G2,  G1,  G3,  G2,  G1,  RS,  G2,  D1,  D1,  G2,  G1,  G3],  // 7
  [G1,  G3,  G2,  G1,  G3,  RS,  D1,  W1,  W2,  D1,  G3,  G2],  // 8  ← pond
  [G3,  G2,  G1,  G3,  G2,  RS,  D1,  W3,  W1,  D1,  G2,  G1],  // 9
  [G1,  G3,  G2,  G1,  G3,  RS,  G1,  D1,  D1,  G2,  G3,  G2],  // 10
  [G2,  G1,  G3,  G2,  G1,  RS,  G2,  G1,  G3,  G2,  G1,  G3],  // 11
]

// Overlay: buildings and features placed ON TOP of ground tiles
interface Overlay { tile: TileKey; col: number; row: number }
const OVERLAYS: Overlay[] = [
  // Upper-left: commercial district
  { tile: 'shop_1',    col: 1,  row: 1 },
  { tile: 'shop_2',    col: 3,  row: 1 },
  { tile: 'store',     col: 1,  row: 3 },
  { tile: 'cafe',      col: 3,  row: 3 },
  // Upper-right: residential
  { tile: 'house_1',   col: 7,  row: 1 },
  { tile: 'house_2',   col: 9,  row: 1 },
  { tile: 'city_house', col: 7, row: 3 },
  { tile: 'shop_3',    col: 9,  row: 3 },
  // Lower-left: homes
  { tile: 'house_1',   col: 1,  row: 7 },
  { tile: 'shop_1',    col: 3,  row: 7 },
  { tile: 'house_2',   col: 1,  row: 9 },
  // Nature: hills near pond
  { tile: 'hill_1',    col: 10, row: 8 },
  { tile: 'hill_1',    col: 10, row: 10 },
]

const DEMO_OMES: CharacterData[] = [
  { id: 'my_ome', name: 'My Ome', col: 4, row: 4, direction: 'down', state: 'idle', paletteIndex: 0 },
  { id: 'baker', name: 'Baker', col: 2, row: 2, direction: 'right', state: 'idle', paletteIndex: 1, accessory: 'hat_chef' },
  { id: 'gardener', name: 'Gardener', col: 8, row: 9, direction: 'left', state: 'idle', paletteIndex: 5 },
  { id: 'merchant', name: 'Merchant', col: 8, row: 2, direction: 'down', state: 'idle', paletteIndex: 8 },
  { id: 'fisher', name: 'Fisher', col: 2, row: 8, direction: 'right', state: 'idle', paletteIndex: 3 },
]

interface Props {
  onOmeClick: (ome: CharacterData) => void
}

export function TownCanvas({ onOmeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current

    const app = new Application()
    let destroyed = false

    const init = async () => {
      await app.init({
        preference: 'webgl',
        width: el.clientWidth,
        height: el.clientHeight,
        background: 0x87CEEB, // sky blue background
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      })

      if (destroyed) return
      el.appendChild(app.canvas as HTMLCanvasElement)

      // Load all tile textures
      const textures = new Map<string, Awaited<ReturnType<typeof Assets.load>>>()
      for (const [name, file] of Object.entries(TILES)) {
        try {
          const tex = await Assets.load(`./tiles/${file}`)
          textures.set(name, tex)
        } catch { /* skip missing */ }
      }

      // World container
      const world = new Container()
      world.sortableChildren = true
      app.stage.addChild(world)

      // Center
      world.x = app.screen.width / 2
      world.y = app.screen.height / 4

      const ROWS = GROUND_MAP.length
      const COLS = GROUND_MAP[0].length

      // ─── Render ground ───
      for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
          const tileKey = GROUND_MAP[row][col]
          const { x, y } = worldToScreen(col, row)
          const tex = textures.get(tileKey)

          if (tex) {
            const sprite = new Sprite(tex)
            // Anchor at bottom-center of diamond face (center-x, ~60% down for 132×83 tiles)
            sprite.anchor.set(0.5, 0.6)
            sprite.x = x
            sprite.y = y
            sprite.zIndex = depthIndex(col, row)
            world.addChild(sprite)
          } else {
            // Fallback colored diamond
            const g = new Graphics()
            g.moveTo(0, -HALF_H)
            g.lineTo(HALF_W, 0)
            g.lineTo(0, HALF_H)
            g.lineTo(-HALF_W, 0)
            g.closePath()
            g.fill({ color: 0x6aaa3a, alpha: 0.6 })
            g.x = x
            g.y = y
            g.zIndex = depthIndex(col, row)
            world.addChild(g)
          }
        }
      }

      // ─── Render overlays (buildings, features) ───
      for (const ov of OVERLAYS) {
        const { x, y } = worldToScreen(ov.col, ov.row)
        const tex = textures.get(ov.tile)

        if (tex) {
          const sprite = new Sprite(tex)
          // Buildings anchor at bottom-center so they "sit" on the tile
          sprite.anchor.set(0.5, 0.75)
          sprite.x = x
          sprite.y = y
          sprite.zIndex = depthIndex(ov.col, ov.row, 2)
          world.addChild(sprite)
        }
      }

      // ─── Render characters ───
      const palette = [0x3a7bd5, 0xd44a3a, 0x4a9a5a, 0xd4943a, 0x9a4ad4,
                       0x3ad4a0, 0xd43a8a, 0x8ad43a, 0xd4c43a, 0x3abbd4]
      const omeSprites = new Map<string, Container>()

      for (const ome of DEMO_OMES) {
        const { x, y } = worldToScreen(ome.col, ome.row)
        const c = new Container()
        c.x = x
        c.y = y - 30
        c.zIndex = depthIndex(ome.col, ome.row, 3)
        c.eventMode = 'static'
        c.cursor = 'pointer'
        c.on('pointerdown', () => onOmeClick(ome))

        const color = palette[ome.paletteIndex % palette.length]

        // Glow for player's Ome
        if (ome.id === 'my_ome') {
          const glow = new Graphics()
          glow.circle(0, 0, 24)
          glow.fill({ color: 0xFFD700, alpha: 0.2 })
          c.addChild(glow)
        }

        // Shadow
        const shadow = new Graphics()
        shadow.ellipse(0, 8, 12, 6)
        shadow.fill({ color: 0x000000, alpha: 0.2 })
        c.addChild(shadow)

        // Body
        const body = new Graphics()
        body.roundRect(-8, -8, 16, 20, 4)
        body.fill({ color })
        c.addChild(body)

        // Head
        const head = new Graphics()
        head.circle(0, -16, 10)
        head.fill({ color: 0xFFDDBB })
        c.addChild(head)

        // Eyes
        const eyes = new Graphics()
        eyes.circle(-3, -18, 2)
        eyes.fill({ color: 0x333333 })
        eyes.circle(3, -18, 2)
        eyes.fill({ color: 0x333333 })
        c.addChild(eyes)

        // Hair
        const hair = new Graphics()
        hair.arc(0, -18, 10, Math.PI, 0)
        hair.fill({ color: color > 0x888888 ? 0x4a3520 : 0x2a1a10 })
        c.addChild(hair)

        // Name
        const nameText = new Text({
          text: ome.name,
          style: new TextStyle({
            fontSize: 11,
            fill: '#ffffff',
            fontFamily: 'system-ui',
            fontWeight: 'bold',
            stroke: { color: '#000000', width: 3 },
          }),
        })
        nameText.anchor.set(0.5, 1)
        nameText.y = -32
        c.addChild(nameText)

        world.addChild(c)
        omeSprites.set(ome.id, c)
      }

      // ─── Camera controls ───
      let dragging = false
      let dragStart = { x: 0, y: 0 }
      let worldStart = { x: 0, y: 0 }

      app.stage.eventMode = 'static'
      app.stage.hitArea = app.screen

      app.stage.on('pointerdown', (e) => {
        dragging = true
        dragStart = { x: e.global.x, y: e.global.y }
        worldStart = { x: world.x, y: world.y }
      })
      app.stage.on('pointermove', (e) => {
        if (!dragging) return
        world.x = worldStart.x + (e.global.x - dragStart.x)
        world.y = worldStart.y + (e.global.y - dragStart.y)
      })
      app.stage.on('pointerup', () => { dragging = false })
      app.stage.on('pointerupoutside', () => { dragging = false })

      el.addEventListener('wheel', (e) => {
        e.preventDefault()
        const s = world.scale.x * (e.deltaY > 0 ? 0.92 : 1.08)
        world.scale.set(Math.max(0.25, Math.min(3, s)))
      }, { passive: false })

      // ─── Idle bob ───
      let tick = 0
      app.ticker.add(() => {
        tick++
        for (const [id, sprite] of omeSprites) {
          const base = DEMO_OMES.find(o => o.id === id)!
          const { y } = worldToScreen(base.col, base.row)
          sprite.y = y - 30 + Math.sin(tick * 0.06 + base.col * 1.5) * 2
        }
      })
    }

    init().catch((err) => {
      console.error('OmeTown init failed:', err)
      if (el) {
        el.innerHTML = `<div style="color:#c8a96e;padding:20px;font-family:system-ui">
          <h2>OmeTown failed to start</h2>
          <pre style="color:#f66;margin-top:8px;white-space:pre-wrap">${err?.message ?? err}</pre>
        </div>`
      }
    })

    return () => {
      destroyed = true
      try { app.destroy(true, { children: true }) } catch { /* */ }
    }
  }, [onOmeClick])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
