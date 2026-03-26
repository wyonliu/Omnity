/**
 * OmeTown Isometric Engine — PixiJS 8 based.
 *
 * Coordinate system:
 *   World: (col, row) grid coordinates
 *   Screen: (x, y) pixel coordinates
 *   Isometric 2:1 diamond projection (30° angle)
 *
 * Tile dimensions: 128×64 px (diamond)
 */

// ─── Constants ───

export const TILE_W = 128
export const TILE_H = 64
export const HALF_W = TILE_W / 2
export const HALF_H = TILE_H / 2

// ─── Coordinate Transforms ───

/** World grid (col, row) → screen pixel (x, y) */
export function worldToScreen(col: number, row: number): { x: number; y: number } {
  return {
    x: (col - row) * HALF_W,
    y: (col + row) * HALF_H,
  }
}

/** Screen pixel (x, y) → world grid (col, row) */
export function screenToWorld(x: number, y: number): { col: number; row: number } {
  return {
    col: (x / HALF_W + y / HALF_H) / 2,
    row: (y / HALF_H - x / HALF_W) / 2,
  }
}

/** Snap screen coords to nearest grid cell */
export function snapToGrid(x: number, y: number): { col: number; row: number } {
  const { col, row } = screenToWorld(x, y)
  return { col: Math.round(col), row: Math.round(row) }
}

// ─── Depth Sorting ───

/** Z-index for isometric depth sorting: tiles further back render first */
export function depthIndex(col: number, row: number, layer: number = 0): number {
  return (col + row) * 100 + layer
}

// ─── Map Data ───

export interface TileData {
  /** Tile type ID from atlas (e.g., "grass_01", "wall_wood_1x1") */
  type: string
  /** Collision: can characters walk here? */
  walkable: boolean
  /** Optional elevation (0 = ground, 1 = raised) */
  elevation?: number
}

export interface MapLayer {
  name: string
  tiles: (TileData | null)[][]  // [row][col]
}

export interface TownMap {
  width: number
  height: number
  layers: MapLayer[]  // ground, buildings, decoration (back to front)
}

// ─── Character ───

export type Direction = 'down' | 'up' | 'left' | 'right'
export type CharState = 'idle' | 'walk' | 'sit'

export interface CharacterData {
  id: string
  name: string
  col: number
  row: number
  direction: Direction
  state: CharState
  paletteIndex: number  // index into palette.json character_palettes
  accessory?: string    // e.g., "hat_farmer"
  speech?: string       // current speech bubble text
}

// ─── Pathfinding (A* on isometric grid) ───

interface PathNode {
  col: number
  row: number
  g: number  // cost from start
  h: number  // heuristic to goal
  f: number  // g + h
  parent: PathNode | null
}

/** Manhattan distance on isometric grid */
function heuristic(a: { col: number; row: number }, b: { col: number; row: number }): number {
  return Math.abs(a.col - b.col) + Math.abs(a.row - b.row)
}

/** A* pathfinding on the ground layer */
export function findPath(
  map: TownMap,
  start: { col: number; row: number },
  goal: { col: number; row: number },
): { col: number; row: number }[] {
  const ground = map.layers[0]
  if (!ground) return []

  const isWalkable = (col: number, row: number): boolean => {
    if (row < 0 || row >= map.height || col < 0 || col >= map.width) return false
    const tile = ground.tiles[row]?.[col]
    return tile?.walkable ?? false
  }

  if (!isWalkable(goal.col, goal.row)) return []

  const open: PathNode[] = [{
    ...start, g: 0, h: heuristic(start, goal), f: heuristic(start, goal), parent: null
  }]
  const closed = new Set<string>()
  const key = (c: number, r: number) => `${c},${r}`

  while (open.length > 0) {
    // Pick lowest f
    open.sort((a, b) => a.f - b.f)
    const current = open.shift()!
    const ck = key(current.col, current.row)

    if (current.col === goal.col && current.row === goal.row) {
      // Reconstruct path
      const path: { col: number; row: number }[] = []
      let node: PathNode | null = current
      while (node) {
        path.unshift({ col: node.col, row: node.row })
        node = node.parent
      }
      return path
    }

    closed.add(ck)

    // 4-directional neighbors (iso grid)
    const neighbors = [
      { col: current.col + 1, row: current.row },
      { col: current.col - 1, row: current.row },
      { col: current.col, row: current.row + 1 },
      { col: current.col, row: current.row - 1 },
    ]

    for (const n of neighbors) {
      const nk = key(n.col, n.row)
      if (closed.has(nk) || !isWalkable(n.col, n.row)) continue

      const g = current.g + 1
      const existing = open.find(o => o.col === n.col && o.row === n.row)

      if (!existing) {
        open.push({ ...n, g, h: heuristic(n, goal), f: g + heuristic(n, goal), parent: current })
      } else if (g < existing.g) {
        existing.g = g
        existing.f = g + existing.h
        existing.parent = current
      }
    }
  }

  return [] // No path found
}

// ─── Animation Helpers ───

/** Lerp between two screen positions for smooth movement */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * Math.min(1, Math.max(0, t))
}

/** Get direction from one grid cell to another */
export function getDirection(
  from: { col: number; row: number },
  to: { col: number; row: number },
): Direction {
  const dc = to.col - from.col
  const dr = to.row - from.row

  if (dc > 0 && dr >= 0) return 'right'
  if (dc <= 0 && dr > 0) return 'down'
  if (dc < 0 && dr <= 0) return 'left'
  return 'up'
}

// ─── Tiled JSON Loader ───

export interface TiledMap {
  width: number
  height: number
  layers: {
    name: string
    data: number[]
    width: number
    height: number
  }[]
  tilesets: {
    firstgid: number
    name: string
    tilecount: number
    columns: number
    tilewidth: number
    tileheight: number
  }[]
}

/** Convert Tiled JSON export to OmeTown TownMap */
export function loadTiledMap(tiled: TiledMap, tileNames: Map<number, string>): TownMap {
  const layers: MapLayer[] = tiled.layers.map(layer => {
    const tiles: (TileData | null)[][] = []

    for (let row = 0; row < tiled.height; row++) {
      const rowTiles: (TileData | null)[] = []
      for (let col = 0; col < tiled.width; col++) {
        const gid = layer.data[row * tiled.width + col]
        if (gid === 0) {
          rowTiles.push(null)
        } else {
          const type = tileNames.get(gid) ?? `tile_${gid}`
          const isPath = type.includes('path') || type.includes('plaza') || type.includes('bridge')
          const isGround = type.includes('grass') || type.includes('dirt')
          rowTiles.push({
            type,
            walkable: layer.name === 'ground' ? (isPath || isGround) : false,
          })
        }
      }
      tiles.push(rowTiles)
    }

    return { name: layer.name, tiles }
  })

  return {
    width: tiled.width,
    height: tiled.height,
    layers,
  }
}
