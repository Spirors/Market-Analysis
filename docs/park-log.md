# Park Log — Resolving the Parked Review Items

**Date:** 2026-08-23 · **Branch:** `parked/review-2026-08-23`

Each parked item from `docs/improvement-review.md` §2 was discussed, decided,
and implemented as its own commit on this branch. One entry per item below.
The review file is removed in the final housekeeping commit; this log is the
permanent record.

---

## P9 — Event delete precedence (`app/api.py`)

**Was:** `DELETE /api/events?link=X&source=Y` deleted by link and silently
ignored `source`.

**Decision:** reject with **400** when both parameters are given — compound
deletes must be two deliberate calls.

**Changed:** both-given guard in `delete_event`; new contract test
(`test_delete_events_with_both_params_returns_400`). UI unaffected (it never
sends both).

---

## P7 — Auth posture for mutation endpoints (`app/api.py`)

**Was:** all endpoints (including DELETE/suppress/watchlist/refresh) accepted
any Host header — a DNS-rebinding page could reach the localhost-bound API
from a browser.

**Decision:** **Host-header allowlist middleware** (chosen over tokens for
zero-friction security; plain cross-site form posts remain theoretically
possible but are low-stakes for this tool and have no cheap fix).

**Changed:** `_host_allowlist` middleware compares the request hostname
(port stripped, IPv6 brackets handled) against new `config.ALLOWED_HOSTS`
(`127.0.0.1`, `localhost`, `[::1]`); foreign hosts get 403. Test client now
uses a real `http://127.0.0.1:8000` base URL; two new contract tests cover
reject/accept.

---

## P8 — Stooq symbol mapping (`app/market.py`)

**Was:** a Yahoo→Stooq fallback (strip `^`/`=`/`-`) of unverified correctness;
the review suspected invalid codes (`GSPC` vs `^spx`, `GCF` vs `gc.f`).

**Investigation (2026-08-23, live):** every code — including certainly-valid
ones like `spy.us` — returns an error/JavaScript browser-verification page
from both `stooq.com` and `stooq.pl`, via curl *and* the app's own urllib
calls. **The entire fallback is dead**, not just the mapping; the original
mapping question is unverifiable while the wall stands.

**Decision:** remove the Stooq fallback entirely. Honest nulls on Yahoo
failure; no more wasted per-symbol retries during outages. Restore from git
history if Stooq ever reopens programmatic access.

**Changed:** deleted `_stooq_quote` / `_stooq_quotes` / `_stooq_history` and
all call sites (`market.get_quotes`, `market.get_history`,
`earnings._validate_by_history`); removed the two test monkeypatches of the
dead function; updated module/config comments.

---

## P4 — Missing cohort data read as neutral (`app/ai_sentiment.py`)

**Was:** `_cohort_tone` turned a missing momentum leg into exactly 0% and a
missing breadth leg into exactly 50% (`roc or 0`, `breadth else 50`), so
partial data was judged as if calm data existed. Scope note: the gauge's
−100..100 score already skipped missing cohorts correctly — only the
per-cohort tone labels were affected; the synthesis engine never reads them.

**Decision:** **unknown-dominant** — if either input is missing, the cohort
reads `"unknown" / "insufficient data"`. No fabricated neutrality.

**Changed:** guard is now `or` instead of `and`; fake-neutral defaults
removed. New test pins all three missing-input combinations to `"unknown"`.

---

## P1 — Semis double-counted in breadth (`app/config.py`)

**Was:** `SECTORS` held both SMH and SOXX — the same market with two votes
out of 13 in every "% above 50-day MA" figure (risk signal #1, indicators).

**Decision:** **keep SMH, drop SOXX.** SMH is the more liquid fund and
already the canonical semi reference elsewhere (`risk.py` AI-theme flip,
bottleneck proxies). Breadth denominator goes 13 → 12; all breadth-derived
numbers shift slightly from this commit forward — that is the intended
correction, not a regression.

**Changed:** removed the `SOXX` entry. Bottleneck proxy lists and the risk
engine's direct SMH reads are separate usages and untouched. Tests build the
breadth universe from `config.SECTORS` dynamically, so none needed changes.

---

## P5 — Regime reports never expired (`app/regime.py`)

**Was:** once a `macro_regime_*.json` existed it was served as current
forever, however old — the only dataset without a freshness bound.

**Decision:** **3-day max age** (chosen over the suggested 7 — flags after
just two missed daily runs); expired reports are **served flagged stale**
rather than hidden, matching the 13F stale-cache-with-stamps style. The daily
09:00 task regenerates reports, so the flag only appears after repeated
detection failures.

**Changed:** `get_regime()` stamps `stale: true` + `age_days` on reports older
than new `config.REGIME_MAX_AGE_DAYS`; the Regime card renders an amber
"Stale report (Nd old)" warning line; two new tests pin fresh-not-flagged and
old-flagged behavior.

---

## P3 — Division score removed (`app/risk.py`)

**Was:** `division_score` (0 = unanimous, higher = divided) was displayed but
gated nothing, and read 1.00 ("maximally divided / healthy") when zero signals
existed — exactly backwards. The divided-vs-unanimous concept already drives
verdicts via the GREEN rung (`|bullish − bearish| <= 1`), so a formal gate
role would have been a redundant second encoding.

**Decision:** **remove entirely** (over keep-and-fix-degeneracy or promote-to-
gate).

**Changed:** metric deleted from the risk payload; "Division score" line
removed from the Risk card; synthesis narrative no longer mentions it;
corresponding test assertions and golden-payload key dropped.
