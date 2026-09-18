# Graph Report - .  (2026-09-18)

## Corpus Check
- Corpus is ~12,425 words - fits in a single context window. You may not need a graph.

## Summary
- 62 nodes · 60 edges · 8 communities
- Extraction: 63% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Registry & Tools|Registry & Tools]]
- [[_COMMUNITY_Scope Enforcement|Scope Enforcement]]
- [[_COMMUNITY_Credibility Scoring|Credibility Scoring]]
- [[_COMMUNITY_Phase Timeline|Phase Timeline]]
- [[_COMMUNITY_Core Mechanisms|Core Mechanisms]]
- [[_COMMUNITY_Data Processing|Data Processing]]
- [[_COMMUNITY_Testing Infrastructure|Testing Infrastructure]]
- [[_COMMUNITY_Orchestration|Orchestration]]

## God Nodes (most connected - your core abstractions)
1. `customer` - 6 edges
2. `make_spec()` - 5 edges
3. `transaction` - 4 edges
4. `counterparty` - 3 edges
5. `ToolSpec` - 3 edges
6. `alert()` - 3 edges
7. `test_tool_spec_is_immutable()` - 3 edges
8. `test_alert_fixture_carries_a_restricted_field()` - 3 edges
9. `ToolSpec` - 2 edges
10. `test_tool_spec_carries_its_permission_scope()` - 2 edges

## Surprising Connections (you probably didn't know these)
- `ToolSpec` --uses--> `ToolSpec`  [INFERRED]
  tests/test_registry.py → src/registry.py

## Import Cycles
- None detected.

## Communities (8 total, 0 thin omitted)

### Community 0 - "Registry & Tools"
Cohesion: 0.18
Nodes (10): alert_id, counterparty, country, name, raised_at, transaction, amount_usd, currency (+2 more)

### Community 1 - "Scope Enforcement"
Cohesion: 0.18
Nodes (11): ToolSpec, Credibility scoring, Permission scoping, ScopeViolation, check_scope, CredibilityStore, update, flatten (+3 more)

### Community 2 - "Credibility Scoring"
Cohesion: 0.18
Nodes (11): Registry, transaction_graph, adverse_media_search, risk_score, Dynamic tool registry, Conflict resolution, build_registry, Orchestrator (+3 more)

### Community 3 - "Phase Timeline"
Cohesion: 0.32
Nodes (7): make_spec(), Tests for the dynamic tool registry.  No tool is actually executed here -- the r, Build a throwaway spec for registry tests., A spec is configuration, not state.      Phase 3 keeps credibility scores in the, test_tool_spec_carries_its_permission_scope(), test_tool_spec_is_immutable(), ToolSpec

### Community 4 - "Core Mechanisms"
Cohesion: 0.33
Nodes (6): customer, country, customer_id, date_of_birth, name, national_id

### Community 5 - "Data Processing"
Cohesion: 0.40
Nodes (5): Any, Proves the project layout works before any real code exists.  If these fail, not, ``national_id`` is the field the Phase 2 scope gate must refuse to leak.      It, test_alert_fixture_carries_a_restricted_field(), test_alert_fixture_has_the_fields_the_tools_need()

### Community 6 - "Testing Infrastructure"
Cohesion: 0.40
Nodes (4): alert(), Any, Test configuration: make ``src/`` importable and load the alert fixture., The single flagged-transaction alert every phase is built around.      Returns:

### Community 7 - "Orchestration"
Cohesion: 0.50
Nodes (3): Dynamic tool registry for ORION orchestration., A tool's static configuration: name, contract, permission scope, and callable., ToolSpec

## Knowledge Gaps
- **14 isolated node(s):** `alert_id`, `raised_at`, `trigger_rule`, `customer_id`, `name` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `customer` connect `Core Mechanisms` to `Registry & Tools`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **What connects `alert_id`, `raised_at`, `trigger_rule` to the rest of the system?**
  _23 weakly-connected nodes found - possible documentation gaps or missing edges._