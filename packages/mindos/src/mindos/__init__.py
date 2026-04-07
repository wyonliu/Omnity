"""Mindos — Multi-layer Intention & Neural Dynamic Operating System.

A portable, persistent digital soul protocol.
"""

__version__ = "0.6.0"

from mindos.core import Mindos
from mindos.config import MindosConfig, ModelRouter, ModelProvider
from mindos.constants import set_locale

__all__ = ["Mindos", "MindosConfig", "ModelRouter", "ModelProvider", "set_locale", "__version__"]
