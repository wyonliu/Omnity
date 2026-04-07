"""Mindos — Multi-layer Intention & Neural Dynamic Operating System.

A portable, persistent digital soul protocol.
"""

__version__ = "0.5.0"

from mindos.core import Mindos
from mindos.config import MindosConfig, ModelRouter, ModelProvider

__all__ = ["Mindos", "MindosConfig", "ModelRouter", "ModelProvider", "__version__"]
