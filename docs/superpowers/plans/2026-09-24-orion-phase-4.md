# ORION Phase 4 Implementation Plan

> **For agentic workers:** the spec marks this phase **Pair**, not author-only.
> Claude supplies the tests and the SDK details; the author writes the
> implementation, or the two are written together at the keyboard. Do not hand
> the whole phase to a subagent.

**Goal:** Put the three finished mechanisms to work. Wrap every registered tool
in a guard that enforces scope, records credibility and writes the audit trail,
hand those guarded tools to the Anthropic Tool Runner, and make the first live
run.

**Architecture:** `guard.py` turns one `ToolSpec` into the function the runner
calls. `audit.py` holds the record that guard writes. `orchestrator.py` renders
the registry as runnable tools and drives the loop. The mechanisms themselves do
not change in this phase: `scope.py` and `credibility.py` are used exactly as
Phases 2 and 3 left them.

**Tech Stack:** `anthropic` 1.6.0, `httpx2` (its HTTP layer, used by the loop
test), Python 3.11 standard library, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-orion-alert-triage-design.md` — read
*Surface: Anthropic Tool Runner* and *How a case flows* first. The guard's order
of operations and the `ToolError` requirement are both recorded there, with the
evidence behind them.

**Prerequisite:** Phases 0–3 complete — registry, four tools, scope gate and
credibility tracker, 75 tests passing.

## How these tests were checked

Every test below was run against a throwaway reference implementation, task by
task, before being written into this plan. For each task the plan states what
you will see *before* you write code and *after* — both were observed, not
predicted. The reference implementation was never committed; you will not find
it anywhere in the repository.

Checked against `anthropic` 1.6.0 and `httpx2` 2.13.0, the versions in
`uv.lock`. The loop test drives the SDK's real `tool_runner` over a mocked
transport, so the turn-taking and the `tool_result` shapes are the SDK's own
rather than this plan's idea of them. With all five tasks done the suite was 97
passed, ruff clean.

If a test behaves differently from what this plan says, that is a bug in the
plan. Say so rather than bending your code to fit.

## Global Constraints

- Everything in the earlier plans' Global Constraints still applies.
- **The mechanisms do not change.** If a Phase 2 or Phase 3 test has to be
  edited to make this phase pass, stop: the guard is wrong, not the mechanism.
- **No tokens in the test suite.** Every test here runs offline. The one live
  test is marked and skipped by default.
- `guard.py` knows nothing about the runner, and `orchestrator.py` knows nothing
  about matching rules or moving averages.

## File Structure

| File | Responsibility |
|---|---|
| `src/audit.py` | `AuditEntry` — one record per attempted call |
| `src/guard.py` | `guard()` — scope, then tool, then credibility and audit |
| `src/orchestrator.py` | `guarded_tools()`, `run()`, the system prompt |
| `tests/test_audit.py` | The record's shape and immutability |
| `tests/test_guard.py` | The guard, called directly, no SDK client |
| `tests/test_loop.py` | Rendering, then the real runner over a mock transport |

---

## Task 15: The audit record

**Files:**
- Create: `src/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AuditEntry`, a frozen dataclass with `tool`, `arguments`,
  `allowed`, `duration_ms`, `credibility_before`, `credibility_after`, and the
  optional `result` and `error`.

- [ ] **Step 1: Write the failing tests**

`tests/test_audit.py`:

```python
"""Tests for the audit entry.

One entry per attempted tool call, including calls the scope gate refused.
The fields are what a reviewer needs to reconstruct the run: what was asked
for, whether it was permitted, how long it took, and what it did to the
tool's credibility.
"""

from __future__ import annotations

import dataclasses

import pytest

from audit import AuditEntry


def test_an_entry_records_what_a_reviewer_needs() -> None:
    entry = AuditEntry(
        tool="sanctions_screen",
        arguments={"name": "Marek Dvorak", "country": "CZ"},
        allowed=True,
        duration_ms=1.5,
        credibility_before=1.0,
        credibility_after=1.0,
        result={"hit": False},
    )

    assert entry.tool == "sanctions_screen"
    assert entry.arguments == {"name": "Marek Dvorak", "country": "CZ"}
    assert entry.allowed is True
    assert entry.result == {"hit": False}
    assert entry.error is None


def test_a_refused_call_is_still_an_entry() -> None:
    """The refusals are the most interesting lines in the trail."""
    entry = AuditEntry(
        tool="adverse_media_search",
        arguments={"national_id": "CZ-760415-2231"},
        allowed=False,
        duration_ms=0.0,
        credibility_before=1.0,
        credibility_after=1.0,
        error="adverse_media_search may not receive: customer.national_id",
    )

    assert entry.allowed is False
    assert entry.result is None
    assert "customer.national_id" in entry.error


def test_an_entry_cannot_be_edited_after_the_fact() -> None:
    """An audit trail that can be rewritten is not an audit trail."""
    entry = AuditEntry("sanctions_screen", {}, True, 1.0, 1.0, 1.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.allowed = False
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_audit.py -v
```

Expected: `ModuleNotFoundError: No module named 'audit'`.

- [ ] **Step 3: Write the implementation — yours to write**

A single frozen dataclass. `result` and `error` both default to `None`: a
success has no error, a refusal and a failure have no result.

Note what is *not* here. There is no `AuditTrail` class: the trail is a plain
`list[AuditEntry]` that the caller owns and the guard appends to. A list already
keeps order and already supports everything Phase 4 needs; a wrapper around it
would be a class with one method. Phase 6 is where the trail learns to write
itself to `outputs/`, and that is the phase to reconsider it.

Order the fields as the test constructs them positionally in the last test:
`tool`, `arguments`, `allowed`, `duration_ms`, `credibility_before`,
`credibility_after`, then the two optional ones.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_audit.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/audit.py tests/test_audit.py
git commit -m "feat: add the audit record for one tool call"
```

---

## Task 16: The guard

**Files:**
- Create: `src/guard.py`
- Test: `tests/test_guard.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `ToolSpec`, `check_scope`, `ScopeViolation`, `CredibilityStore`,
  `AuditEntry`.
- Produces:
  `guard(spec: ToolSpec, alert: Mapping[str, Any], store: CredibilityStore, trail: list[AuditEntry]) -> Callable[..., str]`.

- [ ] **Step 1: Raise the SDK floor**

`pyproject.toml` currently allows `anthropic>=0.34`, which predates
`tool_runner` entirely. The lock file already has 1.6.0; the floor is what is
wrong. Change the dependency to `anthropic>=1.6` before you import from it, so
nobody installs a version where this phase cannot work.

- [ ] **Step 2: Write the failing tests**

`tests/test_guard.py`:

```python
"""Tests for the guard.

The guard is where ORION's mechanisms meet a tool call: scope first, then the
tool, then credibility and the audit trail. These tests call a guarded tool
directly -- no SDK client, no model, no tokens.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from anthropic.lib.tools import ToolError

from audit import AuditEntry
from credibility import CredibilityStore
from guard import guard
from registry import ToolSpec
from tools import ToolTimeoutError, build_registry


def spec_for(
    run: Any, *, name: str = "adverse_media_search", fields: tuple[str, ...] = ()
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="guard test stand-in",
        input_schema={"type": "object", "properties": {}, "required": []},
        run=run,
        allowed_fields=frozenset(fields),
    )


def test_a_success_returns_the_result_as_a_json_string(alert: dict[str, Any]) -> None:
    """The runner requires a string, so the guard encodes the tool's dict."""
    trail: list[AuditEntry] = []
    guarded = guard(spec_for(lambda **_: {"hit": False}), alert, CredibilityStore(), trail)

    assert json.loads(guarded()) == {"hit": False}


def test_a_refused_call_never_reaches_the_tool(alert: dict[str, Any]) -> None:
    """The whole point of the gate: the data does not leave the process."""
    calls: list[dict[str, Any]] = []

    def tool(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return {}

    trail: list[AuditEntry] = []
    guarded = guard(spec_for(tool, fields=("customer.name",)), alert, CredibilityStore(), trail)

    with pytest.raises(ToolError, match=r"customer\.national_id"):
        guarded(name="Marek Dvorak", query="CZ-760415-2231")

    assert calls == []


def test_a_refusal_leaves_credibility_untouched(alert: dict[str, Any]) -> None:
    """The tool did not fail -- it never ran. Scoring it would be a lie."""
    store = CredibilityStore()
    trail: list[AuditEntry] = []
    guarded = guard(spec_for(lambda **_: {}, fields=("customer.name",)), alert, store, trail)

    with pytest.raises(ToolError):
        guarded(query="CZ-760415-2231")

    assert store.get("adverse_media_search") == pytest.approx(1.0)


def test_a_failure_lowers_credibility_and_raises_tool_error(alert: dict[str, Any]) -> None:
    def tool(**_: Any) -> dict[str, Any]:
        raise ToolTimeoutError("Search timeout on attempt 1")

    store = CredibilityStore()
    trail: list[AuditEntry] = []
    guarded = guard(spec_for(tool), alert, store, trail)

    with pytest.raises(ToolError, match="Search timeout"):
        guarded()

    assert store.get("adverse_media_search") == pytest.approx(0.8)


def test_expected_failures_are_tool_errors_not_bare_exceptions(alert: dict[str, Any]) -> None:
    """A ToolError reaches the model as a message; anything else reaches it as
    a repr, and the SDK logs a stack trace for every one."""

    def tool(**_: Any) -> dict[str, Any]:
        raise ToolTimeoutError("Search timeout on attempt 1")

    trail: list[AuditEntry] = []
    guarded = guard(spec_for(tool), alert, CredibilityStore(), trail)

    with pytest.raises(ToolError) as caught:
        guarded()

    assert str(caught.value) == "Search timeout on attempt 1"


def test_a_success_raises_credibility_back_toward_full_trust(alert: dict[str, Any]) -> None:
    store = CredibilityStore({"adverse_media_search": 0.8})
    trail: list[AuditEntry] = []
    guarded = guard(spec_for(lambda **_: {}), alert, store, trail)

    guarded()

    assert store.get("adverse_media_search") == pytest.approx(0.84)


def test_every_call_leaves_one_audit_entry(alert: dict[str, Any]) -> None:
    trail: list[AuditEntry] = []
    store = CredibilityStore()
    ok = guard(
        spec_for(lambda **_: {"hit": False}, name="sanctions_screen", fields=("customer.name",)),
        alert,
        store,
        trail,
    )
    refused = guard(spec_for(lambda **_: {}, fields=("customer.name",)), alert, store, trail)

    ok(name="Marek Dvorak")
    with pytest.raises(ToolError):
        refused(query="CZ-760415-2231")

    assert [(e.tool, e.allowed) for e in trail] == [
        ("sanctions_screen", True),
        ("adverse_media_search", False),
    ]


def test_an_audit_entry_carries_the_scores_on_both_sides(alert: dict[str, Any]) -> None:
    """'Before' cannot be recovered afterwards, so the guard records both."""

    def tool(**_: Any) -> dict[str, Any]:
        raise ToolTimeoutError("boom")

    trail: list[AuditEntry] = []
    guarded = guard(spec_for(tool), alert, CredibilityStore(), trail)

    with pytest.raises(ToolError):
        guarded()

    assert trail[0].credibility_before == pytest.approx(1.0)
    assert trail[0].credibility_after == pytest.approx(0.8)
    assert trail[0].duration_ms >= 0.0


def test_the_arguments_are_recorded_as_submitted(alert: dict[str, Any]) -> None:
    """The reviewer needs to see what was actually sent, refused or not."""
    trail: list[AuditEntry] = []
    guarded = guard(
        spec_for(lambda **_: {}, fields=("customer.name",)), alert, CredibilityStore(), trail
    )

    with pytest.raises(ToolError):
        guarded(name="Marek Dvorak", query="CZ-760415-2231")

    assert trail[0].arguments == {"name": "Marek Dvorak", "query": "CZ-760415-2231"}


def test_the_real_registry_wires_up_unchanged(alert: dict[str, Any]) -> None:
    """The guard takes a ToolSpec, so every registered tool is guardable."""
    registry = build_registry()
    store = CredibilityStore()
    trail: list[AuditEntry] = []
    guarded = guard(registry.get("sanctions_screen"), alert, store, trail)

    assert json.loads(guarded(name="Marek Dvorak", country="CZ"))["hit"] is False
```

Watch the stand-in spec in `test_every_call_leaves_one_audit_entry`: it declares
`customer.name` as allowed. A spec that allowed nothing would have its own
argument refused, and the test would fail for a reason that has nothing to do
with what it is checking. (Observed: without that scope, the call is refused and
the test fails.)

- [ ] **Step 3: Run the tests to verify they fail**

```bash
uv run pytest tests/test_guard.py -v
```

Expected: `ModuleNotFoundError: No module named 'guard'`.

- [ ] **Step 4: Write the implementation — yours to write**

`guard(spec, alert, store, trail)` returns a function that takes `**arguments`
and returns a `str`. Inside it, in this order:

1. **Scope first.** Call `check_scope(spec, arguments, alert)`. On
   `ScopeViolation`: append an entry with `allowed=False`, no credibility
   change, the violation's message as `error`, and raise
   `anthropic.lib.tools.ToolError` with that same message. The tool function
   must not run — that is the one thing this whole mechanism exists to
   guarantee.
2. **Run and time it.** `time.perf_counter()` either side; the entry wants
   milliseconds.
3. **On any exception from the tool:** `store.record(spec.name, success=False)`,
   append the entry, raise `ToolError` with the failure's message.
4. **On success:** `store.record(spec.name, success=True)`, append the entry
   with the result, and return `json.dumps(result)`.

Three things worth knowing before you write it:

- **Why `ToolError` and not the real exception.** Both reach the model as an
  error result, so it is tempting to let `ScopeViolation` and `ToolTimeoutError`
  propagate. Observed with `anthropic` 1.6.0: a plain exception reaches the
  model as `RuntimeError('Search timeout on attempt 1')` — the `repr`, not the
  message — and the SDK logs a full stack trace for each one. A `ToolError`
  reaches the model as the bare message and logs nothing. A refusal and a
  scripted timeout are normal operation here, not incidents.
- **Why a refusal records no outcome.** Credibility measures whether a tool
  *works*. The refused call never reached it. Scoring it would punish a tool for
  the model's choice of arguments.
- **`raise ToolError(...) from None`** keeps the original exception out of the
  chained traceback. Without it you get the noise back that `ToolError` was
  meant to remove.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_guard.py -v
```

Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add src/guard.py tests/test_guard.py pyproject.toml
git commit -m "feat: guard each tool with scope, credibility and audit"
```

---

## Task 17: Rendering the guarded tools

**Files:**
- Create: `src/orchestrator.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `Registry`, `guard`.
- Produces:
  `guarded_tools(registry, alert, store, trail) -> list[BetaFunctionTool]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_loop.py`:

```python
"""Tests for the loop: guarded tools driven by the real Tool Runner.

The SDK's runner is real; only the HTTP layer is faked, so the turn-taking,
the tool_result shapes and the error handling are the SDK's own. No API key,
no tokens. ``anthropic`` 1.x is built on ``httpx2``, so the mock transport
must come from ``httpx2`` and not ``httpx``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from anthropic.lib.tools import ToolError

from audit import AuditEntry
from credibility import CredibilityStore
from orchestrator import guarded_tools
from tools import build_registry


def test_every_registered_tool_is_rendered_for_the_runner(alert: dict[str, Any]) -> None:
    """The model sees the registry: same names, same descriptions, same schemas."""
    registry = build_registry()

    rendered = guarded_tools(registry, alert, CredibilityStore(), [])

    assert [tool.name for tool in rendered] == registry.names()
    for tool in rendered:
        spec = registry.get(tool.name)
        assert tool.description == spec.description
        assert tool.input_schema == spec.input_schema


def test_calling_a_rendered_tool_goes_through_the_guard(alert: dict[str, Any]) -> None:
    """``call`` is the entry point the runner uses, so the guard must sit behind it."""
    trail: list[AuditEntry] = []
    rendered = guarded_tools(build_registry(), alert, CredibilityStore(), trail)
    sanctions = next(tool for tool in rendered if tool.name == "sanctions_screen")

    result = sanctions.call({"name": "Marek Dvorak", "country": "CZ"})

    assert json.loads(result)["hit"] is False
    assert [(entry.tool, entry.allowed) for entry in trail] == [("sanctions_screen", True)]


def test_a_rendered_tool_refuses_data_outside_its_scope(alert: dict[str, Any]) -> None:
    trail: list[AuditEntry] = []
    rendered = guarded_tools(build_registry(), alert, CredibilityStore(), trail)
    media = next(tool for tool in rendered if tool.name == "adverse_media_search")

    with pytest.raises(ToolError, match=r"customer\.national_id"):
        media.call({"name": "Marek Dvorak", "country": "CZ", "national_id": "CZ-760415-2231"})

    assert trail[0].allowed is False
```

The last test is worth pausing on. `national_id` is not in
`adverse_media_search`'s input schema, so it is tempting to assume the SDK
rejects it before your code ever sees it. It does not: checked against 1.6.0, an
argument absent from the schema is passed straight through to the function. The
gate is the only thing standing between the model and that field.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: `ModuleNotFoundError: No module named 'orchestrator'`.

- [ ] **Step 3: Write the implementation — yours to write**

`BetaFunctionTool` from `anthropic.lib.tools` is the runnable-tool type the
runner accepts. Its constructor takes the function first, then keyword
arguments:

```
BetaFunctionTool(func, name=..., description=..., input_schema=...)
```

which lines up with `ToolSpec` field for field. Build one per spec, wrapping
`guard(spec, alert, store, trail)` as the function.

Iterate `registry.names()` rather than any internal dict order — Phase 1 sorted
that list on purpose, and the first test pins the rendered order to it.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_loop.py
git commit -m "feat: render the registry as guarded runnable tools"
```

---

## Task 18: The loop

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `tests/test_loop.py`

**Interfaces:**
- Consumes: `guarded_tools`.
- Produces: `run(client, registry, alert, store, trail) -> str`, plus the module
  constants `MODEL`, `MAX_TOKENS` and `SYSTEM`.

- [ ] **Step 1: Write the failing tests**

Replace the import block at the top of `tests/test_loop.py` with:

```python
from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.lib.tools import ToolError

from audit import AuditEntry
from credibility import CredibilityStore
from orchestrator import guarded_tools, run
from tools import build_registry
```

Then append:

```python
def assistant_turn(content: list[dict[str, Any]], stop_reason: str) -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def tool_use(block_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": block_id, "name": name, "input": arguments}


#: The case flow from the spec: three tools in one turn with the national ID
#: leaked to adverse media, then a retry that times out, then one that works.
TURNS = [
    assistant_turn(
        [
            tool_use("t1", "sanctions_screen", {"name": "Marek Dvorak", "country": "CZ"}),
            tool_use(
                "t2",
                "adverse_media_search",
                {"name": "Marek Dvorak", "country": "CZ", "national_id": "CZ-760415-2231"},
            ),
            tool_use("t3", "transaction_graph", {"customer_id": "CUST-88421"}),
        ],
        "tool_use",
    ),
    assistant_turn(
        [tool_use("t4", "adverse_media_search", {"name": "Marek Dvorak", "country": "CZ"})],
        "tool_use",
    ),
    assistant_turn(
        [tool_use("t5", "adverse_media_search", {"name": "Marek Dvorak", "country": "CZ"})],
        "tool_use",
    ),
    assistant_turn([{"type": "text", "text": "The counterparty is flagged."}], "end_turn"),
]


@pytest.fixture
def scripted_client() -> tuple[anthropic.Anthropic, list[dict[str, Any]]]:
    """A client whose transport replays TURNS and records what was sent."""
    sent: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json=TURNS[len(sent) - 1])

    client = anthropic.Anthropic(
        api_key="not-a-real-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return client, sent


def test_the_run_returns_the_models_closing_text(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    client, _ = scripted_client

    text = run(client, build_registry(), alert, CredibilityStore(), [])

    assert text == "The counterparty is flagged."


def test_a_refusal_reaches_the_model_as_an_error_result(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    """The model has to be able to read the refusal and retry differently."""
    client, sent = scripted_client

    run(client, build_registry(), alert, CredibilityStore(), [])

    results = sent[1]["messages"][-1]["content"]
    refused = next(block for block in results if block["tool_use_id"] == "t2")
    assert refused["is_error"] is True
    assert "customer.national_id" in refused["content"]


def test_one_turns_results_go_back_in_a_single_message(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    client, sent = scripted_client

    run(client, build_registry(), alert, CredibilityStore(), [])

    results = sent[1]["messages"][-1]["content"]
    assert [block["tool_use_id"] for block in results] == ["t1", "t2", "t3"]


def test_the_run_records_every_call_in_order(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    client, _ = scripted_client
    trail: list[AuditEntry] = []

    run(client, build_registry(), alert, CredibilityStore(), trail)

    assert [(entry.tool, entry.allowed) for entry in trail] == [
        ("sanctions_screen", True),
        ("adverse_media_search", False),
        ("transaction_graph", True),
        ("adverse_media_search", True),
        ("adverse_media_search", True),
    ]


def test_a_failure_then_a_success_leaves_credibility_at_0_84(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    """0.8 for the timeout, then 0.84 for the retry. The refusal scored nothing."""
    client, _ = scripted_client
    store = CredibilityStore()

    run(client, build_registry(), alert, store, [])

    assert store.get("adverse_media_search") == pytest.approx(0.84)
    assert store.get("sanctions_screen") == pytest.approx(1.0)


def test_the_tool_list_sent_to_the_model_is_the_registry(
    alert: dict[str, Any], scripted_client: tuple[anthropic.Anthropic, list[dict[str, Any]]]
) -> None:
    client, sent = scripted_client

    run(client, build_registry(), alert, CredibilityStore(), [])

    assert [tool["name"] for tool in sent[0]["tools"]] == [
        "adverse_media_search",
        "risk_score",
        "sanctions_screen",
        "transaction_graph",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: **the whole file errors** with
`ImportError: cannot import name 'run' from 'orchestrator'`, Task 17's three
tests included. A failing import line stops pytest loading the file, as in the
earlier phases.

- [ ] **Step 3: Write the implementation — yours to write**

Three module constants and one function.

`MODEL = "claude-opus-5"`, a `MAX_TOKENS` you are comfortable with, and a
`SYSTEM` prompt that tells the model it is triaging one KYC/AML alert, what it
has to establish, that a tool may refuse data it is not permitted to receive and
should then be retried without it, and that a failed tool is worth one retry.
The prompt is doing real work here: the spec's case flow depends on the model
retrying rather than giving up.

`run(client, registry, alert, store, trail)`:

```
runner = client.beta.messages.tool_runner(
    model=..., max_tokens=..., system=..., messages=[...],
    tools=guarded_tools(registry, alert, store, trail),
)
final = runner.until_done()
```

then return the concatenated text of `final.content` blocks whose `type` is
`"text"`. Taking the client as an argument rather than constructing one is what
lets the test hand you a scripted transport — and is what Phase 6's CLI will use
to hand you a real one.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Run the whole suite and lint**

```bash
uv run pytest -v && uv run ruff check .
```

Expected: 97 passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_loop.py
git commit -m "feat: drive the guarded tools with the Anthropic Tool Runner"
```

---

## Task 19: The first live run

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`
- Modify: `tests/test_loop.py`

**Unlike every other task in this plan, the test here was not run.** It needs a
real API key and spends real tokens, so it was written but never executed. Treat
its expected result as a prediction, which is exactly why it is marked and
skipped by default.

- [ ] **Step 1: Register the marker**

pytest has no configuration in this project yet, so an unknown mark warns. Add
to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["live: hits the real API and spends tokens; deselected by default"]
addopts = "-m 'not live'"
```

`addopts` is what makes "skipped by default" true without anyone remembering a
flag. `uv run pytest -m live` opts in.

- [ ] **Step 2: Document the key**

`.env.example`, committed, holding `ANTHROPIC_API_KEY=` and nothing else. The
real `.env` is already gitignored. `python-dotenv` is already a dependency and
has had nothing to do until now.

- [ ] **Step 3: Write the live test**

Append to `tests/test_loop.py` a test marked `@pytest.mark.live` that loads
`.env`, skips if `ANTHROPIC_API_KEY` is missing, builds a real
`anthropic.Anthropic()`, and calls `run` with the real registry and alert.

Assert only what cannot drift: that the returned text is non-empty, that the
trail is non-empty, and that every entry names a registered tool. Do not assert
which tools the model chose or in what order — that is the model's decision, and
a test that pins it will fail for the wrong reason.

- [ ] **Step 4: Run it, once, on purpose**

```bash
uv run pytest -m live -v
```

This is the first time ORION talks to a model. Watch the trail rather than the
assertions: did the model request several tools in one turn, did it hand the
national ID to `adverse_media_search`, did it retry after the refusal, did it
retry the timeout, did it call `risk_score` only once the others had landed?

The spec's case flow predicts all five. If the model does something else, that
is a finding worth writing down — in the spec, not in a test.

- [ ] **Step 5: Run the offline suite and lint**

```bash
uv run pytest -v && uv run ruff check .
```

Expected: 97 passed, 1 deselected, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example tests/test_loop.py
git commit -m "feat: add the live end-to-end run, skipped by default"
```

---

## Phase 4 exit criteria

- [ ] `tests/test_audit.py`: 3 passed
- [ ] `tests/test_guard.py`: 10 passed
- [ ] `tests/test_loop.py`: 9 passed offline, 1 live test deselected
- [ ] The whole offline suite passes with no API key and no network; ruff clean
- [ ] A scope refusal provably never reaches the tool function
- [ ] One live run has happened, and what the model actually did is written down
- [ ] The author can explain, without looking:
  - why a refusal records no credibility outcome, but a timeout does
  - why expected failures are raised as `ToolError` rather than propagating
  - why the verdict is not being decided anywhere in this phase
- [ ] ponytail review and code review run over the phase diff

## Deviations from the spec

- **The audit trail is a plain list, not an `audit.py` class.** The spec's
  component list describes `audit.py` as writing the trail out as JSON
  "alongside the decision". That belongs with the decision, which is Phase 5–6
  work. Phase 4 produces the records; Phase 6 gives them somewhere to go.
- **The dependency floor was wrong.** The spec assumes `tool_runner`, verified
  against 1.6.0, while `pyproject.toml` allowed `anthropic>=0.34`. Task 16
  raises it.

## What Phase 5 does with these

For orientation only — not part of this plan. Phase 5 turns the results the
guard collected into claims, resolves the ones that contradict each other by
credibility, and produces the verdict in code. Two things in the spec's *Open
questions* should be answered before it starts: the flagship conflict is not
currently a real contradiction, and `sanctions_screen` cannot screen the
counterparty. Both change `tools.py` and one Phase 1 test, and both are cheaper
to settle before Phase 5 than during it.
