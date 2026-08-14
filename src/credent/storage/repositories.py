"""Run-graph and belief-graph persistence.

Repositories map domain models (`credent.domain`) onto rows and back; T2
owns every domain type, so nothing here redefines `BeliefStatus`,
`TransitionKind`, or the belief/observation/source models. Storage must not
import `credent.harness` — the harness maps `ExecutionContext` onto
`InvocationRecord` at its own boundary.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import select

from credent.domain.beliefs import Belief, BeliefStatus
from credent.domain.observations import Observation, Source
from credent.domain.provenance import BeliefGraph
from credent.domain.transitions import StateTransition, TransitionKind
from credent.storage.models import (
    BeliefContradictionRow,
    BeliefRow,
    BeliefSupportRow,
    CapabilityRow,
    InvocationRow,
    ObservationRow,
    RunRow,
    SourceRow,
    StateTransitionRow,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session, sessionmaker


class RunRecord(BaseModel):
    """Storage-facing DTO for one row of the `runs` table."""

    id: str
    capability: str
    invocation_id: str
    parent_run_id: str | None = None
    pipeline: str | None = None
    status: str
    input_json: str
    output_json: str | None = None
    started_at: datetime
    ended_at: datetime | None = None


class InvocationRecord(BaseModel):
    """Storage-facing DTO for one row of the `invocations` table.

    The harness maps `ExecutionContext` onto this DTO; storage never
    imports `credent.harness`.
    """

    id: str
    trigger: str
    actor: str | None = None
    correlation_id: str | None = None
    metadata_json: str = '{}'
    created_at: datetime


def _to_naive_utc(value: datetime) -> datetime:
    """Strip tzinfo for storage, normalizing to UTC first.

    SQLite's `DATETIME` type round-trips naive strings; house style always
    produces UTC-aware datetimes (`datetime.now(UTC)`), so normalizing to
    UTC before dropping tzinfo keeps the wall-clock value correct.
    """
    return value.astimezone(UTC).replace(tzinfo=None)


def _from_naive_utc(value: datetime) -> datetime:
    """Reattach UTC tzinfo to a value loaded from a `DATETIME` column."""
    return value.replace(tzinfo=UTC)


def _run_record_from_row(row: RunRow) -> RunRecord:
    return RunRecord(
        id=row.id,
        capability=row.capability,
        invocation_id=row.invocation_id,
        parent_run_id=row.parent_run_id,
        pipeline=row.pipeline,
        status=row.status,
        input_json=row.input_json,
        output_json=row.output_json,
        started_at=_from_naive_utc(row.started_at),
        ended_at=_from_naive_utc(row.ended_at) if row.ended_at is not None else None,
    )


class RunRepository:
    """Persists capabilities, invocations, and the run graph.

    Parameters
    ----------
    session_factory : sessionmaker[Session]
        Factory used to open one session per method call; each method
        commits its own transaction.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register_capability(self, name: str, description: str) -> None:
        """Upsert a capability row.

        Parameters
        ----------
        name : str
            Capability name; the primary key.
        description : str
            Human-readable description. Overwrites any prior value for
            `name`.
        """
        with self._session_factory() as session, session.begin():
            row = session.get(CapabilityRow, name)
            if row is None:
                session.add(CapabilityRow(name=name, description=description))
            else:
                row.description = description

    def save_invocation(self, record: InvocationRecord) -> None:
        """Persist one invocation row.

        Parameters
        ----------
        record : InvocationRecord
            The invocation to persist.
        """
        with self._session_factory() as session, session.begin():
            session.add(
                InvocationRow(
                    id=record.id,
                    trigger=record.trigger,
                    actor=record.actor,
                    correlation_id=record.correlation_id,
                    metadata_json=record.metadata_json,
                    created_at=_to_naive_utc(record.created_at),
                )
            )

    def create_run(self, run: RunRecord) -> None:
        """Persist one run row.

        Parameters
        ----------
        run : RunRecord
            The run to persist.
        """
        with self._session_factory() as session, session.begin():
            session.add(
                RunRow(
                    id=run.id,
                    capability=run.capability,
                    invocation_id=run.invocation_id,
                    parent_run_id=run.parent_run_id,
                    pipeline=run.pipeline,
                    status=run.status,
                    input_json=run.input_json,
                    output_json=run.output_json,
                    started_at=_to_naive_utc(run.started_at),
                    ended_at=(
                        _to_naive_utc(run.ended_at) if run.ended_at is not None else None
                    ),
                )
            )

    def finish_run(
        self, run_id: str, status: str, output_json: str | None, ended_at: datetime
    ) -> None:
        """Mark a run finished.

        Parameters
        ----------
        run_id : str
            The run to update.
        status : str
            Terminal status (`'succeeded'` or `'failed'`).
        output_json : str | None
            The capability's serialized output, if any.
        ended_at : datetime
            Completion timestamp.

        Raises
        ------
        LookupError
            If no run is registered under `run_id`.
        """
        with self._session_factory() as session, session.begin():
            row = session.get(RunRow, run_id)
            if row is None:
                raise LookupError(f'no run {run_id!r}')
            row.status = status
            row.output_json = output_json
            row.ended_at = _to_naive_utc(ended_at)

    def get_run(self, run_id: str) -> RunRecord | None:
        """Fetch one run by id.

        Parameters
        ----------
        run_id : str
            The run to fetch.

        Returns
        -------
        RunRecord | None
            The run, or `None` if no run is registered under `run_id`.
        """
        with self._session_factory() as session:
            row = session.get(RunRow, run_id)
            return _run_record_from_row(row) if row is not None else None

    def children_of(self, run_id: str) -> list[RunRecord]:
        """List every run whose `parent_run_id` is `run_id`.

        Parameters
        ----------
        run_id : str
            The parent run.

        Returns
        -------
        list[RunRecord]
            Child runs (e.g. the `'baseline'`/`'belief_state'` pipeline
            runs of a `reason-from-evidence` call), ordered by start time.
        """
        with self._session_factory() as session:
            rows = session.scalars(
                select(RunRow)
                .where(RunRow.parent_run_id == run_id)
                .order_by(RunRow.started_at)
            ).all()
            return [_run_record_from_row(row) for row in rows]


class BeliefRepository:
    """Persists and loads the domain `BeliefGraph` for one run.

    Parameters
    ----------
    session_factory : sessionmaker[Session]
        Factory used to open one session per method call; each method
        commits its own transaction.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save_graph(self, run_id: str, graph: BeliefGraph) -> None:
        """Persist a full belief graph under one run, in one transaction.

        Parameters
        ----------
        run_id : str
            The run this graph belongs to.
        graph : BeliefGraph
            Sources, observations, beliefs, and transitions to persist.
        """
        with self._session_factory() as session, session.begin():
            for source in graph.sources:
                session.add(
                    SourceRow(
                        id=source.id,
                        run_id=run_id,
                        name=source.name,
                        kind=source.kind,
                        authority=source.authority,
                        revision=source.revision,
                    )
                )
            for observation in graph.observations:
                session.add(
                    ObservationRow(
                        id=observation.id,
                        run_id=run_id,
                        subject=observation.subject,
                        predicate=observation.predicate,
                        value=observation.value,
                        source_id=observation.source_id,
                        source_revision=observation.source_revision,
                        confidence=observation.confidence,
                    )
                )
            for belief in graph.beliefs:
                session.add(
                    BeliefRow(
                        id=belief.id,
                        run_id=run_id,
                        subject=belief.subject,
                        predicate=belief.predicate,
                        value=belief.value,
                        status=belief.status.value,
                        confidence=belief.confidence,
                        superseded_by_belief_id=belief.superseded_by_belief_id,
                        derived_from_belief_ids_json=json.dumps(
                            list(belief.derived_from_belief_ids)
                        ),
                    )
                )
                for observation_id in belief.supporting_observation_ids:
                    session.add(
                        BeliefSupportRow(
                            belief_id=belief.id, observation_id=observation_id
                        )
                    )
                for observation_id in belief.contradicting_observation_ids:
                    session.add(
                        BeliefContradictionRow(
                            belief_id=belief.id, observation_id=observation_id
                        )
                    )
            for transition in graph.transitions:
                session.add(
                    StateTransitionRow(
                        id=uuid.uuid4().hex,
                        run_id=run_id,
                        belief_id=transition.belief_id,
                        kind=transition.kind.value,
                        from_status=(
                            transition.from_status.value
                            if transition.from_status is not None
                            else None
                        ),
                        to_status=transition.to_status.value,
                        observation_ids_json=json.dumps(list(transition.observation_ids)),
                        reason=transition.reason,
                        created_at=_to_naive_utc(datetime.now(UTC)),
                    )
                )

    def load_graph(self, run_id: str) -> BeliefGraph:
        """Reload the belief graph persisted for one run.

        Parameters
        ----------
        run_id : str
            The run to load.

        Returns
        -------
        BeliefGraph
            Sources, observations, beliefs, and transitions for `run_id`,
            each ordered deterministically by id (transitions by
            `(belief_id, kind)`, mirroring `domain.transitions.reconcile`'s
            own canonical order).
        """
        with self._session_factory() as session:
            source_rows = session.scalars(
                select(SourceRow).where(SourceRow.run_id == run_id).order_by(SourceRow.id)
            ).all()
            observation_rows = session.scalars(
                select(ObservationRow)
                .where(ObservationRow.run_id == run_id)
                .order_by(ObservationRow.id)
            ).all()
            belief_rows = session.scalars(
                select(BeliefRow).where(BeliefRow.run_id == run_id).order_by(BeliefRow.id)
            ).all()
            transition_rows = session.scalars(
                select(StateTransitionRow)
                .where(StateTransitionRow.run_id == run_id)
                .order_by(StateTransitionRow.belief_id, StateTransitionRow.kind)
            ).all()

            belief_ids = [row.id for row in belief_rows]
            support_by_belief = _observation_ids_by_belief(
                session, BeliefSupportRow, belief_ids
            )
            contradiction_by_belief = _observation_ids_by_belief(
                session, BeliefContradictionRow, belief_ids
            )

        sources = tuple(
            Source(
                id=row.id,
                name=row.name,
                kind=row.kind,
                authority=row.authority,
                revision=row.revision,
            )
            for row in source_rows
        )
        observations = tuple(
            Observation(
                id=row.id,
                subject=row.subject,
                predicate=row.predicate,
                value=row.value,
                source_id=row.source_id,
                source_revision=row.source_revision,
                confidence=row.confidence,
            )
            for row in observation_rows
        )
        beliefs = tuple(
            Belief(
                id=row.id,
                subject=row.subject,
                predicate=row.predicate,
                value=row.value,
                status=BeliefStatus(row.status),
                confidence=row.confidence,
                supporting_observation_ids=support_by_belief.get(row.id, ()),
                contradicting_observation_ids=contradiction_by_belief.get(row.id, ()),
                derived_from_belief_ids=tuple(
                    json.loads(row.derived_from_belief_ids_json)
                ),
                superseded_by_belief_id=row.superseded_by_belief_id,
            )
            for row in belief_rows
        )
        transitions = tuple(
            StateTransition(
                belief_id=row.belief_id,
                kind=TransitionKind(row.kind),
                from_status=(
                    BeliefStatus(row.from_status) if row.from_status is not None else None
                ),
                to_status=BeliefStatus(row.to_status),
                observation_ids=tuple(json.loads(row.observation_ids_json)),
                reason=row.reason,
            )
            for row in transition_rows
        )
        return BeliefGraph(
            sources=sources,
            observations=observations,
            beliefs=beliefs,
            transitions=transitions,
        )


def _observation_ids_by_belief(
    session: Session,
    link_row: type[BeliefSupportRow | BeliefContradictionRow],
    belief_ids: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    if not belief_ids:
        return {}
    rows = session.scalars(
        select(link_row)
        .where(link_row.belief_id.in_(belief_ids))
        .order_by(link_row.belief_id, link_row.observation_id)
    ).all()
    by_belief: dict[str, list[str]] = {}
    for row in rows:
        by_belief.setdefault(row.belief_id, []).append(row.observation_id)
    return {belief_id: tuple(ids) for belief_id, ids in by_belief.items()}
