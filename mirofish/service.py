"""Offline P0 session service for a traceable MiroFish-style simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from random import Random
import re
from typing import Callable, Iterable
from uuid import uuid4

from .errors import ConfigurationError, InputValidationError, MiroFishError, StateTransitionError
from .models import (
    Entity,
    Evidence,
    Relation,
    ReportConclusion,
    ReportSection,
    Role,
    SimulationConfig,
    SimulationEvent,
    SimulationReport,
    SimulationSession,
    TaskEvent,
    TaskStatus,
    WorldModel,
)
from .providers import MockSimulationProvider, SimulationProvider


_ALLOWED_SUFFIXES = {".txt", ".md", ".markdown"}
_STOP_WORDS = {
    "about", "after", "against", "among", "and", "are", "from", "into",
    "that", "the", "their", "this", "through", "with", "will", "would",
}
_TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _stable_id(kind: str, *parts: str) -> str:
    normalized = "\x1f".join(part.strip().casefold() for part in parts)
    return f"{kind}-{sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _safe_name(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1] or "seed.txt"


class MiroFishService:
    """In-memory task service with explicit lifecycle and retry semantics.

    The service is deliberately synchronous for P0, matching the base
    llmfetcher public runtime.  Applications may place it behind a worker or
    FastAPI endpoint without changing its deterministic domain API.
    """

    def __init__(self, providers: Iterable[SimulationProvider] = ()) -> None:
        self._providers: dict[str, SimulationProvider] = {"mock": MockSimulationProvider()}
        self._sessions: dict[str, SimulationSession] = {}
        for provider in providers:
            self.register_provider(provider)

    def register_provider(self, provider: SimulationProvider) -> None:
        if not isinstance(provider, SimulationProvider):
            raise TypeError("provider must implement SimulationProvider")
        if not provider.name.strip():
            raise ValueError("provider.name must be non-empty")
        self._providers[provider.name] = provider

    def create_session(
        self,
        *,
        seed_text: str,
        question: str,
        filename: str = "seed.txt",
        config: SimulationConfig | None = None,
    ) -> SimulationSession:
        """Validate a UTF-8 TXT/MD text seed and create a queued session."""
        validated_config = config or SimulationConfig()
        self._validate_config(validated_config)
        seed_name = self._validate_seed_name(filename)
        self._validate_seed_text(seed_text, validated_config)
        self._validate_question(question)
        session = SimulationSession(
            id=f"session-{uuid4().hex}",
            seed_name=seed_name,
            seed_text=seed_text,
            question=question.strip(),
            config=validated_config,
            created_at=_now(),
        )
        self._sessions[session.id] = session
        self._record(session, TaskStatus.QUEUED, "queued", "Session accepted")
        return session

    def create_session_from_bytes(
        self,
        *,
        content: bytes,
        question: str,
        filename: str = "seed.txt",
        config: SimulationConfig | None = None,
    ) -> SimulationSession:
        """Decode a seed explicitly as UTF-8 instead of guessing encodings."""
        try:
            seed_text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputValidationError(
                "seed_not_utf8",
                "Seed material must be UTF-8 encoded TXT or Markdown.",
                "Save the file as UTF-8 and upload it again.",
                {"filename": _safe_name(filename)},
            ) from exc
        return self.create_session(
            seed_text=seed_text, question=question, filename=filename, config=config
        )

    def get_session(self, session_id: str) -> SimulationSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise InputValidationError(
                "session_not_found",
                "No simulation session exists for this ID.",
                "Create a session before reading or running it.",
                {"session_id": session_id},
            ) from exc

    def get_events(self, session_id: str) -> tuple[TaskEvent, ...]:
        return tuple(self.get_session(session_id).events)

    def cancel(self, session_id: str) -> SimulationSession:
        session = self.get_session(session_id)
        if session.status in _TERMINAL:
            raise StateTransitionError(
                "cannot_cancel_terminal_task",
                f"Cannot cancel a {session.status.value} task.",
                "Use retry for a failed or cancelled task, or create a new session.",
            )
        session.cancellation_requested = True
        if session.status in {TaskStatus.QUEUED, TaskStatus.PREPARING}:
            self._mark_cancelled(session, "Cancelled before simulation began")
        return session

    def run(
        self,
        session_id: str,
        *,
        cancellation_check: Callable[[SimulationSession], bool] | None = None,
    ) -> SimulationSession:
        """Run one attempt; terminal attempts require explicit :meth:`retry`."""
        session = self.get_session(session_id)
        if session.status in _TERMINAL:
            raise StateTransitionError(
                "explicit_retry_required",
                f"Task is {session.status.value}; it will not be reused implicitly.",
                "Call retry(session_id) before running this task again.",
            )
        if session.status is not TaskStatus.QUEUED:
            raise StateTransitionError(
                "task_already_started",
                f"Task is already in {session.status.value} state.",
                "Wait for this attempt to finish, cancel it, or inspect its events.",
            )
        try:
            self._transition(session, TaskStatus.PREPARING, "building_world", "Building traceable world model")
            if self._should_cancel(session, cancellation_check):
                return session
            session.world = self._build_world(
                session.seed_text, session.seed_name, session.question, session.config.max_agents
            )
            self._transition(session, TaskStatus.RUNNING, "simulating", "Running deterministic simulation")
            session.started_at = _now()
            provider = self._providers[session.config.provider]
            random = Random(session.config.random_seed)
            for round_number in range(1, session.config.max_rounds + 1):
                if self._should_cancel(session, cancellation_check):
                    return session
                output = provider.run_round(
                    world=session.world,
                    question=session.question,
                    config=session.config,
                    round_number=round_number,
                    random=random,
                )
                session.world.simulation_events.extend(output.events)
                self._record(
                    session,
                    TaskStatus.RUNNING,
                    "simulating",
                    f"Completed deterministic round {round_number}",
                    {"round": round_number, "event_ids": [event.id for event in output.events]},
                )
            if self._should_cancel(session, cancellation_check):
                return session
            self._transition(session, TaskStatus.REPORTING, "generating_report", "Generating traceable report")
            session.report = self._build_report(session)
            self._transition(session, TaskStatus.COMPLETED, "completed", "Simulation completed")
            session.ended_at = _now()
        except Exception as exc:  # Retain partial world/events for inspection.
            if isinstance(exc, MiroFishError):
                error = exc.as_dict()
            else:
                error = {
                    "code": "simulation_failed",
                    "message": "Simulation provider failed during this attempt.",
                    "hint": "Inspect task events and retry explicitly after correcting the provider.",
                }
            session.error = error
            session.status = TaskStatus.FAILED
            session.stage = "failed"
            session.ended_at = _now()
            self._record(session, TaskStatus.FAILED, "failed", error["message"], {"error": error})
        return session

    def retry(self, session_id: str) -> SimulationSession:
        """Start a clean, explicit attempt while preserving a compact audit trail."""
        session = self.get_session(session_id)
        if session.status not in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            raise StateTransitionError(
                "retry_requires_failed_or_cancelled_task",
                f"Cannot retry a {session.status.value} task.",
                "Retry is only available after failed or cancelled attempts.",
            )
        session.attempt_history.append({
            "attempt": session.attempt,
            "status": session.status.value,
            "ended_at": session.ended_at,
            "error": session.error,
            "event_count": len(session.events),
        })
        session.attempt += 1
        session.status = TaskStatus.QUEUED
        session.stage = "queued"
        session.started_at = None
        session.ended_at = None
        session.error = None
        session.world = None
        session.report = None
        session.cancellation_requested = False
        self._record(session, TaskStatus.QUEUED, "queued", "Explicit retry started", {"attempt": session.attempt})
        return session

    def _validate_config(self, config: SimulationConfig) -> None:
        if not isinstance(config.random_seed, int):
            raise ConfigurationError("invalid_random_seed", "random_seed must be an integer.")
        if not 1 <= config.max_agents <= 12:
            raise ConfigurationError("max_agents_out_of_range", "max_agents must be between 1 and 12.", "Use the small default of 3 agents.")
        if not 1 <= config.max_rounds <= 20:
            raise ConfigurationError("max_rounds_out_of_range", "max_rounds must be between 1 and 20.", "Use the small default of 3 rounds.")
        if not 1 <= config.max_seed_chars <= 200_000:
            raise ConfigurationError("max_seed_chars_out_of_range", "max_seed_chars must be between 1 and 200000.")
        if config.provider not in self._providers:
            raise ConfigurationError(
                "provider_not_configured",
                f"Provider '{config.provider}' is not configured for this service.",
                "Use provider='mock' for offline mode, or inject a configured SimulationProvider.",
                {"provider": config.provider},
            )

    @staticmethod
    def _validate_seed_name(filename: str) -> str:
        name = _safe_name(filename)
        if not any(name.casefold().endswith(suffix) for suffix in _ALLOWED_SUFFIXES):
            raise InputValidationError(
                "unsupported_seed_format",
                "Only UTF-8 .txt, .md, and .markdown seed files are supported in P0.",
                "Export the material as UTF-8 TXT or Markdown and try again.",
                {"filename": name},
            )
        return name

    @staticmethod
    def _validate_seed_text(seed_text: str, config: SimulationConfig) -> None:
        if not isinstance(seed_text, str) or not seed_text.strip():
            raise InputValidationError("empty_seed", "Seed material must contain non-whitespace text.", "Add source material and try again.")
        if len(seed_text) > config.max_seed_chars:
            raise InputValidationError(
                "seed_too_large",
                f"Seed material exceeds the {config.max_seed_chars}-character limit.",
                "Split the material or choose a permitted max_seed_chars value.",
                {"max_seed_chars": config.max_seed_chars},
            )

    @staticmethod
    def _validate_question(question: str) -> None:
        if not isinstance(question, str) or not question.strip():
            raise InputValidationError(
                "empty_question",
                "A non-empty simulation question is required.",
                "Ask a concrete question the simulation should explore.",
            )

    def _should_cancel(
        self, session: SimulationSession, check: Callable[[SimulationSession], bool] | None
    ) -> bool:
        if session.cancellation_requested or (check is not None and check(session)):
            self._mark_cancelled(session, "Cancellation requested")
            return True
        return False

    def _mark_cancelled(self, session: SimulationSession, message: str) -> None:
        session.cancellation_requested = True
        session.status = TaskStatus.CANCELLED
        session.stage = "cancelled"
        session.ended_at = _now()
        self._record(session, TaskStatus.CANCELLED, "cancelled", message)

    def _transition(self, session: SimulationSession, status: TaskStatus, stage: str, message: str) -> None:
        allowed = {
            TaskStatus.QUEUED: {TaskStatus.PREPARING},
            TaskStatus.PREPARING: {TaskStatus.RUNNING},
            TaskStatus.RUNNING: {TaskStatus.REPORTING},
            TaskStatus.REPORTING: {TaskStatus.COMPLETED},
        }
        if status not in allowed.get(session.status, set()):
            raise StateTransitionError(
                "invalid_state_transition",
                f"Cannot transition from {session.status.value} to {status.value}.",
            )
        session.status = status
        session.stage = stage
        self._record(session, status, stage, message)

    @staticmethod
    def _record(
        session: SimulationSession,
        status: TaskStatus,
        stage: str,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        # Logical timestamps keep mock event logs reproducible. Wall-clock
        # session timestamps remain available on SimulationSession.
        sequence = len(session.events) + 1
        session.events.append(TaskEvent(
            sequence=sequence,
            timestamp=f"logical:{sequence:06d}",
            status=status,
            stage=stage,
            message=message,
            data=data or {},
        ))

    def _build_world(
        self, seed_text: str, seed_name: str, question: str, max_agents: int
    ) -> WorldModel:
        evidence = self._extract_evidence(seed_text, seed_name)
        entities = self._extract_entities(seed_text, evidence, question)
        relations = self._extract_relations(entities, evidence)
        roles = self._build_roles(entities[:max_agents])
        initial_events = [
            SimulationEvent(
                id=_stable_id("initial", item.id),
                round_number=0,
                actor_role_id=roles[index % len(roles)].id,
                event_type="seed_fact",
                summary=item.text,
                evidence_ids=(item.id,),
                provenance="input_fact",
                uncertainty="low",
            )
            for index, item in enumerate(evidence)
        ]
        return WorldModel(evidence=evidence, entities=entities, relations=relations, roles=roles, initial_events=initial_events)

    @staticmethod
    def _extract_evidence(seed_text: str, seed_name: str) -> list[Evidence]:
        fragments = [match for match in re.finditer(r"[^\n.!?。！？]+[\n.!?。！？]*", seed_text) if match.group().strip()]
        items: list[Evidence] = []
        for match in fragments[:24]:
            text = match.group().strip()
            items.append(Evidence(
                id=_stable_id("evidence", seed_name, str(match.start()), text),
                text=text,
                document_name=seed_name,
                char_start=match.start(),
                char_end=match.end(),
            ))
        if not items:  # _validate_seed_text has rejected whitespace-only input.
            raise InputValidationError("no_extractable_evidence", "No traceable text fragments could be extracted from the seed.")
        return items

    @staticmethod
    def _extract_entities(seed_text: str, evidence: list[Evidence], question: str) -> list[Entity]:
        candidates = re.findall(r"\b[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*\b", seed_text)
        candidates += [word for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", seed_text) if word.casefold() not in _STOP_WORDS]
        names: list[str] = []
        for candidate in candidates:
            name = " ".join(candidate.split())
            if name and name.casefold() not in {item.casefold() for item in names}:
                names.append(name)
            if len(names) >= 8:
                break
        fallback = ["Seed context", "Question focus", "Scenario outlook"]
        entities: list[Entity] = []
        for index, name in enumerate((names + fallback)[: max(3, len(names))]):
            supporting = tuple(item.id for item in evidence if name.casefold() in item.text.casefold())
            provenance = "input_fact" if supporting else "model_inference"
            if name == "Question focus":
                supporting = (evidence[0].id,)
            entities.append(Entity(
                id=_stable_id("entity", name),
                name=name,
                entity_type="source_entity" if provenance == "input_fact" else "analytical_construct",
                summary=(f"Extracted from seed material: {name}" if provenance == "input_fact" else f"Analytical construct for: {question}"),
                evidence_ids=supporting,
                provenance=provenance,
            ))
        # de-duplicate fallback names in a short seed while preserving stable order.
        result: list[Entity] = []
        seen: set[str] = set()
        for entity in entities:
            if entity.id not in seen:
                result.append(entity)
                seen.add(entity.id)
        return result[:8]

    @staticmethod
    def _extract_relations(entities: list[Entity], evidence: list[Evidence]) -> list[Relation]:
        relations: list[Relation] = []
        for source_index, source in enumerate(entities):
            for target in entities[source_index + 1:]:
                shared = tuple(
                    item.id for item in evidence
                    if source.name.casefold() in item.text.casefold()
                    and target.name.casefold() in item.text.casefold()
                )
                if shared:
                    relations.append(Relation(
                        id=_stable_id("relation", source.id, target.id, "co-mentioned"),
                        source_entity_id=source.id,
                        target_entity_id=target.id,
                        relation_type="co-mentioned",
                        summary=f"{source.name} and {target.name} occur in the same input fact.",
                        evidence_ids=shared,
                        provenance="input_fact",
                        uncertainty="low",
                    ))
        if not relations and len(entities) >= 2:
            relations.append(Relation(
                id=_stable_id("relation", entities[0].id, entities[1].id, "possible-influence"),
                source_entity_id=entities[0].id,
                target_entity_id=entities[1].id,
                relation_type="possible-influence",
                summary=f"A simulation hypothesis links {entities[0].name} to {entities[1].name}.",
                evidence_ids=(evidence[0].id,),
                provenance="model_inference",
                uncertainty="high",
            ))
        return relations

    @staticmethod
    def _build_roles(entities: list[Entity]) -> list[Role]:
        roles: list[Role] = []
        for entity in entities[:12]:
            roles.append(Role(
                id=_stable_id("role", entity.id),
                name=f"Perspective: {entity.name}",
                role_type="stakeholder_perspective",
                summary=f"A simulated perspective grounded in {entity.name}.",
                entity_id=entity.id,
                evidence_ids=entity.evidence_ids,
                provenance=entity.provenance,
            ))
        return roles

    @staticmethod
    def _build_report(session: SimulationSession) -> SimulationReport:
        assert session.world is not None
        world = session.world
        seed_refs = tuple(item.id for item in world.evidence[:3])
        event_refs = tuple(item.id for item in world.simulation_events)
        facts = ReportConclusion(
            id=_stable_id("conclusion", session.question, "facts"),
            statement="The seed provides the factual scope used by this simulation.",
            evidence_ids=seed_refs,
            event_ids=(),
            provenance="input_fact",
            uncertainty="low",
        )
        trajectory = ReportConclusion(
            id=_stable_id("conclusion", session.question, "trajectory"),
            statement="The simulated trajectory is a scenario, not a prediction or verified real-world outcome.",
            evidence_ids=seed_refs[:1],
            event_ids=event_refs,
            provenance="model_inference",
            uncertainty="medium",
        )
        uncertainty = ReportConclusion(
            id=_stable_id("conclusion", session.question, "uncertainty"),
            statement="Additional evidence or a configured real provider may change the simulated interpretation.",
            evidence_ids=seed_refs[:1],
            event_ids=event_refs,
            provenance="model_inference",
            uncertainty="high",
        )
        return SimulationReport(
            title="Traceable simulation report",
            question=session.question,
            generated_at="logical:report-complete",
            sections=(
                ReportSection("Scope and seed facts", "This section reports only source-grounded material.", (facts,)),
                ReportSection("Simulated trajectory", "This section contains deterministic mock simulation events.", (trajectory,)),
                ReportSection("Uncertainty and limits", "Simulation output remains an explicitly labelled inference.", (uncertainty,)),
            ),
        )
