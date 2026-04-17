"""OmeGate — multi-platform gateway that lets one Ome serve many surfaces.

Each *adapter* wraps a messaging platform (Telegram today; Slack / Feishu /
WhatsApp tomorrow) and speaks the same :class:`.base.IncomingMessage` /
:class:`.base.OutgoingMessage` dialect. The shared :class:`.base.BindingRegistry`
binds a (``platform``, ``platform_user_id``) pair to a local Ome root so the
same digital twin follows you everywhere.
"""

from ome.gateway.base import (
    BindingRegistry,
    GatewayAdapter,
    IncomingMessage,
    MessageHandler,
    OutgoingMessage,
)
from ome.gateway.runner import GatewayRunner
from ome.gateway.telegram import TelegramAdapter

__all__ = [
    "BindingRegistry",
    "GatewayAdapter",
    "IncomingMessage",
    "MessageHandler",
    "OutgoingMessage",
    "GatewayRunner",
    "TelegramAdapter",
]
