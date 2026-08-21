# LunaFish

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![Offline](https://img.shields.io/badge/offline--first-yes-brightgreen.svg)](https://github.com/LunaticLegacy/LunaFish)
[![Deterministic](https://img.shields.io/badge/deterministic-same_seed_same_output-brightgreen.svg)](https://github.com/LunaticLegacy/LunaFish)

**Deterministic stakeholder simulation — offline-first, fully traceable, ready for real LLM providers.**

LunaFish is the product superproject. It delivers **MiroFish**, an offline-first
stakeholder-simulation service, on top of the **llmfetcher** multi-agent
orchestration framework. Given a plain-text or Markdown brief and a question,
MiroFish builds a traceable world model — entities, relations, roles, evidence
with character offsets, and provenance-labelled events — then runs a bounded,
fully deterministic simulation and produces a Markdown report in which every
claim cites the exact sources that support it. The default engine is a local
mock provider: **no API key, no network, no model cost** — the same seed, the
same question, and the same configuration always produce the identical event
log and report. That reproducibility makes MiroFish an honest tool for
structured *what-if* exploration, stakeholder risk review, and scenario
documentation. When you are ready to move beyond mocks, the same service
plugs into real LLM-backed providers through a small `SimulationProvider`
protocol — without changing a single line of your session code.

## What it is / Architecture

LunaFish is a thin superproject that pins two moving parts together:

| Part | Location | Role |
| --- | --- | --- |
| **llmfetcher** (the engine) | `./llmfetcher` — a git submodule pinned to `main` | Provider-neutral LLM dispatch, tool-using Agent loop, context and memory, `AgentSwarm` + `ExecutionGraph` + `TaskBus`, and RAG modules |
| **MiroFish** (the product) | `./mirofish` — installed as `llmfetcher.mirofish` | Offline-first deterministic stakeholder simulation with world models, stable IDs, provenance, an explicit task lifecycle, and a provider boundary for future real engines |

```text
┌──────────────────────────────────────────────────────────────┐
│  LunaFish (superproject)                                     │
│                                                              │
│  ┌────────────────────────────┐   ┌───────────────────────┐  │
│  │  ./llmfetcher  (submodule) │   │  ./mirofish           │  │
│  │  multi-agent engine        │   │  llmfetcher.mirofish  │  │
│  │                            │   │                       │  │
│  │  LLMFetcher · backends     │   │  MiroFishService      │  │
│  │  Agent loop · tools        │   │  WorldModel · IDs     │  │
│  │  Context · Memory          │   │  Provenance           │  │
│  │  AgentSwarm · Graph·Bus    │   │  Lifecycle            │  │
│  │  RAG                       │   │  Mock provider        │  │
│  └────────────────────────────┘   └───────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

MiroFish does not fork the engine. It imports it: the distribution name is
`llmfetcher` (v0.4.0), the MiroFish package ships inside that distribution as
`llmfetcher.mirofish`, and the two share one install, one Python runtime, and
one version. The superproject exists so the product and its engine move
together as a single auditable unit — the engine revision is pinned as a
submodule commit, and MiroFish code lives in the superproject next to it.

## Features

**MiroFish (product layer)**

- **Offline-first by default** — `MockSimulationProvider` needs no API key and
  performs no network requests; runs are instant and cost nothing.
- **Deterministic** — stable SHA-256-derived IDs, seeded `random.Random`, and
  logical event timestamps mean the same input, seed, and config reproduce
  the identical event log and identical report Markdown.
- **Fully traceable provenance** — every record is labelled `input_fact`
  (extracted verbatim from the seed, with character offsets) or
  `model_inference` (derived by the simulator), and report conclusions cite
  their exact evidence and event sources.
- **World model** — stable entities, relations, roles, initial seed-fact
  events, and per-round simulation events, all addressable by ID.
- **Explicit lifecycle** — `queued → preparing → running → reporting →
  completed | failed | cancelled`, with every transition recorded as an
  observable `TaskEvent`.
- **Auditable retry** — terminal tasks are never silently rerun; an explicit
  `retry()` starts a clean attempt while preserving a compact attempt history.
- **Provider-ready boundary** — a runtime-checkable `SimulationProvider`
  protocol plus `register_provider()` make real LLM-backed engines an
  injection away.
- **Safe, structured errors** — `ConfigurationError`, `InputValidationError`,
  `StateTransitionError`, and `MiroFishError` carry codes, hints, and
  JSON-safe details (never raw seed text or secrets).

**llmfetcher engine layer**

- **Provider-neutral dispatch** — one `LLMFetcher` routes across OpenAI,
  DeepSeek, Anthropic, LiteLLM, OpenVINO, and ONNX Runtime, with ordered
  fallback and per-backend retry.
- **Terminal request cancellation** — `abort_active_requests()` closes
  provider transports and raises `LLMRequestCancelled`; a cancelled request is
  never retried or re-dispatched.
- **Tool-using Agent loop** — synchronous model-and-tool rounds, parallel tool
  batches, token accounting, bounded execution budgets, and cooperative
  stop/steer controls.
- **Durable context and memory** — linear history with LLM compaction,
  retrieval-aware context via the `MemoryProvider` contract, and a persistent
  entity/relation graph (`GraphContextHandler`, `SemanticGraphWorker`).
- **Multi-agent orchestration** — `AgentSwarm` with a dependency-driven
  `ExecutionGraph` (split/gather, mappers, routers) and a `TaskBus` that
  hands off bounded reports instead of raw worker transcripts.
- **Observability** — synchronous `ExecutionEvent` hooks for agent, graph,
  tool, routing, and task lifecycle events.
- **RAG** — `rag_module` and `rag_module_tlb` retrieval modules.
- **CLI + web console** — `llmfetcher` commands and the local
  `llmfetcher-web` console at `http://127.0.0.1:8765`.

## Installation

Requires **Python 3.12 or newer**.

Clone the superproject **with its engine submodule**:

```bash
git clone --recurse-submodules https://github.com/LunaticLegacy/LunaFish.git
```

If you already cloned without submodules:

```bash
git clone https://github.com/LunaticLegacy/LunaFish.git
cd LunaFish
git submodule update --init --recursive
```

Create a virtual environment and install the project (editable, so
`llmfetcher.mirofish` resolves from the repository root):

```bash
cd LunaFish
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

The base install includes the OpenAI, Anthropic, and LiteLLM client libraries
and the web console stack. The local OpenVINO and ONNX Runtime handlers
additionally require their respective runtime packages.

## Quick Start

### 1. A MiroFish simulation (fully offline)

```python
from llmfetcher.mirofish import MiroFishService, SimulationConfig

service = MiroFishService()

session = service.create_session(
    filename="brief.md",
    seed_text="Acme works with City Council on a transport pilot.",
    question="What stakeholder response might follow?",
    config=SimulationConfig(random_seed=7, max_rounds=3),
)

result = service.run(session.id)

print(result.status.value)          # "completed"
print(result.report.to_markdown())
```

No API key, no network — the mock provider produces the same event log and the
same report every time `random_seed=7` is used with this input.

### 2. A tool-using llmfetcher Agent

```python
from llmfetcher import Agent, LLMBackendConfig, LLMFetcher

fetcher = LLMFetcher([
    LLMBackendConfig(
        name="primary",
        provider="openai",
        model="gpt-4.1-mini",
        api_key="<api-key>",
        api_url="https://api.openai.com/v1",
    ),
])

agent = Agent(
    llm_fetcher=fetcher,
    system_prompt="Answer concisely and cite uncertainty.",
    default_max_rounds=6,
    default_max_tokens=2_048,
)

result = agent.run("Explain why shirts use different sleeve lengths.")
print(result.content)
print(agent.usage.total_tokens)
```

## MiroFish deep-dive

### Deterministic offline provider

The default `MockSimulationProvider` is a local, reproducible engine. It never
touches the filesystem, a model endpoint, or the network, and it never prompts
for a key. Rounds are driven by a seeded `random.Random(config.random_seed)`
instance, so any fixed seed yields byte-identical results. Stable IDs are
SHA-256 digests of normalized input (`entity-…`, `evidence-…`, `role-…`), and
the task event log uses logical timestamps so logs are reproducible too —
wall-clock session timestamps remain available on the session object.

```python
service = MiroFishService()                          # registers the "mock" provider
config = SimulationConfig(provider="mock", random_seed=42, max_rounds=5)
```

### Traceability and provenance

Everything MiroFish produces is linked back to its source:

- **Evidence** — seed text is split into fragments with `document_name`,
  `char_start`, `char_end`, and `provenance="input_fact"`.
- **Entities, relations, roles** — each carries `evidence_ids` and a
  `provenance` of `input_fact` (source-grounded) or `model_inference`
  (analytical construct).
- **Simulation events** — per-round role responses are always
  `model_inference` and record their `actor_role_id` and `evidence_ids`.
- **Report** — every conclusion is rendered as
  `[provenance; uncertainty: …] statement (sources: evidence-…, sim-…)`,
  so nothing in the final Markdown is an unsourced claim.

### Retry and cancellation semantics

- **Explicit retry only** — after `completed`, `failed`, or `cancelled`, a
  second `service.run(session.id)` raises `StateTransitionError` with code
  `explicit_retry_required`. There is no implicit re-execution.
- **Audit-preserving retry** — `service.retry(session.id)` works only from
  `failed` or `cancelled`, appends a snapshot of the finished attempt to
  `attempt_history`, bumps `attempt`, and returns the session to `queued` with
  a clean world and report. The previous attempt stays on record.
- **Cancellation** — `service.cancel(session.id)` marks a queued/preparing
  task cancelled immediately; a running task can be interrupted at a round
  boundary via the `cancellation_check` callback. Partial worlds are retained
  for inspection, never silently reused.
- **Failure** — provider exceptions land the session in `failed` with a
  structured `error` dict and the partial world/events left in place for
  diagnosis.

### Configuration bounds

`SimulationConfig` validates before any session is created:

| Field | Default | Bounds |
| --- | --- | --- |
| `provider` | `"mock"` | any registered provider name |
| `random_seed` | `0` | any integer |
| `max_agents` | `3` | 1–12 |
| `max_rounds` | `3` | 1–20 |
| `max_seed_chars` | `100_000` | 1–200 000 |

Seeds must be UTF-8 `.txt`, `.md`, or `.markdown`. Use
`create_session_from_bytes(content=…)` when you have raw bytes, so encoding is
handled explicitly.

## llmfetcher engine usage

### Backends and fallback

Each `LLMBackendConfig` names one backend. `LLMFetcher` tries the default
backend first, retries timeouts up to `max_retries`, then falls through to the
remaining registered backends.

| Provider value | Handler | Typical use |
| --- | --- | --- |
| `openai` | OpenAI-compatible Chat Completions | OpenAI and compatible endpoints |
| `deepseek` | DeepSeek (OpenAI-compatible) | DeepSeek chat and reasoner models |
| `anthropic` | Anthropic Messages API | Claude-compatible endpoints |
| `litellm` | LiteLLM | LiteLLM-supported providers |
| `openvino` | OpenVINO | Local inference |
| `onnxruntime` | ONNX Runtime GenAI | Local inference |

```python
from llmfetcher import LLMBackendConfig, LLMFetcher

fetcher = LLMFetcher([
    LLMBackendConfig(
        name="primary", provider="openai",
        model="deepseek-v4-flash", api_key="<key>",
        api_url="https://api.deepseek.com",
        timeout=90, max_retries=1,
    ),
    LLMBackendConfig(
        name="fallback", provider="anthropic",
        model="claude-sonnet-4-6", api_key="<key>",
        max_retries=0,
    ),
])

response = fetcher.fetch("Summarize this note.")
forced = fetcher.fetch("Independently check the conclusion.", backend_name="fallback")
```

`fetcher.fetch_stream(...)` yields token chunks; `abort_active_requests()`
performs a terminal force-stop that raises `LLMRequestCancelled` instead of
retrying or falling back.

### Tools

A tool has a stable name, description, JSON Schema-like parameters, and a
synchronous handler. Tool calls within one model response run in parallel,
while tool feedback preserves the original call order.

```python
from llmfetcher import Tool
from llmfetcher.llm_types import ToolParameter, ToolSchema

def convert_size(size: str) -> str:
    return {"s": "small", "m": "medium", "l": "large"}.get(size.lower(), "unknown")

agent.add_tool(Tool(
    name="convert_size",
    description="Normalize a jersey size code.",
    schemas=ToolSchema(properties=[
        ToolParameter(name="size", type="string",
                      description="Input size code such as S, M, or L."),
    ]),
    handler=convert_size,
))
```

Built-in factories: `create_shell_tools()` (bounded shell execution),
`create_knowledge_tools()` (knowledge-base adapter),
`create_obscura_tools()` (web search/fetch/scrape), and
`create_swarm_tools()` (coordinator-controlled dynamic workers).

### Context and memory

`ContextHandlerLinear` stores short-term history and persists complete tool
results as JSON when the Agent has a `context_path`; a separate compaction
request protects the next model call when the transcript grows. For long-term
retrieval, `RetrievedContextHandler` composes linear history with any
`MemoryProvider` implementation.

```python
from pathlib import Path

agent = Agent(
    llm_fetcher=fetcher,
    system_prompt="You are a research assistant.",
    context_path=Path("sessions/research.json"),
    max_context_threshold=48_000,
)
```

```python
from llmfetcher.context_handlers import RetrievedContextHandler
from llmfetcher.memory import MemoryProvider

context = RetrievedContextHandler(
    memory_provider=my_memory_provider,   # type: MemoryProvider
    compacting_llmfetcher_handler=fetcher,
    namespace="team:catalog",
)
```

For graph-backed long-term memory, `GraphContextHandler` persists an
entity/relation graph to a companion `<context_path>.graph.json` and can use
`SemanticGraphWorker(llm_fetcher)` for LLM extraction and reranking — with a
deterministic regex fallback that keeps building the graph offline-safe.

### Agent lifecycle and events

`Agent.run()` is a synchronous loop that reads cooperative controls only at
complete model-and-tool boundaries. `AgentRunControl` exposes
`should_stop()`/`drain_steers()`; a stop raises `AgentRunStopped` (carrying
the persisted `last_output`). Terminal workflow tools call
`agent.request_completion()` after persisting their result. Hooks receive
immutable `ExecutionEvent` objects and never break the running Agent.

```python
from llmfetcher.events import ExecutionEvent

def print_event(event: ExecutionEvent) -> None:
    print(event.event_type, event.agent_name, event.message)

agent.add_hook(print_event)
```

### Static swarm workflow

An `AgentSwarm` schedules agents as soon as their dependencies are satisfied,
running independent nodes concurrently up to `max_concurrency_agents`.
`add_split`, `add_gather`, `set_mapper`, and `set_router` provide fan-out,
fan-in, input transformation, and post-completion routing.

```python
from llmfetcher import Agent, AgentSwarm

researcher = Agent(llm_fetcher=fetcher, system_prompt="Find facts.")
writer = Agent(llm_fetcher=fetcher, system_prompt="Write a concise report.")

swarm = AgentSwarm(max_concurrency_agents=2)
swarm.add_agent("researcher", researcher)
swarm.add_agent("writer", writer)
swarm.add_connection("researcher", "writer")

outputs = swarm.run("Research the history of a football shirt.")
print(outputs["writer"].content)
```

### Dynamic subagents with TaskBus

Give `create_swarm_tools()` only to the coordinator. The coordinator can then
dispatch independent workers and wait for their structured reports. Workers
receive a task objective, bounded handoff, and expected artifacts — never the
coordinator's raw model context. Their detailed work is persisted as audit
data; only bounded `TaskReport` fields flow back.

```python
from llmfetcher import Agent, AgentSwarm
from llmfetcher.tools import create_swarm_tools

swarm = AgentSwarm(max_concurrency_agents=4)
coordinator = Agent(
    llm_fetcher=fetcher,
    system_prompt=(
        "Delegate independent research with dispatch_subagents. "
        "Wait for all reports before writing a conclusion."
    ),
    default_max_rounds=8,
    default_max_tokens=4_096,
)
swarm.add_agent("coordinator", coordinator)

coordinator.add_tools(create_swarm_tools(
    swarm=swarm,
    llm_fetcher=fetcher,
    worker_tool_pool=[],
    coordinator_name="coordinator",
    worker_max_rounds=6,
    worker_max_tokens=2_048,
))

outputs = swarm.run("Compare three public data sources.")
```

## Web console & CLI

### Web console

```bash
llmfetcher-web
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) — a local, single-page
console for chatting with an `Agent` and observing its execution. Configure a
provider, model, optional API URL and key, tool sets, budgets, and event hooks
from the UI. API keys are used only for the active run and are never stored in
the persisted context; local state lives under the `.llmfetcher/` directory.

### CLI

```bash
llmfetcher run "Explain how pricing is set for a pilot project."
llmfetcher chat
llmfetcher list-backends
llmfetcher list-tools

# Web console from the main CLI (equivalent to llmfetcher-web):
llmfetcher web --port 8765

# Workspaces — each owns a persistent chat context:
llmfetcher workspace list
llmfetcher workspace create "Product Research"
```

The CLI also honors `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`,
`LLM_API_URL`, and `LLM_CONTEXT_PATH` environment variables.

## Package layout

| Path | Responsibility |
| --- | --- |
| `llmfetcher/` | Engine — git submodule pinned to `main` |
| `llmfetcher/agent.py` | Tool-using synchronous Agent loop |
| `llmfetcher/llm_fetcher.py` | Backend selection, retry, fallback, streaming, terminal cancellation |
| `llmfetcher/llm_types.py` | Provider-neutral models, tool schemas, usage, `LLMRequestCancelled` |
| `llmfetcher/fetcher_handlers/` | Provider adapters (openai, deepseek, anthropic, litellm, openvino, onnxruntime) |
| `llmfetcher/context_handlers/` | Linear and retrieval-aware context handlers |
| `llmfetcher/memory/` | `MemoryProvider` long-term memory contract |
| `llmfetcher/graph_memory/` | `GraphContextHandler`, `SemanticGraphWorker`, graph store/retriever |
| `llmfetcher/swarm_module/` | `ExecutionGraph`, `AgentSwarm`, `TaskBus` |
| `llmfetcher/tools/` | Tool factories incl. `create_swarm_tools` |
| `llmfetcher/rag_module/`, `llmfetcher/rag_module_tlb/` | Retrieval-augmented generation modules |
| `llmfetcher/cli.py`, `webapp.py`, `web/` | CLI and local web console |
| `mirofish/` | MiroFish package, installed as `llmfetcher.mirofish` |
| `mirofish/service.py` | `MiroFishService` session lifecycle |
| `mirofish/models.py` | World model, provenance records, reports |
| `mirofish/providers.py` | `SimulationProvider` protocol + `MockSimulationProvider` |
| `mirofish/errors.py` | Structured, JSON-safe error types |
| `tests/` | Offline regression tests (no API keys required) |
| `pyproject.toml` | Distribution `llmfetcher` v0.4.0; Python ≥ 3.12; CLI + web entry points |

## Testing

The test suite runs fully offline — no API keys, no network.

```bash
python -m unittest discover -s tests -v
```

Run it from the repository root after `pip install -e .`: the editable
install is what lets `llmfetcher.mirofish` resolve directly from the `mirofish/`
source tree. The suite covers the MiroFish lifecycle, determinism, provenance,
retry/cancellation semantics, and configuration bounds.

The engine itself carries a larger offline suite — context compaction, DeepSeek
routing, execution-graph persistence, TaskBus handoffs, usage ledger, and more.
Those tests live under `llmfetcher/tests/` inside the submodule and are run from
the engine checkout, not from the superproject CI.

## Submodule maintenance

The engine is pinned as a git submodule at `./llmfetcher`, tracking the
`main` branch of `https://github.com/LunaticLegacy/llmfetcher`. The
superproject records the exact commit it builds against, so engine updates are
explicit and auditable.

```bash
# Refresh the submodule to the latest main:
git submodule update --remote llmfetcher

# Review what changed, then record the new pin in the superproject:
git add llmfetcher
git commit -m "chore: bump llmfetcher engine to <commit>"
```

After pulling a superproject update that moved the pin, sync your working
tree with `git submodule update --init --recursive`.

## License

LunaFish is licensed under the **GNU Affero General Public License v3 or
later** (AGPL-3.0-or-later); the full text is in [LICENSE](LICENSE). Copyright
(c) 2026 LunaticLegacy (月と猫 — LunaNeko), except where a file or third-party
notice states otherwise.

For deployments that cannot comply with the AGPL (including closed-source
network services), a **commercial license** is available under a separately
signed written agreement. See [LICENSING.md](LICENSING.md) for the dual
licensing terms and [commercial-licensing.md](commercial-licensing.md) as the
scope checklist. Commercial licenses cover only the project code in the
agreement; third-party dependencies, API accounts, model access, and
third-party content remain subject to their own terms.
