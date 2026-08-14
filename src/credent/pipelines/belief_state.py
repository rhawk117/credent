"""The belief-state pipeline: extract, reconcile, reason, render.

Two host calls (`extract`, `reason`) bracket one deterministic domain step
(`reconcile`) and one deterministic shaping step (`render`) — plan.md
decision 2. Host output is validated against the boundary payload models in
`credent.pipelines.models` before any belief-graph state is built.
"""

from typing import TYPE_CHECKING

from credent.domain.observations import Observation
from credent.domain.provenance import BeliefGraph
from credent.domain.transitions import reconcile
from credent.harness.context import new_id
from credent.hosts.base import AgentInvocation
from credent.pipelines.models import (
    HostAnswerPayload,
    HostExtractionPayload,
    PipelineOutcome,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from credent.domain.beliefs import Belief
    from credent.hosts.base import AgentHost
    from credent.pipelines.models import QueryRequest


class UnknownSourceError(Exception):
    """Raised when an extracted observation cites a source id absent from
    the request's evidence.
    """


async def run_belief_state(request: QueryRequest, host: AgentHost) -> PipelineOutcome:
    """Answer `request.question` by extracting, reconciling, then reasoning.

    Parameters
    ----------
    request
        The question and evidence to answer from.
    host
        The agent host to invoke for the `extract` and `reason` stages.

    Returns
    -------
    PipelineOutcome
        `graph` holds the full reconciled `BeliefGraph`.

    Raises
    ------
    ValidationError
        If either host call's `structured_output` fails boundary
        validation. Raised before any observation or belief is built.
    UnknownSourceError
        If an extracted observation's `source_id` matches no source in
        `request.evidence`. Raised before reconciliation runs.
    """
    sources_by_id = {item.source.id: item.source for item in request.evidence}

    extraction_result = await host.invoke(
        AgentInvocation(id=new_id(), metadata={'stage': 'extract'})
    )
    extraction = HostExtractionPayload.model_validate(extraction_result.structured_output)

    for observed in extraction.observations:
        if observed.source_id not in sources_by_id:
            raise UnknownSourceError(
                f'extracted observation cites unknown source {observed.source_id!r}'
            )

    observations = tuple(
        Observation(
            id=new_id(),
            subject=observed.subject,
            predicate=observed.predicate,
            value=observed.value,
            source_id=observed.source_id,
            source_revision=observed.source_revision,
            confidence=observed.confidence,
        )
        for observed in extraction.observations
    )

    reconciliation = reconcile(
        observations,
        tuple(sources_by_id.values()),
        declared_unknowns=extraction.unknowns,
    )

    reason_result = await host.invoke(
        AgentInvocation(
            id=new_id(),
            prompt=_reason_prompt(request, reconciliation.beliefs),
            metadata={'stage': 'reason'},
        )
    )
    answer = HostAnswerPayload.model_validate(reason_result.structured_output)

    graph = BeliefGraph(
        sources=tuple(sources_by_id.values()),
        observations=observations,
        beliefs=reconciliation.beliefs,
        transitions=reconciliation.transitions,
    )
    return PipelineOutcome(answer=answer, graph=graph)


def _reason_prompt(request: QueryRequest, beliefs: Sequence[Belief]) -> str:
    belief_lines = '\n'.join(
        f'{belief.subject} {belief.predicate} = {belief.value!r} ({belief.status.value})'
        for belief in beliefs
    )
    return f'{request.question}\n\n{belief_lines}'
