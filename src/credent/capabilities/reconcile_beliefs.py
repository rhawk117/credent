"""`reconcile-beliefs`: deterministic reconciliation, no host call.

Persists the resulting belief graph under the harness-created run itself
(`context.parent_run_id`) -- this capability never spawns pipeline children.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from credent.domain.observations import Observation, Source
from credent.domain.provenance import BeliefGraph
from credent.domain.transitions import UnknownItem, reconcile

if TYPE_CHECKING:
    from credent.domain.transitions import ReconciliationResult
    from credent.harness.context import ExecutionContext
    from credent.storage.repositories import BeliefRepository


class ReconcileBeliefsInput(BaseModel):
    """Raw observations, their sources, and any declared unknowns to reconcile."""

    sources: tuple[Source, ...]
    observations: tuple[Observation, ...]
    declared_unknowns: tuple[UnknownItem, ...] = ()


class ReconcileBeliefs:
    """Reconciles observations into beliefs, deterministically, no host call.

    Parameters
    ----------
    beliefs : BeliefRepository
        Persists the reconciled belief graph under the harness run.
    """

    name = 'reconcile-beliefs'
    input_model = ReconcileBeliefsInput

    def __init__(self, beliefs: BeliefRepository) -> None:
        self._beliefs = beliefs

    async def execute(
        self, input: ReconcileBeliefsInput, context: ExecutionContext
    ) -> ReconciliationResult:
        """Reconcile `input.observations` and persist the resulting graph.

        Parameters
        ----------
        input : ReconcileBeliefsInput
            Sources, observations, and declared unknowns to reconcile.
        context : ExecutionContext
            Carries `parent_run_id`, the harness-created run this graph is
            persisted under.

        Returns
        -------
        ReconciliationResult
            The reconciled beliefs and the transitions that produced them.

        Raises
        ------
        ValueError
            If `context.parent_run_id` is unset -- this capability only
            runs meaningfully through `Harness.run`, which always sets it.
        """
        result = reconcile(
            input.observations,
            input.sources,
            declared_unknowns=input.declared_unknowns,
        )
        graph = BeliefGraph(
            sources=input.sources,
            observations=input.observations,
            beliefs=result.beliefs,
            transitions=result.transitions,
        )
        run_id = context.parent_run_id
        if run_id is None:
            raise ValueError('ReconcileBeliefs requires a harness-assigned parent_run_id')
        self._beliefs.save_graph(run_id, graph)
        return result
