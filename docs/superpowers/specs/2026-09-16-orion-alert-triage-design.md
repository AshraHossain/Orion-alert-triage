# ORION — Multi-Tool Orchestration for KYC/AML Alert Triage

**Project:** `15-orion-alert-triage`
**Repository:** https://github.com/AshraHossain/Orion-alert-triage (default branch `main`)
**Working copy:** `AI_Engineering_Cockpit/projects/15-orion-alert-triage/` — its own repo, nested in the cockpit folder for convenience only
**Date:** 2026-09-16
**Status:** Approved design, not yet implemented

ORION is the agent's name and is used throughout the code and documentation. The
directory is named for what the project does, following the numbered convention
of the other fourteen cockpit projects.

## Purpose

ORION is a multi-tool orchestration agent. It takes one flagged transaction
alert and produces a decision — escalate, clear, or refer to a human — together
with the reasoning behind it and an audit trail of every tool call made along
the way.

The domain is financial crime: KYC (know your customer) and AML
(anti-money-laundering) alert triage. The domain was chosen because conflicting
evidence is normal there, every action must be auditable, and data-handling
limits are real rather than decorative — which gives each of ORION's mechanisms
something genuine to do.

ORION began as project 15 of the AI Engineering Cockpit and now stands as its
own repository, keeping that project's conventions. It is distinct from the
cockpit's
`03-multi-model-orchestrator` (which compares model outputs) and
`05-hybrid-orchestrator` (which routes between local and hosted models): ORION
orchestrates **tools**, not models.

### Secondary purpose: learning

The author is building this to learn the mechanics, not only to demonstrate
them. That constraint shapes the design — mechanisms stay as small, separately
testable units rather than being folded into a framework, and the build
proceeds test-first with the author writing the implementation code.

## The four mechanisms

ORION exists to demonstrate four things. Everything in the design serves one of
them:

1. **Dynamic tool registry** — tools are entries in a list that can change while
   the system runs, not hardcoded function calls.
2. **Credibility scoring** — each tool carries a score that moves with its
   observed reliability, and that score influences outcomes.
3. **Permission scoping** — each tool declares what it may do and what data it
   may receive; calls outside that scope are refused before execution.
4. **Conflict resolution** — when tools disagree, there is an explicit,
   inspectable procedure for settling it, including the option to decline.

## Architecture

### Surface: Anthropic Tool Runner

The agent loop is driven by `client.beta.messages.tool_runner` from the
`anthropic` Python SDK. The model decides which tools to call and in what
order; the SDK runs the request → execute → loop cycle.

ORION's mechanisms wrap each tool before it is handed to the runner. Every
registered tool is passed to the runner as a **guarded tool**: a function that,
on each call,

1. checks the call against the tool's permission scope and refuses it before
   the real tool runs,
2. runs the tool and times it,
3. records success or failure with the credibility tracker and the audit trail,
4. returns the result as a JSON string, or raises so the runner reports an error.

**Verified against `anthropic` 1.6.0.** The Python Tool Runner exposes no
before- or after-call hook. It iterates over the turn's `tool_use` blocks and
calls each tool's `call(input)` itself, converting any exception into a
`tool_result` with `is_error: true` (an `anthropic.lib.tools.ToolError` sets the
content the model sees). Wrapping the function is therefore the seam, not a
workaround: it is where the runner hands control to ORION's code. It also keeps
the mechanisms independent of the loop — the same guarded tool works under a
manual loop or behind an MCP server.

The runner requires tool results to be a `str` or content blocks, so the guard
JSON-encodes the tools' dict results.

**Verified by experiment, not only by reading the source.** A throwaway spike
ran guarded tools through the real `tool_runner` (`anthropic` 1.6.0) against a
mocked HTTP transport — no API key, no tokens — replaying the case flow below:
three tools requested in one turn, the national ID leaked to
`adverse_media_search`, a timeout, and a successful retry. Confirmed:

- A scope refusal raised in the guard reaches the model as an `is_error` result,
  and the refused tool's function never runs.
- All results from one turn go back to the model together in a single message.
- Tools in a turn run sequentially, in request order.
- A tool's timeout followed by a successful retry leaves its credibility at 0.84
  — a failure then a success — which also shows a scope refusal records no
  outcome.

Two requirements came out of it that reading alone had not made clear:

- **Expected failures must be raised as `ToolError`.** A scope refusal or a
  timeout is normal operation for ORION. Raised as a plain exception, the runner
  logs a full stack trace for each one and shows the model the exception's
  `repr` — `ScopeViolation('adverse_media_search may not receive: …')`. Raised as
  `anthropic.lib.tools.ToolError`, the model receives only the message and
  nothing is logged. A control run with plain exceptions confirmed both effects.
- **`anthropic` 1.x uses `httpx2`, not `httpx`.** Any test that mocks the HTTP
  layer must build its transport from `httpx2`.

**Why this surface.** Three agent surfaces were considered. The Claude Agent SDK
(`claude-agent-sdk`) is Claude Code as a library — it ships built-in file and
bash tools that ORION has no use for, and it is a separate product from the API
SDK the rest of the cockpit uses. Managed Agents moves the loop and the tool
sandbox onto Anthropic's infrastructure, which is production-shaped but hides
the orchestration this project exists to teach. A hand-written loop teaches the
most but discards a maintained implementation for no gain here.

The Tool Runner keeps the loop model-driven — which is what was asked for —
while leaving all four mechanisms as the author's own code in the guard.

**Model:** `claude-opus-5`, adaptive thinking.

### Components

Each component has one job and is testable without a model call.

**Registry** (`registry.py`)
Holds a `ToolSpec` per tool: name, description, input schema, the callable, its
permission scope, and its current credibility score. Supports adding and
removing tools while a run is in progress. The registry renders the tool list
handed to the Tool Runner.

**Scope gate** (`scope.py`)
Runs first in the guard. Each tool declares which alert fields it is permitted
to receive; a call carrying anything else is refused before the tool function
executes, and the refusal is returned to the model as an error result so it can
retry differently.

**What "carrying a field" means.** A tool call contains argument values chosen
by the model, not alert field paths, so the gate matches on **values**. The
alert is flattened to `path → value` (`customer.national_id → "CZ-760415-2231"`).
Every path not in the tool's `allowed_fields` is restricted, and the call is
refused if a restricted value appears in any string argument, at any nesting
depth. The refusal names every restricted path found.

Matching on values rather than argument names is what makes the gate hold: the
model can put an ID number in a `name` argument or inside a free-text query, and
a leak is a leak whatever the argument is called. Three rules keep it from
refusing legitimate calls or missing trivially reformatted ones:

- **Normalized comparison.** Values are compared lowercased with every
  non-alphanumeric character removed, so `cz 760415 2231` still matches.
- **Short values match whole arguments only.** A restricted value under four
  normalized characters (a country code like `EE`) is refused only when an
  argument equals it outright, not when it happens to occur inside a word.
- **Shared values are permitted.** If a restricted field has the same value as
  an allowed field — the customer and the counterparty in the same country —
  the gate cannot tell which one the model used, so it allows it. Refusing
  would block every legitimate call that mentions the country.

The ceiling is known: an encoded or partially transcribed value (a base64 ID,
the last four digits) will not match. That is a deliberate v1 limit, recorded
in the code.

Scope is field-level only. An operation dimension (read vs. write) was
considered and cut: all four v1 tools are read-only, so that check would have no
case that could ever fail, and an unexercised permission check is worse than no
check — it looks like protection without being any. It belongs in the phase that
first introduces a tool that writes.

**Credibility tracker** (`credibility.py`)
Runs after the tool in the guard. Applies an exponential moving average over
outcomes:

```
score = (1 - alpha) * score + alpha * outcome
```

with `outcome` of 1.0 for success and 0.0 for failure, `alpha = 0.2`, an initial
score of 1.0, and a floor of 0.1.

A moving average is used rather than a success counter so that recent behavior
weighs more heavily than distant history, while a single failure does not
destroy a tool's standing. The floor prevents a tool from reaching zero and
becoming permanently unusable — recoverable distrust, not a death sentence.
Scores persist to JSON between runs, so a tool that failed in one run starts the
next run trusted less.

**Conflict resolver** (`conflict.py`)
Tool results are normalized into claims: a dimension (what question the claim
addresses), a verdict, and the credibility of the tool that produced it. Claims
on the same dimension with opposing verdicts are conflicts.

Resolution compares the credibility of the claiming tools:

- Gap **above** the threshold (0.15): the more credible claim wins. The losing
  claim is retained in the output, marked as overridden, with the score gap
  recorded as the justification.
- Gap **at or below** the threshold: no winner. The case resolves to
  `needs human`.

Declining to decide is a first-class outcome. In AML triage a near-arbitrary
automated decision is worse than an acknowledged uncertainty, and a resolver
that always produces a winner would be hiding the ambiguity rather than
reporting it.

**Decision rule** (`decision.py`)
A pure function from resolved claims to a verdict, evaluated in order:

1. Any unresolved conflict → `needs human`.
2. Any surviving claim of elevated risk → `escalate`.
3. Otherwise → `clear`.

An overridden claim is not a surviving claim: if a risk claim lost to a more
credible contradicting one, it does not trigger an escalation. It stays in the
output so the reader can see what was set aside and why.

**The verdict is produced by code, not by the model.** The model writes the
narrative that explains the case; it does not make the call. A regulated
decision has to be reproducible and explainable on demand, and a decision whose
only provenance is a model's turn does not satisfy that. The same inputs and the
same scores must always produce the same verdict.

**Audit trail** (`audit.py`)
Records every tool call: tool name, arguments as submitted, the scope gate's
verdict, execution time, the result or error, and credibility before and after.
Written alongside the decision as JSON.

**Entry point** (`main.py`)
CLI: reads an alert file, runs the orchestration, prints the decision and
reasoning, writes the decision and audit trail to `outputs/`.

### The simulated tools

Four tools, all simulated, in `tools/`. They return realistic canned data with
scripted (not random) behavior, so runs are reproducible and the interesting
paths are always exercised:

| Tool | Returns | Scripted behavior |
|---|---|---|
| `sanctions_screen` | Watchlist match result | Reliable. Reports no match |
| `adverse_media_search` | Negative news on the customer | **Fails on first call** (timeout), succeeds on retry |
| `transaction_graph` | Counterparties and their flags | Reports a link to a **flagged entity** |
| `risk_score` | A 0–100 composite score | Reliable, but requires the other three results as input |

`sanctions_screen` (no match) and `transaction_graph` (flagged counterparty)
make opposing claims on the same dimension — customer risk. That is the conflict
the resolver exists to settle.

`adverse_media_search` is scoped to public-source data and may not receive the
customer's national ID number.

## How a case flows

1. **Load.** Read the alert. Build the registry; load persisted credibility
   scores.
2. **Hand off.** The Tool Runner receives the alert, the tool list, and a system
   prompt describing what the analyst must establish.
3. **First wave.** The model has no reason to sequence sanctions, media and
   graph, so it requests all three in one turn. That is the parallelism ORION
   demonstrates: the model decides the calls are independent, without a
   scheduler declaring it. **Execution is still sequential** — the SDK's runner
   (sync and async alike, as of `anthropic` 1.6.0) calls each tool in turn. With
   simulated tools that cost is zero; with real network tools, concurrent
   execution would need a manual loop or a wrapper that fans the calls out.
4. **Scope refusal.** The model passes the national ID to
   `adverse_media_search`, seeking better matches. The gate refuses the call
   before execution and returns the reason. The model re-issues with name and
   country only. (Sending an identity number to an external news service is a
   genuine privacy failure; this is what the scope check is for.)
5. **Tool failure.** `adverse_media_search` times out. The guard records
   the failure, lowers the score, and returns the error to the model as a failed
   result rather than raising. The model retries; the call succeeds; the score
   partially recovers.
6. **Second wave.** `risk_score` depends on the other three results, so the
   model calls it only once they land. The dependency is real rather than
   declared.
7. **Conflict.** Sanctions and graph disagree on customer risk. The resolver
   compares credibility and either picks a winner (recording the override) or
   returns `needs human`.
8. **Decision.** The decision rule produces the verdict from the resolved
   claims. The model writes the explanatory narrative.
9. **Write.** Decision, reasoning, overridden claims and audit trail to
   `outputs/`; updated scores persisted.

Running the same alert twice is instructive: the second run begins with
`adverse_media_search` already distrusted, and the conflict may resolve
differently. Credibility routing is observable rather than asserted.

## Testing

Every test but one runs offline with no API key. The simulated tools' failures
are scripted, so the suite is deterministic.

| Target | Test |
|---|---|
| Registry | Add and remove a tool mid-run; the rendered tool list reflects it |
| Scope gate | A call carrying the national ID is refused **and the tool function never executes** |
| Credibility | A failure lowers the score; repeated successes recover it without exceeding 1.0; the floor holds |
| Conflict resolver | Clear gap → more credible claim wins, loser marked overridden. Gap within threshold → `needs human` |
| Decision rule | Table-driven over claim combinations (pure function) |
| Audit trail | After a full run, every call appears with scope verdict and before/after scores |
| The guard | A guarded tool called directly: a scope refusal never reaches the tool function; a raised failure lowers credibility and re-raises; a success returns a JSON string. No SDK needed |
| The loop | Mocked SDK client returning a canned tool-call sequence through the real runner. No tokens spent |

One live end-to-end test, marked and skipped by default, exercises the real
model. It is the only proof the wiring works, so it exists; it never blocks the
suite.

**Method:** test-first. Tests are written and explained before the
implementation, and the implementation is written by the author.

## Conventions

Matches the AI Engineering Cockpit projects this one grew out of: flat `src/`,
`tests/` with `conftest.py`,
`uv` with `package = false`, pytest and pytest-cov, ruff. Python 3.11+.

Dependencies: `anthropic`, `python-dotenv`. Nothing else.

## Phases

| # | Phase | Author | Delivers |
|---|---|---|---|
| 0 | Scaffold | Claude | uv project, pyproject, test harness, alert fixture |
| 1 | Registry + tools | **User** | `ToolSpec`, registry, the four simulated tools |
| 2 | Scope gate | **User** | Value-based permission check |
| 3 | Credibility tracker | **User** | Moving average, floor, persistence |
| 4 | Guard + Tool Runner wiring | Pair | Scope, credibility and audit wrapped around each tool; first live run |
| 5 | Conflict resolver + decision rule | **User** | Resolution, override records, verdict |
| 6 | Audit trail + CLI + README | Pair | Presentable output |

Each phase ends with: tests passing → ponytail review → code review → one
commit.

## Open questions

These need the author's decision before Phase 5. Neither blocks Phases 1–4.

### 1. The flagship conflict is not a real contradiction

The spec's conflict pits `sanctions_screen` ("customer: no match") against
`transaction_graph` ("customer transacts with a flagged entity") on a single
*customer risk* dimension. A compliance reviewer would reject that framing:
the two claims are about different facts and are both true at once. A customer
can be unsanctioned and still have a risky counterparty. Settling them by
credibility would present a non-conflict as one, which is exactly the kind of
manufactured certainty the resolver exists to avoid.

**Recommended replacement: a name-match false positive**, the most common real
conflict in sanctions screening. Make the dimension *is counterparty Vantage
Freight OU the listed entity?*

- `sanctions_screen` matches by **name** and says yes.
- `transaction_graph` knows the counterparty's **registration number**, and it
  differs from the listed entity's, so it says no.

Both claims now answer the same question and cannot both be true. Credibility
decides which evidence to trust, or the gap is too close and a human decides.
That is a conflict an AML analyst would recognise.

Cost if adopted: `transaction_graph` returns a registration number per
counterparty; the Phase 1 tests for Task 5 gain one assertion. Phases 2–4 are
unaffected.

### 2. `sanctions_screen` cannot screen the counterparty

Its declared scope is the customer's name, country and date of birth. Screening
counterparties is standard practice, so a well-behaved model will try it and be
refused — teaching the reader that the scope gate blocks correct behaviour.

**Recommended:** add `counterparty.name` and `counterparty.country` to its
`allowed_fields`. Required by open question 1's replacement; worth doing even
without it. Changes `EXPECTED_SCOPES` in the Phase 1 Task 8 test.

## Out of scope for v1

Deliberately deferred. Each is a real capability from the ORION brief, parked
because nothing in v1 needs it yet:

- **Fallback to a different tool on failure.** Requires two tools covering the
  same capability; with four distinct tools there is nothing to fall back to.
  Retrying the same tool is implemented.
- **Mid-run escalation to the user.** The `needs human` verdict covers the case
  for now.
- **Real external APIs** (sanctions lists, news search). Simulated tools keep
  the suite deterministic and offline; swapping one in is a v2 phase.
- **A dashboard.** The cockpit's `08-cost-dashboard` already covers that ground.
- **Batch processing.** The cockpit's `10-batch-pipeline` covers it.

## Tooling

- **GSD** — roadmap and phase artifacts under `.planning/`; one phase discussed,
  planned, executed and verified at a time.
- **superpowers** — the inner loop: test-driven development, review gates,
  verification before any completion claim.
- **ponytail** — reviews each phase for what should not exist.
- **graphify** — builds a queryable knowledge graph of the project once code
  exists.
- **caveman** — context compression. Its MCP server was unavailable at the time
  of writing; nothing depends on it.
- **ruflo** — not installed as a plugin. Artifacts from a prior claude-flow
  initialization exist untracked under `projects/01-hello-world/`. Nothing in
  this design depends on it.
