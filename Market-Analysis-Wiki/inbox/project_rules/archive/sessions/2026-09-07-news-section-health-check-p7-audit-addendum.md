# 2026-09-07 — News section health check (P7 audit addendum)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-07 -- News section health check (P7 audit addendum)

User reported "has there really not been important news for 3 days?"
plus overall news-section health check. Added as P7 to the existing
audit document at `docs/logs/audit-2026-09-07.md`. No code changes.

Investigation:
- Inspected `data/events.json`: 169 events total. Newest by `published`
  is 2026-09-04T17:23:13 (Trump calls for rate cut). 0 events in
  last 72h. 21 in last 168h. Last-7d source breakdown: 15 MarketWatch
  + 6 BBC Business.
- Newest `first_seen`: 2026-09-04T17:56:03 (3 days stale). Newest
  `updated_at`: 2026-09-07T18:23:56 (today, scheduler-touched).
- Probed both `NEWS_FEEDS` live: MarketWatch HTTP 200, 10 entries
  (10/10 within 48h, newest 0.9h old). BBC Business HTTP 200, 52
  entries (11/30 within 48h, newest 2.0h old). Both parse cleanly.
- Ran `app.news.analyze()` on the 21 live 48h items: only 1 clears
  the `IMPORTANCE_THRESHOLD=6.0` ("Is the stock market open today
  for Labor Day? What about bond trading", comp=8.28). The other 20
  score 0.0-3.6 (lifestyle / personal-finance / UK-domestic items).

Findings:
- The "3 days without important news" is genuine soft-news silence,
  NOT a pipeline bug. RSS feeds are alive, scheduler is running
  (`updated_at` touched today), threshold + content filters work.
- Labor Day weekend + generally soft news flow explains the gap.
- No code change recommended. If the user wants more items during
  soft periods, threshold-tune sketch in the audit file
  (lower `IMPORTANCE_THRESHOLD` from 6.0 to ~4.5; trade-off: more
  noise on quiet days).
- README.md:40 stale source list ("MarketWatch / SCMP / Korea
  Herald" - actual is MarketWatch + BBC Business). Same P6 doc-drift
  family; low-priority fix.

Configuration knobs documented in the audit file for future tuning:
- `app/news.py:128` `IMPORTANCE_THRESHOLD = 6.0`
- `app/news.py:131-134` `IMPACT_BANDS` (Critical >=9.0, High >=6.0)
- `app/config.py:242-245` `NEWS_FEEDS` (MarketWatch + BBC Business)
- `app/config.py:251-254` `NEWS_SOURCE_WEIGHTS` (MarketWatch=1.2, BBC=1.0)
- `app/config.py:304` `NEWS_INGEST_WINDOW_HOURS = 48`
- `app/config.py:314` `NEWS_REFRESH_INTERVAL_HOURS = 4`
- `app/news.py:270` `FINANCE_RELEVANCE_BOOST = 1.5x`

Updated:
- `docs/logs/audit-2026-09-07.md` -- new P7 section appended
- `project_rules/HANDOFF.md` -- P0..P6 -> P0..P7, current state
  reflects "3 days no news is real, not a bug"
- `project_rules/SESSION_LOG.md` -- this entry
- `data/logs/summary-2026-09-07.md` -- 1 `log_change("doc", ...)` call

Working tree at session end: `data/events.json` (scheduler-owned,
ignore) + `project_rules/HANDOFF.md` (modified) +
`project_rules/SESSION_LOG.md` (modified) +
`docs/logs/audit-2026-09-07.md` (untracked, new).



