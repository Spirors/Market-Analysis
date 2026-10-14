---
type: source
title: "News direction lexicon expansion #2 + a stored-event re-tag path"
status: evergreen
created: 2026-10-14
updated: 2026-10-14
source_kind: decision
tags:
  - source
  - decision
  - news
  - ai-gauge
---

# News direction lexicon expansion #2 + a stored-event re-tag path

The AI capex-cycle gauge moved right ("Healthy expansion", score 30.2) while
most AI stocks were tumbling. The audit found both causes in the news leg, not
in the momentum legs.

## What the audit found

- **The direction lexicon scored the fresh bad news neutral.** The four
  freshest negative AI stories (Oct 9-14: CoreWeave credit-market stress,
  "Iran threat puts AI stocks at risk", "Nvidia and AMD shares fall", "Firmus
  scraps its listing") all stored `direction: neutral` and contributed 0 to
  the news leg - `BEARISH_TERMS` lacked plain price-action verbs (`fall`,
  `drop`) and narrator nouns (`worry`, `threat`, `scrap`). The +60 news score
  was carried by three older bullish events (two opinion columns plus one
  user-edited row) against a single bearish one.
- **A whole bearish block aged out of the 30-day window at once.** The window
  is a deliberate contract
  ([[sources/project_rules__archive__decisions__ai-gauge-lookback-window-30-days-2026-09-09|AI gauge lookback window = 30 days]]);
  on Oct 14 the Sep-14 bearish events expired, swinging the raw news score
  -50 -> +60 (about +33 score points) with no change in the news itself.
  Design behavior - not changed here.
- **The ROC legs lag by construction.** Cohort ROC is a ~3-month measure; a
  few down days barely move it. Not a defect.

## Decisions

1. **Expand `BEARISH_TERMS` with price-action verbs + narrator nouns.** Added
   `fall/drop/sink/slide/slip/retreat/decline/stumble` (the bearish mirror of
   the bullish `jump/climb/rise/gain/advance` block) plus
   `worry/threat/stress/scrap/at risk`, following the
   [[sources/project_rules__archive__decisions__news-heuristic-expansion-noun-heavy-bearish-ai-capex-coverage-2026-09-09|2026-09-09 noun-heavy expansion]]
   precedent. Accepted tradeoff: bag-of-words false positives on some macro
   phrasings ("unemployment fell") - the same class of tradeoff as the
   existing lists.
2. **Add a re-tag path for stored events (`python run.py --retag-events`).**
   Stored `direction` is computed at ingest and only recomputed when the same
   link is re-fetched (48h ingest window), so a lexicon fix cannot reach rows
   already on disk. `store.retag_live_events` recomputes the heuristic
   dimensions for rows whose `source` is a live feed, honours the
   `user_edited` lock, and never touches hand-tagged seed rows. The gauge's
   serve-time recompute picks the updated rows up on the next dashboard load -
   no restart or full refresh needed.

## Outcome

- Live retag: 318 scanned / 18 updated / 11 user-edited skipped / 116 seed
  rows untouched.
- Gauge after: news leg +60 -> -30 (bearish); score 30.2 "Healthy expansion"
  -> 3.2 "Balanced / mixed" - the read now reflects the negative flow the
  theme was showing.
- Commits `d503f8a` (lexicon + regression tests) and `9f8c4bd` (retag path +
  tests); targeted 208 green, full distributed suite 866 green.

## Consequences

- Any future news lexicon change ships with `--retag-events` in the same
  session; the command is the supported re-tag path, not a one-off script.
- Seeds stay hand-tagged; `user_edited` remains the override for wrong
  classifications (the Sep-17 "fears are subsiding" row stays bullish by user
  edit).
- Watch for bag-of-words false positives degrading the timeline; fix the
  lexicon, not individual rows.
