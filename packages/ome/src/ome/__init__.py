"""Ome — Your AI twin that remembers everything and works for you 24/7."""

__version__ = "0.6.0"

from ome.core import Ome
from ome.life.persona import PersonaDefinition, BigFive, BUILTIN_PERSONAS
from ome.life.emotion import EmotionState
from ome.constants import set_locale

__all__ = ["Ome", "PersonaDefinition", "BigFive", "BUILTIN_PERSONAS", "EmotionState", "set_locale"]
