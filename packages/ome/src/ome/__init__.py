"""Ome — Your AI twin that remembers everything and works for you 24/7."""

__version__ = "0.3.1"

from ome.core import Ome
from ome.life.persona import PersonaDefinition, BigFive, BUILTIN_PERSONAS
from ome.life.emotion import EmotionState

__all__ = ["Ome", "PersonaDefinition", "BigFive", "BUILTIN_PERSONAS", "EmotionState"]
