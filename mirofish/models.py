"""Stable, provenance-aware records used by :mod:`llmfetcher.mirofish`."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


Provenance = Literal["input_fact", "model_inference"]


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Evidence:
    id: str
    text: str
    document_name: str
    char_start: int
    char_end: int
    provenance: Literal["input_fact"] = "input_fact"


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    entity_type: str
    summary: str
    evidence_ids: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True)
class Relation:
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    summary: str
    evidence_ids: tuple[str, ...]
    provenance: Provenance
    uncertainty: str = "medium"


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    role_type: str
    summary: str
    entity_id: str
    evidence_ids: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True)
class SimulationEvent:
    id: str
    round_number: int
    actor_role_id: str
    event_type: str
    summary: str
    evidence_ids: tuple[str, ...]
    provenance: Provenance
    uncertainty: str


@dataclass
class WorldModel:
    """The session-local graph. IDs derive only from normalized input."""

    evidence: list[Evidence] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    initial_events: list[SimulationEvent] = field(default_factory=list)
    simulation_events: list[SimulationEvent] = field(default_factory=list)

    def evidence_by_id(self, evidence_id: str) -> Evidence | None:
        return next((item for item in self.evidence if item.id == evidence_id), None)


@dataclass(frozen=True)
class ReportConclusion:
    id: str
    statement: str
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    provenance: Provenance
    uncertainty: str


@dataclass(frozen=True)
class ReportSection:
    title: str
    body: str
    conclusions: tuple[ReportConclusion, ...]


@dataclass(frozen=True)
class SimulationReport:
    title: str
    question: str
    generated_at: str
    sections: tuple[ReportSection, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"**Question:** {self.question}", ""]
        for section in self.sections:
            lines.extend([f"## {section.title}", "", section.body, ""])
            for conclusion in section.conclusions:
                references = [*conclusion.evidence_ids, *conclusion.event_ids]
                lines.append(
                    f"- [{conclusion.provenance}; uncertainty: "
                    f"{conclusion.uncertainty}] {conclusion.statement} "
                    f"(sources: {', '.join(references) or 'none'})"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class TaskEvent:
    sequence: int
    timestamp: str
    status: TaskStatus
    stage: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationConfig:
    """Bounded configuration with an offline deterministic default."""

    provider: str = "mock"
    random_seed: int = 0
    max_agents: int = 3
    max_rounds: int = 3
    max_seed_chars: int = 100_000


@dataclass
class SimulationSession:
    id: str
    seed_name: str
    seed_text: str
    question: str
    config: SimulationConfig
    status: TaskStatus = TaskStatus.QUEUED
    stage: str = "queued"
    created_at: str = ""
    started_at: str | None = None
    ended_at: str | None = None
    error: dict[str, Any] | None = None
    world: WorldModel | None = None
    report: SimulationReport | None = None
    events: list[TaskEvent] = field(default_factory=list)
    attempt: int = 1
    attempt_history: list[dict[str, Any]] = field(default_factory=list)
    cancellation_requested: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
