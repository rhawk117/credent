"""`reason-from-evidence`: answers one question through both pipelines.

Runs the baseline and belief-state pipelines against the same evidence,
persisting each as a child run of the harness-created parent run
(`context.parent_run_id`) -- plan.md decision 6.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from credent.harness.context import new_id
from credent.pipelines.baseline import run_baseline
from credent.pipelines.belief_state import run_belief_state
from credent.pipelines.models import QueryRequest
from credent.storage.repositories import RunRecord

if TYPE_CHECKING:
    from credent.harness.context import ExecutionContext
    from credent.hosts.base import AgentHost
    from credent.storage.repositories import BeliefRepository, RunRepository

_PIPELINES = {
    'baseline': run_baseline,
    'belief_state': run_belief_state,
}


class PipelineRunSummary(BaseModel):
    """What one pipeline produced for one `reason-from-evidence` call."""

    run_id: str
    pipeline: str
    answer: str | None
    status: str


class ReasonFromEvidenceOutput(BaseModel):
    """Results from both pipelines answering the same `QueryRequest`."""

    results: tuple[PipelineRunSummary, ...]


class ReasonFromEvidence:
    """Answers `input.question` through the baseline and belief-state pipelines.

    Parameters
    ----------
    host : AgentHost
        The agent host both pipelines invoke.
    runs : RunRepository
        Persists the per-pipeline child runs.
    beliefs : BeliefRepository
        Persists the belief graph the belief-state pipeline reconciles.
    """

    name = 'reason-from-evidence'
    input_model = QueryRequest

    def __init__(
        self, host: AgentHost, runs: RunRepository, beliefs: BeliefRepository
    ) -> None:
        self._host = host
        self._runs = runs
        self._beliefs = beliefs

    async def execute(
        self, input: QueryRequest, context: ExecutionContext
    ) -> ReasonFromEvidenceOutput:
        """Run both pipelines, persisting one child run each.

        Parameters
        ----------
        input : QueryRequest
            The question and evidence both pipelines answer from.
        context : ExecutionContext
            Carries `parent_run_id`, the harness-created run these pipeline
            runs hang off of.

        Returns
        -------
        ReasonFromEvidenceOutput
            One `PipelineRunSummary` per pipeline.
        """
        input_json = input.model_dump_json()
        summaries: list[PipelineRunSummary] = []
        for pipeline_name, run_pipeline in _PIPELINES.items():
            child_run_id = new_id()
            self._runs.create_run(
                RunRecord(
                    id=child_run_id,
                    capability=self.name,
                    invocation_id=context.invocation_id,
                    parent_run_id=context.parent_run_id,
                    pipeline=pipeline_name,
                    status='running',
                    input_json=input_json,
                    started_at=datetime.now(UTC),
                )
            )
            outcome = await run_pipeline(input, self._host)
            if outcome.graph is not None:
                self._beliefs.save_graph(child_run_id, outcome.graph)
            summary = PipelineRunSummary(
                run_id=child_run_id,
                pipeline=pipeline_name,
                answer=outcome.answer.answer,
                status=outcome.answer.status,
            )
            self._runs.finish_run(
                child_run_id, 'succeeded', summary.model_dump_json(), datetime.now(UTC)
            )
            summaries.append(summary)
        return ReasonFromEvidenceOutput(results=tuple(summaries))
