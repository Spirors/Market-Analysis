---
type: source
title: "Portfolio history — daily settled-close snapshots and the gain chart"
status: evergreen
created: 2026-10-12
updated: 2026-10-12
source_kind: decision
tags:
  - source
  - decision
  - portfolio
  - data-integrity
---

# Portfolio history — daily settled-close snapshots and the gain chart

The Portfolio card gained a **"Portfolio Performance"** panel above its tables:
a gain-over-time line chart, **total gain ($) on y, date on x**, one line per
portfolio, with a multi-select selector of which portfolios are plotted. Solid
lines are **stored daily snapshots**; dashed lines are a **retrospective
series** ("current holdings applied backwards" over the same ~260 sessions),
computed live on read and never stored. The retrospective answers "what would
my current book have done" without backfilling account history that was never
recorded.

## The snapshot store

`data/portfolio_history.json` is user data (gitignored; written atomically via
`store.save_json`). One entry per **settled US close date**:

- **Write-if-absent.** A past close date is never rewritten, so the store is a
  pure append and re-running a refresh is a no-op (idempotency is pinned by a
  test).
- **Settled-bar guard.** A bar dated "today" is eligible only at/after ~16:15
  US/Eastern; before that the latest earlier session is used. A partial
  in-session bar is never recorded as a close, and the retrospective uses the
  same guard, so writer and read can never disagree.
- **Never a partial sum.** A holding with no close for the date nulls its
  close/value AND the portfolio's `total_value`, with a `coverage {ok, total}`
  stamp. Missing data degrades to null - never 0, never interpolated.
- **Cost parity with the table.** `total_cost` sums every row including cash,
  matching the client-side `portfolioTotals` the live card shows.
- **One writer, one fetch path.** `record_snapshot()` is the single
  read-modify-write writer; it rides `service.refresh_all` (manual Refresh and
  the 9:00 scheduled task) inside try/except, so a snapshot failure can never
  fail a refresh, and it reads closes from the same `get_histories_bulk(...)`
  call shape (260 days, union of symbols) as `enrich_portfolios` - the
  bulk-history cache key is shared.

## The endpoint

`GET /api/portfolios/history` returns `{portfolios, snapshots, retrospective,
meta}`: stored points per portfolio plus the live retrospective. It is
registered **before** the dynamic portfolio routes so the static `/history`
segment is not shadowed (pinned by a test); an empty store yields
`"snapshots": {}` and the panel still renders. Points are
`{date, value, cost, gain, coverage?}`; null marks an unpriceable date.

## The chart (frontend conventions)

- Static chrome inside the Portfolio card, **outside `#portfolioBody`** -
  `renderBody()` rebuilds that container on collapse/expand and re-renders, so
  the canvas and selector must not live inside it.
- Null gains render as **gaps** (`spanGaps: false`), never as zero; the dashed
  retrospective is visually subordinate to the solid actual series.
- Selection persists at `localStorage["pfHistorySelected"]` (missing key = all
  selected); UI prefs stay client-side, no server route.
- Colours are collision-free: hash to a starting palette slot, then linear-probe
  to the first free slot in server order (deterministic; a spec pins six
  distinct swatches for two ids that collide under plain hashing). A live review
  caught two portfolios sharing a hue; the probe fixed it.
- The meta line reads "Gain over time · as of close {latest snapshot date}"; the
  table above shows live prints. The settled-chart vs live-table duality is
  intentional.

## Verification

- Backend: **786 passed** (12 new: write-if-absent idempotency, 15:00-vs-16:20 ET
  guard, missing-close null semantics, empty-store endpoint, route order,
  retrospective on mocked bulk data, refresh wiring + failure containment).
- Frontend: **254 passed** (8 new specs).
- Live smoke recorded the first real snapshot (close **2026-10-12**, all six
  portfolios, full coverage); a live browser check rendered 6 solid + 6 dashed
  datasets over 260 dates with 6 distinct colours. Solid series hold exactly
  one point (today's snapshot) by design until history accrues.
- Commit `756f8e7` (feature).

## Deferred / not included

- Evening (~22:30) snapshot task so same-day closes land sooner; today the 9:00
  run records the latest settled close (the previous session unless an
  after-close refresh ran).
- %-return toggle and range presets (1M/3M/1Y/ALL) - the panel ships $ gains
  per the approved spec.
