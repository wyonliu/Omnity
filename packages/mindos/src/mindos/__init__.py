"""Mindos — Multi-layer Intention & Neural Dynamic Operating System.

A portable, persistent digital soul protocol.
"""

__version__ = "0.7.1"

from mindos.core import Mindos
from mindos.config import MindosConfig, ModelRouter, ModelProvider
from mindos.constants import set_locale
from mindos.constitution import Constitution, ConstitutionRule
from mindos.damping import WritebackDamper, DampingConfig
from mindos.importance import ImportanceTrigger, estimate_importance

__all__ = [
    "Mindos", "MindosConfig", "ModelRouter", "ModelProvider", "set_locale",
    "Constitution", "ConstitutionRule",
    "WritebackDamper", "DampingConfig",
    "ImportanceTrigger", "estimate_importance",
    "__version__",
]
