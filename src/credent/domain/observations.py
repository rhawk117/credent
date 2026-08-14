"""Leaf domain module: sources and the raw observations they assert.

Imports nothing else in `credent.domain`.
"""

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A provenance source for one or more observations.

    Parameters
    ----------
    authority
        Higher wins when two sources disagree on a value during
        reconciliation. Ties between incompatible values produce a
        CONTRADICTED belief rather than a resolved one.
    """

    id: str
    name: str
    kind: str
    authority: int
    revision: str | None = None


class Observation(BaseModel):
    """A single value a source asserts for a (subject, predicate) pair."""

    id: str
    subject: str
    predicate: str
    value: str
    source_id: str
    source_revision: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    """Raw evidence text paired with the source it came from."""

    source: Source
    content: str
