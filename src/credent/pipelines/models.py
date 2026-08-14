"""Boundary payload models pipelines validate host output against.

These are the Structured Agent Contracts (ADR "Structured Agent Contracts"):
Pydantic validates a host's `structured_output` before any state mutation.
They are belief-state vocabulary, so they live here rather than in
`hosts/`, which owns process/invocation mechanics only (plan.md decision
16). `UnknownItem` is the one symbol reused from `credent.domain`.
"""

from typing import Literal

from pydantic import BaseModel, Field

from credent.domain.transitions import UnknownItem


class HostObservation(BaseModel):
    """One (subject, predicate, value) assertion extracted by a host."""

    subject: str
    predicate: str
    value: str
    source_id: str
    source_revision: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class HostContradiction(BaseModel):
    """A (subject, predicate) pair a host flagged as contradicted."""

    subject: str
    predicate: str
    source_ids: tuple[str, ...] = ()


class HostExtractionPayload(BaseModel):
    """Structured output of the `extract` pipeline stage."""

    observations: tuple[HostObservation, ...] = ()
    unknowns: tuple[UnknownItem, ...] = ()
    contradictions: tuple[HostContradiction, ...] = ()


class HostAnswerPayload(BaseModel):
    """Structured output of the `reason`/`baseline` pipeline stages."""

    answer: str | None
    status: Literal['answered', 'unknown']
