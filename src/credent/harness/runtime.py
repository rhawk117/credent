import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from credent.harness.context import ExecutionContext, new_id
from credent.storage.repositories import InvocationRecord, RunRecord

if TYPE_CHECKING:
    from pydantic import BaseModel

    from credent.harness.registry import CapabilityInfo, CapabilityRegistry
    from credent.storage.repositories import RunRepository


def _coerce_input(input_model: type[BaseModel], raw: object) -> BaseModel:
    """Validate/coerce raw capability input through its Pydantic model.

    Parameters
    ----------
    input_model : type[BaseModel]
        The capability's declared input model.
    raw : object
        A dict (e.g. from JSON) or an already-typed instance of
        `input_model`.

    Returns
    -------
    BaseModel
        A validated instance of `input_model`.

    Raises
    ------
    pydantic.ValidationError
        If `raw` fails validation against `input_model`.
    """
    if isinstance(raw, input_model):
        return raw
    return input_model.model_validate(raw)


class Harness:
    """Resolves, validates, and executes capabilities.

    Persistence is optional. Without a `RunRepository`, `run` behaves
    exactly as in T3: no invocation or run rows. With one, every `run` call
    saves an invocation row and a `'running'` run row before `execute`,
    then finishes the row `'succeeded'` (with the output as JSON) or
    `'failed'` if `execute` raises.

    Parameters
    ----------
    registry : CapabilityRegistry
        The capability registry this harness runs against.
    runs : RunRepository | None
        Persists invocations and runs. `None` (the default) skips
        persistence entirely.
    """

    def __init__(
        self, registry: CapabilityRegistry, runs: RunRepository | None = None
    ) -> None:
        self._registry = registry
        self._runs = runs

    async def run(
        self, capability: str, input: object, context: ExecutionContext
    ) -> object:
        """Resolve, coerce, and execute a capability.

        Parameters
        ----------
        capability : str
            Name of a registered capability.
        input : object
            Raw input: a dict (e.g. from JSON) or an instance of the
            capability's `input_model`.
        context : ExecutionContext
            Invocation metadata. `execute` receives a copy carrying a fresh
            `parent_run_id`, so the capability can hang child runs or belief
            graphs off this run.

        Returns
        -------
        object
            Whatever the capability's `execute` returns.

        Raises
        ------
        UnknownCapabilityError
            If `capability` has no registry entry.
        pydantic.ValidationError
            If `input` fails validation against the entry's `input_model`.
        """
        entry = self._registry.get(capability)
        coerced_input = _coerce_input(entry.input_model, input)
        run_id = new_id()
        run_context = context.model_copy(update={'parent_run_id': run_id})

        runs = self._runs
        if runs is None:
            return await entry.capability.execute(coerced_input, run_context)

        started_at = datetime.now(UTC)
        runs.save_invocation(
            InvocationRecord(
                id=context.invocation_id,
                trigger=context.trigger,
                actor=context.actor,
                correlation_id=context.correlation_id,
                metadata_json=json.dumps(context.metadata),
                created_at=started_at,
            )
        )
        runs.create_run(
            RunRecord(
                id=run_id,
                capability=capability,
                invocation_id=context.invocation_id,
                status='running',
                input_json=coerced_input.model_dump_json(),
                started_at=started_at,
            )
        )
        try:
            output = await entry.capability.execute(coerced_input, run_context)
        except Exception:
            runs.finish_run(run_id, 'failed', None, datetime.now(UTC))
            raise
        runs.finish_run(run_id, 'succeeded', output.model_dump_json(), datetime.now(UTC))
        return output

    def list_capabilities(self) -> list[CapabilityInfo]:
        """List every registered capability's public info.

        Returns
        -------
        list[CapabilityInfo]
            One entry per registered capability.
        """
        return self._registry.list_capabilities()
