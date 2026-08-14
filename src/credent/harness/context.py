import uuid

from pydantic import BaseModel


def new_id() -> str:
    """Generate a random identifier.

    Returns
    -------
    str
        A 32-character lowercase hex string (`uuid4().hex`).
    """
    return uuid.uuid4().hex


class ExecutionContext(BaseModel):
    """Metadata threaded through a single capability invocation.

    Parameters
    ----------
    invocation_id : str
        Identifier for the triggering invocation.
    trigger : str
        Dispatch origin, e.g. `'cli'`. `'eval'` is reserved for Phase 2.
    actor : str | None
        Identity of whoever or whatever triggered the invocation.
    correlation_id : str | None
        Cross-system correlation id.
    parent_run_id : str | None
        The enclosing harness run. `Harness.run` sets this on the context
        copy it passes to `execute`, so the capability can hang child runs
        or belief graphs off it.
    metadata : dict[str, object]
        Free-form, capability-specific context (e.g. pipeline stage tags).
    """

    invocation_id: str
    trigger: str
    actor: str | None = None
    correlation_id: str | None = None
    parent_run_id: str | None = None
    metadata: dict[str, object] = {}
