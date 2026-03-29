import { useEffect, useRef } from 'react'
import { Application, Container, Graphics, Sprite, Text, TextStyle, Assets, Spritesheet, AnimatedSprite, Texture } from 'pixi.js'
import { worldToScreen, depthIndex, HALF_W, HALF_H, type CharacterData, type Direction } from './iso'

/*
 * OmeTown — Kenney CC0 Isometric City + Professional Character Sprites
 *
 * Features:
 *   - Kenney isometric tile map (18×18)
 *   - Kenney prototype character sprites (8-dir, idle+walk animation)
 *   - Autonomous NPC wandering (A* pathfinding)
 *   - Speech bubbles and emoji indicators
 *   - Click-to-chat interaction
 */

// ─── Tile ID → filename mapping ───
const T = {
  sidewalk:      'cityTiles_095.png',
  sidewalk2:     'cityTiles_088.png',
  sidewalk3:     'cityTiles_081.png',
  road:          'cityTiles_094.png',
  road2:         'cityTiles_087.png',
  roadLine:      'cityTiles_053.png',
  roadLineB:     'cityTiles_045.png',
  roadCross:     'cityTiles_021.png',
  treesBeige:    'cityTiles_038.png',
  treesDark:     'cityTiles_067.png',
  parkGarden:    'cityTiles_083.png',
  parkLawn:      'cityTiles_075.png',
  parkL:         'cityTiles_062.png',
  parkStrip:     'cityTiles_054.png',
  greenField:    'cityTiles_044.png',
  greenRoad:     'cityTiles_061.png',
  greenRoad2:    'cityTiles_051.png',
  greenRoad3:    'cityTiles_055.png',
  pool:          'cityTiles_039.png',
  fountain:      'cityTiles_042.png',
  lampPost:      'cityTiles_043.png',
  lampPost2:     'cityTiles_065.png',
  bldTallA:      'buildingTiles_001.png',
  bldTallB:      'buildingTiles_002.png',
  bldTallC:      'buildingTiles_003.png',
  bldTallD:      'buildingTiles_004.png',
  bldTallE:      'buildingTiles_009.png',
  bldTallF:      'buildingTiles_010.png',
  bldTallG:      'buildingTiles_012.png',
  bldTallH:      'buildingTiles_014.png',
  bldTallI:      'buildingTiles_017.png',
  bldTallJ:      'buildingTiles_018.png',
  bldTallK:      'buildingTiles_020.png',
  bldTallL:      'buildingTiles_021.png',
  bldTallM:      'buildingTiles_022.png',
  bldTallN:      'buildingTiles_026.png',
  bldTallO:      'buildingTiles_028.png',
  bldTallP:      'buildingTiles_029.png',
  bldTallQ:      'buildingTiles_030.png',
  bldTallR:      'buildingTiles_034.png',
  bldTallS:      'buildingTiles_036.png',
  bldTallT:      'buildingTiles_037.png',
  bldTallU:      'buildingTiles_041.png',
  bldTallV:      'buildingTiles_042.png',
  bldXtallA:     'buildingTiles_027.png',
  bldXtallB:     'buildingTiles_035.png',
  bldXtallC:     'buildingTiles_040.png',
  bldXtallD:     'buildingTiles_046.png',
  bld2stA:       'buildingTiles_011.png',
  bld2stB:       'buildingTiles_019.png',
  bld2stC:       'buildingTiles_025.png',
  bld2stD:       'buildingTiles_033.png',
  shopRedA:      'buildingTiles_005.png',
  shopRedB:      'buildingTiles_013.png',
  shopBlueA:     'buildingTiles_007.png',
  shopBlueB:     'buildingTiles_015.png',
  shopGreenA:    'buildingTiles_006.png',
  shopGreenB:    'buildingTiles_008.png',
  shopWhiteA:    'buildingTiles_000.png',
  shopWhiteB:    'buildingTiles_016.png',
  comA:          'buildingTiles_092.png',
  comB:          'buildingTiles_093.png',
  comC:          'buildingTiles_099.png',
  comD:          'buildingTiles_100.png',
  comE:          'buildingTiles_101.png',
  comF:          'buildingTiles_106.png',
  comG:          'buildingTiles_107.png',
  comH:          'buildingTiles_108.png',
  comI:          'buildingTiles_109.png',
  comJ:          'buildingTiles_113.png',
  comK:          'buildingTiles_114.png',
  comL:          'buildingTiles_115.png',
  comM:          'buildingTiles_116.png',
  comN:          'buildingTiles_117.png',
  comO:          'buildingTiles_122.png',
  comP:          'buildingTiles_123.png',
  comQ:          'buildingTiles_124.png',
  comR:          'buildingTiles_125.png',
} as const

type TileId = keyof typeof T

// Per-file anchor Y
const FILE_ANCHOR_Y: Record<string, number> = {
  'cityTiles_021.png': 0.317, 'cityTiles_038.png': 0.317, 'cityTiles_039.png': 0.317,
  'cityTiles_042.png': 0.317, 'cityTiles_043.png': 0.317, 'cityTiles_044.png': 0.317,
  'cityTiles_045.png': 0.317, 'cityTiles_051.png': 0.317, 'cityTiles_053.png': 0.317,
  'cityTiles_055.png': 0.327, 'cityTiles_061.png': 0.327, 'cityTiles_062.png': 0.327,
  'cityTiles_065.png': 0.317, 'cityTiles_067.png': 0.327, 'cityTiles_075.png': 0.327,
  'cityTiles_083.png': 0.327, 'cityTiles_054.png': 0.327,
  'cityTiles_080.png': 0.333, 'cityTiles_081.png': 0.327, 'cityTiles_087.png': 0.333,
  'cityTiles_088.png': 0.327, 'cityTiles_094.png': 0.333, 'cityTiles_095.png': 0.327,
  'buildingTiles_000.png': 0.294, 'buildingTiles_001.png': 0.465,
  'buildingTiles_002.png': 0.465, 'buildingTiles_003.png': 0.465,
  'buildingTiles_004.png': 0.465, 'buildingTiles_005.png': 0.444,
  'buildingTiles_006.png': 0.444, 'buildingTiles_007.png': 0.294,
  'buildingTiles_008.png': 0.294, 'buildingTiles_009.png': 0.465,
  'buildingTiles_010.png': 0.465, 'buildingTiles_011.png': 0.469,
  'buildingTiles_012.png': 0.465, 'buildingTiles_013.png': 0.444,
  'buildingTiles_014.png': 0.465, 'buildingTiles_015.png': 0.294,
  'buildingTiles_016.png': 0.294, 'buildingTiles_017.png': 0.465,
  'buildingTiles_018.png': 0.465, 'buildingTiles_019.png': 0.469,
  'buildingTiles_020.png': 0.465, 'buildingTiles_021.png': 0.465,
  'buildingTiles_022.png': 0.465, 'buildingTiles_025.png': 0.469,
  'buildingTiles_026.png': 0.465, 'buildingTiles_027.png': 0.477,
  'buildingTiles_028.png': 0.465, 'buildingTiles_029.png': 0.465,
  'buildingTiles_030.png': 0.465, 'buildingTiles_033.png': 0.469,
  'buildingTiles_034.png': 0.465, 'buildingTiles_035.png': 0.477,
  'buildingTiles_036.png': 0.465, 'buildingTiles_037.png': 0.472,
  'buildingTiles_040.png': 0.477, 'buildingTiles_041.png': 0.465,
  'buildingTiles_042.png': 0.472, 'buildingTiles_046.png': 0.477,
  'buildingTiles_092.png': 0.465, 'buildingTiles_093.png': 0.465,
  'buildingTiles_099.png': 0.465, 'buildingTiles_100.png': 0.465,
  'buildingTiles_101.png': 0.465, 'buildingTiles_106.png': 0.465,
  'buildingTiles_107.png': 0.465, 'buildingTiles_108.png': 0.465,
  'buildingTiles_109.png': 0.465, 'buildingTiles_113.png': 0.465,
  'buildingTiles_114.png': 0.465, 'buildingTiles_115.png': 0.465,
  'buildingTiles_116.png': 0.465, 'buildingTiles_117.png': 0.465,
  'buildingTiles_122.png': 0.465, 'buildingTiles_123.png': 0.465,
  'buildingTiles_124.png': 0.465, 'buildingTiles_125.png': 0.465,
}

function anchorY(id: TileId): number {
  return FILE_ANCHOR_Y[T[id]] ?? 0.33
}

// ─── 18×18 Ground Map ───
const SW = 'sidewalk'   as TileId
const RL = 'roadLine'   as TileId
const RC = 'roadCross'  as TileId
const TB = 'treesBeige'  as TileId
const GD = 'parkGarden' as TileId
const GL = 'parkLawn'   as TileId
const GP = 'parkL'      as TileId
const GS = 'parkStrip'  as TileId
const GF = 'greenField' as TileId
const PL = 'pool'       as TileId
const FT = 'fountain'   as TileId
const LP = 'lampPost'   as TileId

const GROUND_MAP: TileId[][] = [
  [ TB, GD, GL, TB, GD, RL, TB, GL, GD, GL, TB, GD, RL, GL, GD, TB, GL, TB],
  [ GL, SW, GS, SW, LP, RL, GS, GF, GS, GF, GS, GP, RL, SW, GS, LP, SW, GD],
  [ GD, SW, SW, SW, GS, RL, GF, SW, SW, SW, SW, GF, RL, SW, SW, SW, GS, GL],
  [ TB, SW, SW, SW, SW, RL, GS, SW, SW, SW, GS, SW, RL, SW, SW, SW, SW, TB],
  [ GD, LP, GS, SW, SW, RL, LP, GS, LP, GS, SW, LP, RL, GS, SW, SW, LP, GL],
  [ RL, RL, RL, RL, RL, RC, RL, RL, RL, RL, RL, RL, RC, RL, RL, RL, RL, RL],
  [ TB, GS, SW, SW, LP, RL, GD, GL, TB, GL, GD, TB, RL, SW, GS, LP, GS, TB],
  [ GL, SW, SW, GS, SW, RL, GL, GD, GS, GD, GL, GD, RL, SW, SW, GS, SW, GD],
  [ GD, SW, SW, SW, SW, RL, TB, GS, FT, GS, TB, GL, RL, SW, SW, SW, SW, GL],
  [ GL, SW, GS, SW, SW, RL, GL, GD, GS, GD, GL, GD, RL, GS, SW, SW, SW, TB],
  [ TB, LP, SW, GS, SW, RL, GD, GL, TB, GL, GD, TB, RL, SW, GS, LP, SW, GL],
  [ GD, SW, SW, SW, SW, RL, TB, PL, GL, PL, TB, GL, RL, SW, SW, SW, GS, GD],
  [ RL, RL, RL, RL, RL, RC, RL, RL, RL, RL, RL, RL, RC, RL, RL, RL, RL, RL],
  [ GL, LP, SW, GS, SW, RL, SW, GS, SW, GS, SW, LP, RL, GS, SW, LP, SW, GL],
  [ TB, SW, SW, SW, GS, RL, GS, SW, SW, SW, GS, SW, RL, SW, SW, SW, SW, TB],
  [ GD, SW, GS, SW, LP, RL, SW, SW, GS, SW, LP, SW, RL, SW, GS, SW, SW, GD],
  [ GL, SW, SW, SW, GS, RL, LP, SW, SW, SW, SW, GS, RL, SW, SW, GS, SW, GL],
  [ TB, GL, GD, TB, GL, RL, TB, GD, GL, GD, TB, GL, RL, GD, TB, GL, GD, TB],
]

// Building overlays
interface Overlay { tile: TileId; col: number; row: number }
const OVERLAYS: Overlay[] = [
  // NW: Commercial
  { tile: 'bldXtallA',  col: 1,  row: 1 }, { tile: 'bldTallA',   col: 2,  row: 1 },
  { tile: 'shopRedA',   col: 3,  row: 1 }, { tile: 'bldTallB',   col: 1,  row: 2 },
  { tile: 'bldTallK',   col: 2,  row: 2 }, { tile: 'bldTallL',   col: 3,  row: 2 },
  { tile: 'shopGreenA', col: 4,  row: 2 }, { tile: 'bld2stA',    col: 1,  row: 3 },
  { tile: 'bldTallG',   col: 2,  row: 3 }, { tile: 'shopBlueA',  col: 3,  row: 3 },
  { tile: 'bldTallI',   col: 4,  row: 3 }, { tile: 'shopRedB',   col: 2,  row: 4 },
  { tile: 'bldTallM',   col: 3,  row: 4 },
  // NE: Residential
  { tile: 'bldTallC',   col: 13, row: 1 }, { tile: 'bldTallD',   col: 14, row: 1 },
  { tile: 'shopWhiteA', col: 15, row: 1 }, { tile: 'bldXtallB',  col: 16, row: 1 },
  { tile: 'bldTallE',   col: 13, row: 2 }, { tile: 'bldTallF',   col: 14, row: 2 },
  { tile: 'bldTallH',   col: 15, row: 2 }, { tile: 'comA',       col: 16, row: 2 },
  { tile: 'shopGreenB', col: 13, row: 3 }, { tile: 'bldTallJ',   col: 14, row: 3 },
  { tile: 'bld2stB',    col: 15, row: 3 }, { tile: 'bldTallN',   col: 16, row: 3 },
  { tile: 'comB',       col: 14, row: 4 }, { tile: 'shopBlueB',  col: 15, row: 4 },
  // W: Apartments
  { tile: 'bldTallO',   col: 1,  row: 7 }, { tile: 'bldTallP',   col: 2,  row: 7 },
  { tile: 'comC',       col: 3,  row: 7 }, { tile: 'bldTallQ',   col: 1,  row: 8 },
  { tile: 'comD',       col: 2,  row: 8 }, { tile: 'shopRedA',   col: 3,  row: 8 },
  { tile: 'bldTallR',   col: 1,  row: 9 }, { tile: 'comE',       col: 2,  row: 9 },
  { tile: 'bld2stC',    col: 3,  row: 9 }, { tile: 'bldTallS',   col: 1,  row: 10 },
  { tile: 'comF',       col: 2,  row: 10 }, { tile: 'shopGreenA', col: 3,  row: 10 },
  // E: Offices
  { tile: 'bldXtallC',  col: 16, row: 7 }, { tile: 'bldTallT',   col: 15, row: 7 },
  { tile: 'comG',       col: 14, row: 7 }, { tile: 'bldTallU',   col: 16, row: 8 },
  { tile: 'comH',       col: 15, row: 8 }, { tile: 'shopBlueA',  col: 14, row: 8 },
  { tile: 'bldTallV',   col: 16, row: 9 }, { tile: 'comI',       col: 15, row: 9 },
  { tile: 'bld2stD',    col: 14, row: 9 }, { tile: 'comJ',       col: 16, row: 10 },
  { tile: 'comK',       col: 15, row: 10 }, { tile: 'shopWhiteB', col: 14, row: 10 },
  // SW: Residential
  { tile: 'bldTallA',   col: 1,  row: 13 }, { tile: 'shopRedB',   col: 2,  row: 13 },
  { tile: 'bldTallB',   col: 3,  row: 13 }, { tile: 'comL',       col: 4,  row: 13 },
  { tile: 'bldXtallD',  col: 1,  row: 14 }, { tile: 'bldTallC',   col: 2,  row: 14 },
  { tile: 'bldTallD',   col: 3,  row: 14 }, { tile: 'shopGreenB', col: 4,  row: 14 },
  { tile: 'comM',       col: 1,  row: 15 }, { tile: 'bld2stA',    col: 2,  row: 15 },
  { tile: 'bldTallE',   col: 3,  row: 15 }, { tile: 'shopBlueB',  col: 4,  row: 15 },
  { tile: 'bldTallF',   col: 1,  row: 16 }, { tile: 'comN',       col: 2,  row: 16 },
  { tile: 'shopWhiteA', col: 3,  row: 16 },
  // SE: Modern
  { tile: 'comO',       col: 13, row: 13 }, { tile: 'bldTallG',   col: 14, row: 13 },
  { tile: 'bldTallH',   col: 15, row: 13 }, { tile: 'shopRedA',   col: 16, row: 13 },
  { tile: 'comP',       col: 13, row: 14 }, { tile: 'bldXtallA',  col: 14, row: 14 },
  { tile: 'bldTallI',   col: 15, row: 14 }, { tile: 'comQ',       col: 16, row: 14 },
  { tile: 'shopGreenA', col: 13, row: 15 }, { tile: 'bldTallJ',   col: 14, row: 15 },
  { tile: 'comR',       col: 15, row: 15 }, { tile: 'bld2stB',    col: 16, row: 15 },
  { tile: 'bldTallK',   col: 13, row: 16 }, { tile: 'shopBlueA',  col: 14, row: 16 },
  { tile: 'bldTallL',   col: 15, row: 16 }, { tile: 'comA',       col: 16, row: 16 },
  // S boulevard commercial
  { tile: 'shopRedA',   col: 7,  row: 13 }, { tile: 'comB',       col: 8,  row: 13 },
  { tile: 'bldTallM',   col: 9,  row: 13 }, { tile: 'shopGreenB', col: 10, row: 13 },
  { tile: 'bldTallN',   col: 7,  row: 14 }, { tile: 'shopBlueA',  col: 8,  row: 14 },
  { tile: 'comC',       col: 9,  row: 14 }, { tile: 'bld2stC',    col: 10, row: 14 },
  { tile: 'comD',       col: 7,  row: 15 }, { tile: 'bldTallO',   col: 8,  row: 15 },
  { tile: 'shopWhiteA', col: 9,  row: 15 }, { tile: 'bldTallP',   col: 10, row: 15 },
  { tile: 'bldTallQ',   col: 7,  row: 16 }, { tile: 'comE',       col: 8,  row: 16 },
  { tile: 'shopRedB',   col: 9,  row: 16 }, { tile: 'bldTallR',   col: 10, row: 16 },
]

// Set of occupied cells (buildings)
const OCCUPIED = new Set<string>()
for (const ov of OVERLAYS) OCCUPIED.add(`${ov.col},${ov.row}`)

// Walkable check: sidewalk and green areas, not roads/trees/buildings/pools
const WALKABLE_TILES = new Set<TileId>([
  'sidewalk', 'sidewalk2', 'sidewalk3', 'parkStrip', 'greenField', 'parkLawn', 'parkGarden', 'parkL',
])
function isWalkable(col: number, row: number): boolean {
  if (row < 0 || row >= 18 || col < 0 || col >= 18) return false
  if (OCCUPIED.has(`${col},${row}`)) return false
  return WALKABLE_TILES.has(GROUND_MAP[row][col])
}

// Simple A* for NPC movement
function findWalkPath(
  startCol: number, startRow: number,
  goalCol: number, goalRow: number,
): { col: number; row: number }[] {
  if (!isWalkable(goalCol, goalRow)) return []
  const key = (c: number, r: number) => `${c},${r}`

  interface Node {
    col: number; row: number; g: number; h: number; f: number; parent: Node | null
  }

  const startKey = key(startCol, startRow)
  const goalKey = key(goalCol, goalRow)
  if (startKey === goalKey) return []

  const h = (c: number, r: number) => Math.abs(c - goalCol) + Math.abs(r - goalRow)
  const open: Node[] = [{ col: startCol, row: startRow, g: 0, h: h(startCol, startRow), f: h(startCol, startRow), parent: null }]
  const closed = new Set<string>()

  while (open.length > 0) {
    open.sort((a, b) => a.f - b.f)
    const cur = open.shift()!
    const ck = key(cur.col, cur.row)
    if (ck === goalKey) {
      const path: { col: number; row: number }[] = []
      let n: Node | null = cur
      while (n) { path.unshift({ col: n.col, row: n.row }); n = n.parent }
      return path.slice(1) // skip start
    }
    closed.add(ck)
    for (const [dc, dr] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const nc = cur.col + dc, nr = cur.row + dr
      const nk = key(nc, nr)
      if (closed.has(nk) || !isWalkable(nc, nr)) continue
      const g = cur.g + 1
      const existing = open.find(o => o.col === nc && o.row === nr)
      if (!existing) {
        open.push({ col: nc, row: nr, g, h: h(nc, nr), f: g + h(nc, nr), parent: cur })
      } else if (g < existing.g) {
        existing.g = g; existing.f = g + existing.h; existing.parent = cur
      }
    }
  }
  return []
}

// Direction from grid movement
function moveDirection(dc: number, dr: number): Direction {
  if (dc > 0 && dr >= 0) return 'right'
  if (dc <= 0 && dr > 0) return 'down'
  if (dc < 0 && dr <= 0) return 'left'
  return 'up'
}

// ─── NPC State Machine ───
interface NpcState {
  ome: CharacterData
  container: Container
  animSprite: AnimatedSprite | null
  nameLabel: Text
  speechBubble: Container
  speechText: Text
  speechTimer: number
  // Movement
  state: 'idle' | 'walking'
  idleTimer: number
  path: { col: number; row: number }[]
  pathIdx: number
  // Smooth interpolation
  screenX: number
  screenY: number
  targetX: number
  targetY: number
  moveProgress: number
  currentCol: number
  currentRow: number
}

// Character palette tints (multiply with the pink mannequin)
const TINTS = [
  0x6699FF, // blue
  0xFF6655, // red
  0x55CC77, // green
  0xFFAA33, // orange
  0xBB66DD, // purple
  0x44DDBB, // teal
  0xFF66AA, // pink
  0x99DD44, // lime
  0xDDCC33, // gold
  0x44AADD, // sky
]

// Fallback characters (used when server is unreachable)
const FALLBACK_OMES: CharacterData[] = [
  { id: 'mayor_chen',    name: 'Mayor Chen',    col: 8,  row: 3,  direction: 'down',  state: 'idle', paletteIndex: 0 },
  { id: 'baker_li',      name: 'Baker Li',      col: 2,  row: 2,  direction: 'right', state: 'idle', paletteIndex: 1 },
  { id: 'gardener_wang', name: 'Old Wang',      col: 7,  row: 7,  direction: 'left',  state: 'idle', paletteIndex: 2 },
  { id: 'merchant_zhao', name: 'Merchant Zhao', col: 14, row: 3,  direction: 'down',  state: 'idle', paletteIndex: 3 },
  { id: 'fisher_zhang',  name: 'Fisher Zhang',  col: 8,  row: 11, direction: 'right', state: 'idle', paletteIndex: 4 },
  { id: 'artist_liu',    name: 'Artist Liu',    col: 15, row: 8,  direction: 'left',  state: 'idle', paletteIndex: 5 },
  { id: 'scholar_wu',    name: 'Scholar Wu',    col: 3,  row: 14, direction: 'down',  state: 'idle', paletteIndex: 6 },
  { id: 'runner_qian',   name: 'Runner Qian',   col: 9,  row: 9,  direction: 'right', state: 'idle', paletteIndex: 7 },
  { id: 'musician_sun',  name: 'Musician Sun',  col: 1,  row: 8,  direction: 'right', state: 'idle', paletteIndex: 8 },
  { id: 'chef_zhou',     name: 'Chef Zhou',     col: 15, row: 14, direction: 'left',  state: 'idle', paletteIndex: 9 },
]

// NPC id → palette index mapping
const NPC_PALETTE: Record<string, number> = {}
FALLBACK_OMES.forEach((o, i) => { NPC_PALETTE[o.id] = i })

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
        background: 0x87CEEB,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      })
      if (destroyed) return
      el.appendChild(app.canvas as HTMLCanvasElement)

      // ─── Load tile textures ───
      const textures = new Map<string, Awaited<ReturnType<typeof Assets.load>>>()
      const allFiles = new Set<string>()
      for (const row of GROUND_MAP) for (const id of row) allFiles.add(T[id])
      for (const ov of OVERLAYS) allFiles.add(T[ov.tile])
      for (const file of allFiles) {
        try { textures.set(file, await Assets.load(`./tiles/${file}`)) } catch { /* skip */ }
      }
      if (destroyed) return

      // ─── Load character spritesheet ───
      let charAnimations: Record<string, Texture[]> = {}
      try {
        const sheetTexture = await Assets.load('./characters/human_sheet.png')
        const atlasJson = await fetch('./characters/human_sheet.json').then(r => r.json())
        const sheet = new Spritesheet(sheetTexture, atlasJson)
        await sheet.parse()
        charAnimations = sheet.animations
      } catch (err) {
        console.warn('Character spritesheet failed, using fallback:', err)
      }
      if (destroyed) return

      // ─── World container ───
      const world = new Container()
      world.sortableChildren = true
      app.stage.addChild(world)

      const centerGrid = worldToScreen(8.5, 8.5)
      world.x = app.screen.width / 2 - centerGrid.x * 0.75
      world.y = app.screen.height / 2 - centerGrid.y * 0.75
      world.scale.set(0.75)

      // ─── Render ground ───
      const ROWS = GROUND_MAP.length
      const COLS = GROUND_MAP[0].length
      for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
          const tileId = GROUND_MAP[row][col]
          const file = T[tileId]
          const { x, y } = worldToScreen(col, row)
          const tex = textures.get(file)
          if (tex) {
            const sprite = new Sprite(tex)
            sprite.anchor.set(0.5, anchorY(tileId))
            sprite.x = x; sprite.y = y
            sprite.zIndex = depthIndex(col, row)
            world.addChild(sprite)
          } else {
            const g = new Graphics()
            g.moveTo(0, -HALF_H).lineTo(HALF_W, 0).lineTo(0, HALF_H).lineTo(-HALF_W, 0).closePath()
            g.fill({ color: 0x6aaa3a, alpha: 0.6 })
            g.x = x; g.y = y; g.zIndex = depthIndex(col, row)
            world.addChild(g)
          }
        }
      }

      // ─── Render building overlays ───
      for (const ov of OVERLAYS) {
        const file = T[ov.tile]
        const { x, y } = worldToScreen(ov.col, ov.row)
        const tex = textures.get(file)
        if (tex) {
          const sprite = new Sprite(tex)
          sprite.anchor.set(0.5, anchorY(ov.tile))
          sprite.x = x; sprite.y = y
          sprite.zIndex = depthIndex(ov.col, ov.row, 2)
          world.addChild(sprite)
        }
      }

      // ─── Fetch initial NPC state from server, fallback to defaults ───
      let initialOmes = FALLBACK_OMES
      try {
        const stateResp = await fetch('/api/town/state', { signal: AbortSignal.timeout(2000) })
        if (stateResp.ok) {
          const serverState = await stateResp.json()
          if (serverState.npcs && serverState.npcs.length > 0) {
            initialOmes = serverState.npcs.map((npc: { id: string; name: string; col: number; row: number; activity: string; direction: string; speech_emoji: string }, i: number) => ({
              id: npc.id,
              name: npc.name,
              col: npc.col,
              row: npc.row,
              direction: (npc.direction || 'down') as Direction,
              state: npc.activity === 'walking' ? 'walk' : 'idle' as const,
              paletteIndex: NPC_PALETTE[npc.id] ?? i,
              speech: npc.speech_emoji || undefined,
            }))
          }
        }
      } catch { /* server not available, use fallback */ }
      if (destroyed) return

      // ─── Create NPC states ───
      const MOVE_SPEED = 0.035 // tiles per frame (~2 tiles/sec at 60fps)
      const npcs: NpcState[] = []
      const npcById = new Map<string, NpcState>()

      for (const ome of initialOmes) {
        const { x, y } = worldToScreen(ome.col, ome.row)
        const container = new Container()
        container.x = x
        container.y = y
        container.zIndex = depthIndex(ome.col, ome.row, 3)
        container.eventMode = 'static'
        container.cursor = 'pointer'
        container.on('pointerdown', () => onOmeClick(ome))

        // Shadow
        const shadow = new Graphics()
        shadow.ellipse(0, 5, 20, 10)
        shadow.fill({ color: 0x000000, alpha: 0.3 })
        container.addChild(shadow)

        // Character sprite (animated or fallback)
        let animSprite: AnimatedSprite | null = null
        const hasSheet = charAnimations['down_idle'] && charAnimations['down_idle'].length > 0

        if (hasSheet) {
          animSprite = new AnimatedSprite(charAnimations['down_idle'])
          animSprite.anchor.set(0.5, 0.95)
          animSprite.scale.set(1.1)
          animSprite.animationSpeed = 0.12
          animSprite.tint = TINTS[ome.paletteIndex % TINTS.length]
          animSprite.play()
          container.addChild(animSprite)
        } else {
          // Fallback: simple colored shape (larger)
          const body = new Graphics()
          body.roundRect(-10, -40, 20, 30, 5)
          body.fill({ color: TINTS[ome.paletteIndex % TINTS.length] })
          container.addChild(body)
          const head = new Graphics()
          head.circle(0, -50, 12)
          head.fill({ color: 0xFFDDBB })
          container.addChild(head)
          const eyes = new Graphics()
          eyes.circle(-4, -52, 2).fill({ color: 0x333333 })
          eyes.circle(4, -52, 2).fill({ color: 0x333333 })
          container.addChild(eyes)
        }

        // Glow for player's Ome
        if (ome.id === 'my_ome') {
          const glow = new Graphics()
          glow.circle(0, -30, 32)
          glow.fill({ color: 0xFFD700, alpha: 0.18 })
          container.addChildAt(glow, 0)
        }

        // Name label
        const nameLabel = new Text({
          text: ome.name,
          style: new TextStyle({
            fontSize: 12, fill: '#ffffff', fontFamily: 'system-ui',
            fontWeight: 'bold', stroke: { color: '#000000', width: 3 },
          }),
        })
        nameLabel.anchor.set(0.5, 1)
        nameLabel.y = -70
        container.addChild(nameLabel)

        // Speech bubble
        const speechBubble = new Container()
        speechBubble.visible = false
        speechBubble.y = -85

        const bubbleBg = new Graphics()
        bubbleBg.roundRect(-40, -14, 80, 22, 8)
        bubbleBg.fill({ color: 0xFFFFFF, alpha: 0.9 })
        // Small triangle pointer
        bubbleBg.moveTo(-4, 8).lineTo(0, 14).lineTo(4, 8).closePath()
        bubbleBg.fill({ color: 0xFFFFFF, alpha: 0.9 })
        speechBubble.addChild(bubbleBg)

        const speechText = new Text({
          text: '',
          style: new TextStyle({
            fontSize: 10, fill: '#333333', fontFamily: 'system-ui',
          }),
        })
        speechText.anchor.set(0.5, 0.5)
        speechText.y = -3
        speechBubble.addChild(speechText)
        container.addChild(speechBubble)

        world.addChild(container)

        const npcState: NpcState = {
          ome,
          container,
          animSprite,
          nameLabel,
          speechBubble,
          speechText,
          speechTimer: 0,
          state: 'idle',
          idleTimer: Math.random() * 60 + 30, // random start delay (0.5-1.5 seconds)
          path: [],
          pathIdx: 0,
          screenX: x,
          screenY: y,
          targetX: x,
          targetY: y,
          moveProgress: 0,
          currentCol: ome.col,
          currentRow: ome.row,
        }
        npcs.push(npcState)
        npcById.set(ome.id, npcState)
      }

      // ─── Server state polling (sync NPC positions from ome-server) ───
      /* eslint-disable @typescript-eslint/no-unused-vars */
      void setInterval(async () => {
        if (destroyed) return
        try {
          const resp = await fetch('/api/town/state', { signal: AbortSignal.timeout(2000) })
          if (!resp.ok) return
          const state = await resp.json()
          if (!state.npcs) return
          for (const serverNpc of state.npcs) {
            const npc = npcById.get(serverNpc.id)
            if (!npc) continue
            const serverCol = serverNpc.col
            const serverRow = serverNpc.row
            // If server moved the NPC to a different tile, animate there
            if (serverCol !== npc.currentCol || serverRow !== npc.currentRow) {
              if (npc.state !== 'walking') {
                const path = findWalkPath(npc.currentCol, npc.currentRow, serverCol, serverRow)
                if (path.length > 0) {
                  npc.path = path
                  npc.pathIdx = 0
                  npc.state = 'walking'
                  npc.moveProgress = 0
                  const next = path[0]
                  const target = worldToScreen(next.col, next.row)
                  npc.targetX = target.x
                  npc.targetY = target.y
                  const dc = next.col - npc.currentCol
                  const dr = next.row - npc.currentRow
                  npc.ome.direction = moveDirection(dc, dr)
                  setAnimation(npc, npc.ome.direction, true)
                }
              }
            }
            // Sync speech from server
            if (serverNpc.speech_emoji && serverNpc.speech_emoji !== '' && npc.speechTimer <= 0) {
              showSpeech(npc, serverNpc.speech_emoji, 180)
            }
          }
        } catch { /* server unreachable, fall back to client-side wandering */ }
      }, 2000) // Poll every 2 seconds (matches server tick)

      // Show initial greeting bubbles
      const greetings = ['👋', '☕', '🌱', '💰', '🐟', '🎨', '📚', '🏃', '🎵', '🍳']
      npcs.forEach((npc, i) => {
        setTimeout(() => {
          if (destroyed) return
          showSpeech(npc, greetings[i] || '👋', 180)
        }, 500 + i * 300)
      })

      function showSpeech(npc: NpcState, text: string, duration: number) {
        npc.speechText.text = text
        npc.speechBubble.visible = true
        npc.speechTimer = duration

        // Resize background to fit text
        const bg = npc.speechBubble.children[0] as Graphics
        bg.clear()
        const w = Math.max(npc.speechText.width + 16, 32)
        bg.roundRect(-w / 2, -14, w, 22, 8)
        bg.fill({ color: 0xFFFFFF, alpha: 0.9 })
        bg.moveTo(-4, 8).lineTo(0, 14).lineTo(4, 8).closePath()
        bg.fill({ color: 0xFFFFFF, alpha: 0.9 })
      }

      // Random walkable destination
      function randomWalkable(): { col: number; row: number } | null {
        for (let attempts = 0; attempts < 50; attempts++) {
          const col = 1 + Math.floor(Math.random() * 16)
          const row = 1 + Math.floor(Math.random() * 16)
          if (isWalkable(col, row)) return { col, row }
        }
        return null
      }

      // Set animation based on direction and state
      function setAnimation(npc: NpcState, dir: Direction, walking: boolean) {
        if (!npc.animSprite || !charAnimations) return
        const key = `${dir}_${walking ? 'walk' : 'idle'}`
        const frames = charAnimations[key]
        if (frames && frames.length > 0) {
          npc.animSprite.textures = frames
          npc.animSprite.animationSpeed = walking ? 0.15 : 0.06
          npc.animSprite.play()
        }
      }

      // ─── Main game loop ───
      app.ticker.add(() => {
        for (const npc of npcs) {
          // Speech bubble timer
          if (npc.speechTimer > 0) {
            npc.speechTimer--
            if (npc.speechTimer <= 0) {
              npc.speechBubble.visible = false
            }
          }

          if (npc.state === 'idle') {
            npc.idleTimer--
            if (npc.idleTimer <= 0) {
              // Pick random destination and pathfind
              const dest = randomWalkable()
              if (dest) {
                const path = findWalkPath(npc.currentCol, npc.currentRow, dest.col, dest.row)
                if (path.length > 0 && path.length <= 20) {
                  npc.path = path
                  npc.pathIdx = 0
                  npc.state = 'walking'
                  npc.moveProgress = 0
                  const next = path[0]
                  const target = worldToScreen(next.col, next.row)
                  npc.targetX = target.x
                  npc.targetY = target.y
                  const dc = next.col - npc.currentCol
                  const dr = next.row - npc.currentRow
                  const dir = moveDirection(dc, dr)
                  npc.ome.direction = dir
                  setAnimation(npc, dir, true)
                  // Random speech when starting to walk
                  if (Math.random() < 0.15) {
                    const emojis = ['🚶', '🎶', '💭', '✨', '🌟', '😊', '🏠', '🌳']
                    showSpeech(npc, emojis[Math.floor(Math.random() * emojis.length)], 90)
                  }
                } else {
                  npc.idleTimer = 60 + Math.random() * 120
                }
              } else {
                npc.idleTimer = 60 + Math.random() * 120
              }
            }
          } else if (npc.state === 'walking') {
            npc.moveProgress += MOVE_SPEED
            if (npc.moveProgress >= 1) {
              // Arrived at next tile
              const tile = npc.path[npc.pathIdx]
              npc.currentCol = tile.col
              npc.currentRow = tile.row
              npc.screenX = npc.targetX
              npc.screenY = npc.targetY
              npc.pathIdx++

              if (npc.pathIdx < npc.path.length) {
                // Next tile in path
                npc.moveProgress = 0
                const next = npc.path[npc.pathIdx]
                const target = worldToScreen(next.col, next.row)
                npc.targetX = target.x
                npc.targetY = target.y
                const dc = next.col - npc.currentCol
                const dr = next.row - npc.currentRow
                npc.ome.direction = moveDirection(dc, dr)
                setAnimation(npc, npc.ome.direction, true)
              } else {
                // Path complete
                npc.state = 'idle'
                npc.idleTimer = 60 + Math.random() * 120 // 1-3 seconds idle
                npc.ome.col = npc.currentCol
                npc.ome.row = npc.currentRow
                setAnimation(npc, npc.ome.direction, false)
                // Arrived speech
                if (Math.random() < 0.2) {
                  const phrases = ['😌', '🏁', '👀', '🎯', '☀️']
                  showSpeech(npc, phrases[Math.floor(Math.random() * phrases.length)], 120)
                }
              }
            } else {
              // Interpolate position
              const prevScreen = worldToScreen(npc.currentCol, npc.currentRow)
              npc.screenX = prevScreen.x + (npc.targetX - prevScreen.x) * npc.moveProgress
              npc.screenY = prevScreen.y + (npc.targetY - prevScreen.y) * npc.moveProgress
            }
          }

          // Update sprite position and depth
          npc.container.x = npc.screenX
          npc.container.y = npc.screenY
          // Smooth depth sorting based on interpolated position
          const effectiveRow = npc.currentRow + (npc.state === 'walking' ? npc.moveProgress : 0)
          const effectiveCol = npc.currentCol + (npc.state === 'walking' ? npc.moveProgress * 0.01 : 0)
          npc.container.zIndex = depthIndex(Math.round(effectiveCol), Math.round(effectiveRow), 3)

          // Gentle bob when idle
          if (npc.state === 'idle') {
            const bob = Math.sin(Date.now() * 0.003 + npc.ome.paletteIndex * 2) * 1.5
            npc.container.y = npc.screenY + bob
          }
        }
      })

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
