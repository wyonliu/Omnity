"""Ome — Your AI twin that remembers everything and works for you 24/7."""

__version__ = "0.7.1"

from ome.core import Ome
from ome.life.persona import PersonaDefinition, BigFive, BUILTIN_PERSONAS
from ome.life.emotion import EmotionState
from ome.life.stages import GrowthGate, Capability
from ome.life.maturity import MaturityScorer, MaturitySnapshot
from ome.constants import set_locale

__all__ = [
    "Ome", "PersonaDefinition", "BigFive", "BUILTIN_PERSONAS", "EmotionState",
    "GrowthGate", "Capability", "MaturityScorer", "MaturitySnapshot",
    "set_locale",
]
