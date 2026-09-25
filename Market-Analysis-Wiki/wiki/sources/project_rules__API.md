---
type: source
title: "API — HTTP Routes and Dashboard Payload Shape"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/API.md"
original_sha256: "daee26e9ee4e07cc609e78e9919f61d982c986d021da36795d43bbb2c2d416b7"
stored_path: ".raw/captured/daee26e9ee4e07cc609e78e9919f61d982c986d021da36795d43bbb2c2d416b7.md"
source_kind: "api"
tags:
  - source
  - api
---

# API — HTTP Routes and Dashboard Payload Shape

> [!warning] Partly superseded — 2026-09-25
> The `/api/bottleneck/categories/*` routes below are **deleted**. See
> [[sources/decision__bottleneck-section-api-and-agent-contract-2026-09-25|Bottleneck section API and agent contract]].
> This page also predates the removal of the `thirteenf` and `ai_analysis`
> dashboard keys (commit `8dedc18`), so treat the route list and payload key
> list here as historical for those three areas.

Complete HTTP API reference for the Market Analysis Tool. Documents all routes (GET/POST/PUT/DELETE) in app/api.py including dashboard, refresh, meta, events, portfolios, regime, bottleneck, and lifecycle endpoints. Also describes the dashboard payload shape: 14 top-level keys (as_of, market, futures, spot, indicators, risk, bottleneck, thirteenf, ai_sentiment, portfolios, column_order/column_visibility, news, regime, ai_analysis, events, coverage, vintage). Lists removed earnings endpoints.

## Citation

- **Original:** `inbox/project_rules/API.md`
  - SHA-256: `daee26e9ee4e07cc609e78e9919f61d982c986d021da36795d43bbb2c2d416b7`
- **Captured:** `.raw/captured/daee26e9ee4e07cc609e78e9919f61d982c986d021da36795d43bbb2c2d416b7.md`

## Key claims

- Dashboard payload contains 14+ top-level keys; vintage stamps track per-card data age separately from the global as_of.
  - *Evidence:* "vintage — `{section: iso_ts}` per-card data-age stamps (separate from the global `as_of`)."
- POST /api/events/tags supports add/remove of user tags; the auto-tag 'ai' cannot be removed manually.
  - *Evidence:* "The auto-tag "ai" cannot be removed manually."
- Earnings watchlist endpoints (GET /api/earnings, GET /api/earnings/validate, POST/DELETE /api/earnings/watchlist) were removed on 2026-09-06.
  - *Evidence:* "The following were removed with the Earnings watchlist section on 2026-09-06. They are listed here so a stale doc reference can be cleaned up"
- Bottleneck category reorder and rename use POST /api/bottleneck/categories/reorder and PUT /api/bottleneck/categories/{name}.
  - *Evidence:* "POST /api/bottleneck/categories/reorder | Reorder bottleneck categories"
- Portfolio column state is per-section: 'portfolio' for the default, 'portfolio.<pid>' for per-portfolio overrides.
  - *Evidence:* "`column_order` / `column_visibility` — per-section prefs (keyed `"portfolio"` for the default + `"portfolio.<pid>`` for per-portfolio overrides)."

## Concepts

- `http-api`
- `dashboard-payload`
- `portfolio-crud`
- `event-tagging`
- `bottleneck-reorder`
- `per-section-column-state`
- `removed-endpoints`

## Entities

- `app/api.py`
- `app/service.py`
- `app/store.py`
- `app/portfolio.py`
- `app/bottleneck.py`
- `app/validation.py`
- `app/config.py`
- `data/dashboard.json`
- `data/events.json`
- `data/portfolios.json`
- `data/bottleneck_prefs.json`
