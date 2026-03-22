"""Ome Identity Protocol — cross-ecosystem verifiable identity standard.

Every Ome carries a standardized identity card that any compatible platform
can read and verify. This is how Ome travels between Claude, ChatGPT,
OpenClaw, MCP servers, SOAP spaces, and future OmeTown.

Protocols supported:
  - mcp: resources/read("ome://identity")
  - http: GET /api/ome/identity
  - soap: agent.presence event payload
  - generic: JSON export
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ome.core import Ome


@dataclass
class OmeIdentity:
    """Ome standard identity protocol — cross-ecosystem passport."""

    ome_id: str = ""  # "ome:{name}:{hash}"
    version: str = "0.4.0"
    public_persona: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    trust_policy: dict[str, Any] = field(default_factory=dict)
    mindos_anchor: str = ""  # sha256 hash of identity content
    signature: str = ""  # optional cryptographic signature
    created_at: float = 0.0

    @classmethod
    def from_ome(cls, ome: "Ome") -> "OmeIdentity":
        """Generate a standard identity card from an Ome instance."""
        identity = ome.soul.identity
        personality = identity.get("personality", {})
        name = identity.get("name", "User")

        # Generate deterministic ome_id
        id_content = json.dumps({
            "name": name,
            "traits": personality.get("traits", []),
            "created_at": identity.get("created_at", ""),
        }, sort_keys=True)
        id_hash = hashlib.sha256(id_content.encode()).hexdigest()[:12]
        ome_id = f"ome:{name.lower()}:{id_hash}"

        # Mindos anchor: hash of full identity for verification
        anchor_content = json.dumps(identity, sort_keys=True, ensure_ascii=False)
        mindos_anchor = hashlib.sha256(anchor_content.encode()).hexdigest()

        # Public persona (safe to share)
        public_persona = {
            "display_name": name,
            "traits": personality.get("traits", [])[:5],
            "interests": personality.get("topics", [])[:5],
            "style_summary": personality.get("style", ""),
            "bond_level": ome.bond.level,
            "bond_name": ome.bond.current_level_info().get("name", ""),
        }

        # Capabilities
        available_skills = ome.list_skills()
        capabilities = {
            "protocols": ["mcp", "http", "soap"],
            "skills": [s["name"] for s in available_skills if s.get("available")],
            "autonomy_level": "observer",  # Will be enhanced in O5
            "can_receive": ["text", "command", "calibration"],
        }

        # Trust policy
        trust_policy = {
            "default_trust": 1,
            "auto_upgrade_after": 10,  # interactions
            "max_auto_trust": 2,
        }

        return cls(
            ome_id=ome_id,
            version="0.4.0",
            public_persona=public_persona,
            capabilities=capabilities,
            trust_policy=trust_policy,
            mindos_anchor=mindos_anchor,
            created_at=time.time(),
        )

    def expose_for(self, protocol: str) -> dict[str, Any]:
        """Format identity for a specific protocol.

        Args:
            protocol: "mcp" | "http" | "soap" | "generic"
        """
        base = {
            "ome_id": self.ome_id,
            "version": self.version,
            "persona": self.public_persona,
            "capabilities": self.capabilities,
        }

        if protocol == "mcp":
            return {
                "uri": "ome://identity",
                "mimeType": "application/json",
                "text": json.dumps(base, ensure_ascii=False),
            }

        elif protocol == "http":
            base["trust_policy"] = self.trust_policy
            base["mindos_anchor"] = self.mindos_anchor
            return base

        elif protocol == "soap":
            return {
                "event": "agent.presence",
                "agent_id": self.ome_id,
                "payload": base,
            }

        else:  # generic
            return {
                **base,
                "trust_policy": self.trust_policy,
                "mindos_anchor": self.mindos_anchor,
                "signature": self.signature,
                "created_at": self.created_at,
            }

    def verify(self, other_anchor: str) -> bool:
        """Verify this identity against a known anchor hash."""
        return self.mindos_anchor == other_anchor

    def to_dict(self) -> dict[str, Any]:
        return {
            "ome_id": self.ome_id,
            "version": self.version,
            "public_persona": self.public_persona,
            "capabilities": self.capabilities,
            "trust_policy": self.trust_policy,
            "mindos_anchor": self.mindos_anchor,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OmeIdentity":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
