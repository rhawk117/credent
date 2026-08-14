"""Deterministic reconciliation: raw observations become reconciled beliefs.

Imports `beliefs.py` and `observations.py`. Nothing else in
`credent.domain` imports this module except `provenance.py`.
"""

import hashlib
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from credent.domain.beliefs import Belief, BeliefStatus

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from credent.domain.observations import Observation, Source


class TransitionKind(StrEnum):
    """What kind of change a `StateTransition` records."""

    CREATED = 'created'
    SUPERSEDED = 'superseded'
    CONTRADICTED = 'contradicted'
    INVALIDATED = 'invalidated'


class StateTransition(BaseModel):
    """One recorded change to a belief's status during reconciliation."""

    belief_id: str
    kind: TransitionKind
    from_status: BeliefStatus | None
    to_status: BeliefStatus
    observation_ids: tuple[str, ...] = ()
    reason: str


class UnknownItem(BaseModel):
    """A (subject, predicate) pair declared as needing evidence."""

    subject: str
    predicate: str
    reason: str = ''


class ReconciliationResult(BaseModel):
    """The beliefs and transitions produced by one `reconcile` call."""

    beliefs: tuple[Belief, ...]
    transitions: tuple[StateTransition, ...]


def reconcile(
    observations: Sequence[Observation],
    sources: Sequence[Source],
    prior_beliefs: Sequence[Belief] = (),
    declared_unknowns: Sequence[UnknownItem] = (),
) -> ReconciliationResult:
    """Reconcile raw observations into beliefs, deterministically.

    Grouping, ranking, and the final ordering of the result all use
    canonical sort keys rather than input order, so the result is
    independent of the order `observations` and `declared_unknowns` arrive
    in.

    Parameters
    ----------
    observations
        Raw values asserted by sources for (subject, predicate) pairs.
    sources
        The sources referenced by `observations`, used for authority
        ranking.
    prior_beliefs
        Beliefs from an earlier reconciliation pass. Any prior belief whose
        `derived_from_belief_ids` or `supporting_observation_ids` reference
        a belief or observation this pass superseded or contradicted is
        invalidated: its status becomes UNKNOWN and its value None, keeping
        its original id.
    declared_unknowns
        (subject, predicate) pairs known to need evidence. Each becomes an
        UNKNOWN belief unless `observations` already covers it.

    Returns
    -------
    ReconciliationResult
        The full set of beliefs this pass produced (including invalidated
        prior beliefs) and the transitions that produced them.
    """
    sources_by_id = {source.id: source for source in sources}
    groups = _group_observations(observations)

    beliefs: list[Belief] = []
    transitions: list[StateTransition] = []
    superseded_belief_ids: set[str] = set()
    contradicted_belief_ids: set[str] = set()
    invalidating_observation_ids: set[str] = set()

    for key in sorted(groups):
        subject, predicate = key
        group_beliefs, group_transitions = _reconcile_group(
            subject, predicate, groups[key], sources_by_id
        )
        beliefs.extend(group_beliefs)
        transitions.extend(group_transitions)
        for belief in group_beliefs:
            if belief.superseded_by_belief_id is not None:
                superseded_belief_ids.add(belief.id)
                invalidating_observation_ids.update(belief.supporting_observation_ids)
            elif belief.status == BeliefStatus.CONTRADICTED:
                contradicted_belief_ids.add(belief.id)
                invalidating_observation_ids.update(belief.supporting_observation_ids)

    matched_keys = set(groups)
    for unknown in sorted(
        declared_unknowns, key=lambda item: (item.subject, item.predicate)
    ):
        key = (unknown.subject, unknown.predicate)
        if key in matched_keys:
            continue
        belief_id = _belief_id(unknown.subject, unknown.predicate, (), ())
        belief = Belief(
            id=belief_id,
            subject=unknown.subject,
            predicate=unknown.predicate,
            value=None,
            status=BeliefStatus.UNKNOWN,
            confidence=0.0,
        )
        beliefs.append(belief)
        transitions.append(
            _created_transition(
                belief, (), unknown.reason or 'declared unknown: no matching observations'
            )
        )
        matched_keys.add(key)

    invalidating_belief_ids = superseded_belief_ids | contradicted_belief_ids
    for prior in prior_beliefs:
        depends_on_invalid_belief = bool(
            set(prior.derived_from_belief_ids) & invalidating_belief_ids
        )
        depends_on_invalid_observation = bool(
            set(prior.supporting_observation_ids) & invalidating_observation_ids
        )
        if not (depends_on_invalid_belief or depends_on_invalid_observation):
            continue
        invalidated = prior.model_copy(
            update={'value': None, 'status': BeliefStatus.UNKNOWN}
        )
        beliefs.append(invalidated)
        transitions.append(
            StateTransition(
                belief_id=invalidated.id,
                kind=TransitionKind.INVALIDATED,
                from_status=prior.status,
                to_status=BeliefStatus.UNKNOWN,
                observation_ids=(),
                reason=(
                    'a supporting belief or observation was superseded or contradicted'
                ),
            )
        )

    beliefs.sort(
        key=lambda belief: (
            belief.subject,
            belief.predicate,
            belief.value or '',
            belief.id,
        )
    )
    transitions.sort(key=lambda transition: (transition.belief_id, transition.kind))

    return ReconciliationResult(beliefs=tuple(beliefs), transitions=tuple(transitions))


def _group_observations(
    observations: Sequence[Observation],
) -> dict[tuple[str, str], list[Observation]]:
    groups: dict[tuple[str, str], list[Observation]] = {}
    for observation in observations:
        key = (observation.subject, observation.predicate)
        groups.setdefault(key, []).append(observation)
    return groups


def _reconcile_group(
    subject: str,
    predicate: str,
    group_observations: Sequence[Observation],
    sources_by_id: Mapping[str, Source],
) -> tuple[list[Belief], list[StateTransition]]:
    by_value: dict[str, list[Observation]] = {}
    for observation in group_observations:
        by_value.setdefault(observation.value, []).append(observation)

    if len(by_value) == 1:
        value, value_observations = next(iter(by_value.items()))
        observation_ids = tuple(sorted(o.id for o in value_observations))
        belief = Belief(
            id=_belief_id(subject, predicate, observation_ids, ()),
            subject=subject,
            predicate=predicate,
            value=value,
            status=BeliefStatus.OBSERVED,
            confidence=max(o.confidence for o in value_observations),
            supporting_observation_ids=observation_ids,
        )
        transition = _created_transition(
            belief, observation_ids, 'agreement across observations'
        )
        return [belief], [transition]

    value_authority = {
        value: max(sources_by_id[o.source_id].authority for o in value_observations)
        for value, value_observations in by_value.items()
    }
    max_authority = max(value_authority.values())
    top_values = sorted(
        value
        for value, authority in value_authority.items()
        if authority == max_authority
    )

    if len(top_values) == 1:
        return _reconcile_with_winner(subject, predicate, by_value, top_values[0])
    return _reconcile_as_contradicted(subject, predicate, by_value)


def _reconcile_with_winner(
    subject: str,
    predicate: str,
    by_value: Mapping[str, list[Observation]],
    winner_value: str,
) -> tuple[list[Belief], list[StateTransition]]:
    winner_ids = tuple(sorted(o.id for o in by_value[winner_value]))
    winner = Belief(
        id=_belief_id(subject, predicate, winner_ids, ()),
        subject=subject,
        predicate=predicate,
        value=winner_value,
        status=BeliefStatus.OBSERVED,
        confidence=max(o.confidence for o in by_value[winner_value]),
        supporting_observation_ids=winner_ids,
    )
    beliefs = [winner]
    transitions = [_created_transition(winner, winner_ids, 'highest-authority agreement')]

    for value in sorted(v for v in by_value if v != winner_value):
        loser_ids = tuple(sorted(o.id for o in by_value[value]))
        loser = Belief(
            id=_belief_id(subject, predicate, loser_ids, ()),
            subject=subject,
            predicate=predicate,
            value=value,
            status=BeliefStatus.OBSERVED,
            confidence=max(o.confidence for o in by_value[value]),
            supporting_observation_ids=loser_ids,
            superseded_by_belief_id=winner.id,
        )
        beliefs.append(loser)
        transitions.append(
            StateTransition(
                belief_id=loser.id,
                kind=TransitionKind.SUPERSEDED,
                from_status=None,
                to_status=BeliefStatus.OBSERVED,
                observation_ids=loser_ids,
                reason=f'superseded by higher-authority value {winner_value!r}',
            )
        )
    return beliefs, transitions


def _reconcile_as_contradicted(
    subject: str,
    predicate: str,
    by_value: Mapping[str, list[Observation]],
) -> tuple[list[Belief], list[StateTransition]]:
    ordered_values = sorted(by_value)
    observation_ids_by_value = {
        value: tuple(sorted(o.id for o in by_value[value])) for value in ordered_values
    }

    beliefs: list[Belief] = []
    transitions: list[StateTransition] = []
    for value in ordered_values:
        own_ids = observation_ids_by_value[value]
        other_ids = tuple(
            observation_id
            for other_value in ordered_values
            if other_value != value
            for observation_id in observation_ids_by_value[other_value]
        )
        belief = Belief(
            id=_belief_id(subject, predicate, own_ids, ()),
            subject=subject,
            predicate=predicate,
            value=value,
            status=BeliefStatus.CONTRADICTED,
            confidence=max(o.confidence for o in by_value[value]),
            supporting_observation_ids=own_ids,
            contradicting_observation_ids=other_ids,
        )
        beliefs.append(belief)
        transitions.append(
            StateTransition(
                belief_id=belief.id,
                kind=TransitionKind.CONTRADICTED,
                from_status=None,
                to_status=BeliefStatus.CONTRADICTED,
                observation_ids=own_ids,
                reason='conflicting values at equal authority',
            )
        )
    return beliefs, transitions


def _created_transition(
    belief: Belief, observation_ids: tuple[str, ...], reason: str
) -> StateTransition:
    return StateTransition(
        belief_id=belief.id,
        kind=TransitionKind.CREATED,
        from_status=None,
        to_status=belief.status,
        observation_ids=observation_ids,
        reason=reason,
    )


def _belief_id(
    subject: str,
    predicate: str,
    supporting_observation_ids: Sequence[str],
    derived_from_belief_ids: Sequence[str],
) -> str:
    """Content hash over identity only — never `value` or `status`.

    Excluding `value`/`status` keeps a belief's id stable when reconcile
    rewrites both to UNKNOWN/None on invalidation, so
    `superseded_by_belief_id`/`derived_from_belief_ids` references never
    dangle.
    """
    payload = '|'.join((
        subject,
        predicate,
        ','.join(sorted(supporting_observation_ids)),
        ','.join(sorted(derived_from_belief_ids)),
    ))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
