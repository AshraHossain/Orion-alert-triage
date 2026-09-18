# ORION

A multi-tool orchestration agent for financial-crime alert triage.

ORION takes one flagged transaction — a KYC/AML alert — and produces a decision
(**escalate**, **clear**, or **refer to a human**), the reasoning behind it, and
an audit trail of every tool call it made along the way.

> **Status:** Phase 0 (ToolSpec) complete. Design and phases 0–3 planned.
> Phase 1 tasks 2–8 are next: the registry, scope gate, credibility tracker,
> and the conflict resolver. Tasks are test-first with full working tests provided.

## Why it exists

Most agent demos show a model calling tools that work. ORION is about what
happens when they don't: when a tool fails, when a tool asks for data it has no
business seeing, and when two tools contradict each other. It demonstrates four
mechanisms:

1. **A dynamic tool registry** — tools are entries in a list that can change
   while the system runs, not hardcoded calls.
2. **Credibility scoring** — each tool carries a score that moves with its
   observed reliability, and that score decides who wins an argument.
3. **Permission scoping** — each tool declares which alert fields it may
   receive. A call carrying anything else is refused *before* it executes.
4. **Conflict resolution** — when tools disagree, an explicit procedure settles
   it, including the option to decline and escalate to a human.

Financial crime is the domain because conflicting evidence is normal there,
every action has to be auditable, and data-handling limits are real rather than
decorative.

## How it works

The agent loop is driven by the Anthropic SDK's Tool Runner: the model decides
which tools to call and in what order. The four mechanisms above live in the
per-turn hooks around that loop — scope enforcement before a tool runs,
credibility scoring after.

The verdict itself is produced by code, not by the model. The model writes the
narrative that explains the case; it does not make the call. A regulated
decision has to be reproducible on demand, and "the model decided" does not
survive an audit.

The four tools are simulated, with scripted rather than random behaviour: one
fails on its first call, and two of them contradict each other. That keeps the
interesting paths exercised on every run and the test suite deterministic.

## Phases

### Phase 0: Foundation (✓ complete)

- **Task 1:** Scaffold. Creates the alert fixture and test structure.
- **Task 2:** `ToolSpec` — a frozen dataclass holding a tool's name, schema, callable, and permission scope. Tests: `test_tool_spec_carries_its_permission_scope`, `test_tool_spec_is_immutable`.

### Phase 1: Registry & Scoring (in progress)

- **Tasks 3–8:** Build the dynamic tool registry, the scope gate (permission enforcement), and credibility tracking. Each task has full test coverage written in advance.
- See [Phase 0–1 plan](docs/superpowers/plans/2026-09-16-orion-phase-0-1.md) for details.

### Phase 2–3: Advanced Mechanisms (planned)

- Scope gate with full field-level matching rules (Phase 2).
- Credibility tracker with atomic JSON persistence (Phase 3).
- See [Phase 2–3 plan](docs/superpowers/plans/2026-09-16-orion-phase-2-3.md).

## Running tests

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync --all-groups
uv run pytest -v
```

Tests run offline: no API key, no network. Phase 0 tests pass. All 43 Phase 1 tests and 32 Phase 2–3 tests are written and waiting for implementation.

Lint:

```bash
uv run ruff check .
```

## Documentation

- [Design spec](docs/superpowers/specs/2026-09-16-orion-alert-triage-design.md) —
  the architecture, the mechanisms, and the reasoning behind each choice
- [Phase 0–1 plan](docs/superpowers/plans/2026-09-16-orion-phase-0-1.md) —
  the implementation broken into test-first tasks

ORION began as project 15 of the
[AI Engineering Cockpit](https://github.com/AshraHossain/AI_Engineering_Cockpit)
and keeps that project's conventions.

## Licence

MIT. See [LICENSE](LICENSE).
