"""Traceable, offline-first P0 simulation service inspired by observed behavior.

This is an independent implementation.  Its default provider is a local,
deterministic mock; no API key or network access is needed.
"""

from .errors import ConfigurationError, InputValidationError, MiroFishError, StateTransitionError
from .models import (
    Entity, Evidence, Relation, ReportConclusion, ReportSection, Role,
    SimulationConfig, SimulationEvent, SimulationReport, SimulationSession,
    TaskEvent, TaskStatus, WorldModel,
)
from .providers import MockSimulationProvider, ProviderRound, SimulationProvider
from .service import MiroFishService

__all__ = [
    "ConfigurationError", "Entity", "Evidence", "InputValidationError",
    "MiroFishError", "MiroFishService", "MockSimulationProvider",
    "ProviderRound", "Relation", "ReportConclusion", "ReportSection", "Role",
    "SimulationConfig", "SimulationEvent", "SimulationProvider", "SimulationReport",
    "SimulationSession", "StateTransitionError", "TaskEvent", "TaskStatus", "WorldModel",
]
