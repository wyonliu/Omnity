import { useEffect, useRef } from 'react'
import { Application, Container, Sprite, Text, TextStyle, Texture, Assets } from 'pixi.js'
import {
  worldToScreen, depthIndex, TILE_W, TILE_H,
  type CharacterData, type TownMap,
} from './iso'

// ─── Tile image paths (served from public/tiles/) ───
const TILE_BASE_URL = './tiles/'

const TILE_FILES: Record<string, string> = {
  grass_01: 'grass_01.png',
  grass_02: 'grass_02.png',
  grass_03: 'grass_03.png',
  grass_04: 'grass_04.png',
  dirt_01: 'dirt_01.png',
  dirt_02: 'dirt_02.png',
  path_straight: 'path_straight.png',
  water_01: 'water_01.png',
  water_02: 'water_02.png',
  flower_bed_01: 'flower_bed_01.png',
  building_house: 'building_house.png',
  building_shop: 'building_shop.png',
  building_cafe: 'building_cafe.png',
  tree_deciduous_01: 'tree_deciduous_01.png',
  tree_deciduous_02: 'tree_deciduous_02.png',
  tree_deciduous_03: 'tree_deciduous_03.png',
  bush_01: 'bush_01.png',
  bush_02: 'bush_02.png',
}

// Fallback colors for tiles when images aren't loaded
const TILE_COLORS: Record<string, number> = {
  grass_01: 0xa0c060,
  grass_02: 0x6d8b4e,
  grass_03: 0x4a7c59,
  grass_04: 0x8ba850,
  dirt_01: 0xc4a882,
  dirt_02: 0x8b7355,
  path_straight: 0xa0936e,
  water_01: 0x4a90d9,
  water_02: 0x5ba3e6,
  flower_bed_01: 0x90c060,
  building_house: 0xd4a574,
  building_shop: 0xe8d8c4,
  building_cafe: 0xc87050,
  tree_deciduous_01: 0x4a8030,
  tree_deciduous_02: 0x90c040,
  tree_deciduous_03: 0x4a8030,
  bush_01: 0x4a8030,
  bush_02: 0x90c040,
}

// ─── Enhanced demo map with buildings & nature ───
type CellDef = { type: string; walkable: boolean }

function cell(type: string, walkable = true): CellDef {
  return { type, walkable }
}

// 12x12 map with paths, buildings, trees, water, flowers
const G1 = () => cell('grass_01')
const G2 = () => cell('grass_02')
const G3 = () => cell('grass_03')
const G4 = () => cell('grass_04')
const P  = () => cell('path_straight')
const D  = () => cell('dirt_01')
const W  = () => cell('water_01')
const W2 = () => cell('water_02')
const FL = () => cell('flower_bed_01')

const GROUND: (() => CellDef)[][] = [
  [G3, G1, G2, G3, G1, P,  P,  G2, G3, G1, G4, G2],
  [G1, G2, FL, G1, G2, P,  P,  G3, G1, G4, G1, G3],
  [G2, G3, G1, G4, G1, P,  P,  G1, G2, G3, G1, G2],
  [G1, G4, G2, G1, G3, P,  P,  G2, G3, G1, G4, G1],
  [G3, G1, G3, G2, G1, P,  P,  G1, D,  D,  G1, G3],
  [P,  P,  P,  P,  P,  P,  P,  P,  P,  P,  P,  P ],
  [P,  P,  P,  P,  P,  P,  P,  P,  P,  P,  P,  P ],
  [G2, G1, G4, G3, G1, P,  P,  G2, G1, G3, G2, G1],
  [G1, G3, G2, G1, G4, P,  P,  W,  W2, G1, G4, G3],
  [G4, G1, G3, G2, G1, P,  P,  W2, W,  G2, G1, G2],
  [G2, G4, G1, FL, G3, P,  P,  G1, G3, G4, G1, G3],
  [G1, G3, G2, G1, G4, P,  P,  G2, G1, G3, G2, G1],
]

// Buildings and nature overlay layer (sparse)
interface OverlayDef { type: string; col: number; row: number }
const OVERLAYS: OverlayDef[] = [
  { type: 'building_house', col: 1, row: 1 },
  { type: 'building_shop',  col: 3, row: 2 },
  { type: 'building_cafe',  col: 1, row: 8 },
  { type: 'building_house', col: 9, row: 1 },
  { type: 'building_shop',  col: 9, row: 9 },
  { type: 'tree_deciduous_01', col: 0, row: 4 },
  { type: 'tree_deciduous_02', col: 10, row: 3 },
  { type: 'tree_deciduous_03', col: 3, row: 10 },
  { type: 'tree_deciduous_01', col: 11, row: 7 },
  { type: 'bush_01', col: 0, row: 0 },
  { type: 'bush_02', col: 11, row: 11 },
  { type: 'bush_01', col: 7, row: 0 },
  { type: 'bush_02', col: 4, row: 11 },
]

const DEMO_MAP: TownMap = {
  width: 12,
  height: 12,
  layers: [{
    name: 'ground',
    tiles: GROUND.map(row => row.map(fn => fn())),
  }],
}

const DEMO_OMES: CharacterData[] = [
  { id: 'my_ome', name: 'My Ome', col: 5, row: 5, direction: 'down', state: 'idle', paletteIndex: 0 },
  { id: 'baker', name: 'Baker', col: 3, row: 4, direction: 'right', state: 'idle', paletteIndex: 1, accessory: 'hat_chef' },
  { id: 'gardener', name: 'Gardener', col: 8, row: 7, direction: 'left', state: 'idle', paletteIndex: 5 },
  { id: 'merchant', name: 'Merchant', col: 6, row: 3, direction: 'down', state: 'idle', paletteIndex: 8 },
]

interface Props {
  onOmeClick: (ome: CharacterData) => void
}

/** Load all tile textures, returns map of tileName -> Texture */
async function loadTileTextures(): Promise<Map<string, Texture>> {
  const textures = new Map<string, Texture>()

  const loadPromises = Object.entries(TILE_FILES).map(async ([name, file]) => {
    try {
      const texture = await Assets.load<Texture>(`${TILE_BASE_URL}${file}`)
      textures.set(name, texture)
    } catch {
      // Tile not found — fallback will be used
    }
  })

  await Promise.all(loadPromises)
  return textures
}

export function TownCanvas({ onOmeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const app = new Application()
    let destroyed = false

    const init = async () => {
      await app.init({
        resizeTo: containerRef.current!,
        background: '#0a0a16',
        antialias: true,
        resolution: window.devicePixelRatio || 1,
      })

      if (destroyed) return
      containerRef.current!.appendChild(app.canvas)

      // Load tile textures (non-blocking — falls back to diamonds)
      const tileTextures = await loadTileTextures()

      // World container (camera target)
      const world = new Container()
      app.stage.addChild(world)

      // Center the map
      const centerX = app.screen.width / 2
      const centerY = app.screen.height / 3
      world.x = centerX
      world.y = centerY

      // ─── Render ground tiles ───
      const map = DEMO_MAP
      const groundLayer = map.layers[0]

      for (let row = 0; row < map.height; row++) {
        for (let col = 0; col < map.width; col++) {
          const tile = groundLayer.tiles[row]?.[col]
          if (!tile) continue

          const { x, y } = worldToScreen(col, row)
          const texture = tileTextures.get(tile.type)

          if (texture) {
            // Real tile sprite
            const sprite = new Sprite(texture)
            sprite.anchor.set(0.5, 0.5)
            sprite.x = x
            sprite.y = y
            sprite.zIndex = depthIndex(col, row)
            world.addChild(sprite)
          } else {
            // Fallback: colored diamond
            const isPath = tile.type.includes('path')
            const color = TILE_COLORS[tile.type]
              ?? (isPath ? 0xa0936e : 0x4a7c59 + ((row + col) % 3) * 0x080808)

            const g = new (await import('pixi.js')).Graphics()
            g.poly([
              { x: 0, y: -TILE_H / 2 },
              { x: TILE_W / 2, y: 0 },
              { x: 0, y: TILE_H / 2 },
              { x: -TILE_W / 2, y: 0 },
            ])
            g.fill({ color, alpha: isPath ? 0.7 : 0.5 })
            g.stroke({ color: 0x1a1a2e, width: 1, alpha: 0.3 })
            g.x = x
            g.y = y
            g.zIndex = depthIndex(col, row)
            world.addChild(g)
          }
        }
      }

      // ─── Render overlay objects (buildings, trees, bushes) ───
      for (const overlay of OVERLAYS) {
        const { x, y } = worldToScreen(overlay.col, overlay.row)
        const texture = tileTextures.get(overlay.type)

        if (texture) {
          const sprite = new Sprite(texture)
          sprite.anchor.set(0.5, 1.0)  // anchor at bottom-center for buildings/trees
          sprite.x = x
          sprite.y = y + TILE_H / 2    // bottom of the isometric cell
          sprite.zIndex = depthIndex(overlay.col, overlay.row, 2)
          world.addChild(sprite)
        } else {
          // Fallback: colored diamond with label
          const color = TILE_COLORS[overlay.type] ?? 0x808080
          const isBuilding = overlay.type.includes('building')
          const g = new (await import('pixi.js')).Graphics()

          if (isBuilding) {
            // Building placeholder: diamond + box
            g.poly([
              { x: 0, y: -TILE_H / 2 },
              { x: TILE_W / 2, y: 0 },
              { x: 0, y: TILE_H / 2 },
              { x: -TILE_W / 2, y: 0 },
            ])
            g.fill({ color, alpha: 0.6 })
            g.rect(-TILE_W / 4, -TILE_H, TILE_W / 2, TILE_H / 2)
            g.fill({ color, alpha: 0.5 })
          } else {
            // Nature placeholder: circle
            g.circle(0, -12, 16)
            g.fill({ color, alpha: 0.6 })
          }

          g.x = x
          g.y = y
          g.zIndex = depthIndex(overlay.col, overlay.row, 2)
          world.addChild(g)
        }
      }

      // ─── Render characters ───
      const omes = DEMO_OMES
      const omeSprites: Map<string, Container> = new Map()

      for (const ome of omes) {
        const { x, y } = worldToScreen(ome.col, ome.row)
        const container = new Container()
        container.x = x
        container.y = y - 24 // Offset up so character stands on tile
        container.zIndex = depthIndex(ome.col, ome.row, 3)
        container.eventMode = 'static'
        container.cursor = 'pointer'
        container.on('pointerdown', () => onOmeClick(ome))

        // Placeholder: colored circle with label
        const palette = [0x5080c0, 0xc85040, 0x4070a0, 0x6b8050, 0xd07040, 0x507040,
                         0x3080a0, 0x805080, 0xc8a040, 0x50a080, 0xc07080, 0x505870]
        const bodyColor = palette[ome.paletteIndex % palette.length]

        const body = new (await import('pixi.js')).Graphics()
        // Simple character: circle body + smaller head
        body.circle(0, 0, 14)
        body.fill({ color: bodyColor })
        body.circle(0, -18, 10)
        body.fill({ color: 0xf0c8a0 }) // skin
        container.addChild(body)

        // Name label
        const nameText = new Text({
          text: ome.name,
          style: new TextStyle({
            fontSize: 11,
            fill: '#e0e0e0',
            fontFamily: 'system-ui',
            dropShadow: {
              color: '#000000',
              blur: 2,
              distance: 1,
            },
          }),
        })
        nameText.anchor.set(0.5, 1)
        nameText.y = -34
        container.addChild(nameText)

        // Highlight "My Ome"
        if (ome.id === 'my_ome') {
          const glow = new (await import('pixi.js')).Graphics()
          glow.circle(0, 0, 20)
          glow.fill({ color: 0xc8a96e, alpha: 0.15 })
          container.addChildAt(glow, 0)
        }

        world.addChild(container)
        omeSprites.set(ome.id, container)
      }

      // Enable depth sorting
      world.sortableChildren = true

      // ─── Camera drag ───
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

      // ─── Zoom ───
      containerRef.current!.addEventListener('wheel', (e) => {
        e.preventDefault()
        const scale = world.scale.x * (e.deltaY > 0 ? 0.9 : 1.1)
        world.scale.set(Math.max(0.3, Math.min(3, scale)))
      }, { passive: false })

      // ─── Idle animation loop ───
      let tick = 0
      app.ticker.add(() => {
        tick++
        // Gentle bob for characters
        for (const [id, sprite] of omeSprites) {
          const base = omes.find(o => o.id === id)!
          const { y } = worldToScreen(base.col, base.row)
          sprite.y = y - 24 + Math.sin(tick * 0.05 + base.col) * 2
        }
      })
    }

    init()

    return () => {
      destroyed = true
      app.destroy(true, { children: true })
    }
  }, [onOmeClick])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
