---
type: source
title: "Portfolio performance — single aggregate total line and range views"
status: evergreen
created: 2026-10-12
updated: 2026-10-12
source_kind: decision
tags:
  - source
  - decision
  - portfolio
  - chart-ux
---

# Portfolio performance — single aggregate total line and range views

The gain chart's per-portfolio lines were replaced by ONE **aggregate total
gain line** for the selected set: the change in total gain of every selected
portfolio combined ($ on y, date on x). The retrospective data stays part of
the dataset (it fills dates that have no recorded snapshot); the
per-portfolio checkbox selector stays (it picks which portfolios feed the
total), and the Chart.js legend is off (a single line is self-evident).

## Aggregate semantics

For every date in the union of the selected portfolios' dates:

- total(d) = the sum over selected portfolios of the best available gain for
  d: the recorded snapshot gain when that portfolio has one, else its
  retrospective gain (a snapshot wins when both exist for a date).
- If ANY selected portfolio has no point or a null gain for d, the total for
  d is **null** - rendered as a gap (`spanGaps: false`), never a partial
  sum. This is the project's "a missing close nulls the portfolio total"
  rule extended across portfolios.
- Portfolio histories start on different dates (live store: the Fidelity
  accounts ~2026-02-09, Important Earnings ~2026-06-12, Watchlist
  ~2026-07-10; Moomoo is complete). The aggregate line therefore *starts*
  where every selected portfolio has data - leading gaps, not interior
  partial sums.

## One line, two stretches

A single dataset with a scriptable `segment.borderDash`: dashed while the
date is retrospective-only, solid from the first recorded snapshot date
onward (`ctx.p0DataIndex < firstSlot` -> dashed). Verified against real
Chart.js 4.4.1, not just the config stub: a runtime probe shows the real
segment context carries `p0DataIndex`, and the resolved split is two
sub-segments (dash + solid); a pixel diff of a transition capture against
an all-dashed control differs exactly at the dash gap inside the solid
stretch. With one recorded snapshot (2026-10-12), the visible line is fully
dashed; the solid stretch grows as snapshots accrue. The note line under
the chart states the convention ("Solid = recorded settled-close snapshots;
dashed = retrospective estimate from current holdings. Snapshots begin
{date}."), with an honest retro-only variant when nothing is recorded.
Tooltips append "(retrospective)" to estimated points.

## Range views (x-axis)

Ticker-style presets **1W / 1M / 3M / 6M / 1Y / ALL** (window = dates >= the
plotted series' max date - N days; ALL = everything; persisted at
`localStorage["pfHistoryRange"]`, default ALL; an invalid stored value
falls back to ALL). No 1D view: history is one point per settled close, so
an intraday view has nothing to plot (intraday capture would be a separate
feature).

Tick labels:

- Long windows (6M/1Y/ALL) tick **once per calendar month**: month starts
  are filtered in `afterBuildTicks` (no autoSkip sampling, which could
  duplicate or skip months). The window's first label anchors its month
  only when it is not crowded against the next boundary (day <= 7, or >= 12
  labels clear, or no boundary at all) - a lone Sep 30 before an Oct 1 tick
  is dropped.
- Short windows (1W/1M/3M) keep sampled autoSkip ticks capped at 8-9, MM-DD
  labels, no rotation.

## Verification

- Frontend: **261 passed / 0 failed**; the portfolio-history spec grew
  8 -> 15 (aggregate sum + snapshot-over-retro precedence, null-total gaps,
  dash segments, range windows + persistence, the month-tick filter incl.
  the crowded leading-label drop, empty states, CDN-missing note, swatch
  distinctness).
- Real-Chart.js runtime probe + pixel diff (above); live smoke against the
  running app (single dataset; the selected total equalled the sum of the
  stored snapshot gains, e.g. -3,885.63 across the real accounts; range
  windows, persistence keys, and tooltip tags verified).
- Commit `b4874ea` (feature).

## Behaviour notes

- The range window anchors to the max date of the *selected* set (all
  portfolios share the close calendar, so this is stable in practice).
- The line is dollar gain; a %-return toggle remains out of scope (noted in
  the earlier decision page).
- No backend change: `GET /api/portfolios/history` is unchanged; the
  aggregation is client-side.

Related:
[[sources/decision__portfolio-history-settled-close-snapshots-and-gain-chart-2026-10-12|Portfolio history — settled-close snapshots and the gain chart]].
