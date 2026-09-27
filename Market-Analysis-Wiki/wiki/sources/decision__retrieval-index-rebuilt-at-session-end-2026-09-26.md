---
type: source
title: "The retrieval index is rebuilt at session end; corpus noise and rerank stay accepted"
status: evergreen
created: 2026-09-26
updated: 2026-09-26
source_kind: decision
tags:
  - source
  - decision
  - retrieval
  - wiki
---

# The retrieval index is rebuilt at session end; corpus noise and rerank stay accepted

The wiki audit (`docs/audit/wiki.md`, 2026-09-26) found that the vault's
retrieval layer had never been provisioned, then built and probe-tested it (111
pages -> 156 chunks; 8/12 top-1, 11/12 top-5). It parked three decisions; this
page records how they were taken.

## 1. Freshness is owned by session end

`contextual-prefix.py` invalidates the BM25 index when the chunk set changes, but
no `save` / `wiki-ingest` transaction rebuilt it - so after the next vault write
the index silently went stale and `retrieve.py` failed closed (exit 10). An
unmaintained index is worse than none, because callers trust stale hits.

**Decision:** the session-end step rebuilds the index, in the same pass that
rewrites `wiki/hot.md` and appends `wiki/log.md`. The build was already the
documented manual path, so no tooling changes.

```bash
# WSL as root, explicit --vault; product root is the sibling claude-obsidian repo
P=/mnt/c/Users/Spirors/Documents/Main/GitHub/Spirors/claude-obsidian
V=/mnt/c/Users/Spirors/Documents/Main/GitHub/Spirors/Market-Analysis/Market-Analysis-Wiki
python3 "$P/scripts/contextual-prefix.py" --vault "$V" --all --no-llm
python3 "$P/scripts/bm25-index.py" --vault "$V" build
```

Rebuilding inside the ingest/save transaction would be a stronger guarantee, but
the transaction engine lives in the shared upstream `claude-obsidian` repository
(a separate clone, v2.2.0). Patching it is a cross-project change for one vault's
benefit, so it was rejected.

## 2. Corpus noise is accepted and documented, not filtered

Two noise sources dilute every result set: the navigation hubs
(`wiki/index.md`, `wiki/hot.md`, `wiki/log.md`) lexically match almost any query -
they appeared in the top-5 of 10 of 12 probes - and `wiki/sources/_retired/**`
competes with live pages despite the index's supersession callouts.

**Decision:** accept and document. Every tooling layer (`contextual-prefix.py`,
`bm25-index.py`, `retrieve.py`, `rerank.py`) selects or filters with no
exclude/down-weight knob, so the real choices were patch upstream, restructure
the vault, or document. Callers must treat the hubs as navigation, not knowledge,
and ignore them in result sets.

Rejected alternatives: relocating `_retired/` to a dot-directory (Python's
`rglob` skips dot-paths) excludes retired pages only, still leaves the hubs, and
breaks the `index.md` references - a structural change for a partial win.
Patching upstream carries the same cross-project cost as decision 1.

## 3. Rerank stays lexical-only

Retrieval scored 8/12 top-1 with BM25 alone; three recall misses remained. A
local `nomic-embed-text-v2-moe` cosine rerank exists in `rerank.py` but needs a
running Ollama instance, which this machine does not have.

**Decision:** stay lexical-only. No external service dependency, no install, and
the misses are tolerable for a corpus this size. Revisit only if the corpus grows
enough that lexical retrieval degrades.

## Consequences

- The retrieval index has an explicit owner and a documented rebuild command.
- Corpus noise is a known, documented limitation - not an open TODO.
- `retrieve.py` stays dependency-free; no Ollama requirement.
- The 12-query probe set in `docs/audit/wiki.md` Sec 3 is the re-score baseline
  after any future retrieval change.
