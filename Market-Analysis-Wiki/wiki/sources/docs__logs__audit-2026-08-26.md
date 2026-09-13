---
type: source
title: "Audit pass — Market Analysis Tool (2026-08-26)"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/audit-2026-08-26.md"
original_sha256: "6f10e4471c8bc8e8f628cf2260236f1d541b7cf3a2248c1d18e89bb69c8408f9"
stored_path: ".raw/captured/6f10e4471c8bc8e8f628cf2260236f1d541b7cf3a2248c1d18e89bb69c8408f9.md"
source_kind: "audit"
tags:
  - source
  - audit
---

# Audit pass — Market Analysis Tool (2026-08-26)

First full codebase audit covering every visible card, Python module, and test. Confirmed all 14 API routes exist, all cards have real renderers, and the risk engine has strong test coverage. Added five new test files closing gaps in indicators, news classification, earnings recommendations, service coverage, and regime staleness.

## Citation

- **Original:** `inbox/docs/logs/audit-2026-08-26.md`
  - SHA-256: `6f10e4471c8bc8e8f628cf2260236f1d541b7cf3a2248c1d18e89bb69c8408f9`
- **Captured:** `.raw/captured/6f10e4471c8bc8e8f628cf2260236f1d541b7cf3a2248c1d18e89bb69c8408f9.md`

## Key claims

- Every card has a real renderer — no dead UI, no orphan renderers.
  - *Evidence:* "Every card has a real renderer. No dead UI, no orphan renderers."
- All 14 documented API routes exist in the backend.
  - *Evidence:* "All 14 documented API routes exist. Nothing was promised in AGENTS.md that the backend doesn't actually serve."
- The risk engine's logic is well-tested with 13 dedicated tests.
  - *Evidence:* "The risk engine's logic is well-tested. 13 dedicated tests cover the GREEN/YELLOW/RED gates, fragility side-tags, valuation stretch, edge cases."
- test_list_events_endpoint_respects_limit references a deleted config.DB_PATH.
  - *Evidence:* "tests/test_api_contract.py::test_list_events_endpoint_respects_limit crashes on setup. It still references config.DB_PATH, which doesn't exist anymore."

## Concepts

- `test-coverage`
- `api-routes`
- `risk-engine`
- `code-audit`

## Entities

- `pytest`
- `risk.py`
- `store.py`
- `earnings.py`
