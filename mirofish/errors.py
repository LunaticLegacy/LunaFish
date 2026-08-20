"""Errors returned by the offline MiroFish-compatible service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MiroFishError(Exception):
    """A safe, actionable error suitable for API and console callers."""

    code: str
    message: str
    hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without seed text or secrets."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            result["details"] = self.details
        return result


class InputValidationError(MiroFishError):
    """Raised when a seed document or question cannot be used."""


class ConfigurationError(MiroFishError):
    """Raised before a task is created when its selected provider is invalid."""


class StateTransitionError(MiroFishError):
    """Raised when an operation is not valid for the current task state."""
