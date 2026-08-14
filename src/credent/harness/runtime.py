from typing import TYPE_CHECKING

from credent.harness.context import ExecutionContext, new_id

if TYPE_CHECKING:
    from pydantic import BaseModel

    from credent.harness.registry import CapabilityInfo, CapabilityRegistry


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

    T3 is persistence-free: it holds no storage or host references. T7 adds
    an optional `RunRepository` and the persistence branch around `execute`.

    Parameters
    ----------
    registry : CapabilityRegistry
        The capability registry this harness runs against.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

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
        return await entry.capability.execute(coerced_input, run_context)

    def list_capabilities(self) -> list[CapabilityInfo]:
        """List every registered capability's public info.

        Returns
        -------
        list[CapabilityInfo]
            One entry per registered capability.
        """
        return self._registry.list_capabilities()
