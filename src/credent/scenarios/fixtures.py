"""The stale-owner fixture: canonical evidence for the exit-criteria run and
contract tests.

Deterministic ground truth: the old README (`platform-team`, lower
authority) disagrees with the current CODEOWNERS (`payments-team`, higher
authority) on who owns `payments-api`. Question, evidence strings, and the
expected owner are verbatim from the ADR stale-owner case (L746-763);
authority ordering is plan.md decision 4. `FakeHost.DEFAULT_RESPONSES`
mirrors this same data.
"""

from credent.domain.observations import EvidenceItem, Source
from credent.pipelines.models import QueryRequest

GROUND_TRUTH_OWNER = 'payments-team'
SUPERSEDED_OWNER = 'platform-team'


def stale_owner_sources() -> tuple[Source, Source]:
    """The two sources behind the stale-owner fixture.

    Returns
    -------
    tuple[Source, Source]
        `(readme, codeowners)` -- the old, lower-authority README and the
        current, higher-authority CODEOWNERS file.
    """
    return (
        Source(
            id='src-readme',
            name='Old README',
            kind='readme',
            authority=1,
            revision='t2',
        ),
        Source(
            id='src-codeowners',
            name='Current CODEOWNERS',
            kind='codeowners',
            authority=2,
            revision='t3',
        ),
    )


def stale_owner_request() -> QueryRequest:
    """Build the stale-owner `QueryRequest`.

    Returns
    -------
    QueryRequest
        Asks who owns `payments-api`, grounded in the README/CODEOWNERS
        evidence pair.
    """
    readme, codeowners = stale_owner_sources()
    return QueryRequest(
        question='Who owns payments-api?',
        evidence=(
            EvidenceItem(
                source=readme, content='Old README: platform-team owns payments-api.'
            ),
            EvidenceItem(
                source=codeowners,
                content='Current CODEOWNERS: payments-team owns payments-api.',
            ),
        ),
    )
