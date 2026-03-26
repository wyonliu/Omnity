import { useEffect, useRef } from 'react'
import { Application, Container, Sprite, Text, TextStyle } from 'pixi.js'
import {
  worldToScreen, depthIndex, TILE_W, TILE_H,
  type CharacterData, type TownMap,
} from './iso'

// Demo map (placeholder until Tiled integration)
const DEMO_MAP: TownMap = {
  width: 12,
  height: 12,
  layers: [{
    name: 'ground',
    tiles: Array.from({ length: 12 }, (_, row) =>
      Array.from({ length: 12 }, (_, col) => {
        // Simple street layout: path in middle, grass elsewhere
        const isPath = (row === 5 || row === 6) || (col === 5 || col === 6)
        return {
          type: isPath ? 'path_straight' : `grass_0${(row + col) % 4 + 1}`,
          walkable: true,
        }
      })
    ),
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

          // Placeholder: colored diamond shapes
          // TODO: Replace with atlas sprites when art is generated
          const isPath = tile.type.includes('path')
          const color = isPath ? 0xa0936e : 0x4a7c59 + ((row + col) % 3) * 0x080808

          const g = new (await import('pixi.js')).Graphics()
          g.poly([
            { x: 0, y: -TILE_H / 2 },       // top
            { x: TILE_W / 2, y: 0 },         // right
            { x: 0, y: TILE_H / 2 },         // bottom
            { x: -TILE_W / 2, y: 0 },        // left
          ])
          g.fill({ color, alpha: isPath ? 0.7 : 0.5 })
          g.stroke({ color: 0x1a1a2e, width: 1, alpha: 0.3 })
          g.x = x
          g.y = y
          g.zIndex = depthIndex(col, row)
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
        container.zIndex = depthIndex(ome.col, ome.row, 1)
        container.eventMode = 'static'
        container.cursor = 'pointer'
        container.on('pointerdown', () => onOmeClick(ome))

        // Placeholder: colored circle with label
        // TODO: Replace with sprite sheet when art is generated
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
