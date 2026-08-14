"""`inspect-belief-state`: read-only lookup of a run, its children, and graph.

`InspectOutput` has no `spans` field yet -- T8 adds it once span persistence
exists.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from credent.domain.provenance import BeliefGraph
from credent.storage.repositories import RunRecord

if TYPE_CHECKING:
    from credent.harness.context import ExecutionContext
    from credent.storage.repositories import BeliefRepository, RunRepository


class InspectInput(BaseModel):
    """The run to inspect."""

    run_id: str


class InspectOutput(BaseModel):
    """A run, its children, and its belief graph.

    T8 adds a `spans` field once span persistence exists.
    """

    run: RunRecord
    children: tuple[RunRecord, ...]
    graph: BeliefGraph | None


class UnknownRunError(LookupError):
    """Raised when `InspectInput.run_id` has no persisted run."""


class InspectBeliefState:
    """Reads back a run, its children, and its belief graph.

    Parameters
    ----------
    runs : RunRepository
        Source of run and child-run records.
    beliefs : BeliefRepository
        Source of the belief graph.
    """

    name = 'inspect-belief-state'
    input_model = InspectInput

    def __init__(self, runs: RunRepository, beliefs: BeliefRepository) -> None:
        self._runs = runs
        self._beliefs = beliefs

    async def execute(
        self, input: InspectInput, context: ExecutionContext
    ) -> InspectOutput:
        """Look up `input.run_id`'s run, children, and belief graph.

        Given a parent run id, `graph` is loaded from its `belief_state`
        pipeline child. Given a leaf run id, `graph` is that run's own
        graph (`None` for a `baseline` leaf, which never has one).

        Parameters
        ----------
        input : InspectInput
            The run to inspect.
        context : ExecutionContext
            Unused -- this capability is read-only and never hangs
            anything off the harness-created run.

        Returns
        -------
        InspectOutput
            The run, its children, and its belief graph.

        Raises
        ------
        UnknownRunError
            If `input.run_id` has no persisted run.
        """
        del context
        run = self._runs.get_run(input.run_id)
        if run is None:
            raise UnknownRunError(input.run_id)

        children = tuple(self._runs.children_of(input.run_id))
        graph = self._resolve_graph(input.run_id, run, children)
        return InspectOutput(run=run, children=children, graph=graph)

    def _resolve_graph(
        self, run_id: str, run: RunRecord, children: tuple[RunRecord, ...]
    ) -> BeliefGraph | None:
        if children:
            belief_child = next(
                (child for child in children if child.pipeline == 'belief_state'), None
            )
            if belief_child is None:
                return None
            return self._beliefs.load_graph(belief_child.id)
        if run.pipeline == 'baseline':
            return None
        return self._beliefs.load_graph(run_id)
