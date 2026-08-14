"""Hypothesis invariants pinned in docs/.agent-backlog/phase-01/context.md:
reconciliation is order-independent; irrelevant evidence does not mutate
other groups; superseded evidence invalidates dependent beliefs; provenance
references always resolve; UNKNOWN never carries a value.
"""

from hypothesis import given
from hypothesis import strategies as st

from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation, Source
from credent.domain.provenance import build_lineage
from credent.domain.transitions import UnknownItem, reconcile

README = Source(
    id='src-readme', name='Old README', kind='readme', authority=1, revision='t2'
)
CODEOWNERS = Source(
    id='src-codeowners',
    name='Current CODEOWNERS',
    kind='codeowners',
    authority=2,
    revision='t3',
)
SOURCES = (README, CODEOWNERS)

FIXTURE_OBSERVATIONS = (
    Observation(
        id='obs-readme',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id=README.id,
        confidence=1.0,
    ),
    Observation(
        id='obs-codeowners',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=CODEOWNERS.id,
        confidence=1.0,
    ),
)


@given(st.permutations(FIXTURE_OBSERVATIONS))
def test_reconciliation_is_order_independent(order: list[Observation]) -> None:
    assert reconcile(order, SOURCES) == reconcile(FIXTURE_OBSERVATIONS, SOURCES)


@given(st.permutations(FIXTURE_OBSERVATIONS))
def test_irrelevant_observations_do_not_mutate_other_groups(
    order: list[Observation],
) -> None:
    irrelevant = Observation(
        id='obs-irrelevant',
        subject='billing-api',
        predicate='owner',
        value='some-other-team',
        source_id=README.id,
        confidence=1.0,
    )
    baseline = reconcile(FIXTURE_OBSERVATIONS, SOURCES)
    with_extra = reconcile([*order, irrelevant], SOURCES)

    relevant_beliefs = tuple(
        belief for belief in with_extra.beliefs if belief.subject == 'payments-api'
    )
    assert relevant_beliefs == baseline.beliefs


@given(st.permutations(FIXTURE_OBSERVATIONS))
def test_superseded_belief_invalidates_dependents(order: list[Observation]) -> None:
    baseline = reconcile(FIXTURE_OBSERVATIONS, SOURCES)
    loser = next(
        belief
        for belief in baseline.beliefs
        if belief.superseded_by_belief_id is not None
    )
    derived = Belief(
        id='derived-belief',
        subject='payments-api',
        predicate='oncall-team',
        value='platform-team',
        status=BeliefStatus.INFERRED,
        confidence=0.5,
        derived_from_belief_ids=(loser.id,),
    )

    result = reconcile(order, SOURCES, prior_beliefs=[derived])
    invalidated = next(belief for belief in result.beliefs if belief.id == derived.id)

    assert invalidated.status == BeliefStatus.UNKNOWN
    assert invalidated.value is None


_subject = st.sampled_from(['payments-api', 'billing-api'])
_predicate = st.just('owner')
_value = st.sampled_from(['payments-team', 'platform-team', 'infra-team'])
_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@st.composite
def _reconciliation_inputs(
    draw: st.DrawFn,
) -> tuple[list[Observation], list[Source], list[UnknownItem]]:
    sources = [
        Source(
            id=f'src-{index}',
            name=f'Source {index}',
            kind='generated',
            authority=draw(st.integers(min_value=0, max_value=5)),
        )
        for index in range(draw(st.integers(min_value=1, max_value=3)))
    ]
    observations = [
        Observation(
            id=f'obs-{index}',
            subject=draw(_subject),
            predicate=draw(_predicate),
            value=draw(_value),
            source_id=draw(st.sampled_from(sources)).id,
            confidence=draw(_confidence),
        )
        for index in range(draw(st.integers(min_value=0, max_value=6)))
    ]
    unknowns = [
        UnknownItem(subject=draw(_subject), predicate=draw(_predicate))
        for _ in range(draw(st.integers(min_value=0, max_value=3)))
    ]
    return observations, sources, unknowns


@given(_reconciliation_inputs())
def test_every_referenced_observation_id_resolves_via_build_lineage(
    reconciliation_inputs: tuple[list[Observation], list[Source], list[UnknownItem]],
) -> None:
    observations, sources, unknowns = reconciliation_inputs
    result = reconcile(observations, sources, declared_unknowns=unknowns)

    build_lineage(result.beliefs, observations)  # must not raise


@given(_reconciliation_inputs())
def test_no_generated_reconciliation_yields_unknown_with_a_value(
    reconciliation_inputs: tuple[list[Observation], list[Source], list[UnknownItem]],
) -> None:
    observations, sources, unknowns = reconciliation_inputs
    result = reconcile(observations, sources, declared_unknowns=unknowns)

    for belief in result.beliefs:
        if belief.status == BeliefStatus.UNKNOWN:
            assert belief.value is None
