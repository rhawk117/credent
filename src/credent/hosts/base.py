"""The host boundary: protocol every agent host adapter implements.

Process/invocation mechanics only — no belief-state vocabulary. A host's
`structured_output` is a plain dict; pipelines validate it against the
boundary payload models in `credent.pipelines.models` before any state
mutation.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class Usage(BaseModel):
    """Token/call accounting for one agent invocation, when a host reports it."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    model_calls: int | None = None


class AgentInvocation(BaseModel):
    """A single request to an `AgentHost`.

    Parameters
    ----------
    metadata : dict[str, object]
        Free-form invocation context; pipelines set `metadata['stage']` to
        select which canned or real response a host produces.
    """

    id: str
    prompt: str | None = None
    payload: dict[str, object] = {}
    timeout_s: float | None = None
    correlation_id: str | None = None
    metadata: dict[str, object] = {}


class AgentResult(BaseModel):
    """What an `AgentHost` returns for one `AgentInvocation`."""

    invocation_id: str
    exit_code: int
    structured_output: dict[str, object] | None = None
    raw_stdout: str = ''
    session_id: str | None = None
    run_id: str | None = None
    started_at: datetime
    ended_at: datetime
    usage: Usage | None = None


@runtime_checkable
class AgentHost(Protocol):
    """An adapter that executes one `AgentInvocation` against a host agent."""

    name: str

    async def invoke(self, request: AgentInvocation) -> AgentResult: ...
