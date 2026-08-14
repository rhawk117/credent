import re

import pytest
from pydantic import BaseModel, ValidationError

from credent.harness.context import ExecutionContext, new_id
from credent.harness.dispatch import dispatch
from credent.harness.registry import CapabilityRegistry, UnknownCapabilityError
from credent.harness.runtime import Harness

_HEX_RE = re.compile(r'[0-9a-f]{32}')


class SpyInput(BaseModel):
    value: str


class SpyOutput(BaseModel):
    received_value: str
    parent_run_id: str | None


class SpyCapability:
    """Records what it was called with, for assertions."""

    def __init__(self) -> None:
        self.call_count = 0
        self.received_input: SpyInput | None = None
        self.received_context: ExecutionContext | None = None

    async def execute(self, input: SpyInput, context: ExecutionContext) -> SpyOutput:
        self.call_count += 1
        self.received_input = input
        self.received_context = context
        return SpyOutput(received_value=input.value, parent_run_id=context.parent_run_id)


def _registry_with_spy() -> tuple[CapabilityRegistry, SpyCapability]:
    registry = CapabilityRegistry()
    spy = SpyCapability()
    registry.register('spy', spy, 'a test capability', SpyInput)
    return registry, spy


def test_new_id_returns_unique_hex_strings() -> None:
    ids = {new_id() for _ in range(200)}

    assert len(ids) == 200
    assert all(_HEX_RE.fullmatch(value) for value in ids)


def test_registry_register_then_get_roundtrip() -> None:
    registry, spy = _registry_with_spy()

    entry = registry.get('spy')

    assert entry.name == 'spy'
    assert entry.capability is spy
    assert entry.description == 'a test capability'
    assert entry.input_model is SpyInput


def test_registry_get_unknown_capability_raises() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(UnknownCapabilityError):
        registry.get('nope')


async def test_harness_run_coerces_dict_input_and_propagates_parent_run_id() -> None:
    registry, spy = _registry_with_spy()
    harness = Harness(registry)
    context = ExecutionContext(invocation_id=new_id(), trigger='cli')

    result = await harness.run('spy', {'value': 'hello'}, context)

    assert spy.received_input == SpyInput(value='hello')
    assert spy.received_context is not None
    assert spy.received_context.parent_run_id is not None
    assert context.parent_run_id is None
    assert result == SpyOutput(
        received_value='hello', parent_run_id=spy.received_context.parent_run_id
    )


async def test_harness_run_invalid_input_raises_before_execute() -> None:
    registry, spy = _registry_with_spy()
    harness = Harness(registry)
    context = ExecutionContext(invocation_id=new_id(), trigger='cli')

    with pytest.raises(ValidationError):
        await harness.run('spy', {'not_value': 'oops'}, context)

    assert spy.call_count == 0


async def test_dispatch_builds_context_with_fresh_invocation_id_and_trigger() -> None:
    registry, spy = _registry_with_spy()
    harness = Harness(registry)

    await dispatch(harness, 'spy', {'value': 'first'}, trigger='cli', actor='tester')
    assert spy.received_context is not None
    first_invocation_id = spy.received_context.invocation_id
    assert spy.received_context.trigger == 'cli'
    assert spy.received_context.actor == 'tester'

    await dispatch(harness, 'spy', {'value': 'second'}, trigger='cli')
    assert spy.received_context is not None
    second_invocation_id = spy.received_context.invocation_id

    assert first_invocation_id != second_invocation_id


async def test_dispatch_returns_harness_run_result() -> None:
    registry, spy = _registry_with_spy()
    harness = Harness(registry)

    result = await dispatch(harness, 'spy', {'value': 'hi'}, trigger='cli')

    assert spy.received_context is not None
    assert result == SpyOutput(
        received_value='hi', parent_run_id=spy.received_context.parent_run_id
    )
