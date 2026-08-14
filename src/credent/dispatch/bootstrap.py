"""Composition root: wires the default `Harness` for CLI/dispatch use.

Lives in `dispatch/`, not `harness/` (plan.md decision 15) -- wiring
capabilities into the harness pulls in `capabilities/`, `storage/`, and
`hosts/` imports the harness itself must never make (the downward-only
dependency gate: dispatch -> capabilities -> harness -> infrastructure).
"""

from typing import TYPE_CHECKING, Any

from credent.capabilities.inspect_belief_state import InspectBeliefState
from credent.capabilities.reason_from_evidence import ReasonFromEvidence
from credent.capabilities.reconcile_beliefs import ReconcileBeliefs
from credent.harness.registry import CapabilityRegistry
from credent.harness.runtime import Harness
from credent.hosts.fake import FakeHost
from credent.storage.database import (
    create_engine_and_schema,
    resolve_db_path,
    session_factory,
)
from credent.storage.repositories import BeliefRepository, RunRepository

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from credent.harness.registry import Capability
    from credent.hosts.base import AgentHost


def build_default_harness(
    host: AgentHost | None = None, db_path: Path | None = None
) -> Harness:
    """Build the default `Harness`, wired against SQLite and the three capabilities.

    Parameters
    ----------
    host : AgentHost | None
        Agent host the host-calling capabilities invoke. Defaults to a
        fresh `FakeHost()`.
    db_path : Path | None
        SQLite database path. Defaults to `resolve_db_path()`.

    Returns
    -------
    Harness
        A harness with `reason-from-evidence`, `reconcile-beliefs`, and
        `inspect-belief-state` registered, persisting through the given (or
        default) SQLite database.
    """
    resolved_host = host if host is not None else FakeHost()
    resolved_db_path = db_path if db_path is not None else resolve_db_path()

    engine = create_engine_and_schema(resolved_db_path)
    factory = session_factory(engine)
    runs = RunRepository(factory)
    beliefs = BeliefRepository(factory)

    registry = CapabilityRegistry()

    def register(
        name: str,
        capability: Capability[Any, Any],
        description: str,
        input_model: type[BaseModel],
    ) -> None:
        """Register `capability` in the in-memory registry and upsert its DB row."""
        registry.register(name, capability, description, input_model)
        runs.register_capability(name, description)

    register(
        ReasonFromEvidence.name,
        ReasonFromEvidence(resolved_host, runs, beliefs),
        'Answers a question from evidence through the baseline and '
        'belief-state pipelines.',
        ReasonFromEvidence.input_model,
    )
    register(
        ReconcileBeliefs.name,
        ReconcileBeliefs(beliefs),
        'Reconciles raw observations into beliefs, deterministically.',
        ReconcileBeliefs.input_model,
    )
    register(
        InspectBeliefState.name,
        InspectBeliefState(runs, beliefs),
        'Reads back a run, its children, and its belief graph.',
        InspectBeliefState.input_model,
    )

    return Harness(registry, runs=runs)
