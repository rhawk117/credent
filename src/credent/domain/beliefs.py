"""Leaf domain module: reconciled beliefs and their status vocabulary.

Imports nothing else in `credent.domain`.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from typing import Self


class BeliefStatus(StrEnum):
    """Where a belief's value came from, or that it has none."""

    OBSERVED = 'observed'
    RETRIEVED = 'retrieved'
    INFERRED = 'inferred'
    ASSUMED = 'assumed'
    CONTRADICTED = 'contradicted'
    UNKNOWN = 'unknown'


class Belief(BaseModel):
    """A reconciled fact about a (subject, predicate) pair.

    Supersession is a relation, not a status: a losing belief keeps its own
    status and value (lineage preserved) and points at the belief that
    replaced it via `superseded_by_belief_id`.
    """

    id: str
    subject: str
    predicate: str
    value: str | None
    status: BeliefStatus
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_observation_ids: tuple[str, ...] = ()
    contradicting_observation_ids: tuple[str, ...] = ()
    derived_from_belief_ids: tuple[str, ...] = ()
    superseded_by_belief_id: str | None = None

    @model_validator(mode='after')
    def _unknown_carries_no_value(self) -> Self:
        if self.status == BeliefStatus.UNKNOWN and self.value is not None:
            raise ValueError('a belief with status UNKNOWN must not carry a value')
        return self
