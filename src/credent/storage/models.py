"""SQLAlchemy ORM models for the run-graph subset (nine tables).

Storage maps domain models (`credent.domain`) onto rows; it never redefines
domain vocabulary such as `BeliefStatus` or `TransitionKind` — those stay
strings here and are round-tripped through the domain enums by
`repositories.py`.
"""

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every storage ORM model."""


class CapabilityRow(Base):
    """A registered capability, upserted on harness startup."""

    __tablename__ = 'capabilities'

    name: Mapped[str] = mapped_column(primary_key=True)
    description: Mapped[str]


class InvocationRow(Base):
    """One triggering invocation (CLI, hook, schedule) of the harness."""

    __tablename__ = 'invocations'

    id: Mapped[str] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(index=True)
    actor: Mapped[str | None] = mapped_column(default=None)
    correlation_id: Mapped[str | None] = mapped_column(default=None)
    metadata_json: Mapped[str]
    created_at: Mapped[datetime]


class RunRow(Base):
    """One harness run: a parent per invocation, one child per pipeline."""

    __tablename__ = 'runs'

    id: Mapped[str] = mapped_column(primary_key=True)
    capability: Mapped[str] = mapped_column(ForeignKey('capabilities.name'), index=True)
    invocation_id: Mapped[str] = mapped_column(ForeignKey('invocations.id'))
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey('runs.id'), default=None)
    pipeline: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str]
    input_json: Mapped[str]
    output_json: Mapped[str | None] = mapped_column(default=None)
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None] = mapped_column(default=None)


class SourceRow(Base):
    """A provenance source, scoped to the run that recorded it."""

    __tablename__ = 'sources'

    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    name: Mapped[str]
    kind: Mapped[str]
    authority: Mapped[int]
    revision: Mapped[str | None] = mapped_column(default=None)


class ObservationRow(Base):
    """A raw observation asserted by a source, scoped to its run."""

    __tablename__ = 'observations'

    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    subject: Mapped[str]
    predicate: Mapped[str]
    value: Mapped[str]
    source_id: Mapped[str] = mapped_column(ForeignKey('sources.id'))
    source_revision: Mapped[str | None] = mapped_column(default=None)
    confidence: Mapped[float]


class BeliefRow(Base):
    """A reconciled belief, scoped to its run.

    `derived_from_belief_ids_json` is a JSON column rather than a tenth
    table — the pack pins exactly nine tables for this task.
    """

    __tablename__ = 'beliefs'

    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    subject: Mapped[str]
    predicate: Mapped[str]
    value: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str]
    confidence: Mapped[float]
    superseded_by_belief_id: Mapped[str | None] = mapped_column(
        ForeignKey('beliefs.id'), default=None
    )
    derived_from_belief_ids_json: Mapped[str]


class BeliefSupportRow(Base):
    """Links a belief to one of the observations that supports it."""

    __tablename__ = 'belief_support'

    belief_id: Mapped[str] = mapped_column(ForeignKey('beliefs.id'), primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey('observations.id'), primary_key=True
    )


class BeliefContradictionRow(Base):
    """Links a belief to one of the observations that contradicts it."""

    __tablename__ = 'belief_contradictions'

    belief_id: Mapped[str] = mapped_column(ForeignKey('beliefs.id'), primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey('observations.id'), primary_key=True
    )


class StateTransitionRow(Base):
    """One recorded change to a belief's status, scoped to its run."""

    __tablename__ = 'state_transitions'

    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    belief_id: Mapped[str]
    kind: Mapped[str]
    from_status: Mapped[str | None] = mapped_column(default=None)
    to_status: Mapped[str]
    observation_ids_json: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[datetime]
