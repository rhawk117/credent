"""A deterministic `AgentHost` for tests and the walking skeleton.

Returns plain dicts, never the boundary payload models in
`credent.pipelines.models` — `hosts/` owns process/invocation mechanics
only, not belief-state vocabulary (plan.md decision 16).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from credent.hosts.base import AgentResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from credent.hosts.base import AgentInvocation

DEFAULT_RESPONSES: dict[str, dict[str, object]] = {
    'extract': {
        'observations': [
            {
                'subject': 'payments-api',
                'predicate': 'owner',
                'value': 'platform-team',
                'source_id': 'src-readme',
            },
            {
                'subject': 'payments-api',
                'predicate': 'owner',
                'value': 'payments-team',
                'source_id': 'src-codeowners',
            },
        ],
        'unknowns': [],
        'contradictions': [],
    },
    'reason': {'answer': 'payments-team', 'status': 'answered'},
    'baseline': {'answer': 'payments-team', 'status': 'answered'},
}


class FakeHost:
    """An `AgentHost` returning canned responses keyed by pipeline stage.

    Parameters
    ----------
    responses : Mapping[str, dict[str, object]] | None
        Overrides merged over `DEFAULT_RESPONSES`, keyed by
        `metadata['stage']` (`'extract'`, `'reason'`, `'baseline'`). A
        stage present in neither the overrides nor the defaults raises
        `ValueError` on invocation.
    """

    name = 'fake'

    def __init__(self, responses: Mapping[str, dict[str, object]] | None = None) -> None:
        self._responses: dict[str, dict[str, object]] = {
            **DEFAULT_RESPONSES,
            **(responses or {}),
        }
        self.invocations: list[AgentInvocation] = []

    async def invoke(self, request: AgentInvocation) -> AgentResult:
        """Record `request` and return the canned response for its stage.

        Parameters
        ----------
        request : AgentInvocation
            The invocation to record; `request.metadata['stage']` selects
            the canned response.

        Returns
        -------
        AgentResult
            `structured_output` set to the canned response dict for
            `request`'s stage.

        Raises
        ------
        ValueError
            If `request.metadata['stage']` has no canned response.
        """
        self.invocations.append(request)
        stage = request.metadata.get('stage')
        if not isinstance(stage, str) or stage not in self._responses:
            raise ValueError(f'FakeHost has no canned response for stage {stage!r}')
        started_at = datetime.now(UTC)
        return AgentResult(
            invocation_id=request.id,
            exit_code=0,
            structured_output=self._responses[stage],
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )
