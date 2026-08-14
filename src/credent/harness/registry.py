from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from credent.harness.context import ExecutionContext


@runtime_checkable
class Capability[InputT, OutputT](Protocol):
    """A unit of harness-executable work.

    Decorated `@runtime_checkable` so Pydantic's `arbitrary_types_allowed`
    isinstance check on `RegistryEntry.capability` works against the
    subscripted `Capability[Any, Any]` annotation.

    Parameters
    ----------
    input : InputT
        Capability input, already validated/coerced by the harness.
    context : ExecutionContext
        Execution metadata for this invocation.

    Returns
    -------
    OutputT
        The capability's structured result.
    """

    async def execute(self, input: InputT, context: ExecutionContext) -> OutputT: ...


class CapabilityInfo(BaseModel):
    """Public-facing summary of a registered capability."""

    name: str
    description: str


class UnknownCapabilityError(LookupError):
    """Raised when a capability name has no registry entry."""


class RegistryEntry(BaseModel):
    """A registered capability plus the metadata the harness runs it with."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    capability: Capability[Any, Any]
    description: str
    input_model: type[BaseModel]


class CapabilityRegistry:
    """In-memory map from capability name to its registry entry."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(
        self,
        name: str,
        capability: Capability[Any, Any],
        description: str,
        input_model: type[BaseModel],
    ) -> None:
        """Register a capability under `name`.

        Parameters
        ----------
        name : str
            Unique capability name.
        capability : Capability[Any, Any]
            The capability instance to register.
        description : str
            Human-readable description, surfaced by `list_capabilities`.
        input_model : type[BaseModel]
            Pydantic model the harness coerces raw input through before
            calling `capability.execute`.
        """
        self._entries[name] = RegistryEntry(
            name=name,
            capability=capability,
            description=description,
            input_model=input_model,
        )

    def get(self, name: str) -> RegistryEntry:
        """Look up a registered capability by name.

        Parameters
        ----------
        name : str
            Capability name to look up.

        Returns
        -------
        RegistryEntry
            The registered entry.

        Raises
        ------
        UnknownCapabilityError
            If no capability is registered under `name`.
        """
        try:
            return self._entries[name]
        except KeyError as exc:
            raise UnknownCapabilityError(name) from exc

    def list_capabilities(self) -> list[CapabilityInfo]:
        """List every registered capability's public info.

        Returns
        -------
        list[CapabilityInfo]
            One entry per registered capability.
        """
        return [
            CapabilityInfo(name=entry.name, description=entry.description)
            for entry in self._entries.values()
        ]
