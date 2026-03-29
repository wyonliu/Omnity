"""OmeTown simulation — 5-layer Omnity architecture fully wired.

Each NPC is:
  Layer 1 — SOAP: spatial presence in a SOAP scene (position, context, affordances)
  Layer 2 — Mindos: 5-layer brain (L0 memory → L1 instinct → L2 cognition → L3 decision → L4 self)
  Layer 3 — Ome: AI twin with personality, emotion, growth, autonomy
  Layer 4 — Maxim: Maslow needs engine driving intentions + GM arbitration
  Layer 5 — OmeTown: PixiJS isometric frontend
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ome.core import Ome

from ome_server.ome_manager import OME_DATA_ROOT, register_user, get_ome, user_exists
from ome_server.town.scenario import NPCS, NpcDef, SCENARIO_NAME, SCENARIO_BRIEF, EVIDENCE_CHAIN, SOLUTION

# ── Maxim (Layer 4) — Maslow needs + GM arbitration ──
from maxim.models import World as MaximWorld, Agent as MaximAgent, Needs as MaximNeeds, GoodDef
from maxim.needs import decay_needs, decide_intention
from maxim.gm import rules_arbitrate, apply_outcomes

# ── SOAP (Layer 1) — Spatial protocol ──
try:
    from omnity_soap.runtime import SOAPRuntime
    SOAP_AVAILABLE = True
except ImportError:
    SOAP_AVAILABLE = False

log = logging.getLogger("ome_server.town")


# ── NPC Spatial State ──────────────────────────────────────────────

@dataclass
class NpcState:
    """Runtime state of an NPC in OmeTown."""
    npc_id: str
    name: str
    name_cn: str
    occupation: str
    col: int
    row: int
    home_col: int
    home_row: int
    activity: str = "idle"  # idle, walking, talking, working
    direction: str = "down"
    target_col: int = -1
    target_row: int = -1
    speech_emoji: str = ""
    speech_timer: float = 0
    # Timing
    idle_until: float = 0
    last_conversation_with: str = ""
    last_conversation_time: float = 0
    # Maxim intention (from last tick)
    last_intention: str = ""
    last_intention_reason: str = ""


# ── Walkability ────────────────────────────────────────────────────

_WALKABLE_GROUND = {
    'sidewalk', 'sidewalk2', 'sidewalk3',
    'parkStrip', 'greenField', 'parkLawn', 'parkGarden', 'parkL',
}

_BUILDING_CELLS: set[tuple[int, int]] = set()
_GROUND_TILE_AT: dict[tuple[int, int], str] = {}

def _init_walkability():
    tile_map = {
        'SW': 'sidewalk', 'S2': 'sidewalk2', 'RL': 'roadLine', 'RC': 'roadCross',
        'TB': 'treesBeige', 'TD': 'treesDark', 'GD': 'parkGarden', 'GL': 'parkLawn',
        'GP': 'parkL', 'GS': 'parkStrip', 'GF': 'greenField', 'GR': 'greenRoad',
        'PL': 'pool', 'FT': 'fountain', 'LP': 'lampPost',
    }
    ground = [
        "TB GD GL TB GD RL TB GL GD GL TB GD RL GL GD TB GL TB",
        "GL SW GS SW LP RL GS GF GS GF GS GP RL SW GS LP SW GD",
        "GD SW SW SW GS RL GF SW SW SW SW GF RL SW SW SW GS GL",
        "TB SW SW SW SW RL GS SW SW SW GS SW RL SW SW SW SW TB",
        "GD LP GS SW SW RL LP GS LP GS SW LP RL GS SW SW LP GL",
        "RL RL RL RL RL RC RL RL RL RL RL RL RC RL RL RL RL RL",
        "TB GS SW SW LP RL GD GL TB GL GD TB RL SW GS LP GS TB",
        "GL SW SW GS SW RL GL GD GS GD GL GD RL SW SW GS SW GD",
        "GD SW SW SW SW RL TB GS FT GS TB GL RL SW SW SW SW GL",
        "GL SW GS SW SW RL GL GD GS GD GL GD RL GS SW SW SW TB",
        "TB LP SW GS SW RL GD GL TB GL GD TB RL SW GS LP SW GL",
        "GD SW SW SW SW RL TB PL GL PL TB GL RL SW SW SW GS GD",
        "RL RL RL RL RL RC RL RL RL RL RL RL RC RL RL RL RL RL",
        "GL LP SW GS SW RL SW GS SW GS SW LP RL GS SW LP SW GL",
        "TB SW SW SW GS RL GS SW SW SW GS SW RL SW SW SW SW TB",
        "GD SW GS SW LP RL SW SW GS SW LP SW RL SW GS SW SW GD",
        "GL SW SW SW GS RL LP SW SW SW SW GS RL SW SW GS SW GL",
        "TB GL GD TB GL RL TB GD GL GD TB GL RL GD TB GL GD TB",
    ]
    for row_idx, row_str in enumerate(ground):
        for col_idx, code in enumerate(row_str.split()):
            tile_name = tile_map.get(code, code)
            _GROUND_TILE_AT[(col_idx, row_idx)] = tile_name

_init_walkability()


def is_walkable(col: int, row: int) -> bool:
    if col < 0 or col >= 18 or row < 0 or row >= 18:
        return False
    if (col, row) in _BUILDING_CELLS:
        return False
    tile = _GROUND_TILE_AT.get((col, row), "")
    return tile in _WALKABLE_GROUND


def random_walkable() -> Optional[tuple[int, int]]:
    for _ in range(50):
        c, r = random.randint(1, 16), random.randint(1, 16)
        if is_walkable(c, r):
            return (c, r)
    return None


# ── SOAP Scene Builder ────────────────────────────────────────────

def _build_soap_scene() -> dict:
    """Build a SOAP scene JSON for OmeTown's 18×18 grid."""
    sid = "ometown_01"
    objects = [
        {
            "id": "fountain_01",
            "uri": f"soap://{sid}/town_center/fountain_01",
            "type": "landmark.fountain",
            "reality": "physical",
            "affordances": ["observe", "sit"],
            "bounds": {"type": "aabb", "min": [8, 0, 8], "max": [9, 1, 9]},
        },
        {
            "id": "star_of_ometown",
            "uri": f"soap://{sid}/museum/star_of_ometown",
            "type": "artifact.gemstone",
            "reality": "physical",
            "affordances": ["observe"],
            "bounds": {"type": "aabb", "min": [8, 0, 2], "max": [9, 0.5, 3]},
        },
    ]
    regions = [
        {
            "id": "town_center",
            "uri": f"soap://{sid}/town_center",
            "name": "Town Center Park",
            "purpose_tags": ["park", "social", "landmark"],
            "contained_object_ids": ["fountain_01"],
        },
        {
            "id": "commercial_nw",
            "uri": f"soap://{sid}/commercial_nw",
            "name": "Northwest Commercial District",
            "purpose_tags": ["commerce", "shopping"],
            "contained_object_ids": [],
        },
        {
            "id": "residential_ne",
            "uri": f"soap://{sid}/residential_ne",
            "name": "Northeast Residential",
            "purpose_tags": ["residential", "housing"],
            "contained_object_ids": [],
        },
        {
            "id": "south_dock",
            "uri": f"soap://{sid}/south_dock",
            "name": "South Dock",
            "purpose_tags": ["dock", "fishing", "transport"],
            "contained_object_ids": [],
        },
        {
            "id": "museum",
            "uri": f"soap://{sid}/museum",
            "name": "OmeTown Museum",
            "purpose_tags": ["museum", "culture", "crime_scene"],
            "contained_object_ids": ["star_of_ometown"],
        },
    ]

    return {
        "soap_version": "0.1.0",
        "space_id": sid,
        "title": "OmeTown — 影子之谜 Mystery of the Shadows",
        "coordinate_frame": {
            "type": "right-handed",
            "unit": "tile",
            "up_axis": "Y",
            "origin_description": "Northwest corner of 18x18 isometric grid, Y=0 is ground level",
        },
        "objects": objects,
        "regions": regions,
        "relations": [],
        "meta": {"conformance_tier_target": "T1"},
    }


# ── Maxim World Builder ───────────────────────────────────────────

# Map NPC occupations to Maxim goods they produce
_OCCUPATION_GOODS = {
    "baker": "food",
    "chef": "food",
    "gardener": "food",
    "merchant": "goods",
    "fisher": "food",
    "artist": "art",
    "musician": "art",
    "scholar": "knowledge",
    "fitness coach": "training",
    "mayor": "governance",
}

# Emoji for Maxim intentions
_INTENTION_EMOJI = {
    "work": "🔨",
    "eat": "🍞",
    "rest": "😴",
    "socialize": "💬",
    "court": "💕",
    "teach": "📚",
    "create": "🎨",
    "explore": "🚶",
    "buy": "💰",
}


def _build_maxim_world(npc_defs: dict[str, NpcDef]) -> MaximWorld:
    """Create a Maxim World populated with NPC agents."""
    world = MaximWorld(name="OmeTown")
    # Goods
    world.goods = [
        GoodDef(name="food", base_price=10.0, producers=["baker", "chef", "gardener", "fisher"]),
        GoodDef(name="art", base_price=15.0, producers=["artist", "musician"]),
        GoodDef(name="knowledge", base_price=12.0, producers=["scholar"]),
        GoodDef(name="goods", base_price=8.0, producers=["merchant"]),
    ]
    # Agents
    for npc_def in npc_defs.values():
        agent = MaximAgent(
            id=npc_def.id,
            name=npc_def.name,
            age=random.randint(25, 55),
            traits=npc_def.traits,
            occupation=npc_def.occupation,
            wealth=random.uniform(80, 200),
            needs=MaximNeeds(
                survival=random.uniform(60, 90),
                safety=random.uniform(50, 80),
                belonging=random.uniform(30, 60),
                esteem=random.uniform(20, 50),
                actualization=random.uniform(10, 30),
            ),
            skills={npc_def.occupation: random.uniform(0.4, 0.8)},
        )
        world.agents[agent.id] = agent
    return world


# ── Town Simulation ────────────────────────────────────────────────

class TownSimulation:
    """Manages all NPC Omes across 5 Omnity layers.

    Every tick:
      1. SOAP — update NPC spatial presence
      2. Maxim — decay needs → decide intentions → arbitrate → apply outcomes
      3. Move NPCs based on Maxim intentions
      4. Ome/Mindos — available for player chat (L0-L4 brain)
    """

    def __init__(self):
        self.npcs: dict[str, NpcState] = {}
        self.npc_defs: dict[str, NpcDef] = {n.id: n for n in NPCS}
        self.initialized = False
        self.tick_count = 0
        self._task: Optional[asyncio.Task] = None
        # Player state
        self.player_discovered_clues: list[str] = []
        self.player_accused: Optional[str] = None
        self.scenario_complete = False
        # Layer 4: Maxim world
        self.maxim_world: Optional[MaximWorld] = None
        # Layer 1: SOAP runtime
        self.soap_runtime: Optional[object] = None  # SOAPRuntime when available

    async def initialize(self):
        """Create NPC Ome agents, Maxim world, and SOAP scene."""
        log.info("Initializing OmeTown — wiring 5 Omnity layers...")

        # ── Layer 4: Maxim world ──
        self.maxim_world = _build_maxim_world(self.npc_defs)
        log.info("[Maxim] World created: %d agents, %d goods",
                 len(self.maxim_world.agents), len(self.maxim_world.goods))

        # ── Layer 1: SOAP scene ──
        if SOAP_AVAILABLE:
            try:
                scene_data = _build_soap_scene()
                # Write temp scene file for SOAPRuntime
                scene_path = Path(OME_DATA_ROOT) / "ometown_scene.json"
                scene_path.parent.mkdir(parents=True, exist_ok=True)
                scene_path.write_text(json.dumps(scene_data, indent=2))
                self.soap_runtime = SOAPRuntime.load(scene_path)
                log.info("[SOAP] Scene loaded: space=%s, %d objects, %d regions",
                         scene_data["space_id"],
                         len(scene_data["objects"]),
                         len(scene_data["regions"]))
            except Exception as e:
                log.warning("[SOAP] Failed to initialize: %s (spatial context will be limited)", e)
                self.soap_runtime = None
        else:
            log.info("[SOAP] Package not available, using basic spatial tracking")

        # ── Layer 2+3: Ome agents (each with Mindos brain) ──
        for npc_def in NPCS:
            npc_user_id = f"npc_{npc_def.id}"

            if not user_exists(npc_user_id):
                log.info("[Ome] Creating NPC: %s (%s)", npc_def.name, npc_def.id)
                try:
                    ome = register_user(
                        user_id=npc_user_id,
                        password=f"npc_secret_{npc_def.id}",
                        name=npc_def.name,
                        traits=npc_def.traits,
                        style=npc_def.style,
                    )
                    # Inject scenario knowledge into Mindos L0 memory
                    ome.remember(
                        f"[SCENARIO CONTEXT] {SCENARIO_BRIEF} "
                        f"[MY SECRET KNOWLEDGE] {npc_def.secret}",
                        source="scenario_init"
                    )
                    ome.remember(
                        f"[MY ROLE] I am {npc_def.name} ({npc_def.name_cn}), "
                        f"the {npc_def.occupation} of OmeTown. {npc_def.personality_prompt}",
                        source="scenario_init"
                    )
                except Exception as e:
                    log.error("[Ome] Failed to create NPC %s: %s", npc_def.id, e)
                    continue

            # Register agent in SOAP scene
            if self.soap_runtime:
                try:
                    self.soap_runtime.register_agent(
                        agent_id=npc_def.id,
                        agent_type="npc",
                        capabilities=["observe", "navigate"],
                        position=[float(npc_def.location[0]), 0.0, float(npc_def.location[1])],
                        meta={"name": npc_def.name, "occupation": npc_def.occupation},
                    )
                except Exception as e:
                    log.warning("[SOAP] Failed to register agent %s: %s", npc_def.id, e)

            # Initialize spatial state
            self.npcs[npc_def.id] = NpcState(
                npc_id=npc_def.id,
                name=npc_def.name,
                name_cn=npc_def.name_cn,
                occupation=npc_def.occupation,
                col=npc_def.location[0],
                row=npc_def.location[1],
                home_col=npc_def.location[0],
                home_row=npc_def.location[1],
                idle_until=time.time() + random.uniform(2, 8),
            )

        self.initialized = True
        log.info("OmeTown initialized: %d NPCs × 5 layers (SOAP=%s, Maxim=%s, Ome=✓, Mindos=✓)",
                 len(self.npcs),
                 "✓" if self.soap_runtime else "basic",
                 "✓")

    def start_loop(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._tick_loop())
            log.info("Town simulation loop started")

    async def _tick_loop(self):
        while True:
            try:
                await asyncio.sleep(2)
                self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Tick error: %s", e)

    def _tick(self):
        """Single tick — Maxim needs + GM arbitration drive NPC behavior."""
        now = time.time()
        self.tick_count += 1

        if not self.maxim_world:
            return

        # ── Layer 4: Maxim decay + decide + arbitrate ──

        # 1) Decay needs (Maxim's Maslow hierarchy)
        #    Maxim decay_needs is per-season (heavy), so we scale down for 2s ticks
        #    Instead of calling decay_needs directly (which removes -15 survival),
        #    we do a micro-decay proportional to tick interval
        TICK_SCALE = 0.01  # 2s tick = ~1% of a Maxim season
        for agent in self.maxim_world.living_agents:
            agent.needs.survival = max(0, agent.needs.survival - 0.15 * TICK_SCALE * 100)
            agent.needs.safety = max(0, agent.needs.safety - 0.05 * TICK_SCALE * 100)
            agent.needs.belonging = max(0, agent.needs.belonging - 0.08 * TICK_SCALE * 100)
            agent.needs.esteem = max(0, agent.needs.esteem - 0.03 * TICK_SCALE * 100)
            agent.needs.actualization = max(0, agent.needs.actualization - 0.02 * TICK_SCALE * 100)
            agent.needs.clamp()

        # 2) Decide intentions (Maxim's Maslow-based decision engine)
        intentions: dict[str, dict] = {}
        for agent in self.maxim_world.living_agents:
            intention = decide_intention(agent, self.maxim_world)
            intentions[agent.id] = intention

        # 3) Arbitrate outcomes (rule-based, no LLM cost for ticks)
        #    Only run arbitration every 10 ticks (~20s) to avoid overhead
        if self.tick_count % 10 == 0:
            try:
                result = rules_arbitrate(self.maxim_world, intentions)
                events = apply_outcomes(self.maxim_world, result)
                if events:
                    log.debug("[Maxim] Arbitration: %d events", len(events))
            except Exception as e:
                log.warning("[Maxim] Arbitration failed: %s", e)

        # ── Move NPCs based on Maxim intentions ──
        for npc_id, npc in self.npcs.items():
            if now < npc.idle_until:
                continue

            intention = intentions.get(npc_id, {})
            action = intention.get("action", "rest")
            reason = intention.get("reason", "")

            npc.last_intention = action
            npc.last_intention_reason = reason

            # Map Maxim intention to spatial behavior
            emoji = _INTENTION_EMOJI.get(action, "💭")

            if action == "rest":
                # Go home
                npc.target_col = npc.home_col
                npc.target_row = npc.home_row
                npc.activity = "walking"
                npc.speech_emoji = "😴"
                npc.speech_timer = now + 3
                npc.idle_until = now + random.uniform(8, 15)
            elif action == "socialize" or action == "court":
                # Walk toward a random spot (simulating seeking others)
                dest = random_walkable()
                if dest:
                    npc.target_col, npc.target_row = dest
                    npc.activity = "walking"
                    npc.speech_emoji = "💬"
                    npc.speech_timer = now + 3
                    npc.idle_until = now + random.uniform(6, 12)
            elif action == "work" or action == "teach" or action == "create":
                dest = random_walkable()
                if dest:
                    npc.target_col, npc.target_row = dest
                    npc.activity = "walking"
                    npc.speech_emoji = emoji
                    npc.speech_timer = now + 3
                    npc.idle_until = now + random.uniform(8, 15)
            elif action == "eat" or action == "buy":
                dest = random_walkable()
                if dest:
                    npc.target_col, npc.target_row = dest
                    npc.activity = "walking"
                    npc.speech_emoji = "🍞" if action == "eat" else "💰"
                    npc.speech_timer = now + 3
                    npc.idle_until = now + random.uniform(5, 10)
            else:
                # explore or default: wander
                dest = random_walkable()
                if dest:
                    npc.target_col, npc.target_row = dest
                    npc.activity = "walking"
                    emojis = ["🚶", "🌟", "☀️", "🎶", "💭"]
                    npc.speech_emoji = random.choice(emojis)
                    npc.speech_timer = now + 2
                    npc.idle_until = now + random.uniform(5, 10)

            # Teleport to target (frontend handles interpolation)
            if npc.activity == "walking" and npc.target_col >= 0:
                npc.col = npc.target_col
                npc.row = npc.target_row
                npc.target_col = -1
                npc.target_row = -1
                npc.activity = "idle"

                # Update SOAP position
                if self.soap_runtime:
                    try:
                        self.soap_runtime.heartbeat(
                            agent_id=npc_id,
                            position=[float(npc.col), 0.0, float(npc.row)],
                            status="active",
                        )
                    except Exception:
                        pass

    def _get_soap_context(self, npc_id: str) -> str:
        """Get SOAP spatial context for an NPC's current location."""
        if not self.soap_runtime:
            return ""
        try:
            context = self.soap_runtime.describe_context(agent_id=npc_id)
            return f"\n[SPATIAL CONTEXT] {context}"
        except Exception:
            return ""

    def _get_maxim_context(self, npc_id: str) -> str:
        """Get Maxim needs/intention context for an NPC."""
        if not self.maxim_world or npc_id not in self.maxim_world.agents:
            return ""
        agent = self.maxim_world.agents[npc_id]
        npc = self.npcs.get(npc_id)
        needs = agent.needs.to_dict()
        lowest = agent.needs.lowest_unmet(threshold=30.0)
        intention = npc.last_intention if npc else "unknown"
        return (
            f"\n[INNER STATE] Needs: survival={needs['survival']:.0f}, "
            f"belonging={needs['belonging']:.0f}, esteem={needs['esteem']:.0f}. "
            f"Current focus: {intention}. "
            f"{'Urgent need: ' + lowest if lowest else 'All needs met.'}"
        )

    async def npc_chat(self, npc_id: str, user_message: str) -> dict:
        """Chat with NPC — Ome brain (Mindos L0-L4) + SOAP context + Maxim state."""
        npc_user_id = f"npc_{npc_id}"
        npc_def = self.npc_defs.get(npc_id)
        if not npc_def:
            return {"reply": "...", "error": "Unknown NPC"}

        try:
            ome = get_ome(npc_user_id)
        except FileNotFoundError:
            return {"reply": f"({npc_def.name} is unavailable)", "error": "Ome not found"}

        # Build rich context from all layers
        soap_ctx = self._get_soap_context(npc_id)
        maxim_ctx = self._get_maxim_context(npc_id)

        context = (
            f"[SCENE] You are {npc_def.name} ({npc_def.name_cn}), {npc_def.occupation} of OmeTown. "
            f"{npc_def.personality_prompt}"
            f"{soap_ctx}"
            f"{maxim_ctx}"
            f"\n[PLAYER MESSAGE] "
        )

        try:
            # Ome.chat() → Mindos L0 recall → L1 classify → L2 cognition → generate → L2 commit
            reply = ome.chat(context + user_message)
        except Exception as e:
            log.error("NPC chat failed for %s: %s", npc_id, e)
            reply = f"({npc_def.name} thinks for a moment but doesn't respond...)"

        # Check clue discovery
        self._check_clue_discovery(npc_id, reply)

        # Update Maxim social need (conversation satisfies belonging)
        if self.maxim_world and npc_id in self.maxim_world.agents:
            agent = self.maxim_world.agents[npc_id]
            agent.needs.belonging = min(100, agent.needs.belonging + 15)
            agent.needs.esteem = min(100, agent.needs.esteem + 5)

        # Update NPC state
        if npc_id in self.npcs:
            npc = self.npcs[npc_id]
            npc.last_conversation_with = "player"
            npc.last_conversation_time = time.time()
            npc.speech_emoji = "💬"
            npc.speech_timer = time.time() + 5

        return {
            "reply": reply,
            "npc_id": npc_id,
            "npc_name": npc_def.name,
            "mood": ome.emotion.mood if hasattr(ome, 'emotion') else "neutral",
        }

    async def npc_chat_stream(self, npc_id: str, user_message: str):
        """Stream chat with NPC, yielding tokens as SSE."""
        result = await self.npc_chat(npc_id, user_message)
        reply = result.get("reply", "...")
        for i in range(0, len(reply), 3):
            chunk = reply[i:i + 3]
            yield chunk
            await asyncio.sleep(0.03)

    def _check_clue_discovery(self, npc_id: str, reply: str):
        """Check if the NPC's reply reveals a clue."""
        reply_lower = reply.lower()
        for evidence in EVIDENCE_CHAIN:
            if evidence["source"] != npc_id:
                continue
            if evidence["clue"] in self.player_discovered_clues:
                continue
            keywords = {
                "broken_glass": ["glass", "breaking", "shatter", "玻璃"],
                "dark_figure": ["dark coat", "figure", "wrapped", "黑衣"],
                "night_jogger_sighting": ["avoiding", "streetlight", "路灯", "2 am", "凌晨"],
                "boot_prints": ["boot", "size 11", "diamond", "脚印", "靴子"],
                "nervous_mayor": ["nervous", "pacing", "agitated", "紧张", "踱步"],
                "restaurant_receipt": ["receipt", "1:15", "restaurant", "收据", "餐厅"],
                "master_key": ["master key", "three people", "钥匙", "三个人"],
                "underground_sale": ["antiquity", "underground", "channel", "黑市", "古董"],
                "mystery_boat": ["boat", "dock", "locked box", "船", "码头"],
                "gambling_debt": ["gambling", "debt", "500", "赌", "欠债"],
            }
            kw_list = keywords.get(evidence["clue"], [])
            if any(kw in reply_lower for kw in kw_list):
                self.player_discovered_clues.append(evidence["clue"])
                log.info("Player discovered clue: %s from %s", evidence["clue"], npc_id)

    def accuse(self, suspect_id: str) -> dict:
        self.player_accused = suspect_id
        if suspect_id == SOLUTION["thief"]:
            self.scenario_complete = True
            return {
                "correct": True,
                "message": (
                    f"🎉 Brilliant detective work! You've solved the Mystery of the Shadows!\n\n"
                    f"Mayor Chen confesses: \"{SOLUTION['motive']}\"\n"
                    f"Method: {SOLUTION['method']}\n"
                    f"The Star of OmeTown has been recovered from {SOLUTION['escape_plan']}."
                ),
                "clues_found": len(self.player_discovered_clues),
                "total_clues": len(EVIDENCE_CHAIN),
            }
        else:
            npc_def = self.npc_defs.get(suspect_id)
            name = npc_def.name if npc_def else suspect_id
            return {
                "correct": False,
                "message": f"❌ {name} has a solid alibi. Keep investigating — the real thief is still out there.",
                "clues_found": len(self.player_discovered_clues),
                "total_clues": len(EVIDENCE_CHAIN),
            }

    def get_state(self) -> dict:
        """Return full town state for the frontend, including Maxim layer info."""
        now = time.time()
        npcs_state = []
        for npc in self.npcs.values():
            npc_data = {
                "id": npc.npc_id,
                "name": npc.name,
                "name_cn": npc.name_cn,
                "occupation": npc.occupation,
                "col": npc.col,
                "row": npc.row,
                "activity": npc.activity,
                "direction": npc.direction,
                "speech_emoji": npc.speech_emoji if now < npc.speech_timer else "",
                "intention": npc.last_intention,
            }
            # Attach Maxim needs if available
            if self.maxim_world and npc.npc_id in self.maxim_world.agents:
                agent = self.maxim_world.agents[npc.npc_id]
                npc_data["needs"] = agent.needs.to_dict()
            npcs_state.append(npc_data)

        return {
            "scenario": {
                "name": SCENARIO_NAME,
                "brief": SCENARIO_BRIEF,
                "clues_found": self.player_discovered_clues,
                "total_clues": len(EVIDENCE_CHAIN),
                "complete": self.scenario_complete,
                "accused": self.player_accused,
            },
            "layers": {
                "soap": "active" if self.soap_runtime else "basic",
                "mindos": "active",
                "ome": "active",
                "maxim": "active" if self.maxim_world else "off",
            },
            "npcs": npcs_state,
            "tick": self.tick_count,
        }


# ── Singleton ──────────────────────────────────────────────────────

_simulation: Optional[TownSimulation] = None

def get_simulation() -> TownSimulation:
    global _simulation
    if _simulation is None:
        _simulation = TownSimulation()
    return _simulation
