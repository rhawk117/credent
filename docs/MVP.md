# MVP: AI Harness for Explicit Belief-State Reasoning

## Status

Proposed

## Summary

This project is an **AI execution and evaluation harness** for experimenting with more reliable ways to use existing large language models.

The first research target is an explicit belief-state architecture for **local coding agents such as Claude Code and GitHub Copilot CLI**. Instead of asking the host agent to reconstruct observations, assumptions, contradictions, uncertainty, provenance, and current truth from an unstructured conversation history, the harness externalizes those concepts into durable structured state and evaluates whether doing so improves reliability.

The harness is the core system.

It exposes reusable **capabilities** such as:

- reason over evidence
- reconcile conflicting claims
- answer from team documentation
- validate a proposed conclusion
- inspect provenance
- run an evaluation
- execute a scheduled AI-assisted workflow
- eventually perform retrieval or RAG-backed workflows

Those capabilities can be invoked through multiple delivery and dispatch mechanisms:

- lifecycle hooks such as `sessionStart`, `sessionEnd`, and `agentStop`
- tool/action hooks
- skills
- scheduled tasks created by lifecycle hooks
- CLI commands
- future webhooks
- future API endpoints
- future event-bus consumers

Hooks and skills are therefore **not the architecture itself**. They are consumption mechanisms.

The MVP should preserve this separation from the beginning.

---

## Core Architectural Model

```text
┌─────────────────────────────────────────────────────────────┐
│ Delivery / Dispatch                                         │
│                                                             │
│ hooks | skills | scheduled tasks | CLI | future API/webhooks│
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Capabilities / Workflows                                    │
│                                                             │
│ reason-from-evidence                                        │
│ reconcile-beliefs                                           │
│ validate-claims                                             │
│ docs-query                                                  │
│ run-evaluation                                              │
│ future: jira-triage, reindex-docs, incident-assist          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Harness Runtime                                             │
│                                                             │
│ belief state | evidence | tasks | evaluation                │
│ persistence | tracing | retrieval | cost/latency tracking   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure                                              │
│                                                             │
│ SQLite | model providers | local models | future vector DB  │
└─────────────────────────────────────────────────────────────┘
```

The central rule is:

> Dispatchers know **when** something should happen. Capabilities know **what** should happen. The harness knows **how AI work executes**.

---

## Problem

Current LLM applications often put fundamentally different kinds of information into the same token stream:

- observations
- retrieved facts
- assumptions
- inferred conclusions
- stale facts
- contradictions
- uncertainty
- tool output
- conversation history
- final natural-language output

The model must repeatedly reconstruct effective state from this unstructured context.

That contributes to recurring failure modes such as:

- hallucination
- stale-information preference
- contradiction blindness
- false-premise acceptance
- weak abstention
- context drift
- provenance errors
- unsupported confidence
- long-horizon state inconsistency
- treating inference as observation
- citing evidence that did not actually drive the conclusion

RAG improves access to evidence but does not solve these problems by itself.

A model may retrieve the correct source and still:

- ignore it,
- over-weight stale information,
- combine incompatible claims,
- invent missing information,
- fail to distinguish evidence from assumption,
- or produce a conclusion whose citation is merely decorative.

---

## Research Hypothesis

The first hypothesis tested by the harness is:

> Explicit epistemic state improves the reliability of existing LLM systems by separating observations, beliefs, assumptions, contradictions, uncertainty, provenance, and state transitions from natural-language generation.

### Conventional Approach

```text
evidence
   |
   v
prompt/context
   |
   v
  LLM
   |
   v
answer
```

### Experimental Approach

```text
evidence
   |
   v
observation extraction
   |
   v
typed belief state
   |
   v
reconciliation / state transition
   |
   v
reasoning over current state
   |
   v
answer rendering
```

The baseline and experimental paths should run through the same host agent and model configuration wherever possible.

For example, compare the same Copilot CLI model or the same Claude Code model with and without harness-managed belief state.

The point is to measure the architecture, not compare unrelated providers or agent runtimes.

---

## What the Harness Is Trying to Determine

The initial research program asks:

1. Does explicit state reduce stale-information failures?
2. Does it improve contradiction detection?
3. Does it improve abstention when evidence is missing?
4. Does it improve resistance to false premises?
5. Does it preserve state better across long interactions?
6. Do conclusions change when supporting evidence changes?
7. Does provenance reflect actual support rather than post-hoc citation?
8. Can model reasoning be decomposed into observable failure stages?
9. Are improvements large enough to justify increased cost and complexity?
10. Do gains survive across multiple model families?

---

## The Harness as a General Runtime

The belief-state experiment is the first workload, not the permanent limit of the system.

Claude Code and Copilot CLI remain the **model execution and agent reasoning environments**. The harness does not wrap them with another agent framework and does not require direct OpenAI or Anthropic API access for the MVP.

A capability may look conceptually like:

```python
class Harness:
    async def run(
        self,
        capability: str,
        input: object,
        context: "ExecutionContext",
    ) -> object:
        ...
```

Examples:

```text
harness.run("reason-from-evidence", ...)
harness.run("validate-claims", ...)
harness.run("docs-query", ...)
harness.run("run-evaluation", ...)
```

Later:

```text
harness.run("jira-triage", ...)
harness.run("reindex-docs", ...)
harness.run("incident-assist", ...)
```

This lets delivery mechanisms evolve without changing the core runtime.

---

## Delivery and Dispatch

### Hooks

Hooks are **event dispatchers and lifecycle task schedulers**.

They translate agent lifecycle or tool events into immediate harness invocations and/or durable scheduled tasks. The harness does not run a resident scheduler daemon.

The primary lifecycle hooks are:

#### `sessionStart`

Use `sessionStart` to prepare a new working session.

Typical responsibilities:

- restore relevant persisted state,
- inspect or dispatch tasks that are due on session start,
- refresh invalidated local state,
- establish correlation and tracing context,
- make prior scheduled work visible to the agent.

```text
sessionStart
    |
    +--> restore session/harness state
    +--> dispatch due session-start capability
    +--> expose pending scheduled work
```

#### `agentStop`

Use `agentStop` as the post-agent execution checkpoint.

Typical responsibilities:

- capture the agent's final execution state,
- persist observations and outputs,
- schedule expensive or deferred follow-up work,
- schedule evals, reports, refreshes, or validation tasks,
- avoid blocking the just-completed agent run on non-critical work.

```text
agentStop
    |
    +--> persist outcome
    +--> schedule "evaluate-run"
    +--> schedule "refresh-derived-state"
```

#### `sessionEnd`

Use `sessionEnd` for session-level finalization.

Typical responsibilities:

- persist final session state,
- close tracing/correlation metadata,
- schedule follow-up work that should happen after the session,
- checkpoint unresolved tasks and contradictions,
- record enough information for a later `sessionStart` to resume intelligently.

```text
sessionEnd
    |
    +--> checkpoint session
    +--> schedule deferred capability
    +--> persist pending task metadata
```

Other hooks can dispatch immediate capabilities:

```text
post-tool event
    |
    v
dispatch "observe-tool-result"
```

```text
pre-completion event
    |
    v
dispatch "validate-claims"
```

Hooks should be:

- thin,
- deterministic where possible,
- easy to test,
- unaware of model-provider details,
- unaware of internal workflow implementation.

A hook should not contain the business logic of the capability it invokes or schedules.

### Skills

Skills are the **agent-facing consumption layer**.

A skill explains:

- when a capability should be used,
- what inputs are required,
- how the result should be interpreted,
- how the agent should react to `UNKNOWN`,
- how contradictions should be surfaced,
- when additional evidence should be gathered.

Skills describe how to consume the harness; they do not implement the harness.

### Scheduled Tasks

Scheduled tasks are durable descriptions of future capability invocations.

The harness does **not** own a long-running scheduler daemon. Lifecycle hooks such as `agentStop` and `sessionEnd` create tasks through a scheduler abstraction exposed by the host environment or task delivery layer.

Conceptually:

```text
agentStop
   |
   v
schedule task
   |
   +--> capability = "evaluate-run"
   +--> run_at = ...
   +--> input = ...
```

and:

```text
sessionEnd
   |
   v
schedule task
   |
   +--> capability = "docs-drift-evaluation"
   +--> trigger = next-session / host schedule / explicit time
```

A scheduled task is data:

```text
task_id
capability
input
created_by
run_at / trigger
correlation_id
status
```

The execution host determines when the task is delivered back to the harness.

If the host cannot execute wall-clock tasks while no session exists, `sessionStart` can opportunistically reconcile and dispatch tasks that became due since the previous session.

Capability logic must remain unaware of whether it was invoked immediately by a hook, later by a scheduled task, manually through the CLI, or eventually through an API.

### CLI

The CLI is the developer/operator surface.

It should support:

- invoking capabilities directly,
- generating scenarios,
- running experiments,
- comparing pipelines,
- inspecting belief state,
- replaying runs,
- validating hooks,
- validating skills,
- debugging workflows.

Example:

```bash
belief-lab run reason-from-evidence
belief-lab eval baseline belief-state
belief-lab inspect <run-id>
belief-lab replay <run-id>
belief-lab hook test post-tool
belief-lab skill validate
```

---

## Core Belief-State Concepts

### Observation

An observation is a claim directly extracted from supplied evidence.

Example:

```text
CODEOWNERS states that payments-team owns payments-api.
```

### Belief

A belief represents the harness's current position on a proposition.

Initial states:

- `OBSERVED`
- `RETRIEVED`
- `INFERRED`
- `ASSUMED`
- `CONTRADICTED`
- `UNKNOWN`

A belief can retain:

- confidence
- supporting evidence
- contradicting evidence
- source authority
- temporal validity
- derivation lineage

### State Transition

New evidence modifies current state.

Examples:

- authoritative new evidence supersedes stale evidence,
- contradiction produces an unresolved state,
- removing required evidence produces `UNKNOWN`,
- a derived belief is invalidated when a dependency changes.

### Provenance

Every material conclusion should be able to answer:

> Why does the system believe this?

Provenance should describe evidence and derivation, not simply attach a citation string after answer generation.

---

## MVP Scope

### In Scope

- general harness runtime
- capability registry and dispatch
- baseline reasoning pipeline
- explicit belief-state pipeline
- skills as an agent delivery mechanism
- hooks as event dispatchers
- scheduled capability execution
- CLI invocation
- structured model outputs
- synthetic scenario generation
- deterministic ground truth
- controlled perturbations
- host-agent abstraction for Claude Code and Copilot CLI
- experiment persistence
- tracing and observability
- deterministic evals
- statistical evals
- cost and latency measurement
- replay and failure inspection

### Deferred

- production web service
- production authentication
- multi-tenancy
- Kubernetes
- distributed execution
- Redis
- message brokers
- production Jira integration
- production GitHub webhook service
- direct model-provider API integration
- custom model training
- fine-tuning
- reinforcement learning
- full autonomous-agent runtime

### RAG

RAG is a planned harness capability, but retrieval should not contaminate the initial belief-state experiment.

The first experiments use identical fixed evidence for baseline and experimental pipelines.

Retrieval is introduced later as its own variable.

---

## Experimental Design

### Baseline Pipeline

```text
evidence
   |
   v
prompt construction
   |
   v
LLM
   |
   v
structured answer
```

### Belief-State Pipeline

```text
evidence
   |
   v
extract observations
   |
   v
reconcile state
   |
   v
current beliefs
   |
   v
reason
   |
   v
render answer
```

Both paths should receive:

- the same question,
- the same evidence,
- the same host agent,
- the same selected model where controllable,
- equivalent inference settings where controllable,
- equivalent output requirements.

---

## Scenario Model

The initial synthetic world should resemble SRE/backend work.

Useful entities:

- teams
- services
- repositories
- deployments
- environments
- dependencies
- incidents
- runbooks
- ownership records
- configuration revisions
- source-control revisions
- policies

Example:

```text
t0: platform-team owns payments-api
t1: ownership transfers to payments-team
t2: old README still names platform-team
t3: current CODEOWNERS names payments-team
t4: Jira comment incorrectly references platform-team
```

The harness owns deterministic ground truth.

---

## Controlled Perturbations

Each scenario should produce variants such as:

- clean evidence
- stale evidence
- contradictory evidence
- missing evidence
- duplicated evidence
- reordered evidence
- false premise
- irrelevant distractors
- semantically similar distractors
- conflicting authority
- changed source revision
- long unrelated history

Example:

```text
Control:
CODEOWNERS = payments-team

Counterfactual:
CODEOWNERS = platform-team

Missing:
ownership evidence removed
```

Expected:

```text
Control        -> payments-team
Counterfactual -> platform-team
Missing        -> UNKNOWN
```

---

## Evaluation Metrics

### Answer Accuracy

Does final output match ground truth?

### State Accuracy

Does the belief state match ground truth before rendering?

### Contradiction Detection

Does the system recognize incompatible evidence?

### Stale-Evidence Resistance

Does newer or more authoritative information supersede stale evidence?

### Abstention Accuracy

Does the system produce `UNKNOWN` when evidence is insufficient?

### False-Premise Rejection

Does the system challenge an unsupported premise?

### Provenance Accuracy

Does the stated evidence actually support the belief?

### Counterfactual Sensitivity

Does changing supporting evidence correctly change the conclusion?

### Distractor Robustness

Does irrelevant context leave the result stable?

### Cost

Track:

- input tokens
- output tokens
- number of model calls
- estimated provider cost

### Latency

Track:

- total latency
- per-stage latency
- p50
- p95

---

## Evaluation Progression

### Phase 1: Fixed Evidence

No retrieval.

Goal:

> Test state architecture in isolation.

### Phase 2: Context Stress

Introduce:

- contradictions
- stale facts
- false premises
- repeated evidence
- large distractor sets
- long histories

Goal:

> Determine whether explicit state degrades more slowly.

### Phase 3: Real Local Agent Integration

Exercise the same capability through Claude Code and GitHub Copilot CLI using:

- hooks,
- skills,
- CLI commands,
- scheduled tasks created from lifecycle hooks.

Goal:

> Verify that the harness improves real local-agent behavior without becoming another agent runtime.

### Phase 4: RAG

Introduce retrieval as a separate harness capability.

Evaluate:

- dense retrieval
- sparse retrieval
- hybrid retrieval
- reranking

Goal:

> Separate retrieval failures from state/reasoning failures.

### Phase 5: Real MkDocs Repository

Apply the system to the team's real documentation repository.

Goal:

> Determine whether synthetic findings generalize to operational documentation.

### Phase 6: Operational Workflows

Add capabilities such as:

- Jira triage
- documentation drift analysis
- incident context gathering
- policy validation
- recurring team checks

These remain consumers of the same harness runtime.

---

## Success Criteria

The belief-state hypothesis is promising if the experimental pipeline produces statistically credible improvements in difficult failure categories without unacceptable cost or latency increases.

Meaningful gains include:

- fewer stale-information failures,
- better contradiction handling,
- stronger abstention,
- better false-premise rejection,
- stronger counterfactual behavior,
- more stable long-context reasoning,
- more accurate provenance.

Universal improvement is not required.

A valid result might be:

> Explicit belief state reduces stale-evidence failures from 18% to 7%, improves false-premise rejection by 19 percentage points, does not improve clean single-hop QA, and increases inference cost by 32%.

---

## Falsification Criteria

The hypothesis is weakened if:

- gains disappear across model families,
- gains are explained entirely by extra inference budget,
- a well-optimized baseline matches the belief-state system,
- reconciliation creates more errors than it prevents,
- provenance appears correct but conclusions do not respond to evidence changes,
- improvements are statistically indistinguishable from noise.

The harness itself is successful even if the belief-state hypothesis fails, provided it can measure that failure rigorously and support the next hypothesis.

---

## MVP Deliverable

The MVP is complete when:

1. the harness exposes a generic capability execution interface,
2. baseline and belief-state capabilities run against the same scenarios,
3. hooks can dispatch capabilities from lifecycle events,
4. skills can instruct agents to consume those capabilities,
5. lifecycle hooks can create scheduled tasks that later dispatch the same capabilities without a resident harness daemon,
6. the CLI can invoke, inspect, replay, and evaluate them,
7. all runs are persisted and traceable,
8. deterministic and statistical evals are reproducible,
9. quality, cost, and latency can be compared,
10. failures can be inspected by stage.

The primary artifact is an **AI systems harness**, not a chatbot, hook collection, skill collection, or RAG service.

Hooks, skills, schedules, and future APIs are simply ways to consume it.
