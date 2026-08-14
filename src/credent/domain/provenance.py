"""Top of the domain DAG: provenance resolution and the run-level graph.

Imports `beliefs.py`, `observations.py`, and `transitions.py`. Nothing else
in `credent.domain` imports this module.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from credent.domain.beliefs import Belief
from credent.domain.observations import Observation, Source
from credent.domain.transitions import StateTransition

if TYPE_CHECKING:
    from collections.abc import Sequence


class Lineage(BaseModel):
    """Per-belief provenance: the observations each belief resolves to."""

    by_belief: dict[str, tuple[Observation, ...]]


class BeliefGraph(BaseModel):
    """The provenance-complete aggregate persisted for one run."""

    sources: tuple[Source, ...]
    observations: tuple[Observation, ...]
    beliefs: tuple[Belief, ...]
    transitions: tuple[StateTransition, ...]


class MissingProvenanceError(Exception):
    """Raised when a belief references an observation or belief id that
    does not resolve within the given collections.
    """


def build_lineage(
    beliefs: Sequence[Belief], observations: Sequence[Observation]
) -> Lineage:
    """Resolve every belief's observation and belief references.

    Parameters
    ----------
    beliefs
        The beliefs to resolve provenance for.
    observations
        The observations `beliefs` may reference.

    Returns
    -------
    Lineage
        Maps each belief id to the observations that support or contradict
        it.

    Raises
    ------
    MissingProvenanceError
        If any belief references an observation id not in `observations`,
        or a belief id (`derived_from_belief_ids`, `superseded_by_belief_id`)
        not in `beliefs`.
    """
    observations_by_id = {observation.id: observation for observation in observations}
    belief_ids = {belief.id for belief in beliefs}

    by_belief: dict[str, tuple[Observation, ...]] = {}
    for belief in beliefs:
        referenced_observation_ids = (
            *belief.supporting_observation_ids,
            *belief.contradicting_observation_ids,
        )
        resolved_observations = []
        for observation_id in referenced_observation_ids:
            observation = observations_by_id.get(observation_id)
            if observation is None:
                raise MissingProvenanceError(
                    f'belief {belief.id!r} references missing observation '
                    f'{observation_id!r}'
                )
            resolved_observations.append(observation)
        by_belief[belief.id] = tuple(resolved_observations)

        referenced_belief_ids = (
            *belief.derived_from_belief_ids,
            belief.superseded_by_belief_id,
        )
        for referenced_belief_id in referenced_belief_ids:
            if (
                referenced_belief_id is not None
                and referenced_belief_id not in belief_ids
            ):
                raise MissingProvenanceError(
                    f'belief {belief.id!r} references missing belief '
                    f'{referenced_belief_id!r}'
                )

    return Lineage(by_belief=by_belief)
