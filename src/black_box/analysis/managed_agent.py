"""Managed Agents integration for long-horizon bag replay.

This module is a SKELETON intended for the "Best use of Managed Agents"
prize track. It maps the Managed Agents primitives (beta
``managed-agents-2026-04-01``, https://platform.claude.com/docs/en/managed-agents/overview)
onto Black Box's forensic workflow:

    * **Agent**       -> ``ForensicAgentConfig`` (model + system prompt +
                         built-in tools + optional MCP servers + skills).
    * **Environment** -> container template with the uploaded bag mounted at
                         ``/mnt/bag`` and the user's source tree mounted
                         read-only so the agent can grep/read code.
    * **Session**     -> ``ForensicSession``: a single running instance bound
                         to one incident (``case_key``).
    * **Events**      -> the ``stream()`` iterator surfaces user turns, tool
                         results, and status updates for the UI to render.
    * **Steering**    -> ``steer()`` posts an additional user event mid-run
                         without restarting the agent, e.g. to focus on a
                         narrower time window.
    * **Outcomes**    -> ``finalize()`` collects the structured
                         PostMortemReport (research preview feature).

Rate limits (from docs, respected by the retry layer we still have to
build): 60 create/min, 600 read/min.

Usage sketch::

    agent = ForensicAgent(ForensicAgentConfig(task_budget_minutes=15))
    session = agent.open_session(bag_path=Path("/mnt/bag"), case_key="crash_001")
    for event in session.stream():
        ui.push(event)                         # reasoning / tool-call / output
    session.steer("focus on the 12s-15s window, ignore earlier")
    report = session.finalize()                # -> PostMortemReport

All real HTTP calls are intentionally absent: this file defines the
shape the rest of the codebase will depend on once the beta SDK lands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

# ---------------------------------------------------------------------------
# Beta handshake
# ---------------------------------------------------------------------------
ANTHROPIC_BETA_HEADER = "managed-agents-2026-04-01"
MODEL = "claude-opus-4-7"

# Built-in tool identifiers advertised by the Managed Agents platform.
# (Bash, file ops, web search/fetch, MCP bridge.) We enable the subset
# that forensic replay actually needs.
BUILTIN_TOOLS: tuple[str, ...] = (
    "bash",
    "file_read",
    "file_write",
    "file_edit",
    "file_glob",
    "file_grep",
    "web_search",
    "web_fetch",
    "mcp",
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class ForensicAgentConfig:
    """Declarative spec for the forensic Agent + its Environment.

    Fields map 1:1 onto the managed-agents create-agent / create-environment
    request bodies.
    """

    task_budget_minutes: int = 15
    model: str = MODEL
    # TODO(managed-agents): pull the real post-mortem prompt from prompts.py
    system_prompt: str = (
        "You are Black Box, a forensic copilot for robot incidents. "
        "Use the mounted bag at /mnt/bag and the source tree at /mnt/src "
        "to produce an evidence-grounded post-mortem."
    )
    tools: tuple[str, ...] = BUILTIN_TOOLS
    mcp_servers: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)          # e.g. ["ros-bag-decoder"]
    mounted_files: list[Path] = field(default_factory=list)  # bag, source tree
    network: Literal["none", "egress_only"] = "egress_only"
    # Container image template name on the managed-agents side.
    environment_template: str = "python-3.11-ros-tools"


# ---------------------------------------------------------------------------
# Agent / Session
# ---------------------------------------------------------------------------
class ForensicAgent:
    """Thin wrapper around the Managed Agents control plane.

    Owns the Agent + Environment specs; mints Sessions on demand.
    """

    def __init__(self, config: ForensicAgentConfig | None = None) -> None:
        self.config = config or ForensicAgentConfig()
        # TODO(managed-agents): lazy-init an anthropic.ManagedAgents client
        #                       with headers={"anthropic-beta": ANTHROPIC_BETA_HEADER}
        self._client = None

    def open_session(self, bag_path: Path, case_key: str) -> "ForensicSession":
        """Create an Environment + Agent and start a Session bound to one case."""
        # TODO(managed-agents): POST /v1/environments
        #                       - template=self.config.environment_template
        #                       - mounts=[{src: bag_path, dst: "/mnt/bag"}, ...]
        #                       - network=self.config.network
        # TODO(managed-agents): POST /v1/agents
        #                       - model, system_prompt, tools, mcp_servers, skills
        # TODO(managed-agents): POST /v1/sessions  (env_id + agent_id)
        # TODO(managed-agents): seed the session with an initial user turn
        #                       containing the case_key + analysis mode.
        raise NotImplementedError("managed-agents session creation not yet wired")


class ForensicSession:
    """Represents one running managed-agents Session.

    The UI treats this as an event stream until ``finalize()`` is called.
    """

    def __init__(self, session_id: str, case_key: str) -> None:
        self.session_id = session_id
        self.case_key = case_key

    # -- event stream --------------------------------------------------------
    def stream(self) -> Iterator[dict]:
        """Yield session Events as structured dicts.

        Each item looks like::

            {"type": "reasoning" | "tool_call" | "tool_result" | "status",
             "ts":   float,
             "payload": {...}}
        """
        # TODO(managed-agents): open SSE on GET /v1/sessions/{id}/events
        # TODO(managed-agents): translate raw Events into the dict shape above
        raise NotImplementedError

    # -- steering ------------------------------------------------------------
    def steer(self, message: str) -> None:
        """Inject a user turn mid-run without restarting the agent."""
        # TODO(managed-agents): POST /v1/sessions/{id}/events with role=user
        #                       and content=message. The agent will see it on
        #                       its next reasoning step.
        raise NotImplementedError

    # -- finalize ------------------------------------------------------------
    def finalize(self) -> dict:
        """Close the session and collect the final structured outcome.

        Outcomes are a research-preview feature; until then we parse the
        last assistant turn as JSON and validate against PostMortemReport.
        """
        # TODO(managed-agents): POST /v1/sessions/{id}/finalize
        # TODO(managed-agents): fetch final outcome (research preview)
        # TODO(managed-agents): validate against analysis.schemas.PostMortemReport
        raise NotImplementedError


__all__ = [
    "ANTHROPIC_BETA_HEADER",
    "MODEL",
    "BUILTIN_TOOLS",
    "ForensicAgentConfig",
    "ForensicAgent",
    "ForensicSession",
]
