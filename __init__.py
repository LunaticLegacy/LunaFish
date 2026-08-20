"""
LLM Fetcher - Multi-Agent Orchestration Framework

A powerful Python framework for building, orchestrating, and executing
LLM-powered multi-agent systems with structured reasoning capabilities.

Example usage:
    from llmfetcher import Agent, LLMFetcher, Tool

    fetcher = LLMFetcher(backends=[...])
    agent = Agent(llm_handler=fetcher, system_prompt="...", provider="anthropic")
"""

__version__ = "0.4.0"
__author__ = "LunaticLegacy"

from .llm_fetcher import (
    LLMBackendConfig,
    LLMBackendHandler,
    LLMFetcher,
    LLMOutput
)

from .agent import (
    Agent,
    AgentRunControl,
    AgentRunStopped,
)

from .tool_handler import (
    Tool,
)

from .llm_types import (
    LLMRequestCancelled,
    ToolParameter,
    ToolSchema,
)

from .tool_executor import (
    ToolExecutor,
)

from .swarm_module import (
    AgentSwarm,
    ExecutionGraph,
    GraphPersistenceError,
    TaskAssignment,
    TaskBus,
    TaskReport,
)

from .context_handlers.linear import (
    ContextHandlerLinear
)

# Offline, provenance-aware simulation service.  This import adds no model
# calls and keeps its real-provider boundary opt-in.
from .mirofish import (
    ConfigurationError,
    InputValidationError,
    MiroFishService,
    SimulationConfig,
    SimulationProvider,
    StateTransitionError,
    TaskStatus,
)
