import pytest

from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation
from credent.domain.provenance import MissingProvenanceError, build_lineage


def test_build_lineage_resolves_supporting_and_contradicting_observations() -> None:
    supporting = Observation(
        id='obs-support',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id='src-1',
        confidence=1.0,
    )
    contradicting = Observation(
        id='obs-contradict',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id='src-2',
        confidence=1.0,
    )
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.CONTRADICTED,
        confidence=1.0,
        supporting_observation_ids=(supporting.id,),
        contradicting_observation_ids=(contradicting.id,),
    )

    lineage = build_lineage([belief], [supporting, contradicting])

    assert lineage.by_belief[belief.id] == (supporting, contradicting)


def test_build_lineage_raises_on_dangling_observation_reference() -> None:
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.OBSERVED,
        confidence=1.0,
        supporting_observation_ids=('missing-observation',),
    )

    with pytest.raises(MissingProvenanceError):
        build_lineage([belief], [])


def test_build_lineage_raises_on_dangling_belief_reference() -> None:
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.OBSERVED,
        confidence=1.0,
        derived_from_belief_ids=('missing-belief',),
    )

    with pytest.raises(MissingProvenanceError):
        build_lineage([belief], [])


def test_build_lineage_raises_on_dangling_superseded_by_reference() -> None:
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.OBSERVED,
        confidence=1.0,
        superseded_by_belief_id='missing-belief',
    )

    with pytest.raises(MissingProvenanceError):
        build_lineage([belief], [])
