# ADR: AI Harness Architecture and Implementation

## Status

Proposed

## Decision

Build the MVP as a Python 3.14 **AI harness** with a clean separation between:

1. delivery and dispatch,
2. capabilities/workflows,
3. harness runtime,
4. infrastructure.

Hooks, skills, schedules, and CLI commands are delivery mechanisms.

They dispatch reusable capabilities into the harness runtime.

They are not themselves the core architecture.

---

# Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Delivery / Dispatch                                         │
│                                                             │
│ lifecycle hooks | skills | scheduled tasks | CLI | API       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Capability Layer                                            │
│                                                             │
│ reason-from-evidence                                        │
│ reconcile-beliefs                                           │
│ validate-claims                                             │
│ run-evaluation                                              │
│ docs-query                                                  │
│ future: jira-triage, reindex-docs, incident-assist          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Harness Runtime                                             │
│                                                             │
│ capability execution                                       │
│ belief-state engine                                         │
│ evidence normalization                                      │
│ host-agent adapters                                         │
│ evaluation                                                  │
│ tracing                                                     │
│ persistence                                                 │
│ usage/cost accounting                                       │
│ future retrieval                                            │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure                                              │
│                                                             │
│ SQLite | model providers | filesystem | future Qdrant       │
└─────────────────────────────────────────────────────────────┘
```

The governing principle is:

> **Dispatchers determine when work should run. Capabilities define what work should run. The harness runtime defines how AI work executes.**

---

# Technology Decisions

Use:

- **Pydantic** for typed application boundaries and structured host-agent contracts
- **Pydantic Evals** for datasets, cases, evaluators, and experiment execution
- **AnyIO** for async subprocess/process orchestration across local agent hosts
- **Phoenix + OpenInference** for tracing where useful
- **SQLite** for local durable state
- **SQLAlchemy** for relational persistence
- **Polars** for experiment analysis
- **NumPy** for numerical processing
- **SciPy** for statistics
- **Typer** for CLI commands
- **Rich** for terminal output
- a small **task scheduling abstraction** for durable future capability invocations; no resident scheduler daemon

Deferred RAG dependencies:

- **Qdrant Client**
- **FastEmbed**
- **SentenceTransformers**
- **Ragas**

The MVP intentionally does **not** use Pydantic AI.

Claude Code and GitHub Copilot CLI already own:

- model selection,
- model execution,
- agent loops,
- tool use,
- context/session handling,
- user interaction.

The harness should integrate with those environments rather than introduce a second model or agent runtime.

The MVP also does not require LangGraph or DSPy. Ordinary Python orchestration is preferable until a concrete workflow becomes complex enough to justify a graph runtime or prompt-program optimizer.

The MVP does not require:

- FastAPI
- Redis
- Celery
- Dramatiq
- Kubernetes
- a message broker
- a standalone vector database service

---

# Why Pydantic Evals Remains

Evaluation is a harness responsibility even though model execution belongs to Claude Code or Copilot CLI.

Pydantic Evals can still own:

- datasets,
- scenario cases,
- expected outputs,
- custom evaluators,
- experiment execution,
- comparison of baseline versus belief-state runs.

The subject under evaluation can be a host-agent adapter, a recorded run, or a harness capability rather than a Pydantic AI agent.

# Runtime Abstractions

## Harness

The harness is the stable execution entrypoint.

Conceptually:

```python
from typing import Protocol, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class Capability(Protocol[InputT, OutputT]):
    async def execute(
        self,
        input: InputT,
        context: "ExecutionContext",
    ) -> OutputT:
        ...


class Harness:
    async def run(
        self,
        capability: str,
        input: object,
        context: "ExecutionContext",
    ) -> object:
        ...
```

The public contract should not expose Claude Code-, Copilot-, or model-provider-specific concepts. Host-specific behavior belongs behind narrow adapters.

---

## Capability Registry

Capabilities are named executable units.

Example:

```python
registry.register(
    "reason-from-evidence",
    reason_from_evidence,
)

registry.register(
    "validate-claims",
    validate_claims,
)
```

Invocation:

```python
result = await harness.run(
    "reason-from-evidence",
    input=request,
    context=context,
)
```

Future capabilities can be added without modifying dispatch mechanisms.

---

## Execution Context

All delivery mechanisms normalize into a common execution context.

```python
from pydantic import BaseModel


class ExecutionContext(BaseModel):
    invocation_id: str
    trigger: str
    actor: str | None = None
    correlation_id: str | None = None
    parent_run_id: str | None = None
    metadata: dict[str, object] = {}
```

Examples of `trigger`:

```text
hook:session_start
hook:session_end
hook:agent_stop
hook:post_tool
hook:pre_completion
skill
scheduled-task
cli
api
webhook
```

This gives tracing and persistence a uniform model regardless of how the capability was invoked.

---

# Delivery and Dispatch

## Hooks

Hooks are event dispatchers.

Their responsibilities are limited to:

1. receive an event,
2. normalize it,
3. construct execution context,
4. select a capability,
5. dispatch to the harness,
6. return or propagate the result.

Example:

```python
async def post_tool(event: ToolEvent) -> None:
    await harness.run(
        "observe-tool-result",
        input=ToolObservationRequest.from_event(event),
        context=ExecutionContext(
            invocation_id=event.id,
            trigger="hook:post_tool",
        ),
    )
```

A hook must not implement:

- belief reconciliation,
- model prompts,
- retrieval,
- source authority,
- evaluation logic.

Those belong in capabilities or runtime modules.

### Event Model

Use typed events:

```python
class HookEvent(BaseModel):
    id: str
    name: str
    timestamp: datetime
    payload: dict[str, object]
```

Specific events may extend this type.

---

## Skills

Skills describe how agents consume capabilities.

They should specify:

- triggering conditions,
- capability name,
- required inputs,
- interpretation rules,
- expected failure behavior.

Example:

```markdown
# Documentation Grounding

Use when answering a question that depends on team documentation,
especially when sources may conflict or be stale.

## Capability

`docs-query`

## Behavior

1. Supply the user's question.
2. Preserve returned provenance.
3. Treat `UNKNOWN` as a valid result.
4. Surface unresolved contradictions.
5. Gather additional evidence only when explicitly requested by the result.
```

Skills should remain versioned files.

The harness records the skill hash/version used for each invocation when known.

---

## Lifecycle Hooks and Scheduled Tasks

The MVP does **not** run an application-owned scheduler daemon.

Instead, lifecycle hooks create immediate or future work.

Primary hooks:

```text
sessionStart
sessionEnd
agentStop
```

Additional event hooks may include:

```text
postTool
preCompletion
postCompletion
```

### `sessionStart`

Responsibilities:

- restore persisted harness/session state,
- create the session execution context,
- inspect or dispatch tasks due at session start,
- expose pending/deferred work,
- refresh invalidated state when required.

### `agentStop`

Responsibilities:

- capture final agent execution metadata,
- persist observations/results,
- schedule post-run capabilities such as evaluation or reporting,
- avoid extending the critical path with non-interactive follow-up work.

Example:

```python
async def agent_stop(event: AgentStopEvent) -> None:
    await task_scheduler.schedule(
        TaskSpec(
            capability="evaluate-run",
            input=EvaluationRequest(run_id=event.run_id),
            trigger=TaskTrigger.after_agent_stop(),
            correlation_id=event.correlation_id,
        )
    )
```

### `sessionEnd`

Responsibilities:

- checkpoint session state,
- persist unresolved beliefs/contradictions,
- close tracing metadata,
- schedule work intended to happen after the interactive session.

Example:

```python
async def session_end(event: SessionEndEvent) -> None:
    await task_scheduler.schedule(
        TaskSpec(
            capability="docs-drift-evaluation",
            input=DocsDriftRequest(session_id=event.session_id),
            trigger=TaskTrigger.deferred(),
            correlation_id=event.correlation_id,
        )
    )
```

### Task Scheduling Contract

Scheduling is represented as data and delegated to a host-specific adapter.

```python
from typing import Protocol


class TaskScheduler(Protocol):
    async def schedule(self, task: "TaskSpec") -> str: ...


class TaskSpec(BaseModel):
    capability: str
    input: dict[str, object]
    correlation_id: str | None = None
    trigger: "TaskTrigger"
```

The adapter may target:

- a host agent task scheduler,
- a platform scheduling API,
- another invocation mechanism,
- or a local persisted task store reconciled at `sessionStart`.

The harness does not need a resident process.

If no external wall-clock scheduler exists, due tasks may be persisted in SQLite and reconciled opportunistically by `sessionStart`.

The capability receives the same execution interface regardless of how the task eventually arrives:

```python
await harness.run(
    task.capability,
    input=task.input,
    context=ExecutionContext(
        invocation_id=new_id(),
        trigger="scheduled-task",
        correlation_id=task.correlation_id,
    ),
)
```

---

## CLI

The CLI is another dispatcher.

Example:

```python
@app.command()
def run(capability: str) -> None:
    anyio.run(
        harness.run,
        capability,
        input,
        ExecutionContext(
            invocation_id=new_id(),
            trigger="cli",
        ),
    )
```

Expected commands:

```bash
belief-lab capability list
belief-lab run <capability>
belief-lab eval <experiment>
belief-lab compare <left> <right>
belief-lab inspect <run-id>
belief-lab replay <run-id>
belief-lab hook test <hook>
belief-lab skill validate
belief-lab schedule list
```

---

# Capability Layer

Capabilities are use-case-level abstractions.

Initial capabilities:

```text
reason-from-evidence
reconcile-beliefs
validate-claims
run-evaluation
inspect-belief-state
```

Planned:

```text
docs-query
reindex-docs
jira-triage
incident-assist
documentation-drift
```

A capability may internally use:

- deterministic Python logic,
- persisted belief/evidence state,
- a host-agent invocation when semantic reasoning is required,
- subprocesses,
- retrieval,
- evaluation,
- task scheduling.

The caller does not need to know.

Capabilities should prefer deterministic local computation. Claude Code or Copilot CLI perform the actual model reasoning when the workflow requires it.

---

# Belief-State Domain Model

## Belief Status

```python
from enum import StrEnum, auto


class BeliefStatus(StrEnum):
    OBSERVED = auto()
    RETRIEVED = auto()
    INFERRED = auto()
    ASSUMED = auto()
    CONTRADICTED = auto()
    UNKNOWN = auto()
```

## Observation

```python
from pydantic import BaseModel, Field


class Observation(BaseModel):
    id: str
    subject: str
    predicate: str
    value: str
    source_id: str
    source_revision: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
```

## Belief

```python
class Belief(BaseModel):
    id: str
    subject: str
    predicate: str
    value: str | None
    status: BeliefStatus
    confidence: float = Field(ge=0.0, le=1.0)

    supporting_observation_ids: tuple[str, ...] = ()
    contradicting_observation_ids: tuple[str, ...] = ()
    derived_from_belief_ids: tuple[str, ...] = ()
```

## Provenance

Provenance is a graph, not merely a citation string.

```text
source
  |
  v
observation
  |
  +----> belief A
  |
  +----> belief B
             |
             v
          belief C
```

Derived beliefs must retain their dependency lineage.

---

# Host Agent Integration

The harness does not own model execution.

Claude Code and GitHub Copilot CLI are external **agent hosts**. They already provide the agent loop, model invocation, tools, session context, and user interaction.

The harness integrates with them through:

- lifecycle hooks,
- skills,
- CLI commands,
- structured stdin/stdout or file contracts,
- subprocess invocation when the harness must launch a host operation,
- durable state that host agents read and update through harness commands.

Conceptually:

```text
Claude Code / Copilot CLI
        |
        +--> skill selects capability
        |
        +--> hook dispatches event
        |
        +--> CLI / subprocess contract
                |
                v
             harness
                |
                +--> belief/evidence state
                +--> task store
                +--> evals
                +--> retrieval
```

There is no second autonomous agent loop inside the harness.

## Host Adapter Contract

Use a deliberately narrow adapter where host-specific behavior cannot be avoided.

```python
from typing import Protocol


class AgentHost(Protocol):
    name: str

    async def invoke(
        self,
        request: "AgentInvocation",
    ) -> "AgentResult":
        ...
```

Initial implementations:

```text
ClaudeCodeHost
CopilotCliHost
RecordedHost
FakeHost
```

Adapters normalize only what the harness needs:

- process invocation,
- stdin/stdout,
- exit status,
- session/run identifiers,
- structured output when available,
- timing,
- usage metadata when exposed,
- trace correlation.

Do not attempt to create a universal abstraction for all host-agent semantics.

## Structured Agent Contracts

Where a host agent is expected to update harness state, prefer explicit structured output over parsing prose.

Example:

```json
{
  "observations": [
    {
      "subject": "payments-api",
      "predicate": "owner",
      "value": "payments-team",
      "source_id": "CODEOWNERS"
    }
  ],
  "unknowns": [],
  "contradictions": []
}
```

Pydantic validates the boundary before state mutation.

## Pipeline Orchestration

Baseline and belief-state pipelines are ordinary Python modules.

Start with direct composition:

```python
async def run_belief_pipeline(request: QueryRequest) -> QueryResult:
    evidence = normalize_evidence(request.evidence)
    observations = await extract_with_host(evidence)
    beliefs = reconcile(observations)
    answer = await render_with_host(request.question, beliefs)
    return validate(answer, beliefs)
```

Do not introduce LangGraph until the workflow has genuinely dynamic branching, interruption, resumability, or topology complex enough that ordinary functions become harder to reason about.

Do not introduce DSPy until the project owns a repeatable model-invocation surface suitable for program optimization. In the MVP, Claude Code and Copilot CLI remain the model-facing systems.

# Pydantic Evals

Use Pydantic Evals for:

- datasets
- scenario cases
- expected outputs
- custom evaluators
- experiment execution

Example:

```python
from pydantic_evals import Case, Dataset


dataset = Dataset(
    name="ownership",
    cases=[
        Case(
            name="stale-owner",
            inputs={
                "question": "Who owns payments-api?",
                "evidence": [
                    "Old README: platform-team owns payments-api.",
                    "Current CODEOWNERS: payments-team owns payments-api.",
                ],
            },
            expected_output={
                "owner": "payments-team",
            },
        ),
    ],
)
```

The eval subject should call the harness capability or host adapter rather than a Pydantic AI agent.

Conceptually:

```python
async def subject(inputs: QueryInputs) -> QueryResult:
    return await harness.run(
        "reason-from-evidence",
        input=inputs,
        context=ExecutionContext(
            invocation_id=new_id(),
            trigger="eval",
        ),
    )
```

A second subject can execute the baseline path through the same Claude Code or Copilot CLI host.

Prefer deterministic evaluators whenever possible.

---

# Persistence

Use SQLite as the authoritative local store.

Use SQLAlchemy for relational access.

Suggested tables:

```text
capabilities
experiments
runs
invocations
scenarios
scenario_variants
sources
observations
beliefs
belief_support
belief_contradictions
state_transitions
model_invocations
hook_invocations
schedule_invocations
evaluation_results
artifacts
```

Key indexes:

```text
runs(experiment_id)
runs(capability)
invocations(trigger)
observations(run_id)
beliefs(run_id)
state_transitions(run_id)
model_invocations(run_id)
evaluation_results(run_id, metric_name)
```

---

# Tracing

Use Phoenix + OpenInference.

Trace the complete dispatch-to-result path:

```text
hook / skill / schedule / CLI
            |
            v
        dispatch
            |
            v
       capability
            |
            v
        graph node
            |
            v
        model call
            |
            v
     state transition
            |
            v
         evaluator
```

Example:

```text
run: ownership-0042
|
+-- trigger: hook:post_tool
|
+-- capability: reason-from-evidence
|   |
|   +-- extract
|   |   +-- model call
|   |
|   +-- reconcile
|   |
|   +-- render
|       +-- model call
|
+-- eval
    +-- state_correct = true
    +-- answer_correct = true
```

---

# Data Analysis

## Polars

Use Polars for experiment analysis and reporting.

```python
report = (
    pl.scan_parquet("artifacts/runs/*.parquet")
    .group_by("pipeline", "perturbation")
    .agg(
        pl.col("correct").mean().alias("accuracy"),
        pl.col("cost_usd").mean().alias("mean_cost"),
        pl.col("latency_ms").quantile(0.95).alias("p95_latency_ms"),
    )
    .collect()
)
```

Use Parquet for exported analytical datasets.

SQLite remains the transactional store.

---

## NumPy and SciPy

Use NumPy for vectorized numerical analysis.

Use SciPy for:

- bootstrap confidence intervals
- permutation tests
- paired tests
- distribution analysis

Because baseline and experimental runs share scenarios, treat them as paired observations.

For paired binary outcomes, use McNemar-style analysis.

Report:

- absolute result
- effect size
- confidence interval
- cost delta
- latency delta

Do not report only p-values.

---

# Source Layout

```text
.
├── pyproject.toml
├── README.md
├── MVP.md
├── ADR.md
│
├── skills/
│   ├── docs-query/
│   │   └── SKILL.md
│   └── belief-validation/
│       └── SKILL.md
│
├── hooks/
│   ├── session_start.py
│   ├── session_end.py
│   ├── agent_stop.py
│   ├── post_tool.py
│   └── pre_completion.py
│
├── src/
│   └── belief_lab/
│       ├── __init__.py
│       │
│       ├── harness/
│       │   ├── runtime.py
│       │   ├── registry.py
│       │   ├── context.py
│       │   └── dispatch.py
│       │
│       ├── capabilities/
│       │   ├── reason_from_evidence.py
│       │   ├── reconcile_beliefs.py
│       │   ├── validate_claims.py
│       │   └── run_evaluation.py
│       │
│       ├── domain/
│       │   ├── beliefs.py
│       │   ├── observations.py
│       │   ├── provenance.py
│       │   └── transitions.py
│       │
│       ├── pipelines/
│       │   ├── baseline.py
│       │   └── belief_state.py
│       │
│       ├── hosts/
│       │   ├── base.py
│       │   ├── claude_code.py
│       │   ├── copilot_cli.py
│       │   ├── recorded.py
│       │   └── fake.py
│       │
│       ├── scenarios/
│       │   ├── generator.py
│       │   ├── perturbations.py
│       │   └── fixtures.py
│       │
│       ├── evals/
│       │   ├── datasets.py
│       │   ├── evaluators.py
│       │   ├── statistics.py
│       │   └── reports.py
│       │
│       ├── dispatch/
│       │   ├── hooks.py
│       │   ├── skills.py
│       │   ├── tasks.py
│       │   └── cli.py
│       │
│       ├── tasks/
│       │   ├── models.py
│       │   ├── scheduler.py
│       │   └── repository.py
│       │
│       ├── storage/
│       │   ├── database.py
│       │   ├── models.py
│       │   └── repositories.py
│       │
│       └── telemetry/
│           ├── tracing.py
│           └── usage.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── capabilities/
│   ├── dispatch/
│   ├── regression/
│   └── evals/
│
├── evals/
│   ├── datasets/
│   ├── scenarios/
│   └── expected/
│
└── artifacts/
    ├── runs/
    ├── reports/
    └── traces/
```

---

# Module Responsibilities

## `harness`

Stable runtime contract.

Owns:

- capability registry
- dispatch
- execution context
- common runtime lifecycle

Must not contain use-case-specific behavior.

## `capabilities`

Use-case-level operations.

Capabilities may compose pipelines, host-agent adapters, domain logic, persistence, retrieval, tasks, or evaluation.

## `domain`

Pure belief-state domain logic.

Must not depend on:

- Claude Code
- Copilot CLI
- Phoenix
- CLI
- hooks
- task scheduling adapters

## `pipelines`

Executable reasoning architectures used by capabilities and evals.

Pipelines use ordinary Python composition for the MVP.

## `hosts`

Thin adapters for Claude Code, Copilot CLI, recorded executions, and test doubles.

Host adapters own process/invocation details only. They do not own belief-state semantics or capability policy.

## `dispatch`

Adapters for:

- lifecycle/event hooks
- skills
- scheduled-task delivery
- CLI

Must stay thin.

## `scenarios`

Synthetic test-world generation.

## `evals`

Evaluation and statistics.

## `storage`

Persistence.

## `telemetry`

Tracing, usage, cost, and latency.

---

# Testing Strategy

Separate software tests from probabilistic evals.

## Unit Tests

No live models.

Test:

- registry behavior
- execution context
- deterministic reconciliation
- provenance graph logic
- state transitions
- hook dispatch
- lifecycle-hook dispatch
- task scheduling adapters
- serialization
- persistence
- statistics
- cost calculations

## Property-Based Tests

Use Hypothesis.

Important invariants:

- deterministic source ordering should not depend on input order,
- irrelevant evidence must not mutate deterministic state,
- superseded evidence invalidates dependent beliefs,
- provenance references always resolve,
- `UNKNOWN` cannot carry a committed value,
- dispatch mechanism does not change capability semantics.

Example:

```python
@given(st.permutations(["a", "b", "c"]))
def test_reconciliation_is_order_independent(order):
    ...
```

## Capability Contract Tests

Every capability should have:

```text
input
expected structured output
expected side effects
expected trace shape
```

Run the same capability through different dispatchers when possible.

Example:

```text
CLI dispatch
hook dispatch
schedule dispatch
```

should produce semantically equivalent capability execution.

## Hook Tests

Test only dispatch behavior and failure handling.

Examples:

- event maps to expected capability,
- context trigger is correct,
- malformed event is rejected,
- harness failure is surfaced safely.

Do not test belief logic through the hook module.

## Skill Tests

Validate:

- required metadata
- referenced capability exists
- input schema matches
- expected behavior is current
- examples remain valid

Later, agent evals can test whether a model correctly selects the skill.

## Lifecycle Hook and Task Scheduling Tests

Use controlled clocks and fake scheduler adapters.

Verify:

- `sessionStart` restores state and dispatches due work,
- `agentStop` creates the expected deferred tasks,
- `sessionEnd` checkpoints state and schedules expected follow-up work,
- task payloads preserve correlation IDs,
- scheduled task delivery dispatches the correct capability,
- duplicate scheduling protections work where required,
- malformed task specifications fail deterministically,
- no test requires a resident daemon or sleeping for wall-clock time.

## Regression Tests

Every important model/system failure becomes a named regression scenario.

Examples:

```text
stale-codeowners-001
false-premise-004
missing-evidence-012
contradiction-authority-018
```

---

# Evaluation Strategy

## Fixed Evidence First

Retrieval is excluded initially.

Both pipelines receive identical evidence and should execute through the same host agent and selected model where controllable.

This isolates:

```text
reasoning/state architecture
```

from:

```text
retrieval quality
```

## Stage-Level Evaluation

### Observation Extraction

Metrics:

- precision
- recall
- unsupported observation rate

### State Reconciliation

Metrics:

- state accuracy
- contradiction detection
- supersession accuracy
- unknown accuracy

### Reasoning

Metrics:

- derived-belief accuracy
- unsupported inference rate

### Rendering

Metric:

- final structured-answer accuracy

### End-to-End

Metrics:

- answer accuracy
- cost
- latency
- model calls

---

# Counterfactual Evaluation

Counterfactuals are mandatory.

Example:

```text
Evidence A:
Alice owns service X.

Expected:
Alice
```

Change one fact:

```text
Evidence B:
Bob owns service X.

Expected:
Bob
```

Remove it:

```text
No ownership evidence.

Expected:
UNKNOWN
```

This tests causal dependence on evidence.

---

# Statistical Analysis

Runs are paired by scenario and variant.

Report:

- baseline result
- experimental result
- paired delta
- 95% confidence interval
- perturbation-specific effect
- cost difference
- latency difference

For binary paired results, use an appropriate paired categorical test such as McNemar's test.

For continuous paired differences, use bootstrap confidence intervals and/or permutation tests.

Avoid pseudo-replication: many variants generated from one base scenario should not automatically be treated as independent experimental units.

---

# Experiment Reproducibility

Persist:

```text
run_id
experiment_id
capability
pipeline
scenario_id
variant_id
random_seed
trigger
host agent
selected model where exposed
host/model configuration
skill hash
hook revision
task trigger/schedule definition
evidence hash
prompt/program hash
code commit
start time
end time
input tokens
output tokens
estimated cost
result
metrics
```

Replay:

```bash
belief-lab replay <run-id>
```

Replay recreates configuration and inputs. It cannot guarantee byte-identical provider output.

---

# RAG Phase

Retrieval becomes another capability inside the harness.

Use:

```toml
"qdrant-client[fastembed]"
"sentence-transformers"
"ragas"
```

Initial design:

```text
query
  |
  +--> dense retrieval ------+
  |                          |
  +--> sparse retrieval -----+
                             |
                             v
                           fusion
                             |
                             v
                          reranker
                             |
                             v
                           evidence
                             |
                             v
                     belief capability
```

This keeps retrieval separate from belief reasoning.

---

# Dependency Shape

```toml
dependencies = [
    "pydantic>=2",
    "pydantic-evals",
    "anyio",
    "arize-phoenix",
    "openinference-instrumentation",
    "sqlalchemy",
    "numpy",
    "scipy",
    "polars",
    "pyarrow",
    "typer",
    "rich",
]

[project.optional-dependencies]
rag = [
    "qdrant-client[fastembed]",
    "sentence-transformers",
    "ragas",
]

dev = [
    "pytest",
    "pytest-asyncio",
    "hypothesis",
    "ruff",
    "ty",
]
```

Pin resolved versions through the lockfile.

`pydantic-ai`, `langgraph`, and `dspy` are intentionally absent from the MVP dependency set.

# Explicit Non-Decisions

The MVP does not adopt:

- FastAPI
- Redis
- Celery
- Dramatiq
- Kubernetes
- distributed queues
- remote Qdrant
- Pydantic AI
- LangGraph for the MVP
- DSPy for the MVP
- LangChain as the top-level architecture
- LlamaIndex as the top-level architecture
- Pandas
- MLflow

These may be added only when a concrete capability requires them.

---

# Consequences

## Positive

- The harness remains independent of any one delivery mechanism.
- Hooks remain simple event dispatchers.
- Skills remain declarative consumption contracts.
- Scheduled workflows can reuse the same capabilities.
- Future APIs and webhooks can be added without redesigning core logic.
- Evaluation is first-class rather than bolted on.
- The harness does not duplicate the agent/model runtime already provided by Claude Code or Copilot CLI.
- AI-specific framework usage is limited to evaluation and later retrieval where it adds concrete value.
- Deterministic and probabilistic logic remain separated.
- RAG can be introduced without redefining the system.

## Negative

- The generic capability/runtime boundary adds initial structure.
- Claude Code and Copilot CLI expose different process, hook, and session semantics, so host adapters must remain intentionally narrow.
- Lifecycle-driven scheduling requires explicit task persistence and host-adapter semantics.
- More model calls may make the experimental architecture slower and more expensive.
- The belief-state hypothesis may fail despite the harness architecture being sound.

That final possibility is intentional.

The harness should survive the failure of any individual AI hypothesis and make the next hypothesis easier to test.
