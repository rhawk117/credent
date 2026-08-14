import pytest
from pydantic import ValidationError

from credent.domain.beliefs import BeliefStatus
from credent.domain.observations import EvidenceItem, Source
from credent.hosts.fake import FakeHost
from credent.pipelines.baseline import run_baseline
from credent.pipelines.belief_state import run_belief_state
from credent.pipelines.models import QueryRequest

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


def _stale_owner_request() -> QueryRequest:
    return QueryRequest(
        question='Who owns payments-api?',
        evidence=(
            EvidenceItem(
                source=README, content='Old README: platform-team owns payments-api.'
            ),
            EvidenceItem(
                source=CODEOWNERS,
                content='Current CODEOWNERS: payments-team owns payments-api.',
            ),
        ),
    )


async def test_baseline_answers_from_a_single_host_call() -> None:
    host = FakeHost()

    outcome = await run_baseline(_stale_owner_request(), host)

    assert outcome.answer.answer == 'payments-team'
    assert outcome.graph is None
    assert len(host.invocations) == 1
    assert host.invocations[0].metadata['stage'] == 'baseline'


async def test_belief_state_reconciles_and_answers() -> None:
    host = FakeHost()

    outcome = await run_belief_state(_stale_owner_request(), host)

    assert outcome.answer.answer == 'payments-team'
    assert outcome.graph is not None
    graph = outcome.graph
    assert {source.id for source in graph.sources} == {README.id, CODEOWNERS.id}
    assert len(graph.observations) == 2

    beliefs_by_value = {belief.value: belief for belief in graph.beliefs}
    assert set(beliefs_by_value) == {'payments-team', 'platform-team'}

    winner = beliefs_by_value['payments-team']
    loser = beliefs_by_value['platform-team']
    assert winner.status == BeliefStatus.OBSERVED
    assert winner.superseded_by_belief_id is None
    assert loser.status == BeliefStatus.OBSERVED
    assert loser.superseded_by_belief_id == winner.id

    stages = [inv.metadata['stage'] for inv in host.invocations]
    assert stages == ['extract', 'reason']


async def test_belief_state_malformed_extract_response_raises_before_graph_built() -> (
    None
):
    host = FakeHost(responses={'extract': {'observations': [{'subject': 'x'}]}})

    with pytest.raises(ValidationError):
        await run_belief_state(_stale_owner_request(), host)

    assert len(host.invocations) == 1
    assert host.invocations[0].metadata['stage'] == 'extract'


async def test_belief_state_unknown_source_id_raises_before_graph_built() -> None:
    host = FakeHost(
        responses={
            'extract': {
                'observations': [
                    {
                        'subject': 'payments-api',
                        'predicate': 'owner',
                        'value': 'payments-team',
                        'source_id': 'src-unknown',
                    }
                ],
                'unknowns': [],
                'contradictions': [],
            }
        }
    )

    with pytest.raises(Exception, match='src-unknown'):
        await run_belief_state(_stale_owner_request(), host)

    assert len(host.invocations) == 1
    assert host.invocations[0].metadata['stage'] == 'extract'
