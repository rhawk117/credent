import pytest
from pydantic import ValidationError

from credent.hosts.base import AgentInvocation
from credent.hosts.fake import FakeHost
from credent.pipelines.models import HostAnswerPayload, HostExtractionPayload


def _invocation(stage: str, invocation_id: str = 'inv-1') -> AgentInvocation:
    return AgentInvocation(id=invocation_id, metadata={'stage': stage})


async def test_fake_host_default_extract_response_validates_as_extraction_payload() -> (
    None
):
    host = FakeHost()

    result = await host.invoke(_invocation('extract'))

    assert result.structured_output is not None
    payload = HostExtractionPayload.model_validate(result.structured_output)
    observed = {(o.value, o.source_id) for o in payload.observations}
    assert observed == {
        ('platform-team', 'src-readme'),
        ('payments-team', 'src-codeowners'),
    }


@pytest.mark.parametrize('stage', ['reason', 'baseline'])
async def test_fake_host_default_answer_response_validates_as_answer_payload(
    stage: str,
) -> None:
    host = FakeHost()

    result = await host.invoke(_invocation(stage))

    assert result.structured_output is not None
    payload = HostAnswerPayload.model_validate(result.structured_output)
    assert payload.answer == 'payments-team'
    assert payload.status == 'answered'


async def test_fake_host_unknown_stage_raises_value_error_naming_stage() -> None:
    host = FakeHost()

    with pytest.raises(ValueError, match='nope'):
        await host.invoke(_invocation('nope'))


async def test_fake_host_records_every_invocation() -> None:
    host = FakeHost()
    first = _invocation('extract', invocation_id='inv-1')
    second = _invocation('reason', invocation_id='inv-2')

    await host.invoke(first)
    await host.invoke(second)

    assert host.invocations == [first, second]


@pytest.mark.parametrize(
    'malformed',
    [
        {
            'observations': [
                {
                    'subject': 'payments-api',
                    'value': 'payments-team',
                    'source_id': 'src-codeowners',
                }
            ]
        },
        {
            'observations': [
                {
                    'subject': 'payments-api',
                    'predicate': 'owner',
                    'value': 'payments-team',
                    'source_id': 'src-codeowners',
                    'confidence': 1.5,
                }
            ]
        },
        {'unknowns': {'subject': 'payments-api', 'predicate': 'owner'}},
    ],
    ids=['missing-predicate', 'confidence-out-of-range', 'unknowns-wrong-type'],
)
def test_host_extraction_payload_rejects_malformed_input(
    malformed: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        HostExtractionPayload.model_validate(malformed)
