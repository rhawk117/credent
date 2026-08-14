from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation, Source
from credent.domain.provenance import BeliefGraph
from credent.domain.transitions import StateTransition, TransitionKind
from credent.storage.database import (
    create_engine_and_schema,
    resolve_db_path,
    session_factory,
)
from credent.storage.models import CapabilityRow
from credent.storage.repositories import (
    BeliefRepository,
    InvocationRecord,
    RunRecord,
    RunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    type Repos = tuple[sessionmaker[Session], RunRepository, BeliefRepository]


@pytest.fixture
def repos(tmp_db: None) -> Repos:
    """Build run/belief repositories against an isolated SQLite file."""
    del tmp_db  # depended on only for the CREDENT_DB env var it sets
    engine = create_engine_and_schema(resolve_db_path())
    factory = session_factory(engine)
    return factory, RunRepository(factory), BeliefRepository(factory)


def test_register_capability_upserts_idempotently(repos: Repos) -> None:
    factory, runs, _ = repos

    runs.register_capability('reason-from-evidence', 'first description')
    runs.register_capability('reason-from-evidence', 'second description')

    with factory() as session:
        row = session.get(CapabilityRow, 'reason-from-evidence')

    assert row is not None
    assert row.description == 'second description'


def test_invocation_and_run_lifecycle(repos: Repos) -> None:
    _, runs, _ = repos
    runs.register_capability('reason-from-evidence', 'answers from evidence')

    created_at = datetime.now(UTC)
    runs.save_invocation(
        InvocationRecord(
            id='inv-1',
            trigger='cli',
            actor='tester',
            correlation_id='corr-1',
            metadata_json='{"key": "value"}',
            created_at=created_at,
        )
    )

    started_at = datetime.now(UTC)
    runs.create_run(
        RunRecord(
            id='run-1',
            capability='reason-from-evidence',
            invocation_id='inv-1',
            status='running',
            input_json='{"question": "who owns payments-api?"}',
            started_at=started_at,
        )
    )

    running = runs.get_run('run-1')
    assert running is not None
    assert running.status == 'running'
    assert running.ended_at is None
    assert running.started_at == started_at

    ended_at = datetime.now(UTC)
    runs.finish_run('run-1', 'succeeded', '{"answer": "payments-team"}', ended_at)

    finished = runs.get_run('run-1')
    assert finished is not None
    assert finished.status == 'succeeded'
    assert finished.output_json == '{"answer": "payments-team"}'
    assert finished.ended_at == ended_at


def test_get_run_returns_none_for_unknown_run(repos: Repos) -> None:
    _, runs, _ = repos

    assert runs.get_run('missing') is None


def test_children_of_returns_pipeline_children(repos: Repos) -> None:
    _, runs, _ = repos
    runs.register_capability('reason-from-evidence', 'answers from evidence')
    runs.save_invocation(
        InvocationRecord(id='inv-1', trigger='cli', created_at=datetime.now(UTC))
    )

    parent_started = datetime.now(UTC)
    runs.create_run(
        RunRecord(
            id='parent-1',
            capability='reason-from-evidence',
            invocation_id='inv-1',
            status='running',
            input_json='{}',
            started_at=parent_started,
        )
    )
    runs.create_run(
        RunRecord(
            id='child-baseline',
            capability='reason-from-evidence',
            invocation_id='inv-1',
            parent_run_id='parent-1',
            pipeline='baseline',
            status='succeeded',
            input_json='{}',
            output_json='{"answer": "payments-team"}',
            started_at=parent_started,
            ended_at=parent_started,
        )
    )
    runs.create_run(
        RunRecord(
            id='child-belief',
            capability='reason-from-evidence',
            invocation_id='inv-1',
            parent_run_id='parent-1',
            pipeline='belief_state',
            status='succeeded',
            input_json='{}',
            output_json='{"answer": "payments-team"}',
            started_at=parent_started,
            ended_at=parent_started,
        )
    )

    children = runs.children_of('parent-1')

    assert {child.id for child in children} == {'child-baseline', 'child-belief'}
    assert {child.pipeline for child in children} == {'baseline', 'belief_state'}
    assert runs.children_of('child-baseline') == []


def _stale_owner_shaped_graph() -> BeliefGraph:
    """A stale-owner-shaped graph plus one synthetic derived belief.

    Mirrors the fixture: an old README (lower authority) disagrees with the
    current CODEOWNERS (higher authority) on `payments-api`'s owner. The
    derived belief exercises `derived_from_belief_ids`, which has no other
    coverage in the pinned schema.
    """
    codeowners = Source(
        id='src-codeowners',
        name='Current CODEOWNERS',
        kind='codeowners',
        authority=2,
        revision='t3',
    )
    readme = Source(
        id='src-readme', name='Old README', kind='readme', authority=1, revision='t2'
    )

    obs_codeowners = Observation(
        id='obs-codeowners',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        source_id='src-codeowners',
        source_revision='t3',
        confidence=1.0,
    )
    obs_readme = Observation(
        id='obs-readme',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        source_id='src-readme',
        source_revision='t2',
        confidence=1.0,
    )

    winner = Belief(
        id='belief-payments-team',
        subject='payments-api',
        predicate='owner',
        value='payments-team',
        status=BeliefStatus.OBSERVED,
        confidence=1.0,
        supporting_observation_ids=('obs-codeowners',),
    )
    loser = Belief(
        id='belief-platform-team',
        subject='payments-api',
        predicate='owner',
        value='platform-team',
        status=BeliefStatus.OBSERVED,
        confidence=1.0,
        supporting_observation_ids=('obs-readme',),
        superseded_by_belief_id='belief-payments-team',
    )
    derived = Belief(
        id='belief-derived-summary',
        subject='payments-api',
        predicate='owner-summary',
        value='payments-team (derived)',
        status=BeliefStatus.INFERRED,
        confidence=0.9,
        derived_from_belief_ids=('belief-payments-team', 'belief-platform-team'),
    )

    t_derived = StateTransition(
        belief_id='belief-derived-summary',
        kind=TransitionKind.CREATED,
        from_status=None,
        to_status=BeliefStatus.INFERRED,
        reason='synthetic derived summary',
    )
    t_winner = StateTransition(
        belief_id='belief-payments-team',
        kind=TransitionKind.CREATED,
        from_status=None,
        to_status=BeliefStatus.OBSERVED,
        observation_ids=('obs-codeowners',),
        reason='highest-authority agreement',
    )
    t_loser = StateTransition(
        belief_id='belief-platform-team',
        kind=TransitionKind.SUPERSEDED,
        from_status=None,
        to_status=BeliefStatus.OBSERVED,
        observation_ids=('obs-readme',),
        reason="superseded by higher-authority value 'payments-team'",
    )

    return BeliefGraph(
        sources=(codeowners, readme),
        observations=(obs_codeowners, obs_readme),
        beliefs=(derived, winner, loser),
        transitions=(t_derived, t_winner, t_loser),
    )


def test_save_and_load_graph_round_trips_stale_owner_shaped_graph(
    repos: Repos,
) -> None:
    _, runs, belief_repository = repos
    runs.register_capability('reason-from-evidence', 'answers from evidence')
    now = datetime.now(UTC)
    runs.save_invocation(InvocationRecord(id='inv-1', trigger='cli', created_at=now))
    runs.create_run(
        RunRecord(
            id='run-1',
            capability='reason-from-evidence',
            invocation_id='inv-1',
            status='running',
            input_json='{}',
            started_at=now,
        )
    )

    graph = _stale_owner_shaped_graph()

    belief_repository.save_graph('run-1', graph)
    loaded = belief_repository.load_graph('run-1')

    assert loaded == graph


def test_resolve_db_path_honors_credent_db_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / 'nested' / 'custom.sqlite'
    monkeypatch.setenv('CREDENT_DB', str(target))

    db_path = resolve_db_path()

    assert db_path == target
    assert db_path.parent.is_dir()


def test_resolve_db_path_defaults_to_artifacts_credent_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv('CREDENT_DB', raising=False)
    monkeypatch.chdir(tmp_path)

    db_path = resolve_db_path()

    assert db_path == Path('artifacts/credent.sqlite')
    assert db_path.parent.is_dir()
