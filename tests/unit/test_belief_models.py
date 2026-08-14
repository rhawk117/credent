import pytest
from pydantic import ValidationError

from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation


def test_belief_status_has_the_six_pinned_members() -> None:
    assert {status.value for status in BeliefStatus} == {
        'observed',
        'retrieved',
        'inferred',
        'assumed',
        'contradicted',
        'unknown',
    }


def test_unknown_belief_with_a_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Belief(
            id='belief-1',
            subject='payments-api',
            predicate='owner',
            value='payments-team',
            status=BeliefStatus.UNKNOWN,
            confidence=1.0,
        )


def test_unknown_belief_without_a_value_is_accepted() -> None:
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value=None,
        status=BeliefStatus.UNKNOWN,
        confidence=0.0,
    )
    assert belief.value is None


@pytest.mark.parametrize('confidence', [-0.1, 1.1])
def test_belief_confidence_out_of_bounds_is_rejected(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Belief(
            id='belief-1',
            subject='payments-api',
            predicate='owner',
            value='payments-team',
            status=BeliefStatus.OBSERVED,
            confidence=confidence,
        )


@pytest.mark.parametrize('confidence', [0.0, 1.0])
def test_belief_confidence_boundary_values_are_accepted(confidence: float) -> None:
    belief = Belief(
        id='belief-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.OBSERVED,
        confidence=confidence,
    )
    assert belief.confidence == confidence


@pytest.mark.parametrize('confidence', [-0.1, 1.1])
def test_observation_confidence_out_of_bounds_is_rejected(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Observation(
            id='obs-1',
            subject='payments-api',
            predicate='owner',
            value='payments-team',
            source_id='src-1',
            confidence=confidence,
        )


@pytest.mark.parametrize('confidence', [0.0, 1.0])
def test_observation_confidence_boundary_values_are_accepted(confidence: float) -> None:
    observation = Observation(
        id='obs-1',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id='src-1',
        confidence=confidence,
    )
    assert observation.confidence == confidence
