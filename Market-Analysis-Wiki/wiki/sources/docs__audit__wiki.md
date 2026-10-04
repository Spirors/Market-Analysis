---
type: source
title: "Wiki retrieval audit"
status: archived
created: 2026-10-04
updated: 2026-10-04
imported_at: 2026-10-04
source_kind: audit
original_path: "docs/audit/wiki.md"
original_sha256: "a301fdfce9bc644641f5e634ece0fe1238a690dc1062fc15314ae34c0acc1355"
stored_path: ".raw/captured/a301fdfce9bc644641f5e634ece0fe1238a690dc1062fc15314ae34c0acc1355.md"
retired_from: "docs/audit/ (removed 2026-10-04; last repo commit 1e03a2e)"
tags:
  - source
  - audit
  - history
---

# Wiki retrieval audit

> **Historical — not live state.** This is the finished app audit's section
> file, archived 2026-10-04 and retired from the repo. It described the code
> as of 2026-09-27 and is kept for reference only: do **not** treat it as
> current status or instructions. Live state is [[wiki/hot.md]]; the code is
> the source of truth.

# Wiki Audit — is the vault a retrievable memory?

**Status:** `COMPLETE` (deep; retrieval built and probe-tested 2026-09-26, three
parked decisions taken — see §6)
**Companion to:** `docs/audit/README.md` (the app audit). Same taxonomy and
`P0–P3` priorities.

**Question this answers:** is the wiki a *memory an agent can search*, or just a
tidy pile of Markdown that only `index.md` makes sense of?

**Answer:** the vault's **content** is well-curated; its **retrieval layer was
never switched on**. It is now built and probe-tested, and it works — with two
systemic noise sources and one freshness gap that need decisions.

Method: read-only recon of `wiki/` + the repo (Orchestrator only — sub-agents
must not read the vault), then a real build of the retrieval cache and a scored
12-query probe set. No wiki content was changed.

---

## 1. What exists today

| Layer | State | Verdict |
|---|---|---|
| `wiki/index.md` | 107 entries (103 live + 4 retired); matches the file tree; one-line subjects; supersession callouts; historical sections quarantined | **Maintained, not bloat-by-default** |
| `wiki/hot.md` | ≤500-word bounded cache, rewritten per session | Good |
| `wiki/log.md` | Append-only, transaction-owned | Good |
| `wiki/sources/` | 107 pages; 55 durable decisions | Good |
| `.vault-meta/bm25/` | Built 2026-09-26 (156 chunks); now rebuilt at session end | **Resolved** — was `P1` "never provisioned" |
| Structure | 43/107 pages (40%) are historical: `session (26)` + `history (10)` + `design-history (7)` | Labelled, but they inflate any scan |

`bm25-index.py stats` before the build: `ERR: no index at
.vault-meta/bm25/index.json. Run build first.` So an agent had exactly two ways
to find memory: read all 177 lines of `index.md`, or grep. Neither is "retrieve
the right page".

## 2. Build (now done)

Local, no network egress (`--no-llm` synthetic prefixes):

```bash
P=<product-root>/claude-obsidian            # scripts/ here
V=…/Market-Analysis-Wiki                    # explicit --vault
python3 "$P/scripts/contextual-prefix.py" --vault "$V" --all --no-llm
python3 "$P/scripts/bm25-index.py" --vault "$V" build
python3 "$P/scripts/bm25-index.py" --vault "$V" stats
```

Result: **111 pages → 156 chunks → 4,282 vocabulary terms**. Read-only query:

```bash
python3 "$P/scripts/retrieve.py" --vault "$V" "<query>" --top 5 --no-rerank
```

## 3. Retrieval quality (12-query probe)

| # | Query intent | Expected page | Rank |
|---|---|---|---|
| 1 | risk gauge / divided sentiment | `…risk-gauge-design…` | **1** |
| 2 | portfolio star scope | `…per-portfolio-scope-must-use-composite-keys…` | **1** |
| 3 | news duplicate/dedupe | `…news-section-overhaul…` | 4 |
| 4 | test isolation → temp dir | `…test-isolation-autouse-conftest…` | 4 |
| 5 | bottleneck topics API contract | `…bottleneck-section-api-and-agent-contract…` | **1** |
| 6 | saved card order / CARD_BAND | `…every-data-card-in-index-html-must-also-appear-in-card-band…` | **1** |
| 7 | yfinance-only market data | `…market-data-yfinance-only…` | **1** |
| 8 | commit message conventions | `project_rules__RUNBOOK` | **absent** |
| 9 | frozen reference files | `…frozen-reference-files-are-not-touched…` | **1** |
| 10 | AI gauge lookback 30 days | `…ai-gauge-lookback-window-30-days…` | **1** |
| 11 | start / reap the server | `project_rules__RUNBOOK` | 3 |
| 12 | why phase 1 ran ahead of phase 0 | `…why-phase-1-ran-ahead-of-phase-0…` | **1** |

**Score: 8/12 top-1, 11/12 top-5.** Lexical BM25 is enough for this vault; a
semantic rerank (Ollama `nomic-embed-text-v2-moe`) is optional and untested here.

## 4. Findings

1. **`P1` · `ARCHITECTURE` · retrieval was never provisioned.** The skills
   existed, the vault didn't. Any agent instructed to "query the wiki" would
   have hit a missing index. *Now built.*

2. **`P1` · `ARCHITECTURE` · nothing keeps the index fresh.** The prefixer
   invalidates the BM25 index when the chunk set changes, but **no transaction
   rebuilds it** — so after the next `wiki-ingest`/`save` the index silently
   goes stale and `retrieve.py` fails closed (exit 10). *Why it matters:* an
   unmaintained index is worse than none, because agents will trust stale hits.
   **Decided 2026-09-26:** session end owns the rebuild (§6.1).

3. **`P2` · `DATA` · meta hub pages pollute every result set.** `wiki/index.md`
   and `wiki/log.md` are giant lists of page titles, so they lexically match
   almost any query. They appear in the top-5 of **10 of 12** probes. *Why:*
   they are navigation, not knowledge — they crowd out the real page and give
   the caller a table of contents instead of an answer. **Decided 2026-09-26:**
   accepted and documented (§6.2).

4. **`P2` · `DATA` · retired/superseded pages compete with live ones.**
   `sources/_retired/**` appeared in the top-5 of 4 probes (e.g. `_retired/
   project_rules__DECISIONS.md` ranked 4th for the portfolio-scope query), and
   superseded decisions are still fully indexed. *Why:* contradicts the
   index's own careful "superseded" callouts — retrieval ignores them.
   **Decided 2026-09-26:** accepted and documented (§6.2).

5. **`P2` · `TEST` · one clean miss.** "commit message scope prefix
   convention" did not surface `RUNBOOK` at all, yet `README.md`/AGENTS.md
   point there for commit conventions. Either `RUNBOOK` under-describes the
   convention or the query tokens miss its phrasing. *Why:* the load-bearing
   operational page is unreachable by its most natural query.

6. **`P3` · `ARCHITECTURE` · 40% of the corpus is historical.** `session (26)` +
   `history (10)` + `design-history (7)`. The index labels them, retrieval does
   not. *Why:* they dilute precision on "how does the system work today"
   questions.

## 5. Recommended improvements (prioritised)

- **`P1`** Rebuild the index as part of the session-end write (or the
  `wiki-ingest`/`save` transaction) so it can never go stale. Smallest viable:
  add the two build commands to the session-end checklist in `RUNBOOK`.
  — **DONE 2026-09-26:** session end owns the rebuild (§6.1); the rule is in
  `AGENTS.md` + `session-memory-protocol.md`.
- **`P2`** Exclude `wiki/index.md`, `wiki/hot.md`, `wiki/log.md` from the chunk
  set (navigation, not knowledge), or down-weight them. — **DECIDED: accept and
  document** (§6.2); the tooling exposes no knob.
- **`P2`** Exclude or down-weight `wiki/sources/_retired/**`, and consider
  down-weighting pages whose frontmatter marks them superseded. — **DECIDED:
  accept and document** (§6.2).
- **`P2`** Add a retrieval line to the session protocol: prefer
  `wiki-query`/`wiki-retrieve` over a full `index.md` scan, and read
  `index.md` only as an orientation map. — **PARTIAL:** `AGENTS.md` already
  routes roadmap/past-decision questions to `wiki-query`; the orientation-map
  wording is still open.
- **`P3`** Enrich `RUNBOOK` (or add a dedicated decision page) with explicit
  commit-convention tokens: `feat(scope)`, `fix(scope)`, `chore`, `docs`,
  `refactor`, `test`, "one logical change per commit". — **OPEN** (P3).
- **`P3`** Maintain a small local query set (the 12 above are a start) and
  re-score after each change — the skill's own "grow" checkpoint. — **OPEN**
  (P3); the §3 probe set is the baseline.

## 6. Decisions taken (2026-09-26)

All three parked decisions are resolved. The durable record is
`wiki/sources/decision__retrieval-index-rebuilt-at-session-end-2026-09-26` in the
vault.

1. **Index freshness owner → session end.** The session-end step rebuilds
   `.vault-meta/bm25` (`contextual-prefix.py --all --no-llm`, then
   `bm25-index.py build`) in the same pass as the `hot.md` rewrite and `log.md`
   append; `AGENTS.md` and `wiki/meta/session-memory-protocol.md` carry the rule.
   The ingest/save transaction was rejected — the transaction engine lives in the
   shared upstream `claude-obsidian` clone, so patching it is a cross-project
   change for one vault's benefit.
2. **Corpus policy → accept and document.** No tooling layer
   (`contextual-prefix.py`, `bm25-index.py`, `retrieve.py`, `rerank.py`) exposes
   an exclude or down-weight knob, so `index`/`hot`/`log` and
   `sources/_retired/**` stay indexed; callers treat the hubs as navigation, not
   knowledge. Relocating `_retired/` to a dot-directory was rejected (partial
   win, breaks `index.md` references); patching upstream was rejected as in (1).
3. **Rerank → stay lexical-only.** No Ollama on this machine, and 8/12 top-1 is
   sufficient for a 107-page corpus. Revisit only if the corpus grows enough that
   lexical retrieval degrades.

The §3 probe set is the re-score baseline after any future retrieval change.

## 7. Verification notes

- Index built locally; **no network egress** (`--no-llm`, synthetic prefixes).
- `.vault-meta/` is gitignored runtime state — nothing to commit in the vault.
- Retrieval output is **not** evidence: the caller still reads the returned
  page before synthesising (per the skill's integrity rules).
- No wiki content files were created, modified, or deleted. *(2026-09-26
  follow-up: the decisions in §6 **were** recorded as one vault decision page
  plus edits to `index`/`log`/`hot`/`overview`/`session-memory-protocol`; the
  retrieval index was rebuilt in the same turn.)*
- Probe runner: `C:\Users\Spirors\AppData\Local\Temp\opencode\wiki-q.sh`.

## 8. Relation to the app audit

The app audit's backlog (`docs/audit/README.md` §13) references durable
decisions by name. With retrieval now live, a future session can resolve those
references with a query instead of reading the whole index. Per the user's
2026-09-26 decision, the wiki is updated **as each README task is tackled** —
this page records the state to resume from.

## Citation

- **Original:** `docs/audit/wiki.md` (retired from the repo 2026-10-04; last repo commit `1e03a2e`)
  - SHA-256: `a301fdfce9bc644641f5e634ece0fe1238a690dc1062fc15314ae34c0acc1355`
- **Captured:** `.raw/captured/a301fdfce9bc644641f5e634ece0fe1238a690dc1062fc15314ae34c0acc1355.md`
