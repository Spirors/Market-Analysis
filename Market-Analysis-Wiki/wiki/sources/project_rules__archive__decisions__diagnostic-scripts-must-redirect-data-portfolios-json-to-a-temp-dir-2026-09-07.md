---
type: source
title: "Diagnostic scripts MUST redirect data/portfolios.json to a temp dir"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/diagnostic-scripts-must-redirect-data-portfolios-json-to-a-temp-dir-2026-09-07.md"
original_sha256: "3a34d8d93828165a5a6b60f7e35da062063543e64e2ef37a462e55ea004c452d"
stored_path: ".raw/captured/3a34d8d93828165a5a6b60f7e35da062063543e64e2ef37a462e55ea004c452d.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Diagnostic scripts MUST redirect data/portfolios.json to a temp dir

A diagnostic script overwrote the user's real data/portfolios.json with test data because it did not redirect paths to a temp directory. Any script exercising the portfolio API must monkeypatch DATA_DIR and PORTFOLIOS_PATH to a tmp dir for the duration of the session; this is now a hard rule.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/diagnostic-scripts-must-redirect-data-portfolios-json-to-a-temp-dir-2026-09-07.md`
  - SHA-256: `3a34d8d93828165a5a6b60f7e35da062063543e64e2ef37a462e55ea004c452d`
- **Captured:** `.raw/captured/3a34d8d93828165a5a6b60f7e35da062063543e64e2ef37a462e55ea004c452d.md`

## Key claims

- Any script exercising the portfolio API must redirect data/portfolios.json and data/dashboard.json to a temp directory.
- Data/*.json files have no git history; a single careless write is permanent without an external backup.

## Concepts

- `test-isolation`
- `data-integrity`
- `diagnostic-safety`

## Entities

- `data/portfolios.json`
- `app.config.DATA_DIR`
- `tests/conftest.py`
