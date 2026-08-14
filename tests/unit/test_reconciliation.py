from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation, Source
from credent.domain.transitions import TransitionKind, UnknownItem, reconcile

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


def test_agreement_produces_a_single_observed_belief() -> None:
    first = Observation(
        id='obs-a',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=README.id,
        confidence=0.6,
    )
    second = Observation(
        id='obs-b',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=CODEOWNERS.id,
        confidence=0.9,
    )

    result = reconcile([first, second], [README, CODEOWNERS])

    assert len(result.beliefs) == 1
    belief = result.beliefs[0]
    assert belief.status == BeliefStatus.OBSERVED
    assert belief.value == 'payments-team'
    assert belief.confidence == 0.9
    assert set(belief.supporting_observation_ids) == {'obs-a', 'obs-b'}
    assert belief.superseded_by_belief_id is None

    assert len(result.transitions) == 1
    assert result.transitions[0].kind == TransitionKind.CREATED
    assert result.transitions[0].from_status is None
    assert result.transitions[0].to_status == BeliefStatus.OBSERVED


def test_higher_authority_supersedes_lower_with_lineage_intact() -> None:
    stale = Observation(
        id='obs-readme',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id=README.id,
        confidence=1.0,
    )
    current = Observation(
        id='obs-codeowners',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=CODEOWNERS.id,
        confidence=1.0,
    )

    result = reconcile([stale, current], [README, CODEOWNERS])

    beliefs_by_value = {belief.value: belief for belief in result.beliefs}
    assert set(beliefs_by_value) == {'payments-team', 'platform-team'}

    winner = beliefs_by_value['payments-team']
    loser = beliefs_by_value['platform-team']

    assert winner.status == BeliefStatus.OBSERVED
    assert winner.superseded_by_belief_id is None

    assert loser.status == BeliefStatus.OBSERVED
    assert loser.superseded_by_belief_id == winner.id
    assert loser.supporting_observation_ids == ('obs-readme',)

    superseded_transitions = [
        t for t in result.transitions if t.kind == TransitionKind.SUPERSEDED
    ]
    assert len(superseded_transitions) == 1
    assert superseded_transitions[0].belief_id == loser.id


def test_equal_authority_conflict_yields_cross_linked_contradictions() -> None:
    second_readme = Source(
        id='src-readme-2', name='Second README', kind='readme', authority=1
    )
    obs_a = Observation(
        id='obs-a',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id=README.id,
        confidence=1.0,
    )
    obs_b = Observation(
        id='obs-b',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=second_readme.id,
        confidence=1.0,
    )

    result = reconcile([obs_a, obs_b], [README, second_readme])

    assert len(result.beliefs) == 2
    for belief in result.beliefs:
        assert belief.status == BeliefStatus.CONTRADICTED
        assert belief.superseded_by_belief_id is None

    beliefs_by_value = {belief.value: belief for belief in result.beliefs}
    assert beliefs_by_value['platform-team'].contradicting_observation_ids == ('obs-b',)
    assert beliefs_by_value['payments-team'].contradicting_observation_ids == ('obs-a',)

    assert len(result.transitions) == 2
    assert all(t.kind == TransitionKind.CONTRADICTED for t in result.transitions)


def test_declared_unknown_without_observations_yields_unknown_belief() -> None:
    unknown = UnknownItem(
        subject='payments-api', predicate='oncall', reason='no evidence found'
    )

    result = reconcile([], [], declared_unknowns=[unknown])

    assert len(result.beliefs) == 1
    belief = result.beliefs[0]
    assert belief.status == BeliefStatus.UNKNOWN
    assert belief.value is None

    assert len(result.transitions) == 1
    assert result.transitions[0].kind == TransitionKind.CREATED
    assert result.transitions[0].to_status == BeliefStatus.UNKNOWN


def test_declared_unknown_matching_an_observation_is_skipped() -> None:
    observed = Observation(
        id='obs-a',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=README.id,
        confidence=1.0,
    )
    unknown = UnknownItem(subject='payments-api', predicate='owner')

    result = reconcile([observed], [README], declared_unknowns=[unknown])

    assert len(result.beliefs) == 1
    assert result.beliefs[0].status == BeliefStatus.OBSERVED


def test_prior_belief_invalidated_when_its_dependency_is_superseded() -> None:
    stale = Observation(
        id='obs-readme',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id=README.id,
        confidence=1.0,
    )
    current = Observation(
        id='obs-codeowners',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id=CODEOWNERS.id,
        confidence=1.0,
    )
    first_pass = reconcile([stale, current], [README, CODEOWNERS])
    loser = next(
        belief for belief in first_pass.beliefs if belief.value == 'platform-team'
    )

    derived = Belief(
        id='derived-oncall',
        subject='payments-api',
        predicate='oncall-team',
        value='platform-team',
        status=BeliefStatus.INFERRED,
        confidence=0.7,
        derived_from_belief_ids=(loser.id,),
    )

    second_pass = reconcile(
        [stale, current], [README, CODEOWNERS], prior_beliefs=[derived]
    )

    invalidated = next(
        belief for belief in second_pass.beliefs if belief.id == derived.id
    )
    assert invalidated.status == BeliefStatus.UNKNOWN
    assert invalidated.value is None

    invalidation_transitions = [
        t for t in second_pass.transitions if t.kind == TransitionKind.INVALIDATED
    ]
    assert len(invalidation_transitions) == 1
    assert invalidation_transitions[0].belief_id == derived.id
    assert invalidation_transitions[0].from_status == BeliefStatus.INFERRED
