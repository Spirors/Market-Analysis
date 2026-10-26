---
type: meta
title: Wiki Log
status: evergreen
created: 2026-09-13
updated: 2026-10-20
tags:
  - meta
  - log
---

# Wiki Log

Newest completed operations appear first.


## 2026-10-26 - regime-gap anomaly: scheduled logs were blind; fixed + failure logging

- Operation: `session-end-20261026-regime-log-visibility`.
- Symptom: no regime report on 2026-10-18 and 2026-10-19 while the rest of each
  `--refresh` completed; nothing to diagnose from.
- Root cause (reproduced with a hidden-launch probe): under `wscript.exe` the
  interpreter starts with invalid std handles. `_setup_logfile` only did
  `os.dup2`, which redirects the C descriptors (children) but leaves
  `sys.stdout`/`sys.stderr` wrapping the dead handle - every Python-level print
  was dropped and each scheduled log held only a 201-byte `lost sys.stderr`
  artifact (all `data/logs/*.log` since 2026-09-25).
- Fix: `7591740` rebinds the Python streams after the `dup2` (dead-handle
  flush/dup2 are best-effort); the hidden probe now logs real output.
  `ceca8ab` logs every `DetectorRunner` failure path (timeout, spawn error,
  non-zero exit with stderr tail, exit 0 with no report); the error was
  previously returned but never logged.
- Detector rerun into a scratch dir is green in 6 s (9 ETFs, composite 55.2,
  Contraction), so the 10-18/19 misses were transient data-source failures and
  cannot be backfilled without fabricating history. The next occurrence is now
  diagnosable.
- Tests: `879 passed` (`pytest -q -n auto`, 84 s) - the 873 baseline plus 6 new
  (dead-std-handle log capture + 3 runner-logging cases).
- Healthcheck: the screenshot's check (1 day / 4 h grace, green) is consistent -
  last ping is the 08:43Z run; the 12:00Z attempt lands ~16:00Z by design. Its
  ping URL is a bearer capability: rotate the check if that image is shared.
- Pushed together with this entry.

## 2026-10-26 - weekly scheduled-pipeline health check: all lanes green

- Operation: `session-end-20261026-weekly-health-check`.
- Scope (read-only): GitHub Actions `capture.yml` on `Spirors/Market-Analysis`,
  the four local `MarketAnalysis-*` tasks, and the private data repo
  `Spirors/Market-Analysis-Data`.
- Cloud: **23 scheduled attempts 2026-10-19..26, 22 green, 1 red** - the red is
  `39453109698` (2026-10-20 15:57Z), the push race fixed the same day (`fc52a73`,
  verified by dispatch `39506876448`). Every day 2026-10-19..25 got all three
  attempts; 2026-10-26 had two by check time (the 12:00Z slot lands ~16:00Z).
  Runs still land +4-5 h after their cron slots (tolerated by design).
- Data repo: 37 status records (successful runs only export one), **all
  `ok=true`**; `captures/history/` holds every US trading day 2026-10-12..23
  exactly once (10 files); latest status `40294126067-1` ok,
  `latest_close_date` `2026-10-23`, `new_events` 0 (Monday, pre-close);
  `state/` commits daily 2026-10-19..26, `state/portfolio_history.json` matches
  the local snapshots (10 dates). Local clone 0/0 after the 10:50 sync.
- Local tasks: last boot 2026-10-26 10:43; the missed 09:00/09:30 slots
  caught up at 10:50:23 (`refresh-20261026.log`, `news-refresh-20261026.log`,
  `sync-20261026.log`, DailyRefresh Last Result 0). Full refresh wrote
  `macro_regime_2026-10-26_105038.json`; dashboard `as_of` 14:50Z with full
  coverage (market 25/25, breadth 16/16, sectors 12/12). Artifacts exist for
  every day 2026-10-19..26; all four tasks carry `StartWhenAvailable=true`
  (catch-up after a late boot), `InteractiveToken` (no runs while logged off).
- Soft anomaly: no regime report was produced on 2026-10-18 and 2026-10-19
  (the detector returned no report; the rest of the refresh completed and the
  card served the previous report, by design). The latest report is 2026-10-26
  10:50; `REGIME_MAX_AGE_DAYS = 3` would flag only after 2026-10-29.
- Not verifiable locally: healthchecks.io heartbeat state (secret-only) and the
  still-gated backup destination. Per-run Task Scheduler history is
  unavailable (operational log disabled), so local health is artifact-based.
- Note, not a failure: the public repo is 5 `events: auto-commit` commits ahead
  of `origin/main` - only `EventsCommit` writes them, sessions push.

## 2026-10-20 - local `Sync` push hardened with the same retry+rebase

- Operation: `session-end-20261020-sync-push-retry`.
- Change (`669969e`): `run.py` gained `_push_with_rebase` - up to 5 attempts,
  `git fetch` + `git rebase @{u}` between tries, and `git rebase --abort` plus a
  manual-resolution message if a rebase ever conflicts. Both push sites in
  `sync_data_repo` (the stranded-commit recovery and the normal commit+push) use
  it. Never force-pushes.
- Why: the capture workflow pushes `captures/**` to the same branch, so a
  capture landing between sync's opening `pull --rebase` and its push made the
  push a non-fast-forward - the mirror of run `39453109698`.
- Tests (`tests/test_run_sync.py`, 7 pass):
  `test_push_with_rebase_recovers_from_a_concurrent_capture` asserts an
  unguarded `push --dry-run` is rejected, then that the helper lands both
  commits with the state commit still touching only `state/events.json`;
  `test_sync_retries_when_a_capture_lands_mid_run` races a real capture push
  into the fold hook and drives the whole `sync_data_repo` flow green.
- Accepted gap: a capture that lands mid-run is folded on the next sync, not
  retroactively - the fold runs before the push.

## 2026-10-20 - capture push race (run 39453109698) diagnosed; retry+rebase fix

- Operation: `session-end-20261020-capture-push-race-fix`.
- Failure: scheduled run `39453109698` (2026-10-20 15:57Z) died at `Commit and
  push captures` after 2m09s: `! [rejected] HEAD -> main (fetch first)`. Every
  earlier step passed - refresh ok, export wrote 2 files / skipped 6 / 2 new
  events (latest close `2026-10-19`), validate ok (46 capture files).
- Root cause: the local `Sync` task pushed `d752c54 state: sync 2026-10-20
  11:59` (= 15:59:10Z) 14 s before the workflow's push; the run had cloned
  `main` at `e78549c` two minutes earlier. Structural, not random: the 12:00 UTC
  attempt lands ~15:57Z, which is the Sync slot.
- Data impact: none durable. `history/2026-10-19.json` was already published by
  `39392756627-1` (08:21Z, ok); only that run's events snapshot (NEW-only diff)
  and status record were lost, and the next run re-detects events by link.
- Fix: `fc52a73` `fix(ci): retry capture push with rebase after a concurrent
  sync push` - up to 5 attempts with `git fetch` + `git rebase
  origin/<branch>` between tries. The commit sets are disjoint (`captures/`
  here, `state/` there), so the rebase cannot conflict; a fetch failure still
  aborts immediately under `set -e`.
- Verification: the race was reproduced in a throwaway bare repo - plain push
  rejected with the identical message, the loop rebased and pushed, the capture
  commit still touched only `captures/`, and the sync commit survived. Pushed
  `74cea72..fc52a73`; manual dispatch `39506876448` (private/repo) green -
  `Commit and push captures`, freshness gate and fold rehearsal all success;
  private `main` head `9f5889d`, latest status ok, close `2026-10-20`,
  `check_capture_freshness.py` ok (0.0 h).
- Open: the local `Sync` push still has the mirror race inside its own window
  (milliseconds after its initial pull); it fails with a manual-resolution
  message and was not changed this session.

## 2026-10-18 - capture pipeline verified steady-state; phase-1 dry-run workflow retired

- Operation: `session-end-20261018-capture-verify-cleanup` (save).
- Verification (all read-only): `capture.yml` scheduled runs are **12/12
  green** since the `d95aaed` fix (three attempts/day, 2026-10-15 ->
  2026-10-18, every run `schedule` on `main`); the private repo `main` head
  is `576ac09` (`state: sync 2026-10-18 15:25`, pushed by the local Sync
  task) with captures through the `2026-10-16` settled close
  (`history/2026-10-16.json` written by `21db11f`); latest status
  `39138591368-1` ok=True (`new_events` 1, `new_history_dates` []);
  `check_capture_freshness.py` -> ok (age 4.9 h);
  `cloud_export.py validate` -> ok (33 capture files); fold rehearsal into
  a scratch data dir added history `2026-10-12..16` + 19 events and the
  second fold was a clean no-op; local `portfolio_history` snapshots
  `2026-10-12..16` agree.
- Suites: backend **873 passed** (distributed `-n auto`, 100.9 s; known
  cosmetic auto-reap stderr line), frontend **261 passed** (2.3 min).
- Cleanup: `.github/workflows/pipeline-dry-run.yml` retired - its phase-1
  manual/synthetic proof is covered by `capture.yml` local mode
  (`ed7e8d7`); `scripts/ci_dry_run.py` docstring retargeted (`92f4d23`);
  stale local `spike/` scratch removed; fully-merged remote branches
  `ci/dry-run-phase1` + `ci/capture-phase2` deleted (`spike/gha-probe` +
  `parked/hosting-phase1` kept as evidence/parked).
- Remaining: backup destination (still gated).


## 2026-10-15 - data-repo default branch -> `main`; 12:00Z attempt landed green

- Operation: `session-end-20261015-data-repo-default` (save).
- `Spirors/Market-Analysis-Data` default branch changed `dry-run` -> `main`
  (owner request - the owner had opened `dry-run` and seen synthetic data).
  Applied via API PATCH with the locally stored git credential (never printed);
  verified `git ls-remote --symref` -> `refs/heads/main`. `dry-run` remains for
  the synthetic path; the workflow is unaffected (it checks out its target
  branch explicitly).
- Today's 12:00Z attempt (run `38764279582`, fired 15:53Z, +3h53m late) landed
  fully green: pushed `cc335eb` (2 new events; history untouched -
  write-if-absent no-op), status ok, `latest_close_date` `2026-10-14`. All
  three attempts fired ~+4-5 h after their cron slots (GitHub queue behaviour;
  tolerated by design).
- Watch: Yahoo EOD tail (attempts cover); backup destination still gated.


## 2026-10-15 - scheduled capture proven green; 2026-10-14 close published

- Operation: `session-end-20261015-schedule-proven` (save).
- Runs `38687648085` (05:35Z) and `38703529900` (08:08Z): both fully green with
  the production path - private clone + repo-data seed ran (skipped pre-fix),
  export / validate / commit+push / freshness / fold-rehearsal all ok, success
  heartbeat sent. Both still fired ~4.5-5 h after their cron slots.
- Published: `0e9c53b` (history `2026-10-14` + events) and `b03e7cd` (events
  only - write-if-absent made the second attempt's history a no-op, as
  designed) on the data repo `main`; latest status ok, `latest_close_date =
  2026-10-14`, mode `private`.
- Prerequisite found by the re-check: `d95aaed` had sat unpushed (local 9
  commits ahead of `origin/main`); pushed + verified live via the contents API
  before the run window. The push itself triggers no workflow (schedule /
  `ci/**` / dispatch only).
- Watch: the 12:00 UTC attempt still pending at check time (11:17 ET);
  data-repo default branch still `dry-run`.


## 2026-10-14 - gauge news leg: recency decay (7-day half-life)

- Operation: `session-end-20261014-gauge-recency-decay` (save).
- Follow-up to the same-day gauge audit: the news leg's 30-day window expiry
  cliff is smoothed by exponential decay - each AI-news event's weight
  multiplies by 0.5 ** (age_days / AI_SENTIMENT_NEWS_HALF_LIFE_DAYS), new
  knob `AI_SENTIMENT_NEWS_HALF_LIFE_DAYS = 7`. Window, impact weights, cap
  and verdict cutoffs unchanged; events with a missing/unparseable
  `published` are excluded (age unknowable). `/api/meta` carries the knob;
  the gauge tooltip explains the decay.
- Verified: live recompute news leg -30 -> -55.6, gauge 3.2 -> -4.5
  "Balanced / mixed"; backend targeted 83 + full distributed 873 green;
  full frontend Playwright suite 261 passed.
- Commit `1fa3e4c` (feat(ai-gauge)); decision page updated in place.

## 2026-10-14 - gauge audit: news direction lexicon expansion #2 + --retag-events

- Operation: `session-end-20261014-gauge-news-direction-fix` (save).
- Audit: the AI capex-cycle gauge read "Healthy expansion" (30.2) while AI
  stocks tumbled. Two causes: (1) the four freshest negative AI headlines
  (Oct 9-14: CoreWeave credit stress, Iran threat, Nvidia/AMD fall, Firmus
  listing scrapped) all stored `direction: neutral` - `BEARISH_TERMS` lacked
  plain price-action verbs (`fall`, `drop`) and nouns (`worry`, `threat`,
  `scrap`, `at risk`) - so the +60 news leg was carried by older bullish
  rows; (2) four bearish Sep-14 events aged out of the 30-day window at
  once, swinging the raw news score -50 -> +60 (+33 score). (2) is design;
  (1) was the defect.
- Fix `d503f8a` (lexicon expansion #2 + regression tests on the four
  observed headlines). Fix `9f8c4bd`: new `python run.py --retag-events`
  (`store.retag_live_events`) recomputes heuristic dimensions for stored
  live-feed rows only - honours `user_edited`, never touches seeds.
- Verified: live retag 318 scanned / 18 updated / 11 user-edited skipped /
  116 seed rows untouched; news leg +60 -> -30 (bearish); gauge 30.2
  "Healthy expansion" -> 3.2 "Balanced / mixed". Targeted 208 green; full
  distributed suite 866 green (one pre-existing portfolio flake, clean on
  rerun).
- Data note: `data/events.json` carries the retag result; left for the
  events auto-commit pipeline, not hand-committed.

## 2026-10-14 - first scheduled capture runs failed red; fixed

- Operation: `session-end-20261014-schedule-inputs-fix` (save).
- Both first-ever scheduled attempts failed at `Export captures` -
  `38535888734` (08:32Z) and `38595174693` (16:06Z). Cause: `schedule` events
  carry no `workflow_dispatch` inputs, so `REPO_MODE`/`DATA_MODE` evaluated
  empty - both data-repo setup steps skipped, the seed fell through to
  synthetic, and `cloud_export.py export --mode ""` died in argparse (exit 2;
  reproduced locally). The refresh itself was green in both runs; nothing was
  written or pushed. All prior green runs were manual dispatches, which masked
  the gap.
- Fix `d95aaed`: env fallbacks `inputs.repo_mode || 'private'` and
  `inputs.data || 'repo'` - scheduled runs now run production (private repo,
  repo data -> `main`); push and dispatch defaults unchanged.
- Watch: the next scheduled attempt (01:00/03:00/12:00 UTC) is the first real
  proof; last good capture remains `479e4c0` (run `38499084197-1`,
  2026-10-13). Also observed: both attempts fired hours off their cron slots.


## 2026-10-13 - hosting phase 3 steps 4-5: verification + activation COMPLETE

- Operation: `session-end-20261013-hosting-step45` (save).
- Step 4 monitoring: healthchecks check (period 1 day / grace 4 h) + repo secret
  `HEALTHCHECK_URL` + GitHub failure emails; controlled failure verified
  end-to-end - run `38498568442` failed red at the state restore in 25 s
  (`pull-state: INCOMPLETE restore` as designed), fail heartbeat delivered;
  nothing written.
- Hardening shipped (`de08bc3`, `6a538ad`, `1f2001e`, `b0ce561`; suite 858
  green): stranded-push recovery; strict restore completeness (fail-loud
  `pull-state`); mirror extended (six state files); `scripts/backup_data.py`
  (CRC-validated zips + retention; destination configurable - its TASK is not
  activated until a destination is supplied).
- Oct-13 close: local refresh recorded `2026-10-13` (live; coverage 38/38;
  the 10-12 entry untouched); six-file state sync `bbaf0e9`.
- Green verification: run `38499084197` -> capture commit `479e4c0` on `main`
  (`captures/history/2026-10-13.json`, events 0, status ok; validate ok;
  JSON-equal to the local entry; no synthetic; `dry-run` untouched). Local
  fold = clean no-op (data already present); scratch fold demo: existing 2 /
  added none.
- Activation (owner-approved): `capture.yml` schedules ON - `0 1`, `0 3`,
  `0 12` UTC (`3b352e3`); weekends/holidays store the most recent settled
  session; write-if-absent + skip-existing make repeats safe no-ops. Local
  task `MarketAnalysis-Sync` installed (daily 09:30 local, hidden wscript
  launcher, same XML pattern as the app tasks) and live-tested: the fired run
  spawned python, exited cleanly, and updated the clone's `FETCH_HEAD`
  (proving the task resolves `MARKET_ANALYSIS_DATA_REPO`).
- Corrections: the state mirror now carries SIX files (step-3 notes cited
  four - pre-extension).
- Remaining risks: backup destination undecided; scheduled-task logs still
  carry only the known shutdown-noise pattern (real execution proven via
  `FETCH_HEAD`/timestamps); Yahoo EOD tail + rare overnight misses (covered by
  the three attempts + the local morning backstop); data-repo default branch
  still `dry-run`; public-repo 60-day activity rule (mitigated by ongoing
  pushes + healthchecks).


## 2026-10-13 - hosting phase 3 step 3: recovery + resilience suite verified

- Operation: `session-end-20261013-hosting-step3` (save).
- Scope: testing only; scratch trees under `%TEMP%/opencode/step3/` (never the
  live data dir - 939/939 files byte-identical before/after; no stray
  processes; private repo clone and public repo unchanged).
- Recovery (18/18 checks): the state mirror restores all four state files (six since the step-5 extension)
  (3 byte-identical to local; `events.json` JSON-identical - canonical
  re-serialization); captures alone rebuild `portfolio_history` for 10-12 and
  nothing else; malformed state/captures refuse all-or-nothing (bytes
  unchanged); missing files are tolerated (partial restore - flagged risk).
- Safety: history write-if-absent held (a mutated local entry survived a
  fold); user-edited events survived same-link filtering AND cross-source
  title-similarity merges (only `updated_at` touched); duplicate captures
  deduped to a single insert.
- Sync simulations: healthy + idempotent OK; divergent edits -> rebase
  conflict -> refusal with manual-resolution guidance, nothing applied/pushed,
  rebase abort restores. **Finding: after a failed push, a re-run prints
  "nothing to publish" and does NOT re-push the stranded commit** (manual
  `git push` is the remedy; a run.py hardening is recommended before step 5).
- Backup: full data-dir zip (939 files, 21.3 MB) -> restore -> 0 mismatches.
  Recommended: automate at step 5 to a second physical destination (the
  private repo already mirrors the four state files off-site (six since the step-5 extension)).
- Item 5 (not recoverable from the private repo today): `watchlist.json`
  (empty), `earnings_removed.json` (15 tickers) - user state, unmirrored;
  caches (`dashboard.json`, `ai_valuation.json`, `bottleneck_jobs.json`) -
  regenerable; `analysis.db` - obsolete legacy (layer removed); `news.db.
  migrated` - 0-byte marker. Correction to earlier notes: suppressions ride
  `events.json` (mirrored); standalone `suppressed_sources.json` is unused.
- Yahoo EOD timing (librarian brief; sources in the brief/log): no official
  docs; same-day bar publication is lazy/variable, observed tail ~20:13-20:40
  ET (our probes); rare next-morning misses; bars are revised after first
  publication; volume-only rows occur (accept only non-null OHLC).
  Recommended two-attempt cloud schedule: primary 01:00 UTC + retry 03:00 UTC
  (write-if-absent makes redundant attempts safe; weekends/holidays: the
  writer already records the most recent settled session); optional third
  pre-open attempt (~11-12 UTC) for PC-off overnight coverage. Owner decision
  pending.


## 2026-10-13 - hosting phase 3 step 2: first production capture verified

- Operation: `session-end-20261013-hosting-step2` (save).
- Production run `38490902295` (workflow_dispatch, main, green, 2m16s) pushed
  capture commit `5f38214` to private `main`: `history/2026-10-12.json` (real
  6-portfolio entry, JSON-equal to local), `events/38490902295-1.json` (0 new),
  `_status/...json` (ok=true). `validate` ok=True; run artifacts: none; public
  repo unchanged.
- Finding (timing, not a defect): `2026-10-13` was NOT captured - at 20:34 ET
  the bulk daily series still ended at 10-12; a 20:40 ET probe showed the
  10-13 bar available. The ~16:15 ET settle-guard writer correctly records
  only source-available closes (never fabricates); the date lands via the next
  refresh + a subsequent cloud export (write-if-absent). Watch item for the
  Step-5 schedule time.
- Local syncs: first attempt refused cleanly (the env var is not visible to
  pre-existing shells - the fail-safe held); retry pulled the capture commit
  and folded: history existing 10-12, added none; events 0; "sync: nothing to
  publish (state unchanged)"; local sha256s unchanged. Second sync identical
  (idempotent); scratch fold demo + `--expect-noop` both exit 0.
- No synthetic in production: `merge-base(main, dry-run)` = none; no `dry-run`
  key in any capture; `dry-run` ref unchanged (`b03f3b5`).


## 2026-10-13 - hosting phase 3 step 1: real state/ published to the private repo

- Operation: `session-end-20261013-hosting-step1` (save).
- Scope: owner approved Step 1 only. Set `MARKET_ANALYSIS_DATA_REPO` (User
  scope) to the sibling clone, and the clone's commit identity to the user's
  own (`Spirors <siyuanzou99@gmail.com>`).
- Pre-flight: local state validated (4 files; JSON+shape ok; 6 portfolios,
  1 history snapshot `2026-10-12`, 307 events, 2 topic keys; sha256 recorded);
  raw backup + manifests in `%TEMP%/opencode/state-backup-2026-10-13/`;
  private repo re-confirmed not publicly visible (unauth API 404).
- One `python run.py --sync`: published `state/` to the private `main` as root
  commit `60ab0d1` "state: sync 2026-10-13 19:56 [skip ci]" (exactly the four
  state files); the push created `origin/main`; `dry-run` unchanged
  (`b03f3b5`); `merge-base main dry-run` shows NO common history.
- Verified: local sha256s byte-identical before/after (nothing local touched);
  the published copy is JSON-equal to local (3/4 files byte-identical;
  `events.json` differs only in canonical re-serialization); the public repo is
  unchanged; no schedules/monitoring/captures touched.
- Observations for later: the local schedule has NO post-close full refresh
  (DailyRefresh 09:00 + catch-up; NewsRefresh 4-hourly, news-only), so a
  same-day close snapshot lags until the next post-16:15 refresh - the cloud
  capture slot (22:00 UTC) fills exactly that gap; scheduled-task logs contain
  only Python shutdown noise ("lost sys.stderr") - flagged for a look; the
  data repo's default branch is still `dry-run` (flip to `main` for hygiene);
  `suppressed_sources.json` (empty today) is not in the state mirror.


## 2026-10-13 - hosting phase 2 validation: private transport verified; phase 3 prepared (awaiting approval)

- Operation: `session-end-20261013-hosting-validation` (save).
- Owner ran the private-transport validation: workflow `Capture (private data
  repo)` via manual dispatch on `main` - run 38484530937, success, mode
  `private`, data `synthetic`, target branch `dry-run`.
- Verified from the local clone (read-only) + the exports:
  - `refs/heads/dry-run` = one commit `capture 38484530937-1 [skip ci]` with
    exactly `captures/history/2026-10-13.json`, `captures/events/
    38484530937-1.json` (0 new events that run - no fresh news since the last
    local fetch; the diff mechanism itself is test-covered), and
    `captures/_status/38484530937-1.json` (ok=true; sanitized - no
    holdings/values).
  - **No `main` ref in the private repo** - production branch untouched.
  - `scripts/cloud_export.py validate` -> ok=True; folding the captures into a
    scratch dir added exactly the date; a second fold was byte-stable (no-op) -
    idempotency confirmed.
- Phase 3 prepared (NOT executed): (1) local sync setup (env
  `MARKET_ANALYSIS_DATA_REPO` + first `run.py --sync` publishes `state/` with
  real data to the private `main`); (2) first production capture (manual,
  `repo_mode=private`, `data=repo`); (3) backup/recovery drill + the
  events-push decision; (4) monitoring activation (healthchecks + GitHub
  notifications); (5) schedule activation (daily post-close cron + a local
  sync task). Risks tracked: yfinance is unofficial, the 60-day
  scheduled-workflow auto-disable on public repos (needs repo activity),
  PAT expiry/rotation, dual-writer coexistence (reconciled by design).


## 2026-10-13 - hosting phase 2: private data-repo transport implemented + tested

- Operation: `session-end-20261013-hosting-phase2` (save).
- Owner approved GitHub Actions + the private repo `Spirors/Market-Analysis-Data`
  (no Supabase/Oracle) and set the missed-date policy: never fabricate;
  backfill only when accurate reconstruction is possible (historical holdings,
  prices, cash flows); otherwise keep the gap.
- Shipped on `main` (pushed; tip `dcb876c`): `b2faed2` conservative backfill
  for missed settled dates (reconstruct only when the current book provably
  equals the last stored entry - shares/cash/cost exact; else omit the
  portfolio; entries marked `backfilled: true`; write-if-absent);
  `39be4c7` `app/sync.py` transport core + `scripts/cloud_export.py` CLI
  (write-once history captures, events diffed by link, sanitized status; the
  fold validates everything first and applies all-or-nothing; state mirror
  both ways); `59a0e6d` + `5f1e628` `run.py --sync` local flow (pull --rebase,
  fold, publish `state/**` only; conflicts abort loudly, never force; a fresh
  empty data repo is handled); `c455c9b` freshness gate; `66feba9` + `27fda7b`
  `.github/workflows/capture.yml` (manual + `ci/**` only; no `schedule:`;
  synthetic pinned to the `dry-run` branch; commits restricted to
  `captures/**`; no artifacts; token never logged; heartbeats).
- Invariants: disjoint scopes (cloud `captures/**`, local `state/**`) so
  conflicts cannot occur silently; all public outputs sanitized (no
  holdings/values in logs, commits, or artifacts); the local app and fallback
  are untouched.
- Evidence: backend suite **846 passed** (812 + 34 new); CI green - the
  capture workflow ran on `ci/capture-phase2` @ `5f1e628` (success; the
  phase-1 dry-run also re-ran green on that push); `origin/main` == `dcb876c`.
- State: owner created the private repo + secrets and a local clone at
  `C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis-Data`
  (verified private; `DATA_REPO_TOKEN` reported set). No schedules active;
  no real data migrated. Next: the private-mode validation run, then
  production activation on explicit approval.


## 2026-10-13 - hosting phase 1: GitHub Actions dry-run + cross-platform lockfile fix on main

- Operation: `session-end-20261013-hosting-phase1` (save).
- Owner approved GitHub Actions as the runner; Oracle dropped as primary.
- Storage evaluation (git-only private data repo vs GHA+Supabase): **git-only
  recommended** - one invariant kills edit conflicts by construction (the
  cloud writes only `captures/**`; the local machine is the sole writer of
  `data/**`); the capture log is the backup; Supabase adds a ~7-day pause
  risk, no backups, and re-implements in SQL a merge the code already has.
  **Pending owner approval**; open decision: missed-date catch-up policy for
  the snapshot writer (it records only the latest eligible close; a missed
  run leaves a permanent gap).
- Phase 1 shipped on `main` (pushed): `b950f74` cross-platform `_pid_alive`
  (POSIX `os.kill` branch + never-raise; cherry-picked from
  `parked/hosting-phase1`, +5 tests); `aea4429` synthetic seed/validate
  helper `scripts/ci_dry_run.py` (+21 tests; refuses to overwrite existing
  data); `b609345` `.github/workflows/pipeline-dry-run.yml` (manual
  `workflow_dispatch` + `ci/**` push only; **no `schedule:`**; read-only
  permissions; heartbeat steps no-op until `HEALTHCHECK_URL` is set).
- Validation: backend suite **812 passed** (distributed; 786 + 26 new); local
  scratch-clone rehearsal (synthetic data) - refresh OK, snapshot OK,
  double-run idempotency OK (no rewrites, no lost dates), dead-lock heal OK;
  CI run **38472612111 success**; `origin/main` == `b609345`; zero runs fire
  on `main` pushes (verified).
- No schedules active; no real portfolio data migrated. Testing branch
  `ci/dry-run-phase1` remains on origin. Owner config before phase 2: private
  data repo + fine-grained PAT (`DATA_REPO_TOKEN`), optional `HEALTHCHECK_URL`.


## 2026-10-13 - hosting the pipeline off-PC: verified GitHub Actions spike + proposed architecture (pending decision)

- Operation: `session-end-20261013-hosting-exploration` (save).
- Question explored: how to run the three scheduled jobs (DailyRefresh /
  NewsRefresh / EventsCommit) without the PC. Research: Supabase free as a
  central store (500 MB DB, 5 GB egress, pauses after ~7 days of low DB
  activity, no automatic backups, pg_cron UTC-only, no Python in Edge
  Functions), GitHub Actions as the runner (public repo, free minutes), and
  Oracle Always Free as fallback. Yahoo-from-cloud-IP was the load-bearing
  unknown, so it was tested for real.
- Spike (verified; both runs green): branch `spike/gha-probe` ran the real
  pipeline on `ubuntu-latest` / Python 3.12 - yfinance works from the runner
  IP (SPY 777.93, `fast_info` ok, 1.41 s), regime detector ok (2.9 s,
  Concentration/HIGH, no extra deps), news refresh ok, full `run.py
  --refresh` 57.6 s with a complete dashboard and a correct prior-close
  portfolio snapshot, `--commit-events` ok (needs a git identity). The known
  Linux blocker reproduced exactly: a fresh `data/refresh.lock` crashes
  `--refresh`/`--news-refresh` with `AttributeError: ctypes.windll`
  (app/lockfile.py:51) and the lock persists; a stale-by-age lock heals.
  FRED spot timed out for all three series from the runner (non-fatal;
  degrade-to-null held). Evidence: `downloaded_files/gha-spike/`; runs
  38457536801 / 38458116291.
- Proposed architecture (memo delivered; **pending owner decision**): cloud
  captures the irreplaceable append-only stores (portfolio-history snapshots
  + new news events) and pushes portfolios/suppressions up; local keeps
  presentation (dashboard/caches/regime stay single-writer local - no second
  writer for the same numbers); Supabase free = operational store; git =
  mandatory backup + fallback; atomic versioned-bundle publishing; runner =
  GitHub Actions (spike-verified), Oracle = untested fallback. Nothing
  implemented or deployed.
- State: the earlier Linux/server Phase-1 fixes were reverted at owner
  request and parked at `parked/hosting-phase1` (4 commits: cross-platform
  `_pid_alive`, ALLOWED_HOSTS env, server-mode shutdown guard, deploy/
  scaffolding). The lockfile fix is runner-agnostic (required for any Linux
  runner); the rest is Oracle-specific. Main untouched.


## 2026-10-12 - portfolio performance chart: one aggregate total line + range views

- Operation: `session-end-20261012-portfolio-chart-rework` (save).
- The Portfolio Performance panel now plots ONE aggregate total-gain line
  for the selected portfolios (previously one solid + one dashed line
  each): per date, the snapshot gain where recorded else the retrospective,
  summed; any selected portfolio missing or null on a date makes the total
  null - a gap, never a partial sum. Dashed = retrospective-only stretch,
  solid from the first recorded snapshot (scriptable `segment.borderDash`
  on p0DataIndex, one dataset, legend off, selector row unchanged).
  Ticker-style ranges 1W/1M/3M/6M/1Y/ALL persist at
  `localStorage.pfHistoryRange`; long windows tick once per calendar month
  via an `afterBuildTicks` month-start filter (no duplicated or skipped
  month labels; a crowded leading label is dropped), short windows keep
  sampled MM-DD ticks; tooltips tag retro points. Live-data review showed
  each portfolio's history starting on a different date (leading gaps by
  design). Commit `b4874ea`.
- Evidence: frontend **261 passed / 0 failed** (portfolio-history spec
  8 -> 15); a real-Chart.js runtime probe confirmed the segment context +
  the dash/solid split, and a pixel diff of a transition capture against an
  all-dashed control differed exactly at the solid stretch; live smoke on
  the real app verified one dataset, the total equalling the sum of the
  selected snapshot gains, the range windows and the persistence keys.
- Decision page:
  [[sources/decision__portfolio-performance-single-aggregate-total-line-and-range-views-2026-10-12]].


## 2026-10-12 - portfolio history: daily settled-close snapshots + the gain chart

- Operation: `session-end-20261012-portfolio-history` (save).
- The Portfolio card gained a "Portfolio Performance" panel: total gain ($) over
  date per portfolio with a multi-select selector; solid = stored daily
  snapshots, dashed = retrospective (current holdings applied backwards,
  computed live, never stored). `data/portfolio_history.json` (user data) takes
  one write-if-absent entry per settled US close date; a partial in-session bar
  is never eligible (~16:15 ET guard) and a missing close nulls the holding AND
  the portfolio total (coverage-stamped) - never a partial sum. The writer rides
  `service.refresh_all` and shares the bulk-history cache key with enrichment;
  `GET /api/portfolios/history` serves snapshots + retrospective, registered
  ahead of the dynamic routes. A live review caught two portfolios sharing a
  chart colour; fixed with collision-free assignment (hash + linear probe).
  Commit `756f8e7`.
- Evidence: backend **786 passed** (distributed; +12), frontend **254 passed**
  (246 + 8); live smoke recorded the first real snapshot (close 2026-10-12,
  full coverage); live browser check rendered 6 solid + 6 dashed datasets over
  260 dates with 6 distinct colours.
- Decision page:
  [[sources/decision__portfolio-history-settled-close-snapshots-and-gain-chart-2026-10-12]].


## 2026-10-04 - market quotes are now live intraday (stale portfolio/dashboard closes fixed)

- Operation: `session-end-20261004-live-quotes` (save).
- Fixed the reported "portfolio last price looks a day old" bug. The shared quote
  provider `app/market.py::_quote_snapshot` derived price + daily change from
  settled daily bars, so every quote card (portfolios, indices, rates, commodities,
  futures) showed the previous session's close during a live session. It now
  composes the latest intraday 5m print (one bulk 5d/5m download across
  equities/indices/futures/crypto/foreign) with the most recent settled daily close
  strictly before that bar's session date - correct live, after close, on weekends
  and for 24/7 crypto. Fallback ladder: `fast_info` then latest daily close;
  unavailable symbols are omitted (never fabricated). `get_quotes` is now a
  per-symbol cache (`LIVE_QUOTE_TTL = 120s`) shared by dashboard/futures/portfolios;
  the explicit Refresh forces a fresh fetch (`ttl=0`). Commit `68f1538`.
- Evidence: 132 relevant backend tests pass; the 774-test backend suite passes via a
  distributed run (the serial suite aborts at ~484 tests on a **pre-existing,
  unrelated** leaked lifecycle-watchdog thread that calls `os._exit(0)` ~60s in);
  live probe returned AAPL 333.79 vs prior 330.32 (+1.05%) with graceful rate-limit
  fallback. `static/js/cards.js` tooltips updated (no longer say "fast_info is broken").
- Decision page:
  [[sources/decision__market-quotes-live-intraday-date-anchored-prior-close-2026-10-04]].


## 2026-10-04 - the last audit item (04 narrow-width) verified fine

- Operation: `session-end-20261004-04-verified` (save).
- The user visually checked the `breadth` / `breadth-ai` chart cards at narrow
  widths and reported them fine. No change needed.
- The app audit is therefore fully closed: no tracked items remain. The
  `sources/docs__audit__*` archive pages stay the reference record.

## 2026-10-04 - app audit archived into the vault (docs/audit retired)

- Operation: `ingest-20261004-audit-archive` (ingest).
- The finished app audit (`docs/audit/`) is archived here as 11 provenance-stamped
  source pages (`sources/docs__audit__*`), each captured immutably at
  `.raw/captured/<sha>.md`. They are filed under the index's `### history` group -
  one-time artifacts kept for reference, **not** part of the live knowledge base.
- Live state is `wiki/hot.md` + the code; these pages describe the code as of
  2026-09-27 and must not be read as current status. The repo copy of `docs/audit/`
  was removed on 2026-10-04 (last commit `1e03a2e`); `next-session.md` was deliberately
  NOT archived (it is an executable session prompt).
- Project status at close: all nine section audits deep-audited, the tracked
  backlog closed, frontend **246 passed / 0 failed**, backend 763 green. The only
  open item is the `04` narrow-width chart-legibility DESIGN check (needs a human
  visual pass).

## 2026-09-27 - 00-W fixed; the 04 narrow-width visual check deferred

- Operation: `session-end-20260927-00w-04` (save).
- `00-W` `739cc4c`: the portfolio `.pf-grand-total` and the bottleneck card's
  `.cov-badge` were also appended **inside** their `<h2>` (the same class as the
  fixed `00-V`). Both now render in `.card-head` beside the `h2`; the portfolio
  total's heading-inherited `letter-spacing` is pinned so the paint is unchanged,
  and `bottleneck.spec.mjs`'s selector was updated. Cache-bust `572a396`.
- `04` narrow-width chart legibility is **deferred**: it needs a human visual
  pass. The Playwright harness deliberately aborts the Chart.js CDN
  (`breadth-labels.spec.mjs:12`), so the canvases never render in tests, and
  agent-browser could not hold a viewport session in this environment. A bounded
  candidate (`.chart-box` horizontal scroll + canvas `min-width` at <=720px) is
  recorded in `docs/audit/README.md` Sec 13 for approval.
- Verified: frontend **246 passed / 0 failed**; backend **763 passed / 0 failed**.
  Canonical state: `docs/audit/README.md`.

## 2026-09-27 - runtime probes + the last of the audit surface

- Operation: `session-end-20260927-probes-surface` (save).
- Ran the live probes against a frozen detached worktree with a dead proxy (no
  live `data/` touched). `01-F1` (all histories empty -> fabricated GREEN) was
  **NOT confirmed**: the served payload degraded correctly
  (`risk = {error:"insufficient data"}`, `coverage.risk = 0/7`). `01-F7`
  (risk error clears fragility), the `08` chip-focus behaviour and the `00`
  heading-name question are now pinned by mock specs (`9e34583`).
- Closed the remaining tracked surface: `cf2f202` (08 focus restore, empty-state
  split, dead CSS), `a432e4e` (dedupe tolerance documented at the logic),
  `6e96746` (02-I: the refresh path now threads the cached valuation),
  `d533aed` (04 tooltip deps reconciled).
- The probe lane found a real a11y defect (`00-V`): the coverage/cooldown badges
  were appended **inside** the card `<h2>`, polluting the heading's accessible
  name ("Risk divergence, 2 of 3 data points available"). Fixed in `c589a95` -
  the badges now render in `.card-head` beside the `h2`, with the visual paint
  preserved. The same class remains for the portfolio grand total and the
  bottleneck badge (`00-W`, tracked).
- Housekeeping: removed a stray `static/style.css.orig` (`285d051`); ignored
  agent-browser's transient `downloaded_files/` (`866e343`).
- Verified: frontend **246 passed / 0 failed**; backend **763 passed / 0 failed**.
  Canonical state: `docs/audit/README.md`.

## 2026-09-27 - 02-O single-sources the tooltip constants; 08-U dimensions 500

- Operation: `session-end-20260927-02o-08u` (save).
- `02-O` `a8a6274` (the last deferred audit item): the AI-sentiment tooltip's
  numbers now have ONE source of truth. `app/config.py` is served read-only
  through `/api/meta`'s new `ai` block; `static/js/meta.js` exposes `aiConfig`
  with built-in defaults mirroring config; the tooltip `text` is a function
  provider that interpolates the values, so the copy cannot drift from the
  backend. With the endpoint unavailable the rendering is byte-identical to the
  previous hard-coded string, and a backend test asserts `meta.ai == config`.
- `08-U` `1eaaa51`: `POST /api/events/dimensions` with a non-string value (e.g.
  `{"category": ["macro"]}`) raised an uncaught `TypeError` in the frozenset
  membership check -> HTTP 500. Found by the runtime-probe recon, not the
  original audit. The handler now catches it and returns 400, with a regression
  test.
- Verified: frontend **242 passed / 0 failed**; backend **758 passed / 0 failed**.
  Canonical state: `docs/audit/README.md`.

## 2026-09-27 - decision round: naming, badges, the rising pin, and the Role row

- Operation: `session-end-20260927-decisions-round2` (save).
- Answered the parked + deferred decisions from `docs/audit/README.md` Sec 13.
- `06-O` `b05b00f`: the bottleneck topic card's schema-echo "Role" row (always
  "downstream") is deleted.
- `02-N` + `01-BADGE` `bc094e0`: the cohort/risk tables' "Read" header became
  "Note"; the shared coverage badge wording is now unit-neutral ("N of M data
  points available", honest for cohorts/signals/quotes alike); the `fragility`
  sub-card now shows the badge, reusing `coverage.risk` - no backend key needed.
- `02-N(a)` `fd44083`: the info button's `aria-label` is derived from the card's
  visible `<h2>` title (direct text nodes only, so injected badges and the
  portfolio grand total are excluded) - no card exposes its internal slug any
  more; the `global-refresh` and `tooltip` specs were updated with it.
- `01-RISE` `736fefe`: tests pin the asymmetric "rising" windows as intended
  (risk 62-vs-63 ROC slots; indicators 50-bar include/exclude breadth MA). The
  ROC asymmetry measurably biases `_is_rising` near thresholds and is documented
  in-code as a deliberate legacy quirk.
- `02-O` (tooltip constant de-duplication) stays deferred by decision.
- Cache-busts `936bf79`, `f990274`, `ab506c5`.
- Verified: frontend **241 passed / 0 failed**; backend **754 passed / 0 failed**.
  Canonical state: `docs/audit/README.md`.

## 2026-09-27 - long-run handoff: tooltip convergence, 06-X, and the P3 batches

- Operation: `session-end-20260927-longrun-handoff` (save).
- Worked `docs/audit/next-session.md`. Cross-section tooltip convergence
  (`fe40eed`): 26 shell reorder `title=` removed, events (2 migrated, 3 deleted)
  and portfolio/`tickerTable` migrated to the shared `attachTooltip`; documented
  natives kept (`tickerTable` arrow buttons that sit behind the Columns menu, the
  disabled reorder branch, and the `watchColors` star whose `title` must equal its
  `aria-label`). `fd25d0c` made `tooltip.js` import-safe outside a DOM - a Node
  import of `events.js` had crashed the whole Playwright collection.
- All 13 `CARD_TOOLTIPS` entries now state as-of/freshness (`2894c5e`, `3b8d5a4`).
- `06-X` (`8f40461`): a cancelled generation job is now interruptible. The job
  path is `app/topic_agent.py` (not `bottleneck.py`): the HTTP completion runs on
  an abandonable daemon thread and child processes are cancelled, killed and
  reaped; the serial lock, terminal status and atomic writes are preserved. Stub
  follow-up `dedb7b4`.
- P3 batches: `1628a14` (06-I evidence rows kept, 06-K terminal poll-failure
  panel, 06-L clipboard fallback + feedback, 06-M real `h3`/`h4` headings),
  `749a9e8` (06-J one canonical label per action), `20436cd` (02-L explicit
  unavailable state, 02-Q gauge direction, 02-P stale comment), `9d76447` (02-P
  in `events.js`).
- Test hygiene: `594ed86` (02-R, 17 backend tests) plus 17 frontend specs - the
  `card-tooltips-coverage` 5-point contract for every card plus 02-L/02-Q/06-J/06-M.
- Parked for user decisions: `02-N` (user-facing naming drift) and `06-O` (the
  bottleneck topic card's schema-echo "Role" row). Deferred: `02-O`, `01-BADGE`,
  `01-RISE`. `01-DIV` confirmed (no `division_score` consumer).
- Verified: backend suite green (754 tests); frontend **241 passed / 0 failed**.
  Canonical state: `docs/audit/README.md`.

## 2026-09-27 - 06-A tooltip triage + long-run handoff prompt

- Operation: `session-end-20260927-06a-handoff` (save).
- 06-A ("Option B" triage, `95bb4c2`): the bottleneck section's 17 native
  `title=` attributes are gone - redundant ones deleted; the informative ones
  (metric explanation, 40-day ROC as-of, provenance hashes, disabled-Generate
  reason, and the momentum badge) migrated to the shared `attachTooltip`
  focusable-trigger pattern with `aria-describedby`. Zero `title=` remains in
  `bottleneck.js`.
- Docs `2e5d122`: `06-bottleneck.md` 06-A -> FIXED, README Sec 10/12/13/14, and a
  rewritten `docs/audit/next-session.md` - a long-run handoff prompt queuing the
  remaining optional work (cross-section tooltip convergence for
  events/portfolio/shell, the `06-X` cancel-lock, and the P3 polish batches) with
  lane briefs and stop-and-ask gates.
- Verified: full backend suite green; the frontend suite is **224 passed / 0
  failed** (was 221). Canonical state: `docs/audit/README.md`.

## 2026-09-27 - app audit: 02/06 decisions answered and landed

- Operation: `session-end-20260927-02-06-decisions` (save).
- Answered the six `docs/audit/README.md` Sec 13 decisions. Backend `70680b3`:
  the AI gauge reads the shared `history_universe_symbols()` cache (02-G); the
  serve-time recompute is guarded, degrading to a null card instead of a 500
  (02-H); the valuation payload carries `fetched_at`/`cache_ttl_hours` (02-M).
- Cards `b80b211`: the gauge axis gradient/labels now match the verdict colour
  bands (02-K) and the valuation meta shows a compact PE cache age (02-M).
- Bottleneck `bf66de5`: an unparsable underdog ceiling is caught client-side
  (06-E); inline guards before discarding a dirty panel or dismissing a job
  (06-H); panels focus on open / restore on close and the delete confirm defaults
  to Cancel (06-F); unlabelled inputs got accessible names (06-G).
- Remaining: `06-A` (17 inline tooltips) stays DEFERRED; optional P3 polish in
  the section files; the `06-X` cancel-lock is tracked out of scope.
- Verified: full backend suite green; the frontend suite is **221 passed / 0
  failed** (was 209). Canonical state: `docs/audit/README.md`.

## 2026-09-27 - app audit: 02 + 06 audited; every section now has a section file

- Operation: `session-end-20260927-02-06-pass` (save).
- Deep-audited `02-ai-sentiment` (`docs/audit/02-ai-sentiment.md`). Fixes
  (`5820786`): an unavailable valuation no longer renders as "· ok"; a missing
  score no longer draws a midpoint needle; the decorative gauge is `aria-hidden`;
  new `ai-sentiment-null.spec.mjs` guards the freshness stamp and null paths.
- Light editor/forms pass on `06-bottleneck` (new `docs/audit/06-bottleneck.md`,
  prior art `ff9fc12`). Fixes (`6772f6b`): a failed draft apply now surfaces its
  error; the New-topic name and Generate theme survive a poll re-render; panel
  messages announce (`role="status"`).
- Awaiting the user (`docs/audit/README.md` Sec 13): 02-G (gauge history cache vs
  the shared universe), 02-H (guard the serve-time recompute), 02-K (gauge axis vs
  verdict colours), 02-M (surface valuation cache age), 06-H (unsaved-changes
  guard). `06-A` (17 inline titles) stays DEFERRED; `06-X` cancel-lock tracked.
- Verified: the frontend suite is **209 passed / 0 failed** (was 204). Canonical
  state: `docs/audit/README.md`.

## 2026-09-27 - app audit: decisions answered, the regime + market cards made honest

- Operation: `session-end-20260927-audit-decisions` (save).
- The seven open product decisions in `docs/audit/README.md` Sec 13 were answered
  and landed. The regime card now shows the detector report's own
  `metadata.generated_at` as its date, opts out of the generic refresh
  `.vintage-note`, and `refresh_all` stamps `vintage["regime"]` only when
  detection actually re-runs (`d169c62`).
- Market quotes: the commodities foot shows the spot source date when known
  (else the fetch time) and renders `spot.attribution`; the indices, rates and
  commodities tooltips were rewritten to the five-point standard (`1432d13`). The
  computed-but-unrendered `cov["futures"]` flag is dropped (`9cc83be`).
- Cleanups: the unused `initialSort` option is gone (`e928717`); 12 specs' stale
  `column_order`/`column_visibility` mocks and two dead `PUT .../columns/`
  branches are removed (`0116dc5`).
- `06-A` (bottleneck inline tooltips) stays DEFERRED; the bottleneck cancel-lock
  is tracked, out of scope. `03-regime` and `05-market-quotes` are now COMPLETE.
- Verified: the full backend suite is green; the frontend suite is **204 passed /
  0 failed** (was 198). Canonical state: `docs/audit/README.md`.

## 2026-09-27 - app audit: every section deep-audited, the suite went fully green

- Operation: `session-end-20260927-audit-complete` (save).
- The app audit (`docs/audit/`, canonical) closed its tracked backlog. All nine
  sections are deep-audited; section files exist for 00/01/02/03/04/05/07/08 (06
  is a light pass only). Fixes span the risk engine, shell tooltips, events
  (including a P1 where Enter on the focused Cancel button ran the destructive
  confirm), regime, indicators/breadth, market quotes (null policy), portfolio
  (sort restore, keyboard access, dead server prefs removed) and AI-sentiment
  freshness.
- Cross-section: event timestamps are now explicit UTC (`Z`) with
  legacy-tolerant readers; the dead `GET /api/regime` route is gone; the dead
  per-section refresh scaffolding is gone and `COOLDOWN_SECONDS` has one source.
- Test hygiene: the three stale baseline specs were repaired and a modal
  focus-trap regression spec was added. The frontend suite is **198 passed /
  0 failed** - no baseline failures remain.
- Awaiting the user: four product decisions (regime authoritative timestamp;
  market "As of" meaning; unrendered spot attribution/source_date; the dead
  `cov["futures"]` flag) plus two small cleanups. Detail in
  `docs/audit/README.md` Sec 13.

## 2026-09-27 - app audit: ten fixes landed, the frontend suite went fully green

- Operation: `session-end-20260927-audit-fixes` (save).
- The app audit (`docs/audit/`, canonical) moved from findings to fixes. Landed:
  risk flip strings derived from their own gate constants (`5b00879`);
  `attachTooltip` gained a live-text provider, and the header Refresh tooltip
  moved onto it (`e0bd9db`); events tag pills became keyboard-operable
  (`8fbc301`); the regime tooltip now covers all five standard points
  (`372ffd3`); the breadth cards stopped labelling the aggregate share while
  plotting per-symbol distance (`5bf3b1f`); the Rates card labels its yields
  `Yield (%)` (`4fbb73e`).
- Test hygiene `99907a7`: the three stale baseline specs (dash-layout x2 mirror,
  portfolio-star-scope expansion assumption) were repaired without touching a
  single `expect()` line. The frontend suite is **169 passed / 0 failed** - no
  baseline failures remain, so a new failure is now a real regression.
- Still open (canonical in `docs/audit/README.md` Sec 13): portfolio 07-A..E,
  ai-sentiment 02-A, bottleneck 06-A, the remaining deep audits, and the
  cross-section decisions.

## 2026-09-26 - wiki retrieval: freshness owner, corpus policy, and rerank decided

- Operation: `session-end-20260926-retrieval-decisions` (save).
- Closed the three decisions parked by `docs/audit/wiki.md` Sec 6.
- Freshness: the session-end step now rebuilds `.vault-meta/bm25`
  (`contextual-prefix.py --all --no-llm`, then `bm25-index.py build`). The
  ingest/save transaction was rejected - it would require patching the shared
  upstream claude-obsidian tooling for one vault's benefit.
- Corpus: the navigation hubs (`index`/`hot`/`log`) and `sources/_retired/**`
  stay indexed; the tooling has no exclude/down-weight knob, so the noise is
  accepted and documented rather than fixed.
- Rerank: lexical BM25 only. `rerank.py`'s Ollama cosine stage needs a local
  Ollama instance this machine does not run, and 8/12 top-1 is enough here.
- New page: [[sources/decision__retrieval-index-rebuilt-at-session-end-2026-09-26]].

## 2026-09-26 - bottleneck section audit: the draft-reopen bug and ten fixes

- Operation: `session-end-20260926-bottleneck-section-audit` (save).
- User-reported: a refresh kept re-opening the newest succeeded draft. Fixed with
  an `applied` marker on the job (idempotent `apply_draft`), a persisted
  dismissed-job list in `localStorage["bottleneck.dismissedJobs.v1"]`, and a
  `recoverJobState` that opens only a succeeded draft that is neither applied nor
  dismissed; the 35 already-applied jobs were backfilled.
- An independent audit of the whole section found ten more, all fixed in `ff9fc12`.
  The blocker: the research source probe was an SSRF - a findings line citing
  `http://127.0.0.1:<port>/api/shutdown` made the app GET its own shutdown route;
  probes now require a public http(s) host (IP-literal + DNS checks) and do not
  follow redirects. Also: `cancelling` as an honest non-terminal cancel status;
  stale `running` jobs recovered at startup; a completed stage no longer
  relabelled `skipped`; a cancel after the last check no longer overwritten by
  `succeeded`; polling no longer wipes unsaved input; `PUT` cannot overwrite
  `revisions`/`created`; imported topics get a real `id`; unknown evidence tiers
  are no longer relabelled "Social"; momentum `as_of` is stamped from the snapshot.
- Verified: 705 passed (+13 lifecycle); the bottleneck Playwright spec 34 passed.
- Still open: a cancelled job's serial lock can be held up to the request timeout
  (cancel is honest but not yet interruptible); a terminal failure hides the stage
  list.

## 2026-09-26 - the AI bottleneck taxonomy: 16 topics, US-listed only

- Operation: `session-end-20260926-ai-bottleneck-taxonomy` (save).
- Rebuilt the Bottleneck ("Serenity") section from a clean slate around three
  categories - Virtual AI Hardware (10 topics), AI Applications (1), Physical AI
  (5) - and generated and applied all 16 through the in-app pipeline. Commit
  `61259a6` shipped the pipeline changes the run needed: `MAX_RESEARCH_CHARS`
  20k -> 120k (the cap was applied at the research seam, so findings were already
  truncated before the fill prompt saw them), US-listed tickers with ADR/OTC
  mapping, a deterministic exchange-suffix filter, a market-source resolution
  drop, and a research-source liveness filter.
- Result: 16/16 succeeded; 658 source URLs; no topic over the 120k cap; no
  foreign-exchange ticker anywhere in the store; one ticker (`PLL`) dropped as
  unresolvable. Two weak first-pass topics were repaired: cooling (1 layer -> 6)
  and advanced packaging (a 600s research timeout -> 6 layers / 37 sources).
- Known limits: edge-AI inference is honestly thin (3 layers / 6 tickers); ADR
  mapping depends on the model knowing the US symbol and the resolution drop can
  only drop, not map; a sampled liveness probe was ~66% live, the remainder
  transient errors or bot-blocked sites rather than dead links.
- Open (pre-existing): Cancel only takes effect between attempts (600s timeout);
  a terminal generation failure hides the stage list; a run is minutes, not
  seconds, and bills the Go subscription via the CLI.

## 2026-09-26 - phase 2 closed: researched sources shown, draft chain kept

- Operation: `session-end-20260926-phase-two-closed` (save).
- Two commits on the Bottleneck ("Serenity") section. `32bbaea`: `_reconcile_fill`
  makes the final thesis a strict refinement of the draft chain — every skeleton
  layer (matched by name, case-insensitively) and every skeleton ticker survives,
  restored from the skeleton itself (nothing invented) while additions are kept;
  the job persists `fill_adjustments` + `skeleton`, and the prompt states the rule.
  `e68f5d4`: the review panel lists `job["research"].sources` (http(s) only become
  links, so a `javascript:` value stays inert text), shows a degraded run's note,
  keeps the findings in a collapsed block, and states which layers/tickers the
  refinement tried to drop; stage rows now print any note.
- Verified live end-to-end: a real generation persisted 47 researched source URLs
  and 18,587 chars of findings, and its fill added two tickers while dropping none
  (`fill_adjustments: []`, every skeleton ticker present). Backend 670 passed
  (+13 lifecycle); Playwright 149 passed with the 4 known pre-existing failures;
  the bottleneck spec 26.
- Two pre-existing defects found while testing. A full-suite flake: a cancelled
  worker held `_generation_lock` into the next test, so `start_generation` returned
  an unpersisted "already running" job and `_wait` timed out (it reproduced on a
  clean HEAD baseline). And a test-isolation violation: a worker outliving the
  autouse fixture's monkeypatch restore wrote the temp job list over the live
  `data/bottleneck_jobs.json`, destroying 3 real draft jobs (the durable
  `data/bottleneck_topics.json` was untouched). `tests/conftest.py` now drains
  `_generation_lock` before and after each test, while the paths are still
  redirected; the live jobs file is byte-identical before and after a run.
- Open: Cancel only takes effect between attempts (600s timeout); a terminal
  failure hides the stage list; a run is now ~5-8 minutes and bills the Go
  subscription via the CLI.

## 2026-09-26 - session close: phase-2 items recorded

- Operation: `session-end-20260926-phase-two` (save).
- Session closed after 13 commits (`992efec..76f7dcc`), all pushed. The Bottleneck
  generation pipeline now: gates underdogs at $3B, states each card field's type
  in the prompt, labels upstream layers, scopes the lens as method rather than
  answer, researches the web through the opencode CLI harness, and serializes
  job-store reads against writes.
- Recorded a user-reported phase-2 item: **the draft chain and the final thesis
  can disagree.** `fill` refines the `draft` skeleton against the researched
  findings, but nothing constrains it to be a *refinement* — it may add, drop or
  rename layers and tickers — so the mid-run preview is inconsistent with the
  applied result. Which inconsistency was observed is not yet pinned down; the
  next session should establish that before designing the fix.
- Also carried into phase 2: researched sources are persisted on the job
  (`job["research"]`) with their URLs but are not yet shown in the UI.
- Open beyond phase 2: Cancel only takes effect between attempts (600s timeout);
  a terminal failure hides the stage list; a run is now ~5-8 minutes and bills the
  Go subscription via the CLI.

## 2026-09-25 - feat(bottleneck): the agent gets a harness and researches the web

- Operation: `session-end-20260925-research-stage` (save).
- Commits `bc585f1` (the research pipeline) and `15191d6` (the job-store race).
  A skill is a prompt bundle with no capabilities — the harness supplies the
  tools — and the app had kept the files and the model while dropping the
  harness, so the lens was its only evidence. A generation now runs six stages:
  refresh skill -> read lens -> draft chain -> research web -> draft thesis ->
  pull market data. The research stage shells out to the local opencode CLI with
  a project-scoped read-only agent (`.opencode/agents/researcher.md`, mode
  primary, edit/shell/question denied) and `--standalone`; the prompt travels on
  stdin, the model is `opencode-go/<id>` so it bills the subscription, and cwd is
  the repo root so the project agent resolves. Both model calls keep the strict
  JSON contract; only the middle stage is agentic.
- Verified live on two real themes: CPO returned 30 source URLs and 14,283 chars
  of findings; the AR-eyewear theme — previously three empty layers — returned 53
  source URLs and 19,920 chars and now names real suppliers (VUZI/AMAT/GLW/COHR
  waveguides; HIMX/KOPN/AMS microdisplays).
- Fixed while testing: both spawns decoded output with the Windows locale codec,
  which raised on the CLI's UTF-8 and silently discarded the findings; and
  neither set `CREATE_NO_WINDOW`, so a console window flashed on every refresh.
- Fixed the flaky gate, which was a real bug: `get_job`/`list_jobs` read the job
  file without `_JOBS_LOCK`, so a read could interleave with the writer's
  `os.replace` — a Windows sharing violation that killed the worker thread. It
  failed 3-12 tests per run with a different set each time; five consecutive runs
  now pass and the full suite is 656 passed.
- Open: Cancel still only takes effect between attempts; a terminal failure still
  hides the stage list; researched sources are persisted on the job but not yet
  shown in the UI (phase 2); generation is now ~5 minutes and bills the Go
  subscription via the CLI.

## 2026-09-25 - fix(bottleneck): label and explain generated upstream layers

- Operation: `session-end-20260925-layer-shape-contract` (save).
- Commit `58e87f6`. The drafting prompt asked for a layer shaped as `layer` +
  `stocks` while the store, engine and renderer all speak `name` +
  `physical_constraint` + `what_to_watch` + `stocks`; nothing bridged them, so
  generated layers rendered an em dash with the Constraint/Watch lines dropped.
  Fixed in four places: the prompt asks for the real four-field layer,
  `_normalize_draft` promotes a legacy `layer` key into `name`, `_layer_block`
  aliases that key on read (so stored topics repair without migration), and
  `_validate_layer` rejects a nameless or mistyped layer so the retry loop
  self-corrects. No frontend change was needed.
- Why the suite missed it: every render and contract fixture hand-supplied a
  layer name, and only agent-generated topics were affected — the editor path
  always round-tripped all three fields.
- Verified live: a fresh headless generation returned five named layers each
  with a constraint and a watch item, validator clean on attempt 1, 19,094
  completion tokens (12,144 reasoning) in 102s. The pre-fix stored topic now
  labels all five layers from its legacy `layer` key.
- Operational notes worth keeping: PowerShell mangles braces in `git commit -m`
  (a `{...}` body was parsed as a pathspec) — write the message to a file and use
  `git commit -F`. And when reaping processes by command-line match, exclude the
  current shell, or the filter matches its own command line and kills the script
  mid-run.
- Open: the backend gate is intermittently flaky — a temp-file race between the
  job poller and the worker's `os.replace` produced 0, 1 and 5 failures on
  identical code and reproduced on a HEAD mirror. Vault counts are unchanged
  (the fix was folded into the existing decision page).

## 2026-09-25 - fix(bottleneck): make a real topic generation complete

- Operation: `session-end-20260925-drafting-budget-and-field-types` (save).
- Two commits, `8014c0c..0d22495`, closing the follow-up the previous entry
  recorded. `8014c0c`: `MAX_TOKENS` 8000 -> 64000 and `REQUEST_TIMEOUT_S`
  120 -> 600. `deepseek-v4.1-flash` is a reasoning model and its reasoning
  tokens are counted inside `completion_tokens`, so the old cap was consumed
  entirely by reasoning: empty `content`, `finish_reason='length'`, and three
  identical retries. `0d22495`: the schema block stated field *names* but never
  their *types*, so a real draft returned a string `invalidation` and a
  non-string inside `upstream[].stocks`; an explicit type table plus a
  plain-ticker-strings rule fixed it.
- Measured headlessly on the live Go endpoint (same theme): reasoning 12,208 ->
  13,274 tokens, completion 15,971 -> 16,501, ~80s at ~200 tok/s, and the typed
  prompt's draft passed `validate_topic` with no errors on attempt 1.
- Method note: `max_tokens` is a cap, not a reservation — a large value costs
  nothing unless it is emitted — and the timeout must scale with it, or the
  failure merely becomes a read timeout.
- Also established: `GET /zen/go/v1/models` returns ids only (no limit fields)
  and needs `x-opencode-session`; it lists 35 models and `ALLOWED_MODELS` is a
  superset. `reasoning_content` / `usage` are returned and were being discarded,
  which is why the failure looked opaque. Vault counts are unchanged — the fix
  was folded into the existing decision page rather than adding a page.
- Open: with a 600s timeout, Cancel only takes effect between attempts, so a
  cancel can look unresponsive for up to 10 minutes; and a terminal failure
  still hides the four-stage list.

## 2026-09-25 - feat(bottleneck): $3B underdogs + named research stages

- Operation: `session-end-20260925-serenity-underdog-and-stages` (save).
- Two commits, `992efec..db148e7`. `992efec`: `UNDERDOG_CEILING_DEFAULT` $10B ->
  $3B (the skill's own headroom threshold, `references/methodology.md:334`), the
  core/extended conviction tier removed end to end (at a $3B ceiling it collided
  with `CORE_TIER_MAX = $3B`, leaving `extended` unreachable), and the underdog
  definition — "emerging stocks with great potential" — stated verbatim in the
  per-topic note and the `cards.js` help text. `db148e7`: a generation job
  persists an ordered four-stage list (`refresh_skill`, `read_lens`, `draft`,
  `warm_metrics`) with per-stage status + note; only `draft` is fatal; the metrics
  warm is bounded at 20s; legacy stage-less jobs still render.
- Behaviour change: stage 1 now runs the `npx` skill refresh inside a generation
  run, where before the refresh was reachable only from `POST /skill/refresh`.
- Verified: backend 633 (+ 13 lifecycle), Playwright 143 with the 4 known
  pre-existing failures, bottleneck spec 20; each commit also tested alone. Live
  against the real app: the four stages rendered and advanced, `refresh_skill`
  came back `done` (npx really ran), a degraded run showed `draft: failed` +
  `warm_metrics: skipped`, and a hand-created topic stored
  `underdog_ceiling = 3000000000` with the chip reading `≤ $3B` and 0 tier pills.
- Corrected: `agent-browser screenshot` **is** verified — it saved a PNG. The
  prior "unverified" note came from three redirected-pipe wrapper hangs, not the
  tool. `AGENTS.md` updated.
- Open: a real generation currently fails on the token budget
  (`finish_reason='length'`, empty content; `MAX_TOKENS = 8000` against a ~136 KB
  lens) — pre-existing, not from these commits, but it blocks the happy path. A
  terminal failure also hides the four-stage list. Both are recorded on the
  decision page.

## 2026-09-25 - docs(agents): trim AGENTS.md to the WHAT/WHY/HOW shape

- Operation: `session-end-20260925-agents-trim` (save).
- `AGENTS.md` 222 -> 189 lines. Each hard rule is one line stating the rule
  followed by a `Detail:` pointer to the vault page carrying its rationale and
  worked examples — a decision page where one exists, `project_rules__RUNBOOK`
  where the rationale is operational (commit hygiene, file ownership, wiki sync).
  No rule was weakened or dropped; only the prose moved.
- Pointers are repo-root-relative and all 18 resolve, verified by script along
  with the file's factual claims (100 source pages, 52 decisions). A first pass
  wrote them as `wiki/...`, which dangled — cheap lesson: a pointer-resolution
  check catches this class of error in one run.
- Closed: the `AGENTS.md` split watch opened when the file crossed its 200-line
  threshold. Its own Documentation-hygiene rule required proposing the split in
  the same session, which this completes.

## 2026-09-25 - chore(tools): install agent-browser, keep Playwright as the gate

- Operation: `session-end-20260925-browser-tooling` (save).
- `agent-browser` 0.38.1 + Chrome 154.0.8037.57 installed globally. The local
  `.agents/skills/agent-browser/SKILL.md` was already present but is only a
  discovery stub, so it pointed at a CLI that did not exist; it is live now.
- Decision: **Playwright stays the front-end regression gate** (18 specs) and
  `agent-browser` takes the exploratory pass it cannot do. Recorded in `AGENTS.md`
  with its verification status. Relevant caveat found while checking: the
  Playwright `webServer` is a static `python -m http.server` and the specs mock
  every endpoint, so the suite never exercises the real backend — a live
  `agent-browser` pass is the only browser check that does.
- Verified live against the real app: `agent-browser open` loads it, and
  `/api/bottleneck/topics` serves the new payload in process
  (`framework: serenity-aleabitoreddit`, `topics: 0`, `generation.enabled: true`).
- Not verified: `screenshot` / `snapshot` end-to-end. Three attempts hung in the
  PowerShell wrapper, not the tool — redirected-pipe handle inheritance from the
  spawned Chrome, plus a truncating `Select-Object -First` truncation. All three
  leaked processes, which were reaped and confirmed clean (0 processes, 0
  listeners). The trap is now a Process hygiene rule in `AGENTS.md`.
- Also corrected: `AGENTS.md` claimed 95 source pages / `### decision (47)`
  (now 100 / 52) and did not mention that vault writes need root under WSL.
- Open: `AGENTS.md` is 222 lines and a split is proposed; `agent-browser`'s
  screenshot path needs one in-lane confirmation.

## 2026-09-25 - docs(wiki): record the bottleneck API/agent contract and the delegation finding

- Operation: `session-end-20260925-bottleneck-contract` (save).
- Follow-up to the entry below, after auditing the driving plan file against the
  vault: three things it carried were not yet durable, and one vault page was
  stale.
- New decision pages: the Bottleneck section's route table, error mapping, job
  semantics, agent endpoint/limits/cost and the tiering evidence; and the finding
  that a poisoned agent-model binding is inherited by child sessions, so a session
  in that state cannot delegate and must be replaced rather than retried.
- Callout added to `sources/project_rules__API.md`: this page documents the
  **deleted** `/api/bottleneck/categories/*` routes and also predates the removal
  of the `thirteenf` and `ai_analysis` dashboard keys (commit `8dedc18`), so its
  route and payload-key lists are historical for those areas. The second of those
  predates this session.
- Corrections: `AGENTS.md` still claimed 95 live source pages and
  `### decision (47)`; now 100 and 52. `wiki/hot.md` records that vault writes must
  run as **root** under WSL, because `.vault-meta/transactions/` holds root-owned
  mode-700 state dirs from earlier sessions and the engine reads that directory
  before it can start.
- Retired: the driving plan file `HANDOFF-bottleneck-section.md` is deleted; its
  phase table and skill-refresh command were already superseded by the decision
  pages.
- Decisions: 50 -> 52. Verification: lint introduces no new findings (the 2 dead
  links are pre-existing prefix-style wikilinks in the two `_retired/` pages).

## 2026-09-25 - feat(bottleneck): topic-driven chokepoint section (10 commits, a40c85e..099e932)

- Operation: `session-end-20260925-bottleneck-topics` (save).
- Replaced the section's 5 hardcoded categories and their reorder/rename prefs
  with user-authored **topics**: a demand driver, its upstream constraining
  layers, and downstream per-stock thesis cards. Added 13 routes
  (`/api/bottleneck/topics` CRUD + import/export, generate, job poll/cancel,
  apply, skill status/refresh); `GET /topics` is the front-end's single render
  call.
- New: `app/bottleneck_topics.py` (topic store), `app/topic_agent.py` (in-app
  drafting agent — the app's only keyed path and only child-process spawn site),
  `static/js/bottleneck.js`, `tests/test_bottleneck_topics.py`,
  `tests/test_topic_agent.py`, `tests/test_api_bottleneck.py`,
  `tests/frontend/bottleneck.spec.mjs` (18 tests).
- Deleted: `BOTTLENECK_CATEGORIES`, `app/bottleneck_prefs.py` + its 2 routes and
  tests, the old renderer, its 2 endpoint clients and their 2 Playwright specs.
  `data/bottleneck_prefs.json` left on disk, not migrated (precedent: `8dedc18`).
- Skill: the vendored `w-y-p/serenity-aleabitoreddit-skill` is deleted (10
  files); upstream `yan-labs/serenity-aleabitoreddit` is installed into
  `.agents/skills/` and gitignored (upstream `license: null`), with
  `skills-lock.json` tracking provenance. Footer link re-pointed.
- Config: `OPENCODE_GO_API_KEY` in a gitignored `.env` plus a committed
  `.env.example`. Every keyed path degrades to null; the app runs without it.
- Four cross-view divergence defects were found and fixed during the build: two
  PE sources, a frozen copy served for a live value, a render-path fetch on a
  second cache key, and a header badge reading the dashboard while the body read
  the topics payload. All four are the same shape; the fixes are recorded as a
  durable decision.
- Verification: backend 620 passed + 13 lifecycle passed as a separate invocation
  (`test_lifecycle.py`'s watchdog truncates a single-process run, as documented);
  frontend Playwright 141 passed / 4 pre-existing failures (news-row chips,
  portfolio-star-scope, dash-layout x2). Live OpenCode Go smoke test: HTTP 200 on
  `deepseek-v4.1-flash`, envelope captured before the agent hardened on it.
- Decisions: 47 -> 50. Three new decision pages; the category-prefs decision is
  annotated superseded in the index.
- Deviations worth carrying forward: the skill CLI needs `-a universal --copy -y`
  to run non-interactively; `skills-lock.json` is tracked and was rewritten by the
  CLI; the agent's `skill_snapshot` hash is a different scheme from the lockfile's
  `computedHash`.
- Not committed: the plan file `HANDOFF-bottleneck-section.md` (untracked).

## 2026-09-25 - refactor(dashboard): remove AI Analysis Run Log + Superinvestors 13F (8dedc18)

- Operation: `session-end-20260925-remove-analysis-13f` (save).
- Removed two dashboard sections the user reported as hardly used: the
  "AI Analysis · Run Log" card and the "Superinvestors · 13F" card. Recon
  showed they were a closed pair - nothing surviving consumed `ai_analysis`
  or `thirteenf` (the analysis engine was 13F's only other consumer) - so
  both backends were removed wholesale.
- Deleted `app/analysis.py` (deterministic weighted-vote synthesis),
  `app/thirteenf.py` (SEC EDGAR 13F), the `analysis_runs` SQLite run-log in
  `app/store.py`, `GET /api/analysis/history`, `ANALYSIS_DB_PATH`,
  `THIRTEENF_TTL` and `SUPERINVESTORS`; stripped the service
  refresh/coverage/enrich wiring and the frontend renderers, layout
  registries, error routing, tooltips and dead CSS.
- Preserved the legacy `news.db` -> `events.json` migration in `store.py`
  (events path untouched). Left on disk (persisted/derived data, not
  deleted per the user's choice): `data/analysis.db`,
  `data/thirteenf_snapshot.json`. Regenerated the stale
  `data/dashboard.json` oracle so its top-level keys match the new payload.
- Verification: backend 526 passed + 13 lifecycle passed (a single-process
  full-suite run truncates on a pre-existing `test_lifecycle.py` watchdog
  `os._exit` after ~60s - unrelated); frontend Playwright 134 passed / 6
  pre-existing failures (bottleneck-move x2, news-row chips,
  portfolio-star-scope, dash-layout x2 - the last pair already broken by
  the earlier earnings-card removal). Commit 8dedc18: 23 files, +48/-1518.
- Follow-up: `static/style.css.orig` is a stale tracked backup that still
  contains the deleted `.tf-holdings` / `.ana-*` rules - left in place
  (pre-existing; separate logical change).

## 2026-09-23 - fix(dashboard): stop HTTP 500 on non-finite floats (4af86f1)

- Operation: `session-end-20260923-dashboard-nan-500` (save).
- Bug: GET /api/dashboard answered HTTP 500 ("Failed to load dashboard:
  HTTP 500" in the UI). Starlette's JSONResponse serialises with
  allow_nan=False, so one NaN anywhere in the payload raised
  `ValueError: Out of range float values are not JSON compliant: nan`
  and took down the entire response. The regime detector emits NaN for
  all 38 component values (current_ratio, sma_6m/12m, roc_3m/12m,
  crossover.gap_pct) when its price source is unavailable
  (`treasury_data_available: false`) - 6 of 189 reports on disk, all 5
  from 2026-09-23. That report was embedded in the cached
  `data/dashboard.json`, so every load 500'd; `/api/regime` broke the
  same way.
- Fix: new `store.json_safe()` recursively maps NaN/Infinity -> None (the
  project's "no data" sentinel; the UI already renders null as an em
  dash). Applied at both JSON-serving boundaries: `service._enrich()`
  (covers the dashboard, including a NaN already baked into the cache)
  and `regime.get_regime()` (covers `/api/regime`). `store.save_json()`
  now sanitises too, so our own caches never persist invalid JSON again.
  Composite score/zone preserved - only genuinely missing values become
  null.
- Tests: +4 regression tests (store.json_safe unit, save_json
  non-finite, `/api/dashboard` with a NaN-bearing cached payload,
  `/api/regime` with a NaN-bearing detector report). Verified against the
  real server: both endpoints 200, strict JSON parse (System.Text.Json)
  clean, no standalone NaN token. Backend suite 564 passed; the 4
  pre-existing test_portfolio_cache_sync failures (the same NaN
  ValueError) drop to a single flaky worker crash.
- Root-cause note for future coverage: the NaN originates in the
  third-party macro-regime-detector skill (pinned in skills-lock.json),
  so the fix sanitises at our serve boundary rather than patching the
  skill. test_portfolio_cache_sync is network-dependent (real yfinance
  calls) and flaky under xdist.

## 2026-09-22 - fix(portfolio): register the missing rename route (534fd5f)

- Operation: `fix-20260922-portfolio-rename-route` (save).
- Bug: portfolio rename was broken in both the UI and the API.
  `app/portfolio.py` already had `rename_portfolio()` and
  `static/js/api.js` already sent `PUT /api/portfolios/{pid}?name=...`,
  but `app/api.py` never registered that route - the path existed only
  for DELETE, so FastAPI answered 405 Method Not Allowed. The inline
  pencil handler then alerted and re-rendered, silently reverting the
  name, which is why the change "did not work and did not persist".
- Fix: added `portfolios_rename()` to `app/api.py` (name as query param,
  400 on empty/whitespace name, 404 on unknown pid, no live-price
  enrichment because a rename touches only the name). Returns the same
  `{id, portfolio}` shape as POST /api/portfolios.
- Tests: three API-level regression tests in `tests/test_portfolio.py`
  (rename persists across GET, empty name -> 400, unknown pid -> 404).
  Backend suite: 106 passed.
- Root-cause note for future coverage: the gap was invisible to both
  existing layers - backend tests called `portfolio.rename_portfolio()`
  directly (bypassing HTTP routing) and the Playwright rename specs mock
  the PUT endpoint, so a route that was never registered passed both.
  HTTP-level tests are the layer that catches missing/dropped routes.

## 2026-09-14 - Project skills consolidated into .agents/skills (55d4080)

- Operation: `maint-20260914-project-skills-consolidation` (save).
- Moved the 4 project-authored domain skills (data-pull,
  financial-deep-research, news-filter, risk-divergence) from
  .opencode/skills/ to .agents/skills/ via git mv so OpenCode and Freebuff
  share one canonical skills home. Verified via opencode debug skill: all
  4 resolve from .agents/skills post-move; 19 skills total live there now
  (15 claude-obsidian + 4 domain). Empty .opencode/skills/ removed.
- skills-lock.json audit: it is the provenance manifest of the
  GitHub-sourced skill installer and tracks only the 8 third-party
  .agents/skills skills. The 15 claude-obsidian skills (managed via the
  sibling checkout, provenance in AGENTS.md) and the 4 project-authored
  domain skills deliberately stay out of it - no GitHub source to pin.
- Removed the empty untracked .slim/ runtime dir (slim skills recreate it
  on demand) and broadened the .gitignore rule from .slim/deepwork/ to
  .slim/ to keep future codemap/deepwork state out of the tree.

## 2026-09-14 - Global claude-obsidian skills removed; think migrated (233568b, 9355c72)

- Operation: `maint-20260914-global-skills-removed` (save).
- User-authorized cleanup: deleted the 15 redundant global copies under
  ~/.config/opencode/skills/ - the 14 migrated earlier plus think, the
  15th claude-obsidian skill initially misclassified as slim-managed (it
  is upstream and absent from the slim 8-skill manifest). think was copied
  project-locally first (byte-identical to the checkout), then all 15
  verified resolving to .agents/skills via opencode debug skill with the
  globals gone for real.
- oh-my-opencode-slim untouched: its 8 managed skills, plugins, and MCP
  grants stay global. context7/gh_grep are slim preset grants in
  ~/.config/opencode/oh-my-opencode-slim.json (librarian gets both;
  orchestrator gets gh_grep only); the servers are registered by the slim
  plugin, not by opencode.jsonc ("mcp": {} is empty).
- AGENTS.md skills bullet now lists the full set incl. think and the
  product root (sibling ../claude-obsidian), tightened back to the
  200-line threshold (8e28412). README Architecture section notes the
  bundled project-local skills (9355c72).

## 2026-09-14 - Session end: claude-obsidian skills migrated to project-local .agents/skills (862bcee)

- Operation: `session-end-20260914-skills-local-migration` (save).
- Migrated all 14 claude-obsidian skills (wiki, wiki-cli, wiki-ingest,
  wiki-fold, wiki-lint, wiki-mode, wiki-query, wiki-retrieve, save,
  autoresearch, defuddle, obsidian-bases, obsidian-markdown, canvas) from
  ~/.config/opencode/skills/ into .agents/skills/ as byte-identical copies
  including references/ and templates/ (verified drift-free against the
  durable product checkout, v2.2.0). oh-my-opencode-slim managed skills,
  plugins, and global MCP config untouched (no MCPs currently active).
- Verification: `opencode debug skill` resolves all 14 to
  .agents/skills/<name>/SKILL.md when the global copies are absent; while
  both exist OpenCode prefers the global copy (identical content, so
  behavior is unchanged). Read-only wiki-lint green: 104 pages, 101
  findings all pre-existing (archived-page frontmatter gaps + 2 retired
  dead links), none introduced by the migration. No absolute paths or
  Claude-Code-specific assumptions in the migrated skills.
- Freebuff reads .agents/skills/ natively (user-confirmed). AGENTS.md
  updated (9498500) to point at the project-local skills.

## 2026-09-14 - claude-obsidian clone relocated out of Temp

- Operation: `maint-20260914-relocate-obsidian-core` (save).
- Moved the product clone from the old AppData/Local/Temp/opencode location
  (ephemeral, subject to Windows temp cleanup) to the durable checkout at
  Documents/Main/GitHub/Spirors/claude-obsidian. Git checkout intact
  (32ac5a0, v2.2.0); no embedded absolute-path references; doctor ok from
  the new path (WSL root + explicit --vault unchanged). Session temp
  artifacts (pytest outputs, TestClient verify dirs) removed.
- hot.md updated with the durable path; Active Threads watch item cleared.

## 2026-09-14 - Session end: fix(ai-valuation) forward-PE re-wiring (1ba5288) + test repairs (47e5a7f)

- Operation: `session-end-20260914-ai-valuation-fwdpe-rewire` (save).
- Bug: BREADTH - AI Proxies hover intermittently missing FWD PE despite a
  fresh data/ai_valuation.json; Refresh seemed to trigger it. Root cause:
  PEs were wired only inside compute_indicators; cold start computed
  indicators before the PE cache existed, and the 30-min indicators cooldown
  re-served the PE-less payload on every refresh. Fix: indicators.wire_forward_pe
  (idempotent, drops unbacked PEs) called on compute, cooldown-reuse, and
  every serve (after the AI-gauge recompute that populates the cache).
  Commits: 1ba5288 (fix + regression tests), 47e5a7f (3 pre-existing test
  failures repaired, clean-tree verified).
- Verification: backend full suite green; frontend breadth-ai-valuation 7/7;
  live 62/71 tickers with forward_pe; AI gauge valuation repopulated.
- Changelog: data/logs/summary-2026-09-14.md 15:07:39 fix.

## 2026-09-13 — Layer 2 prune: 10 historical artifacts + 7 design specs/plans regrouped (+ corrections)

- Operation: `wiki-fold-20260913-history-regroup`
- Pre-check: grepped `app/`, `static/`, `tests/`, `AGENTS.md`, `README.md`, and
  the rest of the wiki for references to all 18 candidates (11 historical
  artifacts + 7 superpowers specs/plans). **Zero live references** anywhere.
- Removed 16 single-entry groups from `wiki/index.md`:
  - 9 historical: `audit (2)`, `fix-log (1)`, `improvements-log (1)`,
    `migration-guide (1)`, `park-log (1)`, `refactor-example (1)`,
    `refactor-metrics (1)`, `summary (1)`, `test-plan (1)`
  - 7 design-history: `ai-capex-design (1)`, `ai-capex-plan (1)`,
    `ai-valuation-plan (1)`, `news-overhaul-design (1)`,
    `news-overhaul-plan (1)`, `portfolio-design (1)`, `portfolio-plan (1)`
- Added 2 new groups:
  - `### history (10)` — one-time audits, refactor logs, prior state summaries
  - `### design-history (7)` — pre-ship design specs and implementation plans;
    the spec/plan annotation explicitly directs readers to `### decision (47)`
    for current guidance and the spec/plan only for design rationale
- **Correction (same session):** `ARCHITECTURE_DETAILS` was a
  misclassification in the first pass — it's a live companion to
  `ARCHITECTURE`, not a historical artifact. Moved out of history into
  `### architecture (2)`, with an inline annotation marking it as a
  companion to the module map.
- Source page count: unchanged at 95 (this is a regroup, not a delete).
- Reversible: re-splitting any of the tail groups into their original
  single-entry categories is a small edit if ever needed.

## 2026-09-13 — Layer 1 prune: 4 umbrella pages retired

- Operation: `wiki-fold-20260913-umbrella-retire`
- Moved to `wiki/sources/_retired/` (preserves content, marks `status: retired` + `superseded_by:` in frontmatter + Obsidian deprecation callout):
  - `project_rules__HANDOFF.md` — superseded by [[wiki/hot.md]] + [[wiki/overview.md]]
  - `project_rules__DECISIONS.md` — superseded by `### decision (47)` in [[wiki/index.md]]
  - `project_rules__SESSION_LOG.md` — superseded by `### session (26)` in [[wiki/index.md]] + [[wiki/log.md]]
  - `project_rules__ROADMAP.md` — superseded by [[wiki/overview.md]] (migration history) + [[wiki/hot.md]] (active threads)
- `wiki/index.md`: removed 4 single-entry groups (`### decisions (1)`, `### handoff (1)`, `### roadmap (1)`, `### session-log (1)`); added `### retired (4)` group at the end of Sources with supersession mapping.
- Captures at `.raw/captured/<sha>.md` are immutable; this prune only restructures the live wiki source pages. Reversible by re-ingesting from the captures.
- Decisions and session count: 47 / 26 — unchanged.

## 2026-09-13 — Migration: wiki-native session memory adopted

- Operation: `migration-20260913-wiki-native-memory`
- Scope: `AGENTS.md` rewritten to wiki-native session protocol; `README.md` updated to point at the vault; `wiki/overview.md` expanded from a one-line stub; `wiki/meta/session-memory-protocol.md` created; `wiki/log.md` + `wiki/hot.md` updated.
- Behaviour change: session start now reads `wiki/hot.md` (was: `inbox/project_rules/HANDOFF.md` + `ROADMAP.md` + `DECISIONS.md` + `RUNBOOK.md`). The old inbox-based protocol is deprecated; `inbox/project_rules/` is preserved as a frozen archive.
- Decisions: remain as source pages under `wiki/sources/`, listed in `wiki/index.md` (47 entries, unchanged).

## 2026-09-13 — Initial ingest: 99 sources from project_rules/ + docs/

- Operation: `ingest-20260913-initial-99`
- Source count: 99 (9 project_rules root, 26 archive/sessions, 47 archive/decisions, 17 docs/)
- Wiki pages: 99 source pages at `wiki/sources/<slug>.md`
- Captures: 99 immutable snapshots at `.raw/captured/<sha>.md` (created by capture apply earlier)
- Source manifest: 99 entries added to `.raw/.manifest.json`
- Citations: every source page has original_path + original_sha256 + stored_path back to inbox/ + .raw/captured/.
