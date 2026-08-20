"""Provider boundary for a future llmfetcher-backed simulation engine.

The P0 package intentionally registers only ``MockSimulationProvider``.  A
real adapter can implement ``SimulationProvider`` around ``LLMFetcher`` but
must be injected by an application; this module never makes a network call.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Protocol, runtime_checkable

from .models import Role, SimulationConfig, SimulationEvent, WorldModel


@dataclass(frozen=True)
class ProviderRound:
    """A provider's bounded, inspectable contribution to one simulation turn."""

    events: tuple[SimulationEvent, ...]


@runtime_checkable
class SimulationProvider(Protocol):
    """Injection point for deterministic mocks or real LLM-backed providers."""

    name: str

    def run_round(
        self,
        *,
        world: WorldModel,
        question: str,
        config: SimulationConfig,
        round_number: int,
        random: Random,
    ) -> ProviderRound:
        """Return provenance-labelled events without mutating the session."""


class MockSimulationProvider:
    """Local reproducible engine; it does not access models, files, or network."""

    name = "mock"
    _ACTIONS = ("signals concern", "supports coordination", "requests clarification")

    def run_round(
        self,
        *,
        world: WorldModel,
        question: str,
        config: SimulationConfig,
        round_number: int,
        random: Random,
    ) -> ProviderRound:
        if not world.roles:
            return ProviderRound(events=())
        role: Role = world.roles[random.randrange(len(world.roles))]
        action = self._ACTIONS[random.randrange(len(self._ACTIONS))]
        evidence_ids = role.evidence_ids or tuple(item.id for item in world.evidence[:1])
        event = SimulationEvent(
            id=f"sim-{round_number:03d}-{role.id[-10:]}",
            round_number=round_number,
            actor_role_id=role.id,
            event_type="role_response",
            summary=(
                f"{role.name} {action} while considering the question: {question}"
            ),
            evidence_ids=tuple(evidence_ids),
            provenance="model_inference",
            uncertainty="medium",
        )
        return ProviderRound(events=(event,))
