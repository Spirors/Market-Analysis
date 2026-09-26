---
type: source
title: "Underdogs are $3B emerging names, and generation reports four named research stages"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - bottleneck
  - serenity
---

# Underdogs are $3B emerging names, and generation reports four named research stages

Two changes to the Bottleneck ("Serenity") section, shipped together
(`992efec`, `db148e7`).

## 1. Underdogs: a $3B gate and a stated definition

`UNDERDOG_CEILING_DEFAULT` is **$3B**, not $10B. $3B is the skill's own headroom
threshold — `references/methodology.md:334`, "Small enough (<~$3B at call for his
moonshots) that institutional re-rating is still ahead?" — so the app's default
now matches the lens it drafts with. The per-topic `underdog_ceiling` override
stays: this is a default, not a hardcode.

Underdogs are defined as **emerging stocks with great potential**, and the
definition is written once and mirrored verbatim in the two places a reader meets
it: the per-topic note (`app/bottleneck.py:_topic_note`) and the section help text
(`static/js/cards.js`). "Great potential" is carried by the researched thesis card
(`why_chokepoint`, `catalyst`, `evidence`) — the ceiling is the mechanical gate,
and no metric is invented to express it.

The **core/extended conviction tier is removed end to end**: the constant, the
`tier_for_market_cap()` helper, the `conviction_tier` card field, its validation,
the tier pill and its CSS. Reason: at a $3B ceiling it collided with
`CORE_TIER_MAX = $3B`, so `extended` became unreachable and every underdog would
have been `core`. Re-cutting the cutoff lower would have meant inventing a number
the skill does not supply, so the tier went instead. Ranking is unchanged and
stays deterministic: 40-day ROC, descending, in the pure read engine.

## 2. Generation reports four named research stages

A generation job persists an ordered `stages` list — the frontend's progress
contract — with statuses `pending | running | done | skipped | failed` and a
`note` for any degraded step:

| key | label |
|---|---|
| `refresh_skill` | Refresh skill |
| `read_lens` | Read lens |
| `draft` | Draft thesis |
| `warm_metrics` | Pull market data |

- Only `draft` can fail the job; the other three are **non-fatal** and record a
  note instead (e.g. an offline `npx` refresh falls through to the cached lens).
- `warm_metrics` is bounded (~20s) and reuses the existing warm path rather than
  a parallel warmer; a timeout leaves the succeeded draft intact.
- Jobs persisted before the field existed are served as-is, and the panel falls
  back to the old indeterminate bar.
- Transport is unchanged: 1.5s polling of `GET /api/bottleneck/jobs/{id}`. There
  is no SSE or streaming anywhere in the app.

**Behaviour change to keep in mind:** stage 1 now actually runs the `npx` skill
refresh as part of a generation run. Before this, the refresh was reachable only
from the explicit `POST /skill/refresh` endpoint, so a generation could draft
from a stale lens.

Research reach is deliberately **skill-lens only**: refresh the skill, read its
reference files, and use the app's own market/news caches. The drafting call is a
single `chat/completions` request with no tools, so it cannot browse; live web
lookup would need a new mechanism and stays out of scope.

## Verified

Backend 633 passed (+ 13 lifecycle); Playwright 143 passed with the 4 known
pre-existing failures; the bottleneck spec 20 passed. Each commit was also tested
alone, so neither is a broken intermediate. Live against the real backend: the
four stages rendered and advanced (`refresh_skill: done`, so the npx refresh ran
for real), a degraded run showed `draft: failed` + `warm_metrics: skipped`, and a
hand-created topic stored `underdog_ceiling = 3000000000` with the chip reading
`≤ $3B` and zero tier pills.

`agent-browser screenshot` is now **verified** end-to-end (it saved a PNG); the
earlier "unverified" note came from three redirected-pipe wrapper hangs, not the
tool.

## Generation budget and prompt contract

Follow-up 1 below is closed. `deepseek-v4.1-flash` is a **reasoning** model on
the Go lane (models.dev: context 1M, output 384k, Reasoning: Yes), and its
reasoning tokens are counted inside `completion_tokens`, so they share the
`max_tokens` budget. At the old `MAX_TOKENS = 8000` the reasoning stream alone
consumed the budget, so the response came back with empty `content` and
`finish_reason='length'` — no retry could have produced content, and the retry
loop resent an identical request.

Measured headlessly against the live endpoint, same theme, same prompt:

| run | reasoning tokens | completion tokens | elapsed | result |
|---|---|---|---|---|
| before | — | 8000 (capped) | ~90s | empty content, `length` |
| cap raised | 12,208 | 15,971 | 78.4s | `stop`, 14,125 chars, validator errors |
| typed prompt | 13,274 | 16,501 | 82.0s | `stop`, 12,670 chars, validator clean |

So `MAX_TOKENS = 64_000` and `REQUEST_TIMEOUT_S = 600`. Two rules this
established:

- **`max_tokens` is a cap, not a reservation** — a large value costs nothing
  unless the model actually emits it, so it is set far above the ~2k tokens a
  draft needs. The model's own ceiling is 384,000.
- **The timeout must scale with the cap**, or the failure merely becomes a read
  timeout instead of a `length` stop. Throughput is ~200 tok/s, so the two move
  together.

Cost is not a concern on the subscription: ~$0.01/request, and Go meters this
model in rolling dollar windows ($12/5h, $30/week, $60/month off-peak).

The second, independent blocker was the **prompt contract**. The schema block
listed each card field's *name* and never its *type*, so a real draft returned
`invalidation` as a string (5 cards) and a non-string inside
`upstream[].stocks` (3 layers), failing `validate_topic` on both. The prompt now
carries an explicit type table — strings, `invalidation` is a LIST, `evidence`
is a list of objects, `metrics`/`provenance` are objects, and the four checklist
flags are tri-state rather than strings — plus a plain-ticker-strings rule.
Guarded by `test_schema_instructions_state_each_field_type`.

Go-lane facts worth not re-deriving: `GET /zen/go/v1/models` returns model ids
only (no limits) and needs the `x-opencode-session` header; it lists 35 models
and the app's frozen `ALLOWED_MODELS` is a superset of them. `max_tokens` is the
accepted field on `chat/completions`. `reasoning_content` and `usage` are
present in the response and were being discarded — they are what made this
diagnosable.

## Upstream layer shape: name, constraint, watch

The drafting prompt asked for a layer shaped as `layer` + `stocks` while the
store, engine and renderer all speak `name` + `physical_constraint` +
`what_to_watch` + `stocks`. Nothing bridged the two: `_normalize_draft`
back-filled only the *topic* `name`, `_validate_layer` checked only `stocks`, so
`_layer_block` emitted an empty `name` and the UI showed an em dash with the
Constraint/Watch lines silently dropped. Every render and contract fixture
hand-supplied a layer name, which is why the suite never caught it — only
agent-generated topics were unlabelled, and the editor path was always fine.

The contract is now stated in all four places:

| place | contract |
|---|---|
| prompt (`_schema_instructions`) | a layer is `{name, physical_constraint, what_to_watch, stocks}`; `name` must be non-empty; the prose fields are strings (`""` when unknown) |
| `_normalize_draft` | promotes a legacy `layer` key into `name`; defaults the prose fields to `""`; keeps unknown keys |
| `_layer_block` (engine) | aliases `layer` -> `name` on read — the same idiom it already used to fold a legacy `gauge` into `what_to_watch` |
| `_validate_layer` | rejects a nameless or mistyped layer, so the drafting retry loop self-corrects |

The read-path alias means **already-stored topics repair without migration**:
the topic generated before the fix now labels all five layers from its stored
`layer` key. Its `physical_constraint` / `what_to_watch` stay empty, because that
draft never produced them and nothing invents data.

Verified live: a fresh headless generation returned five layers each with a
name, a constraint and a watch item — `finish_reason='stop'`, 19,094 completion
tokens (12,144 of them reasoning) in 102s, validator clean on attempt 1.

## Research: the agent gets a harness

The skill is instructions plus reference files — a prompt bundle with no
capabilities. Inside an opencode session it *appears* to research because the
harness supplies `websearch`/`webfetch`/`Bash`; the skill is identical either
way. The app kept the skill's **files** and the **model** and dropped the
**harness**, so the lens was the only evidence it ever had: a theme outside the
lens came back as either the wrong chain (an AR-eyewear theme returned the InP
datacenter chain) or as three empty layers.

A generation now runs six stages:

| key | label |
|---|---|
| `refresh_skill` | Refresh skill |
| `read_lens` | Read lens |
| `draft` | Draft chain |
| `research` | Research web |
| `fill` | Draft thesis |
| `warm_metrics` | Pull market data |

`draft` is the existing one-shot JSON call and emits a thin skeleton. `research`
shells out to the local **opencode CLI**, whose harness supplies the web tools:
`opencode run --agent researcher --model opencode-go/<model> --format json
--auto --standalone`. `fill` is a second one-shot JSON call that refines the
skeleton against method + lens + the researched findings, so the strict JSON
contract holds on both model calls and only the middle stage is agentic. The lens
is no longer the answer; it is method plus evidence.

Four rules the CLI stage depends on, each learned the hard way:

- **`--standalone`**, or the run attaches to the user's shared background server.
- **The prompt travels on stdin** — Windows caps argv at 32,767 chars and
  literal-quotes any argument containing a space.
- **`provider/model` is required** (`opencode-go/...`); a bare id does not select
  the Go subscription, and `opencode/...` would be Zen pay-per-token instead.
- **`cwd` must be the repo root**, or the project-scoped agent is not discovered.

The agent is version-controlled at `.opencode/agents/researcher.md`:
`mode: primary` (a `subagent`-mode agent silently falls back to the default) and
a V2 `permissions` array allowing read/glob/grep/webfetch/websearch and denying
edit/shell/question. `deny` beats `--auto`, and headless auto-rejects anything
left `ask`, so the read-only confinement is real rather than advisory.

Every research failure is non-fatal: the stage is noted and the pipeline falls
back to the lens-only skeleton. Findings and their source URLs are persisted on
the job as `job["research"]`.

Verified live against two real themes. The CPO theme returned 30 source URLs and
14,283 chars of findings. The AR-eyewear theme — which previously produced three
empty layers — returned 53 source URLs and 19,920 chars, and its layers now name
real suppliers: VUZI/AMAT/GLW/COHR for waveguides, HIMX/KOPN/AMS for
microdisplays, sourced from IDTechEx, RoadToVR, Lumus/Quanta, optics.org,
Applied Materials IR, ams-OSRAM and Nichia.

## Two spawn defects found while testing

- **Locale-decoded output.** Both child spawns used `text=True` with no
  `encoding`, so the Windows locale codec (cp1252) decoded the CLI's UTF-8
  output, raised mid-stream and silently discarded the findings — the research
  stage reported "no usable findings" while the CLI had run fine for three
  minutes. Both now pass `encoding="utf-8", errors="replace"`.
- **A console window flashed on every refresh** because neither spawn set
  `CREATE_NO_WINDOW`. One shared `_spawn_kwargs()` helper now applies it on
  Windows for both.

## The job-store race (the "flaky gate")

`_load_jobs`/`_save_jobs` are lock-free and the write callers hold `_JOBS_LOCK`,
but the public readers `get_job()`/`list_jobs()` did not. A reader could open the
job file while a writer thread was inside `store.save_json`'s `os.replace` — a
Windows sharing violation that surfaces as a `PermissionError` on the read and
kills the worker thread mid-job. It failed 3-12 tests per run with a different
set each time, which is why the gate could not be trusted; in the live app it is
a request handler erroring while a job runs. Both readers now take the lock, and
five consecutive runs of the previously-flaky file pass.

## Open follow-ups

1. **With a 600s timeout, Cancel only takes effect between attempts.** An
   in-flight request is not aborted, so a cancel can look unresponsive for up to
   10 minutes.
2. **A terminal failure hides the stage list**, so the "which step failed" view
   disappears exactly when it is wanted.

### Phase 2

3. **Researched sources are persisted but not visible.** `job["research"]`
   carries the findings and their URLs; the review panel does not show them yet.
4. **The draft chain and the final thesis can disagree.** `fill` refines the
   `draft` skeleton against the researched findings, but nothing constrains it to
   be a *refinement*: it may add, drop or rename layers and tickers relative to
   the skeleton, so the mid-run preview and the applied result are inconsistent.
   *(User-reported, 2026-09-26.)* Establish which inconsistency was actually
   observed before designing the fix, then decide whether the final must be a
   strict refinement of the skeleton or whether the difference should be surfaced
   in the review panel.

### Cost

5. **Generation is now minutes, not seconds.** The research stage browses, so a
   run is ~5-8 minutes and bills the Go subscription through the CLI.
