"""Contract tests for the three T7 capabilities through `harness.run`.

Each test: input -> expected structured output -> expected persisted rows,
against an isolated SQLite file (`tmp_db`). Expected-trace-shape assertions
(the pipeline/host-call span nesting under a capability run) are deferred to
Phase 3 -- dispatch equivalence there needs the hook/schedule dispatchers
that don't exist yet.
"""

from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import select

from credent.capabilities.inspect_belief_state import InspectInput, UnknownRunError
from credent.capabilities.reconcile_beliefs import ReconcileBeliefsInput
from credent.dispatch.bootstrap import build_default_harness
from credent.domain.beliefs import BeliefStatus
from credent.domain.observations import Observation
from credent.domain.transitions import TransitionKind
from credent.harness.context import ExecutionContext, new_id
from credent.scenarios.fixtures import (
    GROUND_TRUTH_OWNER,
    SUPERSEDED_OWNER,
    stale_owner_request,
    stale_owner_sources,
)
from credent.storage.database import (
    create_engine_and_schema,
    resolve_db_path,
    session_factory,
)
from credent.storage.models import RunRow
from credent.storage.repositories import BeliefRepository, RunRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from credent.capabilities.inspect_belief_state import InspectOutput
    from credent.capabilities.reason_from_evidence import ReasonFromEvidenceOutput
    from credent.domain.transitions import ReconciliationResult

    type Repos = tuple[sessionmaker[Session], RunRepository, BeliefRepository]


@pytest.fixture
def repos(tmp_db: None) -> Repos:
    """A second run/belief repository pair against the same DB, for assertions."""
    del tmp_db  # depended on only for the CREDENT_DB env var it sets
    engine = create_engine_and_schema(resolve_db_path())
    factory = session_factory(engine)
    return factory, RunRepository(factory), BeliefRepository(factory)


def _context() -> ExecutionContext:
    return ExecutionContext(invocation_id=new_id(), trigger='test')


async def test_reason_from_evidence_answers_and_persists_run_graph(
    repos: Repos,
) -> None:
    _, runs, beliefs = repos
    harness = build_default_harness()

    output = cast(
        'ReasonFromEvidenceOutput',
        await harness.run('reason-from-evidence', stale_owner_request(), _context()),
    )

    assert len(output.results) == 2
    assert {result.answer for result in output.results} == {GROUND_TRUTH_OWNER}
    assert {result.pipeline for result in output.results} == {
        'baseline',
        'belief_state',
    }

    belief_child = next(r for r in output.results if r.pipeline == 'belief_state')
    child_run = runs.get_run(belief_child.run_id)
    assert child_run is not None
    parent_run_id = child_run.parent_run_id
    assert parent_run_id is not None

    parent_run = runs.get_run(parent_run_id)
    assert parent_run is not None
    assert parent_run.status == 'succeeded'

    children = runs.children_of(parent_run_id)
    assert {child.id for child in children} == {r.run_id for r in output.results}
    assert {child.pipeline for child in children} == {'baseline', 'belief_state'}

    graph = beliefs.load_graph(belief_child.run_id)
    winner = next(b for b in graph.beliefs if b.value == GROUND_TRUTH_OWNER)
    loser = next(b for b in graph.beliefs if b.value == SUPERSEDED_OWNER)
    assert loser.superseded_by_belief_id == winner.id
    assert {t.kind for t in graph.transitions} >= {
        TransitionKind.CREATED,
        TransitionKind.SUPERSEDED,
    }


async def test_reconcile_beliefs_reconciles_and_persists_graph_under_its_own_run(
    repos: Repos,
) -> None:
    factory, _, beliefs = repos
    harness = build_default_harness()

    readme, codeowners = stale_owner_sources()
    reconcile_input = ReconcileBeliefsInput(
        sources=(readme, codeowners),
        observations=(
            Observation(
                id='obs-readme',
                subject='payments-api',
                predicate='owner',
                value=SUPERSEDED_OWNER,
                source_id=readme.id,
                source_revision=readme.revision,
                confidence=1.0,
            ),
            Observation(
                id='obs-codeowners',
                subject='payments-api',
                predicate='owner',
                value=GROUND_TRUTH_OWNER,
                source_id=codeowners.id,
                source_revision=codeowners.revision,
                confidence=1.0,
            ),
        ),
    )

    result = cast(
        'ReconciliationResult',
        await harness.run('reconcile-beliefs', reconcile_input, _context()),
    )

    winner = next(b for b in result.beliefs if b.value == GROUND_TRUTH_OWNER)
    loser = next(b for b in result.beliefs if b.value == SUPERSEDED_OWNER)
    assert winner.status == BeliefStatus.OBSERVED
    assert loser.superseded_by_belief_id == winner.id

    with factory() as session:
        run_id = session.scalars(
            select(RunRow.id).where(RunRow.capability == 'reconcile-beliefs')
        ).one()

    graph = beliefs.load_graph(run_id)
    assert {b.id for b in graph.beliefs} == {winner.id, loser.id}


async def test_inspect_belief_state_on_parent_and_child_and_missing_run(
    repos: Repos,
) -> None:
    _, runs, _ = repos
    harness = build_default_harness()

    output = cast(
        'ReasonFromEvidenceOutput',
        await harness.run('reason-from-evidence', stale_owner_request(), _context()),
    )
    belief_child = next(r for r in output.results if r.pipeline == 'belief_state')
    child_run = runs.get_run(belief_child.run_id)
    assert child_run is not None
    parent_run_id = child_run.parent_run_id
    assert parent_run_id is not None

    parent_inspection = cast(
        'InspectOutput',
        await harness.run(
            'inspect-belief-state', InspectInput(run_id=parent_run_id), _context()
        ),
    )
    assert len(parent_inspection.children) == 2
    assert parent_inspection.graph is not None
    assert any(b.value == SUPERSEDED_OWNER for b in parent_inspection.graph.beliefs)

    child_inspection = cast(
        'InspectOutput',
        await harness.run(
            'inspect-belief-state',
            InspectInput(run_id=belief_child.run_id),
            _context(),
        ),
    )
    assert child_inspection.children == ()
    assert child_inspection.graph == parent_inspection.graph

    with pytest.raises(UnknownRunError):
        await harness.run(
            'inspect-belief-state', InspectInput(run_id='missing'), _context()
        )
