from typing import TYPE_CHECKING

from credent.harness.context import ExecutionContext, new_id

if TYPE_CHECKING:
    from credent.harness.runtime import Harness


async def dispatch(
    harness: Harness,
    capability: str,
    payload: object,
    *,
    trigger: str,
    actor: str | None = None,
) -> object:
    """Build a fresh `ExecutionContext` and run a capability through it.

    Generic plumbing only — dispatcher-specific wiring (which capabilities
    exist, which host/storage they use) lives in the composition root
    (`credent.dispatch.bootstrap`), not here.

    Parameters
    ----------
    harness : Harness
        The harness to run the capability through.
    capability : str
        Name of a registered capability.
    payload : object
        Raw capability input: a dict (e.g. from JSON) or a typed model.
    trigger : str
        Dispatch origin, e.g. `'cli'`.
    actor : str | None
        Identity of whoever or whatever triggered the invocation.

    Returns
    -------
    object
        The result of `harness.run`.
    """
    context = ExecutionContext(invocation_id=new_id(), trigger=trigger, actor=actor)
    return await harness.run(capability, payload, context)
