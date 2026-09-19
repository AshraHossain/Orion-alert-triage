# Graph Report - .  (2026-09-18)

## Corpus Check
- Corpus is ~15,922 words - fits in a single context window. You may not need a graph.

## Summary
- 253 nodes · 378 edges · 14 communities (12 shown, 2 thin omitted)
- Extraction: 70% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.73)
- Token cost: 92,905 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Scope Gate Code|Scope Gate Code]]
- [[_COMMUNITY_Credibility Tracker Code|Credibility Tracker Code]]
- [[_COMMUNITY_Simulated Tools|Simulated Tools]]
- [[_COMMUNITY_Tool Registry Code|Tool Registry Code]]
- [[_COMMUNITY_Registry Tests|Registry Tests]]
- [[_COMMUNITY_Scope and Credibility Design|Scope and Credibility Design]]
- [[_COMMUNITY_Registry and Tools Design|Registry and Tools Design]]
- [[_COMMUNITY_Alert Fixture Fields|Alert Fixture Fields]]
- [[_COMMUNITY_Registry Assembly|Registry Assembly]]
- [[_COMMUNITY_Conflict and Decision Design|Conflict and Decision Design]]
- [[_COMMUNITY_Scaffold Tests|Scaffold Tests]]
- [[_COMMUNITY_Test Configuration|Test Configuration]]
- [[_COMMUNITY_Deferred Fallback|Deferred Fallback]]
- [[_COMMUNITY_Test-First Method|Test-First Method]]

## God Nodes (most connected - your core abstractions)
1. `check_scope()` - 21 edges
2. `Any` - 18 edges
3. `spec_allowing()` - 16 edges
4. `CredibilityStore` - 14 edges
5. `ToolSpec` - 14 edges
6. `make_spec()` - 14 edges
7. `Registry` - 13 edges
8. `make_adverse_media_search()` - 10 edges
9. `build_registry()` - 10 edges
10. `update()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_a_success_at_full_trust_stays_at_full_trust()` --calls--> `update()`  [INFERRED]
  tests/test_credibility.py → src/credibility.py
- `test_repeated_failures_stop_at_the_floor()` --calls--> `update()`  [INFERRED]
  tests/test_credibility.py → src/credibility.py
- `test_the_score_never_exceeds_full_trust()` --calls--> `update()`  [INFERRED]
  tests/test_credibility.py → src/credibility.py
- `test_an_unknown_tool_starts_fully_trusted()` --calls--> `CredibilityStore`  [INFERRED]
  tests/test_credibility.py → src/credibility.py
- `test_the_store_starts_from_given_scores()` --calls--> `CredibilityStore`  [INFERRED]
  tests/test_credibility.py → src/credibility.py

## Import Cycles
- 1-file cycle: `src/tools.py -> src/tools.py`

## Communities (14 total, 2 thin omitted)

### Community 0 - "Scope Gate Code"
Cohesion: 0.10
Nodes (41): Exception, check_scope(), flatten(), _normalize(), Any, Permission scope gate.  A tool call carries argument values chosen by the model,, A tool call carries the value of an alert field outside the tool's scope., Map dotted paths to every leaf value, as text. (+33 more)

### Community 1 - "Credibility Tracker Code"
Cohesion: 0.08
Nodes (31): CredibilityStore, Path, Credibility scoring: a per-tool moving average with a floor, persisted as JSON., update(), Path, Tests for credibility scoring.  The update rule is an exponential moving average, A reviewer should be able to open it and see why a tool was distrusted., The very first run has no history, and that is not an error. (+23 more)

### Community 2 - "Simulated Tools"
Cohesion: 0.08
Nodes (34): make_adverse_media_search(), Simulated tools for ORION alert triage.  All tools are deterministic: canned dat, Calculate overall risk based on three dimensions.      Sanctions hits dominate;, Screen a name and country against international sanctions lists.      Returns wh, Retrieve the transaction graph for a customer.      Returns known counterparties, Factory for the adverse media search tool.      Returns a stateful callable that, risk_score(), sanctions_screen() (+26 more)

### Community 3 - "Tool Registry Code"
Cohesion: 0.10
Nodes (19): Registry, RuntimeError, Any, Dynamic tool registry for ORION orchestration., A tool's static configuration: name, contract, permission scope, and callable., Dynamic tool registry: tools can be added and removed while the system runs., Register a tool.          Raises ValueError if a tool with this name is already, Unregister a tool by name.          Raises KeyError if the tool does not exist. (+11 more)

### Community 4 - "Registry Tests"
Cohesion: 0.13
Nodes (19): make_spec(), Tests for the dynamic tool registry.  No tool is actually executed here -- the r, The API wants exactly name, description and input_schema — no more.      ``allow, This is the whole point of a *dynamic* registry., Build a throwaway spec for registry tests., A spec is configuration, not state.      Phase 3 keeps credibility scores in the, Prompt caching keys on an exact prefix, and the tool list is part of it.      A, Two tools with one name means the model's call is ambiguous. (+11 more)

### Community 5 - "Scope and Credibility Design"
Cohesion: 0.11
Nodes (19): Atomic JSON Persistence, check_scope, CredibilityStore, Credibility Tracker, flatten, Guarded Tool Pattern, Model Configuration, Exponential Moving Average (+11 more)

### Community 6 - "Registry and Tools Design"
Cohesion: 0.16
Nodes (17): adverse_media_search, Alert Fixture (alert-001.json), build_registry, Customer Risk Dimension, Factory Pattern for Stateful Tool, Frozen Dataclass Immutability, National ID Leak Scenario, Open Question: Real Contradiction Format (+9 more)

### Community 7 - "Alert Fixture Fields"
Cohesion: 0.12
Nodes (16): alert_id, counterparty, country, name, customer, country, customer_id, date_of_birth (+8 more)

### Community 8 - "Registry Assembly"
Cohesion: 0.22
Nodes (12): build_registry(), Assemble the complete registry for ORION alert triage.      Each build returns a, Tests for the assembled registry.  This is the seam every later phase starts fro, The single most important assertion in Phase 1.      Phase 2's gate is only as g, It consumes other tools' findings, never the customer's data., Two runs in one process must not share a failure counter.      Without this, the, test_adverse_media_may_not_receive_the_national_id(), test_all_four_tools_are_registered() (+4 more)

### Community 9 - "Conflict and Decision Design"
Cohesion: 0.33
Nodes (6): Audit Trail, Conflict Resolver, Credibility Gap Threshold, Decision Rule, needs_human Outcome, Verdict Produced by Code

### Community 10 - "Scaffold Tests"
Cohesion: 0.40
Nodes (5): Any, Proves the project layout works before any real code exists.  If these fail, not, ``national_id`` is the field the Phase 2 scope gate must refuse to leak.      It, test_alert_fixture_carries_a_restricted_field(), test_alert_fixture_has_the_fields_the_tools_need()

### Community 11 - "Test Configuration"
Cohesion: 0.40
Nodes (4): alert(), Any, Test configuration: make ``src/`` importable and load the alert fixture., The single flagged-transaction alert every phase is built around.      Returns:

## Knowledge Gaps
- **36 isolated node(s):** `alert_id`, `raised_at`, `trigger_rule`, `customer_id`, `name` (+31 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Registry` connect `Tool Registry Code` to `Scope Gate Code`, `Registry Assembly`, `Simulated Tools`, `Registry Tests`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Why does `ToolSpec` connect `Tool Registry Code` to `Scope Gate Code`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `check_scope()` (e.g. with `test_a_call_using_only_allowed_values_passes()` and `test_a_reformatted_value_is_still_refused()`) actually correct?**
  _`check_scope()` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Any` (e.g. with `ToolSpec` and `ScopeViolation`) actually correct?**
  _`Any` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `CredibilityStore` (e.g. with `Path` and `test_an_unknown_tool_starts_fully_trusted()`) actually correct?**
  _`CredibilityStore` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ToolSpec` (e.g. with `Registry` and `Any`) actually correct?**
  _`ToolSpec` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `alert_id`, `raised_at`, `trigger_rule` to the rest of the system?**
  _101 weakly-connected nodes found - possible documentation gaps or missing edges._