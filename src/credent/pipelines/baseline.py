"""The baseline pipeline: one direct host call, no belief-state reasoning.

Answers `request.question` from the raw evidence text with a single agent
invocation. Never builds a `BeliefGraph` — the comparison point for the
belief-state pipeline in `belief_state.py`.
"""

from typing import TYPE_CHECKING

from credent.harness.context import new_id
from credent.hosts.base import AgentInvocation
from credent.pipelines.models import HostAnswerPayload, PipelineOutcome

if TYPE_CHECKING:
    from credent.hosts.base import AgentHost
    from credent.pipelines.models import QueryRequest


async def run_baseline(request: QueryRequest, host: AgentHost) -> PipelineOutcome:
    """Answer `request.question` with one host call over the raw evidence.

    Parameters
    ----------
    request
        The question and evidence to answer from.
    host
        The agent host to invoke.

    Returns
    -------
    PipelineOutcome
        `graph` is always `None`.
    """
    result = await host.invoke(
        AgentInvocation(
            id=new_id(),
            prompt=_prompt(request),
            metadata={'stage': 'baseline'},
        )
    )
    answer = HostAnswerPayload.model_validate(result.structured_output)
    return PipelineOutcome(answer=answer)


def _prompt(request: QueryRequest) -> str:
    evidence_text = '\n'.join(item.content for item in request.evidence)
    return f'{request.question}\n\n{evidence_text}'
