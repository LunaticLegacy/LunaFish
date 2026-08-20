"""Offline P0 regression tests for the traceable simulation service."""

from __future__ import annotations

import unittest
from random import Random

from llmfetcher.mirofish import (
    ConfigurationError,
    InputValidationError,
    MiroFishService,
    ProviderRound,
    SimulationConfig,
    StateTransitionError,
    TaskStatus,
)
from llmfetcher.mirofish.models import WorldModel


SEED = "Acme works with City Council on a transport pilot. Acme publishes a timeline."
QUESTION = "How might stakeholders respond to the pilot?"


class FailingProvider:
    name = "failing"

    def run_round(
        self,
        *,
        world: WorldModel,
        question: str,
        config: SimulationConfig,
        round_number: int,
        random: Random,
    ) -> ProviderRound:
        raise RuntimeError("deliberate offline failure")


class MiroFishP0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MiroFishService()

    def create(self, **kwargs):
        return self.service.create_session(
            seed_text=kwargs.pop("seed_text", SEED),
            question=kwargs.pop("question", QUESTION),
            filename=kwargs.pop("filename", "brief.md"),
            config=kwargs.pop("config", SimulationConfig(random_seed=11, max_rounds=3)),
            **kwargs,
        )

    def test_accepts_utf8_txt_and_md_and_rejects_actionable_bad_input(self) -> None:
        session = self.service.create_session_from_bytes(
            content=SEED.encode("utf-8"), question=QUESTION, filename="brief.txt"
        )
        self.assertEqual(session.status, TaskStatus.QUEUED)

        with self.assertRaises(InputValidationError) as unsupported:
            self.create(filename="brief.pdf")
        self.assertEqual(unsupported.exception.code, "unsupported_seed_format")
        self.assertIn("Markdown", unsupported.exception.hint)

        with self.assertRaises(InputValidationError) as invalid_encoding:
            self.service.create_session_from_bytes(
                content=b"\xff", question=QUESTION, filename="brief.md"
            )
        self.assertEqual(invalid_encoding.exception.code, "seed_not_utf8")

        with self.assertRaises(InputValidationError) as missing_question:
            self.create(question="   ")
        self.assertEqual(missing_question.exception.code, "empty_question")

    def test_world_ids_are_stable_and_all_records_are_traceable(self) -> None:
        first = self.service.run(self.create().id)
        second = self.service.run(self.create().id)
        assert first.world is not None
        assert second.world is not None
        self.assertGreaterEqual(len(first.world.entities), 3)
        self.assertTrue(first.world.relations)
        self.assertTrue(first.world.roles)
        self.assertTrue(first.world.initial_events)
        self.assertEqual(
            [(item.id, item.provenance, item.evidence_ids) for item in first.world.entities],
            [(item.id, item.provenance, item.evidence_ids) for item in second.world.entities],
        )
        self.assertTrue(all(item.provenance == "input_fact" for item in first.world.evidence))
        self.assertTrue(all(item.provenance == "model_inference" for item in first.world.simulation_events))
        evidence_ids = {item.id for item in first.world.evidence}
        self.assertTrue(all(set(item.evidence_ids) <= evidence_ids for item in first.world.relations))

    def test_complete_lifecycle_is_observable(self) -> None:
        session = self.service.run(self.create().id)
        self.assertEqual(session.status, TaskStatus.COMPLETED)
        self.assertEqual(session.stage, "completed")
        self.assertIsNotNone(session.started_at)
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(
            [event.status for event in session.events if event.status != TaskStatus.RUNNING],
            [TaskStatus.QUEUED, TaskStatus.PREPARING, TaskStatus.REPORTING, TaskStatus.COMPLETED],
        )
        self.assertTrue(all(event.timestamp.startswith("logical:") for event in session.events))

    def test_cancellation_requires_explicit_retry_and_keeps_audit(self) -> None:
        session = self.create(config=SimulationConfig(random_seed=4, max_rounds=4))
        cancelled = self.service.run(
            session.id,
            cancellation_check=lambda current: len(current.world.simulation_events) >= 1 if current.world else False,
        )
        self.assertEqual(cancelled.status, TaskStatus.CANCELLED)
        self.assertIsNotNone(cancelled.world)
        with self.assertRaises(StateTransitionError) as rerun:
            self.service.run(session.id)
        self.assertEqual(rerun.exception.code, "explicit_retry_required")

        retried = self.service.retry(session.id)
        self.assertEqual(retried.status, TaskStatus.QUEUED)
        self.assertEqual(retried.attempt, 2)
        self.assertEqual(retried.attempt_history[-1]["status"], "cancelled")
        self.assertIsNone(retried.world)
        self.assertEqual(self.service.run(session.id).status, TaskStatus.COMPLETED)

    def test_failure_requires_explicit_retry_without_reusing_partial_world(self) -> None:
        service = MiroFishService(providers=[FailingProvider()])
        session = service.create_session(
            seed_text=SEED,
            question=QUESTION,
            config=SimulationConfig(provider="failing"),
        )
        failed = service.run(session.id)
        self.assertEqual(failed.status, TaskStatus.FAILED)
        self.assertEqual(failed.error["code"], "simulation_failed")
        self.assertIsNotNone(failed.world)
        service.retry(session.id)
        self.assertIsNone(session.world)
        self.assertEqual(session.attempt_history[-1]["status"], "failed")

    def test_mock_event_log_and_report_are_deterministic(self) -> None:
        config = SimulationConfig(random_seed=97, max_rounds=4)
        first = self.service.run(self.create(config=config).id)
        second = self.service.run(self.create(config=SimulationConfig(random_seed=97, max_rounds=4)).id)
        self.assertEqual(first.events, second.events)
        assert first.report is not None and second.report is not None
        self.assertEqual(first.report.to_markdown(), second.report.to_markdown())
        self.assertIn("model_inference", first.report.to_markdown())
        self.assertIn("sources: evidence-", first.report.to_markdown())

    def test_unconfigured_real_provider_returns_structured_configuration_error(self) -> None:
        with self.assertRaises(ConfigurationError) as context:
            self.create(config=SimulationConfig(provider="real_llm"))
        error = context.exception.as_dict()
        self.assertEqual(error["code"], "provider_not_configured")
        self.assertEqual(error["details"]["provider"], "real_llm")
        self.assertNotIn(SEED, str(error))

    def test_configuration_limits_bound_the_offline_workload(self) -> None:
        with self.assertRaises(ConfigurationError) as invalid_rounds:
            self.create(config=SimulationConfig(max_rounds=21))
        self.assertEqual(invalid_rounds.exception.code, "max_rounds_out_of_range")

        session = self.service.run(
            self.create(config=SimulationConfig(max_agents=1, max_rounds=1)).id
        )
        assert session.world is not None
        self.assertEqual(len(session.world.roles), 1)


if __name__ == "__main__":
    unittest.main()
