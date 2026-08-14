# Phase 1 Walking Skeleton — Implementation Plan

> **For agentic workers:** execute this plan through the project loop (`.claude/skills/loop/`, roster and per-task cycle in /CLAUDE.md) — one **engineer** per task, **plan-critic**-gated, **git-publisher** per PR. This plan supplements `docs/.agent-backlog/phase-01/{objectives,context,tasks}.md`; the pack defines scope, this plan pins interfaces and sequencing. Where this plan and the pack disagree, the pack wins — report the disagreement instead of guessing.

**Goal:** one capability runs end-to-end (CLI → harness → capability → both pipelines → FakeHost → deterministic reconciliation → SQLite → inspect) with `./check.sh` green and the three exit-criteria commands from objectives.md producing recorded output.

**Architecture:** four layers, dependencies downward only (dispatch → capabilities → harness → infrastructure); `domain/` pure. Capabilities get their dependencies (host, repositories) by constructor injection at registration; the harness owns run lifecycle and validates capability input at the boundary; tracing rides an OTel-style ContextVar.

**Tech stack:** Python 3.14.6 via uv, Pydantic v2, SQLAlchemy 2 (sync engine, SQLite), Typer + Rich, anyio, pytest + pytest-asyncio + Hypothesis. No LangGraph/DSPy/Pydantic AI/FastAPI/Redis/Celery/Pandas/MLflow (ADR Explicit Non-Decisions).

## Global constraints

Every task inherits these; they come from the pack, CLAUDE.md, and verified repo state:

- uv only; `./check.sh` (ruff check, ruff format --check, ty check, pytest) green before any completion claim; `./format.sh` before committing.
- Ruff is strict (90-col, single quotes, `INP` selected with empty per-file-ignores → every test package needs `__init__.py`; `S101` globally ignored → bare `assert` in tests is fine). ty runs `error-on-warning`.
- House style: **python-style** skill idioms — PEP 695 generics (`class Capability[InputT, OutputT](Protocol)`), free functions over `@staticmethod`, `datetime.now(UTC)` (ruff `DTZ`).
- `domain/` imports nothing host-specific: no hosts, storage, CLI, telemetry, Phoenix.
- No live models anywhere in `tests/`. Structured host output is Pydantic-validated before any state mutation.
- DB path: `CREDENT_DB` env var, default `artifacts/credent.sqlite` (`artifacts/` is gitignored — verified). No migration tooling; delete stale local DBs on schema change.
- Branches `feat/p01-<slug>` off `develop`; commits `kind(scope): summary` through pre-commit (installed — verified); squash-merge to `develop` on green CI; evidence (actual command output) recorded in tasks.md per task.
- `[project.scripts]` currently `credent = "credent:main"` (stub prints "Hello from credent!"); it keeps working until T9 repoints it.

## Decisions pinned by this plan

Each was open after the pack; alternatives considered are recorded so they stay closed.

1. **`A002` added to the ruff ignore list (in T3).** The ADR-pinned signature `execute(self, input, context)` shadows the `input` builtin, and ruff's `A` family is selected — `A002` fires on the protocol and every implementation. Alternatives: renaming the parameter (rejected: ADR wins for signatures, per context.md), per-file-ignores (rejected: the signature recurs in harness, capabilities, and pipelines — a growing exception list is churn without safety).
2. **Belief pipeline stages: `extract` (host call) → `reconcile` (deterministic) → `reason` (host call) → `render` (deterministic shaping).** Reconciles the pack's four stage names with the ADR's two host calls (`extract_with_host`, `render_with_host` + `validate`, ADR L717-724): `reason` is the second host call (answer from reconciled beliefs), `render` is deterministic validation/shaping of the final result. Alternative — `reason` deterministic and `render` the host call — rejected: it inverts the ADR's semantics (the host does the semantic reasoning; ADR L524-536).
3. **Supersession is a relation, not a status: `Belief.superseded_by_belief_id: str | None`.** The pack pins exactly six BeliefStatus values and none is SUPERSEDED. The losing belief keeps its status and value (lineage preserved, per pack reconciliation semantics) and points at its successor. Alternatives: a SUPERSEDED status (rejected: contradicts the pinned enum), a separate supersessions table (rejected: one nullable FK covers Phase 1; YAGNI).
4. **Source authority: `Source.authority: int`, higher wins.** Deterministic supersession needs an authority order; the MVP timeline (t2 old README vs t3 CODEOWNERS) is recency, but free-text timestamps don't reconcile deterministically. An integer rank on `Source` (fixture: CODEOWNERS=2, README=1) is the minimal mechanism; `revision` is carried as opaque lineage. Equal authority + incompatible values → CONTRADICTED (pack semantics). Alternative — parse timestamps (rejected: invents data the fixture doesn't have).
5. **Deterministic belief ids: content hash over identity, not state.** `belief_id = sha256(subject | predicate | sorted(supporting_observation_ids) | sorted(derived_from_belief_ids))[:16]`. Required by the order-independence Hypothesis invariant — random UUIDs make permuted inputs produce unequal results. `value` and `status` are deliberately **excluded** from the hash: invalidation (reconcile rule 6) rewrites both to UNKNOWN/None, and an id that hashed the value would change under invalidation, dangling every `superseded_by_belief_id`/`derived_from_belief_ids` reference and breaking the provenance-resolution invariant (adversarial-review finding). Observation/run/span ids stay `uuid4().hex` (`new_id()` in `harness/context.py`; ADR's CLI example calls `new_id()`).
6. **Run graph: one parent run per `harness.run`, one child run per pipeline.** `reason-from-evidence` executes both pipelines; each becomes a child run (`parent_run_id` set, `pipeline` column `'baseline'`/`'belief_state'`), belief-graph rows hang off the belief child. Satisfies "persists runs" (plural) in exit criterion 2 and gives Phase 2's compare per-pipeline runs for free. Alternatives: one run with a pipeline tag on every row (rejected: pollutes every table), capability-managed sibling runs without a parent (rejected: harness owns run lifecycle; ExecutionContext already carries `parent_run_id`).
7. **Spans persist to a `spans` table added in T8.** Neither the pack's nine-table list (which scopes T4 only) nor the ADR's suggested tables include spans; local persistence "with the run" needs a home. Row shape mirrors OTel `ReadableSpan` (verified against installed opentelemetry-sdk 1.44.0: name, ids, parent, start/end, status, attributes; OpenInference adds span-kind via the `openinference.span.kind` attribute — semconv 0.1.32), so Phase 3 export is a mapping, not a rework. Alternative — spans as JSON on the run row (rejected: not queryable per stage, exit criterion 3 renders them).
8. **Tracing via ContextVar** (`telemetry/tracing.py`): the Capability protocol's two-argument `execute` leaves no clean parameter for a tracer; smuggling it through `ExecutionContext.metadata` hides a contract in a dict. A module-level `ContextVar[Tracer | None]` set by `Harness.run` is the OTel-standard ambient pattern. This is a deliberate, documented exception to explicit-data-flow preferences.
9. **Input coercion at the harness boundary.** Registry entries carry `input_model: type[BaseModel]`; `Harness.run` validates/coerces `input` through it before `execute`. Dict-from-JSON (CLI) and typed models (tests) both arrive as validated models. Alternative — each capability validates internally (rejected: N copies of boundary logic).
10. **Sync SQLAlchemy called from async code.** aiosqlite is not a dependency and won't be added (minimal scope); local SQLite writes are sub-millisecond. Repositories are sync; capabilities call them directly.
11. **Shared pipeline models live in `pipelines/models.py`** (`QueryRequest`, `PipelineOutcome`, and — per decision 16 — the boundary payloads). The ADR layout lists only `baseline.py`/`belief_state.py`, but both need the same request/outcome types; defining them in one pipeline and importing into the other creates a false dependency. Precedent: decision log #5 added a file the ADR layout omitted.
12. **T8 → T9 sequenced, not parallel.** tasks.md marks T9 as depending only on T7, but T9's `inspect` renders spans, which exist only after T8. Running them in parallel would have T9 code against an unmerged interface.
13. **CLI default input exists only for `reason-from-evidence`** (the stale-owner fixture, per exit criterion 2). `run reconcile-beliefs` / other capabilities without `--input` exit with a clear error naming the flag. Alternative — fixture defaults for every capability (rejected: exit criteria don't need it; YAGNI).
14. **`__version__` from `importlib.metadata.version("credent")`** — single source of truth in pyproject; the T1 smoke test asserts it.
15. **Composition root: `src/credent/dispatch/bootstrap.py` (created in T7).** Wiring capabilities inside `harness/dispatch.py` would make the harness import `capabilities/` — an upward edge that violates the downward-only gate, and the ADR bars use-case-specific behavior in the harness (adversarial-review finding). `build_default_harness` therefore lives in the delivery layer; `harness/dispatch.py` keeps only generic plumbing (the `dispatch()` helper). File addition beyond the pack's `dispatch/` list follows the decision-log #5 precedent. Alternatives: wiring inline in `cli.py` (rejected: Phase 2/3 dispatchers need the same root and the CLI must stay thin); wiring only in test fixtures (rejected: exit criteria must run through real wiring).
16. **Boundary payload models live in `pipelines/models.py`, created in T5.** `HostObservation`/`HostExtractionPayload`/`HostAnswerPayload` are belief-state vocabulary, and CLAUDE.md bars `hosts/` from owning belief-state semantics (adversarial-review finding). T5 still owns the pack's boundary-validation deliverable — the models just live one layer up, where the pipelines that validate them sit; `FakeHost` returns plain dicts and never imports them. T6 extends the same module with `QueryRequest`/`PipelineOutcome`.
17. **Registry method is `list_capabilities()`, never `list()`.** A class-scope name `list` shadows the builtin: ty rejects the `-> list[CapabilityInfo]` annotation and PEP 649 lazy annotations make `get_type_hints` raise at runtime on Python 3.14 (verified empirically in review).

## Interface contracts

These are the seams between tasks. An engineer may refine internals, but names, fields, and signatures here are load-bearing for neighboring tasks — changing one means updating this plan and telling the primary agent.

### Domain (`src/credent/domain/`) — T2

```python
# beliefs.py
class BeliefStatus(StrEnum):
    OBSERVED = 'observed'
    RETRIEVED = 'retrieved'
    INFERRED = 'inferred'
    ASSUMED = 'assumed'
    CONTRADICTED = 'contradicted'
    UNKNOWN = 'unknown'

class Belief(BaseModel):
    id: str
    subject: str
    predicate: str
    value: str | None
    status: BeliefStatus
    confidence: float  # ge=0.0, le=1.0
    supporting_observation_ids: tuple[str, ...] = ()
    contradicting_observation_ids: tuple[str, ...] = ()
    derived_from_belief_ids: tuple[str, ...] = ()
    superseded_by_belief_id: str | None = None
    # model_validator: status == UNKNOWN requires value is None (raise ValueError)

# observations.py — leaf module (imports nothing else in domain)
class Source(BaseModel):
    id: str
    name: str
    kind: str            # e.g. 'readme', 'codeowners'
    authority: int       # higher wins; ties of incompatible values → CONTRADICTED
    revision: str | None = None

class Observation(BaseModel):
    id: str
    subject: str
    predicate: str
    value: str
    source_id: str
    source_revision: str | None = None
    confidence: float  # ge=0.0, le=1.0

class EvidenceItem(BaseModel):
    source: Source
    content: str

# provenance.py — top of the domain DAG (imports beliefs, observations, transitions)
class Lineage(BaseModel):
    by_belief: dict[str, tuple[Observation, ...]]

class BeliefGraph(BaseModel):    # the provenance-complete run aggregate; pure domain
    sources: tuple[Source, ...]
    observations: tuple[Observation, ...]
    beliefs: tuple[Belief, ...]
    transitions: tuple[StateTransition, ...]

def build_lineage(
    beliefs: Sequence[Belief], observations: Sequence[Observation]
) -> Lineage:
    ...  # raises MissingProvenanceError on any dangling observation/belief reference

class MissingProvenanceError(Exception): ...

# transitions.py
class TransitionKind(StrEnum):
    CREATED = 'created'
    SUPERSEDED = 'superseded'
    CONTRADICTED = 'contradicted'
    INVALIDATED = 'invalidated'

class StateTransition(BaseModel):
    belief_id: str
    kind: TransitionKind
    from_status: BeliefStatus | None   # None on creation
    to_status: BeliefStatus
    observation_ids: tuple[str, ...] = ()
    reason: str

class UnknownItem(BaseModel):
    subject: str
    predicate: str
    reason: str = ''

class ReconciliationResult(BaseModel):
    beliefs: tuple[Belief, ...]
    transitions: tuple[StateTransition, ...]

def reconcile(
    observations: Sequence[Observation],
    sources: Sequence[Source],
    prior_beliefs: Sequence[Belief] = (),
    declared_unknowns: Sequence[UnknownItem] = (),
) -> ReconciliationResult:
    ...
```

Intra-domain import DAG (pinned — review found the previous split circular): `beliefs.py` and `observations.py` are leaves; `transitions.py` imports both; `provenance.py` imports all three; nothing in `domain/` imports `provenance.py`.

`reconcile` algorithm (deterministic, order-independent — sort by canonical keys, never input order):

1. Group observations by `(subject, predicate)`; within a group rank by `(source.authority, source_id, value, observation.id)`.
2. Agreement on one value → one OBSERVED belief supported by all observations; `confidence = max(supporting confidences)`.
3. Conflicting values, one strictly-highest authority → winner OBSERVED; each losing value still becomes a belief (lineage kept) with `superseded_by_belief_id` = winner id; SUPERSEDED transition per loser.
4. Conflicting values tied at top authority → one belief per value, all CONTRADICTED, cross-linked via `contradicting_observation_ids`; CONTRADICTED transitions.
5. `declared_unknowns` with no matching observations → UNKNOWN belief, `value=None`, UNKNOWN-kind CREATED transition.
6. `prior_beliefs` whose `derived_from_belief_ids` or `supporting_observation_ids` reference a belief/observation that this pass superseded or contradicted → transition to UNKNOWN (`value=None`), INVALIDATED kind.

### Hosts (`src/credent/hosts/`) — T5

```python
# base.py
class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_calls: int | None = None

class AgentInvocation(BaseModel):
    id: str
    prompt: str | None = None
    payload: dict[str, object] = {}
    timeout_s: float | None = None
    correlation_id: str | None = None
    metadata: dict[str, object] = {}   # pipelines set metadata['stage']

class AgentResult(BaseModel):
    invocation_id: str
    exit_code: int
    structured_output: dict[str, object] | None = None
    raw_stdout: str = ''
    session_id: str | None = None
    run_id: str | None = None
    started_at: datetime
    ended_at: datetime
    usage: Usage | None = None

class AgentHost(Protocol):
    name: str
    async def invoke(self, request: AgentInvocation) -> AgentResult: ...

# fake.py
class FakeHost:
    name = 'fake'
    def __init__(self, responses: Mapping[str, dict[str, object]] | None = None) -> None:
        ...  # keyed by metadata['stage']: 'extract' | 'reason' | 'baseline';
             # responses are PLAIN DICTS — hosts/ never imports the payload
             # models (decision 16); defaults reproduce the stale-owner fixture;
             # records every AgentInvocation on self.invocations for test
             # assertions; unknown stage → ValueError naming the stage
```

### Boundary payloads (`src/credent/pipelines/models.py`) — created T5, extended T6

The Structured Agent Contracts (ADR L694-706), validated by pipelines before any state mutation. `hosts/` must not own belief-state vocabulary (decision 16); `UnknownItem` comes from `domain/transitions.py`.

```python
class HostObservation(BaseModel):
    subject: str
    predicate: str
    value: str
    source_id: str
    source_revision: str | None = None
    confidence: float = 1.0  # ge=0.0, le=1.0

class HostContradiction(BaseModel):
    subject: str
    predicate: str
    source_ids: tuple[str, ...] = ()

class HostExtractionPayload(BaseModel):
    observations: tuple[HostObservation, ...] = ()
    unknowns: tuple[UnknownItem, ...] = ()
    contradictions: tuple[HostContradiction, ...] = ()

class HostAnswerPayload(BaseModel):
    answer: str | None
    status: Literal['answered', 'unknown']
```

### Harness (`src/credent/harness/`) — T3

```python
# context.py
def new_id() -> str: ...        # uuid4().hex

class ExecutionContext(BaseModel):
    invocation_id: str
    trigger: str                # Phase 1: 'cli'; 'eval' reserved for Phase 2
    actor: str | None = None
    correlation_id: str | None = None
    parent_run_id: str | None = None
    metadata: dict[str, object] = {}

# registry.py
class Capability[InputT, OutputT](Protocol):
    async def execute(self, input: InputT, context: ExecutionContext) -> OutputT: ...

class CapabilityInfo(BaseModel):
    name: str
    description: str

class UnknownCapabilityError(LookupError): ...

class RegistryEntry(BaseModel):
    name: str
    capability: Capability[Any, Any]          # model_config allows arbitrary types
    description: str
    input_model: type[BaseModel]

class CapabilityRegistry:
    def register(self, name: str, capability: Capability[Any, Any],
                 description: str, input_model: type[BaseModel]) -> None: ...
    def get(self, name: str) -> RegistryEntry: ...   # raises UnknownCapabilityError
    def list_capabilities(self) -> list[CapabilityInfo]: ...   # decision 17

# runtime.py
class Harness:
    def __init__(self, registry: CapabilityRegistry) -> None: ...
        # T7 modifies this to (registry, runs: RunRepository | None = None) —
        # harness → storage is a legal downward import once T4 exists; T3 must
        # not reference storage or host symbols that land in later tasks
    async def run(self, capability: str, input: object, context: ExecutionContext) -> object:
        ...  # resolve → coerce input via entry.input_model → generate run_id =
             # new_id() → call execute with
             # context.model_copy(update={'parent_run_id': run_id}) so the
             # capability can hang child runs/graphs off the harness run.
             # T7 adds the persistence branch around execute: save invocation,
             # create run row ('running'), finish row ('succeeded'/'failed' +
             # output json). T8 adds tracer setup + span persistence.
    def list_capabilities(self) -> list[CapabilityInfo]: ...

# dispatch.py — generic plumbing ONLY; the composition root is
# credent/dispatch/bootstrap.py (decision 15, lands in T7)
async def dispatch(harness: Harness, capability: str, payload: object,
                   *, trigger: str, actor: str | None = None) -> object:
    ...  # builds ExecutionContext(invocation_id=new_id(), trigger=trigger, ...)
         # and awaits harness.run — used by the CLI in T9, hooks in Phase 3
```

T3's harness has no persistence and no storage/host imports; T3's unit tests exercise registration, lookup failure, coercion, context propagation, and the `dispatch()` helper without a database.

### Storage (`src/credent/storage/`) — T4

`database.py`: `resolve_db_path() -> Path` (reads `CREDENT_DB`, defaults `artifacts/credent.sqlite`, mkdirs parent), `create_engine_and_schema(db_path) -> Engine`, `session_factory(engine) -> sessionmaker[Session]`.

`models.py` — SQLAlchemy 2 typed ORM, `DeclarativeBase`. Columns (the ADR pins names + indexes only — L796-826; columns are pinned here):

| table | columns |
|---|---|
| `capabilities` | `name` TEXT PK, `description` TEXT |
| `invocations` | `id` PK, `trigger` (indexed), `actor` NULL, `correlation_id` NULL, `metadata_json` TEXT, `created_at` |
| `runs` | `id` PK, `capability` FK→capabilities.name (indexed), `invocation_id` FK, `parent_run_id` NULL FK→runs.id, `pipeline` TEXT NULL (`'baseline'`/`'belief_state'`), `status` (`'running'/'succeeded'/'failed'`), `input_json` TEXT, `output_json` TEXT NULL, `started_at`, `ended_at` NULL |
| `sources` | `id` PK, `run_id` FK (indexed), `name`, `kind`, `authority` INT, `revision` NULL |
| `observations` | `id` PK, `run_id` FK (indexed), `subject`, `predicate`, `value`, `source_id` FK, `source_revision` NULL, `confidence` REAL |
| `beliefs` | `id` PK, `run_id` FK (indexed), `subject`, `predicate`, `value` NULL, `status`, `confidence` REAL, `superseded_by_belief_id` NULL, `derived_from_belief_ids_json` TEXT (a JSON column, not a tenth table — the pack pins exactly nine; review found the field had no persistence home) |
| `belief_support` | (`belief_id` FK, `observation_id` FK) composite PK |
| `belief_contradictions` | (`belief_id` FK, `observation_id` FK) composite PK |
| `state_transitions` | `id` PK, `run_id` FK (indexed), `belief_id`, `kind`, `from_status` NULL, `to_status`, `observation_ids_json` TEXT, `reason`, `created_at` |

`repositories.py` — constructed with the sessionmaker; each method opens a session and commits:

```python
class RunRecord(BaseModel):      # storage-facing DTO; domain types stay pure
    id: str; capability: str; invocation_id: str
    parent_run_id: str | None = None; pipeline: str | None = None
    status: str; input_json: str; output_json: str | None = None
    started_at: datetime; ended_at: datetime | None = None

class InvocationRecord(BaseModel):   # storage must NOT import harness (upward
    id: str                          # dependency) — the harness maps
    trigger: str                     # ExecutionContext onto this DTO
    actor: str | None = None
    correlation_id: str | None = None
    metadata_json: str = '{}'
    created_at: datetime

class RunRepository:
    def register_capability(self, name: str, description: str) -> None: ...  # upsert
    def save_invocation(self, record: InvocationRecord) -> None: ...
    def create_run(self, run: RunRecord) -> None: ...
    def finish_run(self, run_id: str, status: str, output_json: str | None,
                   ended_at: datetime) -> None: ...
    def get_run(self, run_id: str) -> RunRecord | None: ...
    def children_of(self, run_id: str) -> list[RunRecord]: ...

class BeliefRepository:   # persists/loads the domain BeliefGraph (defined in T2)
    def save_graph(self, run_id: str, graph: BeliefGraph) -> None: ...  # one transaction
    def load_graph(self, run_id: str) -> BeliefGraph: ...
```

Storage maps domain models to rows and never redefines them (T2 owns all domain types).

### Pipelines (`src/credent/pipelines/`) — T6

```python
# models.py — T6 adds these to the T5-created module:
class QueryRequest(BaseModel):
    question: str
    evidence: tuple[EvidenceItem, ...]

class PipelineOutcome(BaseModel):
    answer: HostAnswerPayload
    graph: BeliefGraph | None = None    # None for baseline

# baseline.py
async def run_baseline(request: QueryRequest, host: AgentHost) -> PipelineOutcome: ...
    # one host call, metadata['stage']='baseline'; validate HostAnswerPayload

# belief_state.py
async def run_belief_state(request: QueryRequest, host: AgentHost) -> PipelineOutcome: ...
    # extract: host call, stage='extract'; HostExtractionPayload.model_validate on
    #   result.structured_output BEFORE anything else (ValidationError propagates,
    #   nothing persisted)
    # reconcile: domain.reconcile(...) on Observations built from the payload
    #   (ids from new_id(), sources from request evidence)
    # reason: host call, stage='reason', prompt from question + current beliefs;
    #   validate HostAnswerPayload
    # render: deterministic — assemble PipelineOutcome(graph=BeliefGraph(...))
```

### Capabilities (`src/credent/capabilities/`) — T7

```python
# reason_from_evidence.py
class PipelineRunSummary(BaseModel):
    run_id: str; pipeline: str; answer: str | None; status: str

class ReasonFromEvidenceOutput(BaseModel):
    results: tuple[PipelineRunSummary, ...]

class ReasonFromEvidence:
    name = 'reason-from-evidence'
    input_model = QueryRequest
    def __init__(self, host: AgentHost, runs: RunRepository,
                 beliefs: BeliefRepository) -> None: ...
    async def execute(self, input: QueryRequest,
                      context: ExecutionContext) -> ReasonFromEvidenceOutput: ...
        # per pipeline ('baseline', 'belief_state'): create child RunRecord
        # (parent_run_id = context.parent_run_id set by harness), run pipeline,
        # save belief graph for the belief child, finish child run

# reconcile_beliefs.py — deterministic, no host
class ReconcileBeliefsInput(BaseModel):
    sources: tuple[Source, ...]
    observations: tuple[Observation, ...]
    declared_unknowns: tuple[UnknownItem, ...] = ()

class ReconcileBeliefs:
    name = 'reconcile-beliefs'
    input_model = ReconcileBeliefsInput
    # persists the resulting graph under its own run; output = ReconciliationResult

# inspect_belief_state.py — read-only
class InspectInput(BaseModel):
    run_id: str

class InspectOutput(BaseModel):
    run: RunRecord
    children: tuple[RunRecord, ...]
    graph: BeliefGraph | None
    # T8 adds: spans: tuple[SpanRecord, ...] = ()  (SpanRecord does not exist at T7)
    # given a parent run id: children listed, graph loaded from the belief child,
    # spans are the parent run's; given a child/leaf id: its own graph, no spans;
    # unknown id → UnknownRunError
```

### Composition root (`src/credent/dispatch/bootstrap.py`) — T7

```python
def build_default_harness(
    host: AgentHost | None = None,          # default FakeHost()
    db_path: Path | None = None,            # default resolve_db_path()
) -> Harness: ...   # engine + schema, repositories, registers all three
                    # capabilities with descriptions; delivery layer, so its
                    # imports of capabilities/storage/hosts all point downward
```

### Telemetry (`src/credent/telemetry/tracing.py`) — T8

```python
class SpanRecord(BaseModel):
    span_id: str
    parent_span_id: str | None
    name: str                    # e.g. 'reason-from-evidence', 'extract'
    kind: str                    # 'capability' | 'pipeline' | 'pipeline_stage' | 'host_call'
    started_at: datetime
    ended_at: datetime
    status: Literal['ok', 'error']
    attributes: dict[str, object] = {}

class Tracer:
    spans: list[SpanRecord]
    @contextmanager
    def span(self, name: str, kind: str, **attributes: object) -> Iterator[None]: ...

current_tracer: ContextVar[Tracer | None]

@contextmanager
def span(name: str, kind: str, **attributes: object) -> Iterator[None]:
    ...  # no-op when current_tracer is unset — pipelines/capabilities call this
         # unconditionally; T8 threads it, earlier tasks never see it
```

Storage: T8 adds a `spans` table (`span_id` PK, `run_id` FK indexed, `parent_span_id` NULL, `name`, `kind`, `started_at`, `ended_at`, `status`, `attributes_json`) and `SpanRepository.save_spans(run_id, spans)` / `.for_run(run_id)`. Shape maps 1:1 onto OTel `ReadableSpan`; OpenInference kind lands in `attributes` at Phase 3 export time (`openinference.span.kind`: capability→AGENT, pipeline/stage→CHAIN, host_call→LLM).

### Fixture (`src/credent/scenarios/fixtures.py`) — T7

```python
GROUND_TRUTH_OWNER = 'payments-team'
SUPERSEDED_OWNER = 'platform-team'

def stale_owner_sources() -> tuple[Source, Source]:
    return (
        Source(id='src-readme', name='Old README', kind='readme',
               authority=1, revision='t2'),
        Source(id='src-codeowners', name='Current CODEOWNERS', kind='codeowners',
               authority=2, revision='t3'),
    )

def stale_owner_request() -> QueryRequest:
    readme, codeowners = stale_owner_sources()
    return QueryRequest(
        question='Who owns payments-api?',
        evidence=(
            EvidenceItem(source=readme,
                         content='Old README: platform-team owns payments-api.'),
            EvidenceItem(source=codeowners,
                         content='Current CODEOWNERS: payments-team owns payments-api.'),
        ),
    )
```

(Question, evidence strings, and expected owner are verbatim from the ADR stale-owner case, L746-763; authority ordering from decision 4.) FakeHost's default canned responses mirror this fixture: `extract` → the two observations (platform-team/src-readme, payments-team/src-codeowners), `reason`/`baseline` → `{"answer": "payments-team", "status": "answered"}`.

### CLI (`src/credent/dispatch/cli.py`) — T9

Typer app; `[project.scripts]` becomes `credent = "credent.dispatch.cli:app"`; the stub `main()` in `credent/__init__.py` is deleted in the same task. Commands (each: `build_default_harness()` from `credent.dispatch.bootstrap`, then `harness/dispatch.py`'s `dispatch(..., trigger='cli')` under `anyio.run` — `functools.partial` for the keyword-only args):

- `credent capability list` — Rich table from `harness.list_capabilities()` (no run row created).
- `credent run <capability> [--input FILE.json]` — payload from file, or the stale-owner fixture when the capability is `reason-from-evidence`; other capabilities without `--input` exit code 2 with a message naming the flag. Prints run ids + answers.
- `credent inspect <run-id>` — `harness.run('inspect-belief-state', {'run_id': ...}, ...)`, rendered with Rich: run header, children table, belief tree (status, value, superseded→successor links, per-belief provenance with source names), transitions, spans.

## Task plan

Task scope, dependency order, and verification commands are tasks.md's; branch names, files, and step granularity are pinned here. Every task: TDD (failing test → implement → green), `./format.sh`, commit through pre-commit, PR to `develop`, evidence into tasks.md.

**Parallelism map:** T1 → (T2 ∥ T3) → (T4 ∥ T5) → T6 → T7 → T8 → T9 → T10. Parallel pairs run one engineer each in isolated worktrees (see Orchestration).

### T1 — Package skeleton and tooling wiring — `feat/p01-skeleton`

**Files:** create `src/credent/{harness,domain,storage,hosts,pipelines,capabilities,dispatch,scenarios,telemetry}/__init__.py` (empty), `tests/__init__.py`, `tests/unit/__init__.py`, `tests/capabilities/__init__.py`, `tests/unit/test_package.py`; modify `pyproject.toml` (append `[tool.pytest.ini_options]`), `src/credent/__init__.py` (add `__version__`; keep `main()`).

- [ ] Write `tests/unit/test_package.py`:
  ```python
  import credent


  def test_version_exposed() -> None:
      assert credent.__version__
  ```
- [ ] Run `uv run --group test pytest` → fails (no `__version__`).
- [ ] Add to `src/credent/__init__.py`: `__version__ = importlib.metadata.version('credent')`. Create all package `__init__.py`s. Append to pyproject:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  asyncio_default_fixture_loop_scope = "function"
  testpaths = ["tests"]
  ```
- [ ] `./check.sh` → green (pytest now runs: 1 passed). Commit `chore(pkg): package skeleton, pytest wiring, version smoke test`.

Verify: `./check.sh`

### T2 — Domain models and reconciliation — `feat/p01-domain` (∥ T3)

**Files:** create `src/credent/domain/{beliefs,observations,provenance,transitions}.py`, `tests/unit/{test_belief_models,test_provenance,test_reconciliation,test_reconciliation_properties}.py`.

**Produces:** every symbol in "Domain" contracts above. **Consumes:** nothing beyond T1.

- [ ] Failing model tests first (`test_belief_models.py`): BeliefStatus members; `Belief(status=UNKNOWN, value='x')` raises; confidence bounds enforced on Belief and Observation.
- [ ] Failing reconciliation unit tests (`test_reconciliation.py`), fixture-shaped: agreement → single OBSERVED; higher authority wins with loser superseded (lineage intact, SUPERSEDED transition); equal-authority conflict → CONTRADICTED cross-links; declared unknown → UNKNOWN with `value=None`; prior derived belief invalidated → UNKNOWN + INVALIDATED transition.
- [ ] Failing provenance tests: `build_lineage` resolves; dangling ref raises `MissingProvenanceError`.
- [ ] Implement models → provenance → `reconcile` (algorithm in contracts section) until green.
- [ ] Hypothesis invariants (`test_reconciliation_properties.py`) — all five from context.md:
  ```python
  @given(st.permutations(FIXTURE_OBSERVATIONS))
  def test_reconciliation_is_order_independent(order) -> None:
      assert reconcile(order, SOURCES) == reconcile(FIXTURE_OBSERVATIONS, SOURCES)
  ```
  plus: irrelevant (subject, predicate) observations leave other groups' beliefs unchanged; superseding a belief invalidates its dependents; every referenced observation id resolves via `build_lineage`; no generated reconciliation ever yields UNKNOWN with a value.
- [ ] `./check.sh`; commit `feat(domain): belief models and deterministic reconciliation`.

Verify: `uv run --group test pytest tests/unit -q -k "domain or belief or reconcil or provenance"`

### T3 — Harness core — `feat/p01-harness` (∥ T2)

**Files:** create `src/credent/harness/{context,registry,runtime,dispatch}.py`, `tests/unit/test_harness.py`; modify `.ruff.toml` (add `"A002"` to `[lint] ignore` with comment `# Capability.execute(input=...) is an ADR-pinned signature`).

**Produces:** "Harness" contracts — persistence-free; the composition root is NOT here (decision 15). **Consumes:** nothing from T2; no storage or host imports (their symbols land in T4/T5).

- [ ] Failing tests: `new_id()` unique/hex; registry register→get roundtrip; `get('nope')` raises `UnknownCapabilityError`; `Harness.run` coerces a dict input into the entry's `input_model` and passes execute a context copy with `parent_run_id` set (spy capability records it); invalid input dict → `ValidationError`, capability never called; `dispatch()` builds a context with the given trigger and a fresh invocation id and returns `harness.run`'s result.
- [ ] Implement context → registry → runtime → the `dispatch()` helper.
- [ ] `./check.sh`; commit `feat(harness): execution context, registry, runtime`.

Verify: `uv run --group test pytest tests/unit -q -k harness`

### T4 — Storage: run-graph subset — `feat/p01-storage` (∥ T5)

**Files:** create `src/credent/storage/{database,models,repositories}.py`, `tests/unit/test_storage.py`, `tests/conftest.py` (`tmp_db` fixture: `monkeypatch.setenv('CREDENT_DB', str(tmp_path / 'test.sqlite'))`).

**Produces:** "Storage" contracts (nine tables, `RunRepository`, `BeliefRepository`, `RunRecord`, `InvocationRecord`). **Consumes:** T2 domain models (including `BeliefGraph`) — nothing from T3; storage never imports harness.

- [ ] Failing round-trip tests against a temp SQLite file: capability upsert idempotent; invocation + run create/finish/get; `children_of` returns pipeline children; `save_graph`/`load_graph` round-trips the full stale-owner-shaped graph (sources, observations, beliefs incl. `superseded_by_belief_id`, support/contradiction links, transitions, **plus one synthetic derived belief with non-empty `derived_from_belief_ids`** — review found the field would otherwise silently drop) with domain models equal after the round trip; `resolve_db_path` honors `CREDENT_DB` and defaults to `artifacts/credent.sqlite`.
- [ ] Implement database → ORM models → repositories.
- [ ] `./check.sh`; commit `feat(storage): run-graph schema and repositories`.

Verify: `uv run --group test pytest tests/unit -q -k storage`

### T5 — Host protocol and FakeHost — `feat/p01-hosts` (∥ T4)

**Files:** create `src/credent/hosts/{base,fake}.py`, `src/credent/pipelines/models.py` (boundary payloads only — decision 16), `tests/unit/test_hosts.py`.

**Produces:** "Hosts" contracts + "Boundary payloads" contracts. **Consumes:** T2 `UnknownItem` (imported by `pipelines/models.py`, never by `hosts/`).

- [ ] Failing tests: FakeHost returns default canned extraction for `stage='extract'` and that dict validates as `HostExtractionPayload`; `stage='reason'`/`'baseline'` → dicts validating as `HostAnswerPayload`; unknown stage → `ValueError`; invocations recorded; malformed payloads (missing `predicate`, `confidence=1.5`, `unknowns` of wrong type) each raise `ValidationError` — the rejection path is a first-class test, not an afterthought.
- [ ] Implement `hosts/base.py` models → `pipelines/models.py` payloads → FakeHost with `DEFAULT_RESPONSES` mirroring the fixture data (values verbatim from the Fixture contract above).
- [ ] `./check.sh`; commit `feat(hosts): agent host protocol, fake host, boundary validation`.

Verify: `uv run --group test pytest tests/unit -q -k host`

### T6 — Pipelines — `feat/p01-pipelines`

**Files:** create `src/credent/pipelines/{baseline,belief_state}.py`, `tests/unit/test_pipelines.py`; modify `src/credent/pipelines/models.py` (add `QueryRequest`, `PipelineOutcome`).

**Produces:** "Pipelines" contracts. **Consumes:** T2 `reconcile`/models, T5 hosts + payloads.

- [ ] Failing tests through FakeHost: baseline returns `answer='payments-team'`, `graph is None`; belief_state returns graph with two sources, two observations, winner belief `payments-team` OBSERVED and loser `platform-team` with `superseded_by_belief_id` set; FakeHost with a malformed `extract` response → `ValidationError` raised before any graph is built (assert via FakeHost recording only one invocation and the error propagating); an extract payload whose `source_id` matches no request source → error before any graph is built.
- [ ] Implement the `models.py` additions → `baseline.py` → `belief_state.py` (stage order per decision 2; wrap each stage in `telemetry.span(...)`? **No** — spans arrive in T8; write stages as plain awaits/calls).
- [ ] `./check.sh`; commit `feat(pipelines): baseline and belief-state composition`.

Verify: `uv run --group test pytest tests/unit -q -k pipeline`

### T7 — Capabilities, fixture, contract tests — `feat/p01-capabilities`

**Files:** create `src/credent/capabilities/{reason_from_evidence,reconcile_beliefs,inspect_belief_state}.py`, `src/credent/scenarios/fixtures.py`, `src/credent/dispatch/bootstrap.py` (composition root — decision 15), `tests/capabilities/test_capability_contracts.py`; modify `src/credent/harness/runtime.py` (add `runs: RunRepository | None = None` plus the invocation/run-row persistence branch around `execute`).

**Produces:** "Capabilities" + "Fixture" + "Composition root" contracts; harness persistence. **Consumes:** T3 harness, T4 repositories, T6 pipelines.

- [ ] Failing contract tests (each: input → expected structured output → expected persisted rows, on `tmp_db`):
  - `reason-from-evidence` via `harness.run` on the default fixture: output has two `PipelineRunSummary` entries both answering `payments-team`; DB holds one parent + two child runs; the belief child's graph has the superseded `platform-team` belief pointing at the `payments-team` winner; transitions include CREATED + SUPERSEDED.
  - `reconcile-beliefs` on fixture-shaped observations JSON: `ReconciliationResult` output; graph rows persisted under its run.
  - `inspect-belief-state` on the parent run id: children listed, graph populated; on the belief child id: same graph; on `run_id='missing'`: `UnknownRunError`.
  - Module docstring note (per tasks.md): expected-trace-shape assertions deferred to Phase 3 — dispatch equivalence needs hook/schedule dispatchers.
- [ ] Implement fixture → capabilities → wiring until green.
- [ ] `./check.sh`; commit `feat(capabilities): three capabilities, stale-owner fixture, contract tests`.

Verify: `uv run --group test pytest tests/capabilities -q`

### T8 — Minimal span capture — `feat/p01-spans`

**Files:** create `src/credent/telemetry/tracing.py`, `tests/unit/test_tracing.py`; modify `storage/models.py` + `storage/repositories.py` (spans table + `SpanRepository`), `harness/runtime.py` (create tracer, root span, persist), `pipelines/{baseline,belief_state}.py` + `capabilities/reason_from_evidence.py` (wrap stages/host calls in `span(...)`), `capabilities/inspect_belief_state.py` (populate `spans`).

**Produces:** "Telemetry" contracts + `SpanRepository`. **Consumes:** everything through T7.

- [ ] Failing tests: `Tracer.span` nests (parent ids correct) and records error status on exception; module-level `span()` is a no-op without a current tracer; after `harness.run('reason-from-evidence', ...)` on `tmp_db`, `SpanRepository.for_run(parent_id)` yields the root capability span plus pipeline/stage/host-call spans with correct parentage (`capability` → `pipeline` → `pipeline_stage` → `host_call`); span rows round-trip attributes.
- [ ] Implement tracing → schema/repository → thread `span(...)` through harness, pipelines, capability.
- [ ] `./check.sh` (note: stale local `artifacts/credent.sqlite` from earlier tasks lacks the spans table — delete it; tests use `tmp_db` and are unaffected); commit `feat(telemetry): local span capture persisted with runs`.

Verify: `uv run --group test pytest tests/unit -q -k "span or trace"`

### T9 — CLI — `feat/p01-cli`

**Files:** create `src/credent/dispatch/cli.py`, `tests/unit/test_cli.py`; modify `pyproject.toml` (`[project.scripts] credent = "credent.dispatch.cli:app"`), `src/credent/__init__.py` (delete stub `main()`; keep `__version__`).

**Produces:** the three CLI commands. **Consumes:** T7 `build_default_harness` + fixture, T8 spans in inspect output.

- [ ] Failing `typer.testing.CliRunner` tests on `tmp_db`: `capability list` names all three; `run reason-from-evidence` (no args) prints run ids and `payments-team`; `run reconcile-beliefs` without `--input` exits 2 naming the flag; `run reason-from-evidence --input <file>` honors the file; `inspect <parent-run-id>` output contains the children table, the superseded belief with its source names, and span names; `inspect <belief-child-id>` shows that child's graph; `inspect missing` exits nonzero with a clear message.
- [ ] Implement app + Rich rendering; repoint `[project.scripts]`; `uv sync` to refresh the entry point.
- [ ] `./check.sh`; commit `feat(cli): capability list, run, inspect`.

Verify: `uv run credent capability list && uv run credent run reason-from-evidence && uv run credent inspect <run-id>` (run-id from the `run` output)

### T10 — Walking-skeleton exit — `feat/p01-exit`

**Files:** create `tests/capabilities/test_exit_criteria.py`.

- [ ] End-to-end test on `tmp_db` via CliRunner: `run reason-from-evidence` then `inspect` on the belief child — asserts both pipelines answered `payments-team` from identical fixture evidence and the rendered output shows the `platform-team` belief superseded with provenance (source `Current CODEOWNERS` on the winner, `Old README` on the loser).
- [ ] Run the three exit-criteria commands from objectives.md against a fresh checkout state (delete `artifacts/credent.sqlite` first); record verbatim output in tasks.md Evidence and objectives evidence.
- [ ] `./check.sh`; commit `test(capabilities): walking-skeleton exit criteria`.

Verify: `./check.sh` plus the three exit commands from objectives.md, outputs recorded

## Orchestration

- **Loop integration:** task selection and evidence recording follow `.claude/skills/loop/`; this plan is the pinned "how" the loop's plan-critic gate has already reviewed. Engineer dispatch prompts are written with **promptlint** and must name the **python-style** skill; prompts point engineers at this file's Interface contracts section for their task plus the pack files.
- **Worktrees for parallel pairs (T2∥T3, T4∥T5):** do **not** rely on automatic worktree isolation — it bases worktrees on `main`, which is 4 commits behind `develop` (verified; main's tip is the initial scaffold). Pre-create explicitly, outside the repo tree (in-repo worktrees leak stale `.ruff.toml` copies into `ruff check .` and break `./check.sh`):
  ```bash
  git -C /home/rhawk/dev/credent worktree add -b feat/p01-domain <scratch>/wt-t2 develop
  git -C /home/rhawk/dev/credent worktree add -b feat/p01-harness <scratch>/wt-t3 develop
  ```
  Pass the absolute worktree path in the dispatch prompt. After both PRs merge: `git worktree remove <path> && git worktree prune`, then `git pull` on `develop` before the next task.
- **Publishing:** git-publisher per task — PR from the template, watch CI (`check` status), squash-merge on green (approved policy). Phase completion (`develop` → `main`, tag `phase-01`) is user-gated — never opened unprompted.
- **Sequencing note:** T8 before T9 (decision 12), overriding tasks.md's looser dependency note for T9.

## Environment state (verified 2026-08-14)

Synced and gate-green before this plan was written: `uv sync --all-groups` clean, pre-commit hook installed, `gh` authenticated as rhawk117, `./check.sh` passes, no leftover worktrees (`.claude/worktrees/` empty), `artifacts/` gitignored. Environment facts and tool versions: `docs/.agent-backlog/README.md` + phase-01 `context.md` (re-verified 2026-08-14).

## Not investigated / known risks

- Copilot CLI remains uninstalled and out of Phase 1 scope (decision log #6).
- pydantic-evals API and Phoenix export wiring: deliberately untouched (pack "Not investigated"); nothing here imports them.
- ty's treatment of PEP 695 generic Protocols with `input` shadowing has not been exercised in this repo yet; if ty rejects a pinned signature spelling, the engineer reports back rather than silently renaming (ADR wins for signatures).
- Rich rendering specifics (tree vs table for inspect) are engineer's choice; only the content assertions in T9/T10 tests are binding.
