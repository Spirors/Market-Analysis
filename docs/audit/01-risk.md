# Section 01 — Risk divergence (+ hidden Fragility)

**Status:** `AUDITED` (deep static audit complete; runtime probes not yet run)
**Priority:** 2 of 9 — **contains the audit's only `P0`**
**Last updated:** 2026-09-26

**Covers (raw parts):** `risk` card (`index.html:28-35`) and the hidden
`fragility` sub-card (`index.html:46-53`).
**Backend:** `app/risk.py` (`compute_risk`, `risk.py:559-574`),
`app/indicators.py` (VIX/breadth), payload via `/api/dashboard` → `risk`.
**Semantic reference:** `.agents/skills/risk-divergence/SKILL.md` (found
**stale** — finding 5).
**Evidence:** static review of `risk.py`, `indicators.py`, `cards.js`,
`layout.js`, `style.css`, and the risk/tooltip specs.

---

## 1. Purpose

The headline verdict card: aggregates 7 free cross-asset signals into a
GREEN/YELLOW/RED read whose core thesis is **inverted** — divided sentiment is
healthy, unanimous optimism is fragile. It also owns the hidden `#fragility`
sub-card listing optimism/distress flags with their flip conditions.

## 2. User workflow

Open dashboard → read the top card's colour wash + `<LEVEL> — <verdict>` → scan
Bull/Bear/Neutral counts → read the signals table (tone/value/read). When flags
exist, a separate "Fragility flags" card appears lower in the Stats band.

## 3. Current controls / interactions

Reorder ↑/↓ (`index.html:30-31`) · global header Refresh · injected info icon
(`cards.js:597-610`) · coverage badge `n/m` · per-card "As of … ET" vintage
stamp. No per-card refresh control.

## 4. Current tooltips

| Tooltip | Location | vs the 5-point standard |
|---|---|---|
| risk info | `cards.js:539-542` | ~2/5 — (1) ✓ · (2) partial (**only RED mechanics**; never GREEN/YELLOW or the reversed thesis) · (3) partial · (4) deps understated · **(5) ✗** |
| fragility info | `cards.js:587-589` | ~3/5 — (1) ✓ · (2) ✓ side split · (3) partial · (4) dep `valuation` is **false** · **(5) ✗** |
| inline `title=` | `index.html:30-31`, `cards.js:507,650` | one-liners, mechanism (b) — not converged |

**A user cannot predict a flip from the tooltip** (finding 3).

## 5. Bugs / correctness findings

1. **`BUG`/`DATA` · P0 — zero data fabricates a confident GREEN.**
   `risk.py:550-551`: with `total_tone == 0` (all histories missing) every gate
   fails and `abs(0-0) <= 1` yields **GREEN "Divided sentiment — healthy
   tug-of-war"**. `compute_risk` never returns an error (`risk.py:559-574`), so
   `renderRisk` paints the card green and prints "Bull 0 / Bear 0 / Neutral 0".
   This is **intentionally encoded** by `tests/test_risk_gates.py:228-239`, and
   it **violates the hard rule "unavailable → null/—, never invented"**. *Why:*
   the app's most consequential verdict confidently reports health from no data.
   **Inline-safe** — when `total_tone == 0` (or below a floor) return
   `risk_level: null`, neutral colour, verdict "Insufficient data" (or reuse the
   `risk.error` branch). The test must change with it.

2. **`BUG`/`UX` · P1 — an all-neutral tape reads GREEN.** `risk.py:550`:
   `abs(bullish - bearish) <= 1` does not require both sides present, so 7
   neutrals → "healthy tug-of-war". *Why:* a no-signal tape looks healthy.
   **Inline-safe** — require `bullish > 0 and bearish > 0` for GREEN, else
   YELLOW "No clear edge".

3. **`DATA` · P1 — VIX "unknown" rendered as "vol normal"; two views disagree.**
   `_signal_vix` abstains only on `"no data"` (`risk.py:304`), but `vix_signal`
   returns `signal:"unknown"` when the MA is short (`indicators.py:199-200`), so
   it falls through to `else → tone neutral, note "vol normal"`, value
   `"<lvl> vs MA None"` (`risk.py:318-322`) — a literal `None`. Meanwhile the
   Indicators card prints VIX signal **"unknown"** (`cards.js:165`). *Why:* the
   cross-view consistency rule; a stringified `None` is also user-visible.
   **Inline-safe** — abstain on `"unknown"`, never stringify `None`.

## 6. UX / clarity findings

4. **`UX` · P2 — group headings are unstyled.** `cards.js:61` emits
   `.flag-group-head`, but no rule exists in `style.css` (or `.orig`);
   "Euphoria evidence" / "Distress signals" render as undifferentiated text in a
   `list-style:none` list. **Inline-safe** — add the CSS rule.

5. **`UX` · P2 — the contradiction is not surfaced.** Both flag groups carry an
   identical amber `pill gov` "Active" with no side differentiation; when
   optimism and distress fire together the card offers no reconciliation. The
   docstring explains the split, the UI does not. **Inline-safe** — aside copy.

6. **`UX`/`DESIGN` · P2 — the sub-card is detached from its parent.**
   `layout.js:15-17`: `risk` → `sentiment` band but `fragility` → `stats` band,
   and `fragility` is absent from `SECTION_CARDS` (`cards.js:464-481`), so it
   gets no vintage/coverage badge despite being risk data. **Inline-safe**
   (band placement) / **track-only** (badge wiring).

7. **`UX` · P2 — stale fragility survives a risk error.** `renderRisk`
   early-returns on `!risk || risk.error` (`cards.js:22-26`) without hiding
   `#fragility`, so previous flags stay visible under a fresh "unavailable"
   banner. **Inline-safe**.

## 7. Accessibility findings

None specific to this section beyond the shared shell findings
(`00-shell-and-tooltips`). Positive: the verdict/tone **words** are rendered, so
the state is not colour-only, and the palette (`risk.py:545-555`) exactly matches
the CSS tokens (`style.css:2-4`).

## 8. Other technical findings

8. **`TOOLTIP` · P1 — the tooltip omits half the verdict logic.** `cards.js:540`
   says RED fires "when 2+ optimism-side flags align, on trend break, or on
   broad risk-off" but never states the tone supermajority that is *also*
   required (`risk.py:537-539`), nor what GREEN/YELLOW/`Divided` mean.
   **Inline-safe.**

9. **`TOOLTIP`/`DATA` · P1 — fragility deps name a non-existent source.**
   `cards.js:589` lists `valuation`, but `app/risk.py` imports only `config,
   indicators` and has no valuation strategy (`risk.py:479-488`) — the stretch
   signal was removed. Stale docstring too (`risk.py:34`), and
   `tooltip.spec.mjs:137` locks the wrong 5 deps. **Inline-safe** (copy + test).

10. **`TOOLTIP`/`ARCHITECTURE` · P1 — the semantic reference is stale.**
    `SKILL.md:16` documents `division_score`, which `compute_risk` does **not**
    return (`risk.py:559-574`), and the skill omits the 8th (AI-theme) strategy.
    *Why:* anyone reading the reference to interpret the card is misled.
    **Track-only.**

11. **`TOOLTIP` · P1 — flip numbers contradict their own thresholds.** Breadth
    overheat flip "below 65%" vs threshold 75 (`risk.py:246` / `:240`); washout
    "above 35%" vs 25 (`:259` / `:239`); AI "below 15%" vs
    `RISK_AI_EXTENSION_ROC = 25` (`:471` / `:449`); VIX "above MA" vs complacent
    ratio 0.85. Top-level `_flip_conditions` uses yet other numbers ("~55%",
    "~40%", `:577-594`). Same event, three numbers. **Inline-safe** — derive
    flips from `config`.

12. **`ARCHITECTURE` · P2 — `risk.flip_conditions` is dead output.** Computed
    (`risk.py:568`), never rendered (`renderRisk`; `.flip-block` only feeds the
    AI gauge at `cards.js:213`), yet the skill and `API.md` promise "what would
    change the call". **Track-only** — product call: render or delete.

13. **`ARCHITECTURE` · P3 — asymmetric "rising" test.** The current ROC spans 62
    slots vs the prior 63 (`risk.py:127-143`); the breadth current MA includes
    the compared bar while the prior MA does not (`indicators.py:51-85`).
    Documented quirks, but they bias `_is_rising` near thresholds. **Track-only.**

## 9. Suggested improvements

- A single `_unknown_read()` path for missing coverage (subsumes findings 1–3).
- One config-derived source for every threshold **and** its flip string
  (finding 11).
- Render `flip_conditions` under the thesis, or delete it (finding 12).
- Rewrite the tooltip to carry all 5 points, including the counter-intuitive
  thesis and freshness.

## 10. Fixes completed

**Backend (`fix-2`)** — 12/12 focused risk tests pass; frontend baseline unchanged:

- [x] **FIX-01-A** `BUG`/`DATA` **P0** — insufficient coverage now returns the `risk.error` unavailable payload instead of a fabricated GREEN; new floor knob `RISK_MIN_TONE_COVERAGE` (`app/risk.py:533-539`, `app/config.py:234`). Commit `bb59e2f`.
- [x] **FIX-01-B** `BUG`/`UX` P1 — GREEN now requires `bullish > 0 and bearish > 0`; all-neutral → YELLOW "No clear edge" (`app/risk.py:556-559`). Commit `b7521d6`.
- [x] **FIX-01-C** `DATA` P1 — `_signal_vix` abstains on `"unknown"`; `None` is never stringified (`app/risk.py:304`). Commit `19a33d4`.

**Presentation (`fix-3`)** — frontend suite unchanged at 157/4:

- [x] **FIX-01-D** `TOOLTIP` P1 — risk tooltip rewritten to all 5 points (`cards.js:549-550`). Commit `27c69fc`.
- [x] **FIX-01-F** `TOOLTIP`/`DATA` P1 — false `valuation` dep dropped (`deps` 5→4); stale flag name corrected (`cards.js:597-598`, `tooltip.spec.mjs:137`). Commit `2c6abf0`.
- [x] **FIX-01-G** `DATA`/`UX` P2 — `#fragility` hidden and cleared on risk error (`cards.js:22-35`). Commit `c17df15`.
- [x] **FIX-01-H** `UX` P2 — `.flag-group-head` rule added (`style.css:245-258`). Commit `4bfbee5`.
- [x] **FIX-01-I** `UX`/`DESIGN` P2 — `fragility` moved to the `sentiment` band (`layout.js:17`). Commit `ea3dfd7`.

**Presentation, second pass** — frontend suite **160/3** (163 tests):

- [x] **FIX-01-E** `TOOLTIP` P1 — every flip string now interpolates the exact
      constant its flag is gated on (breadth overheat 75 / washout 25, VIX ratio
      0.85, credit band 1, correlation 0.3, AI-extension 25), including the
      top-level `_flip_conditions`; new `RISK_VIX_COMPLACENT_RATIO`
      (`app/risk.py:246,259,314,345,392,471,585-602`, `app/config.py:227`).
      Commit `5b00879`.

Remaining: the `SKILL.md` / `flip_conditions` items — see §11.

## 11. Tracked TODOs

**Applied (see §10):** FIX-01-A, FIX-01-B, FIX-01-C, FIX-01-D, FIX-01-E,
FIX-01-F, FIX-01-G, FIX-01-H, FIX-01-I.

**Still to dispatch:** none.

**Track-only / follow-up:**
- [ ] Update `.agents/skills/risk-divergence/SKILL.md` (drop `division_score`, add the AI-theme strategy)
- [ ] Decide render-vs-delete for `flip_conditions`; sync `API.md`
- [ ] Give `fragility` a vintage/coverage badge (`SECTION_CARDS`)
- [ ] Confirm no consumer expects `division_score`

**Runtime probes (Q6 bounded):**
- [ ] Force all histories empty; confirm the live GREEN fabrication (F1)
- [ ] Send `{risk:{error:true}}`; confirm the stale fragility card persists (F7)

## 12. Verification notes

Static + specs are sufficient for findings 1–7 and 9–13. **Positive:** the risk
breadth % and the Indicators "Breadth — Sectors & Indices" are the **same**
`pct_above_ma` universe and agree — a cross-view consistency win. The P0 fix
(`FIX-01-A`) changes an existing green-path test, so it must land with its test
in the same commit. Any applied fix is verified via `README.md` §8.
