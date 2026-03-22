"""HITL Permission Sandbox — all external actions need user approval.

Trust Levels:
  0 - Locked: Ome cannot act without explicit per-action approval
  1 - Observer: Can read (recall, search), cannot write or send
  2 - Assistant: Can write locally (drafts, notes, files), cannot send externally
  3 - Deputy: Can send on user's behalf (messages, emails) with batch approval
  4 - Autonomous: Can act freely within pre-approved scopes
  5 - Full Trust: Unrestricted (reserved for bonded Ome, level 6+)

Phase 1 implements 0-2. Levels 3-5 are for Maxim/OmeTown stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class TrustLevel(IntEnum):
    LOCKED = 0
    OBSERVER = 1
    ASSISTANT = 2
    DEPUTY = 3
    AUTONOMOUS = 4
    FULL_TRUST = 5


class ActionCategory(str):
    """Categories of actions with different permission requirements."""
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    READ_LOCAL = "read_local"
    WRITE_LOCAL = "write_local"
    DRAFT = "draft"              # Create draft (email, article) — needs review
    TRANSACT = "transact"        # Execute transaction (send, pay, delete)
    SEND_MESSAGE = "send_message"
    API_CALL = "api_call"
    IOT_CONTROL = "iot_control"
    SOCIAL_INTERACT = "social_interact"


class PermissionResult:
    """Three-state permission check result."""
    ALLOWED = "allowed"       # Go ahead
    NEEDS_APPROVAL = "needs_approval"  # Ask user first
    DENIED = "denied"         # Cannot do at all


# Minimum trust level required for each action category
_ACTION_TRUST_MAP: dict[str, TrustLevel] = {
    ActionCategory.READ_MEMORY: TrustLevel.OBSERVER,
    ActionCategory.WRITE_MEMORY: TrustLevel.OBSERVER,
    ActionCategory.READ_LOCAL: TrustLevel.OBSERVER,
    ActionCategory.WRITE_LOCAL: TrustLevel.ASSISTANT,
    ActionCategory.DRAFT: TrustLevel.ASSISTANT,
    ActionCategory.TRANSACT: TrustLevel.DEPUTY,
    ActionCategory.SEND_MESSAGE: TrustLevel.DEPUTY,
    ActionCategory.API_CALL: TrustLevel.DEPUTY,
    ActionCategory.IOT_CONTROL: TrustLevel.AUTONOMOUS,
    ActionCategory.SOCIAL_INTERACT: TrustLevel.DEPUTY,
}


@dataclass
class PermissionRequest:
    """A request from the autonomy engine to perform an action."""
    action: str  # ActionCategory
    description: str  # Human-readable description
    details: dict[str, Any] = field(default_factory=dict)
    approved: Optional[bool] = None  # None = pending, True/False = decided

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "details": self.details,
            "approved": self.approved,
        }


@dataclass
class PermissionSandbox:
    """Controls what the Ome can do based on trust level.

    Default: TrustLevel.OBSERVER (can read, cannot write/send).
    Users can raise trust as bond grows.
    """

    trust_level: TrustLevel = TrustLevel.OBSERVER
    approved_scopes: set[str] = field(default_factory=set)  # Pre-approved action categories
    pending_requests: list[PermissionRequest] = field(default_factory=list)
    action_log: list[dict[str, Any]] = field(default_factory=list)

    def can_do(self, action: str) -> bool:
        """Check if the current trust level allows this action."""
        required = _ACTION_TRUST_MAP.get(action, TrustLevel.FULL_TRUST)
        return self.trust_level >= required or action in self.approved_scopes

    def check(self, action: str) -> str:
        """Three-state permission check.

        Returns:
            PermissionResult.ALLOWED: go ahead
            PermissionResult.NEEDS_APPROVAL: ask user first
            PermissionResult.DENIED: cannot do at all (trust too low, no path to approval)
        """
        if action in self.approved_scopes:
            return PermissionResult.ALLOWED

        required = _ACTION_TRUST_MAP.get(action, TrustLevel.FULL_TRUST)

        if self.trust_level >= required:
            return PermissionResult.ALLOWED

        # One level below required → can request approval
        if self.trust_level >= required - 1:
            return PermissionResult.NEEDS_APPROVAL

        return PermissionResult.DENIED

    def request_permission(self, action: str, description: str, **details) -> PermissionRequest:
        """Request permission for an action that exceeds current trust level.

        Returns a PermissionRequest. In CLI mode, the caller should prompt the user.
        In App mode, this becomes a push notification.
        """
        req = PermissionRequest(
            action=action,
            description=description,
            details=details,
        )
        self.pending_requests.append(req)
        return req

    def approve(self, request: PermissionRequest, remember_scope: bool = False):
        """Approve a pending permission request."""
        request.approved = True
        if remember_scope:
            self.approved_scopes.add(request.action)
        self._log_action(request.action, request.description, approved=True)

    def deny(self, request: PermissionRequest):
        """Deny a pending permission request."""
        request.approved = False
        self._log_action(request.action, request.description, approved=False)

    def raise_trust(self, new_level: TrustLevel):
        """Raise trust level (typically when bond level increases)."""
        if new_level > self.trust_level:
            self.trust_level = new_level

    def _log_action(self, action: str, description: str, approved: bool):
        from datetime import datetime
        self.action_log.append({
            "action": action,
            "description": description,
            "approved": approved,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep log manageable
        if len(self.action_log) > 100:
            self.action_log = self.action_log[-50:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trust_level": int(self.trust_level),
            "approved_scopes": list(self.approved_scopes),
            "action_log_count": len(self.action_log),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PermissionSandbox":
        return cls(
            trust_level=TrustLevel(d.get("trust_level", 1)),
            approved_scopes=set(d.get("approved_scopes", [])),
        )
