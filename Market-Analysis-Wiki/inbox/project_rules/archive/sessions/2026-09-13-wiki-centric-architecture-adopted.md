
---

# 2026-09-13 — Wiki-centric architecture adopted

**Summary:** Adopted `github.com/AgriciDaniel/claude-obsidian` as the
project's knowledge-base tool; ingested all 99 sources from
`project_rules/*.md`, `project_rules/archive/**/*.md`, `docs/logs/*.md`,
and `docs/superpowers/{plans,specs}/*.md` into the
`Market-Analysis-Wiki/` vault; restructured to a wiki-centric
architecture where source documents live at
`Market-Analysis-Wiki/raw/<dir>/<file>.md` (preserving the original
directory structure) and `AGENTS.md` is the only canonical rules
file (no separate `project-rules` skill).

## What shipped

**Phase 0 — Environment check.** WSL confirmed available
(`docker-desktop` default). The docker-desktop WSL distro has no
Python or bash, so Ubuntu 22.04 was installed via
`wsl --install -d Ubuntu-22.04 --no-launch` (admin required for WSL
install). Python 3.12.13 was installed via
`apt-get install python3.12 python3.12-venv` from the deadsnakes PPA.

**Phase 1 — Install and adopt.**
- Cloned `AgriciDaniel/claude-obsidian` to
  `C:\Users\Spirors\AppData\Local\Temp\opencode\claude-obsidian`
  (scratch location, NOT inside the vault — per the product's design
  that the source clone is not the vault).
- Adopted the existing vault via
  `python3.12 claude-obsidian.py adopt` (not `init` — the vault
  already existed with `.obsidian/` config). Approval SHA
  `d8af041ccc0f0b8d05870990868cac6e51c4eb05092d6ba2041517d8261cd08e`;
  applied 11 foundation files: `.claude-obsidian.json`,
  vault-local `.gitignore`, `.obsidian/snippets/vault-colors.css`,
  `.raw/.manifest.json`, `inbox/.gitkeep`, `wiki/{hot,index,log,overview}.md`,
  `wiki/meta/ledgers/{claim,source}-ledger.json`.
- Installed OpenCode integration via
  `bash scripts/setup-multi-agent.sh --host opencode --apply`
  (Git Bash on Windows — the bash script is POSIX-portable). 15
  skill symlinks created at `~/.config/opencode/skills/<name>`:
  autoresearch, canvas, defuddle, obsidian-bases, obsidian-markdown,
  save, think, wiki, wiki-cli, wiki-fold, wiki-ingest, wiki-lint,
  wiki-mode, wiki-query, wiki-retrieve. The 8 pre-existing
  skills were left untouched — installer's `--check` confirmed no
  conflicts.
- **WSL metadata workaround:** added
  `[automount] options = "metadata"` to `/etc/wsl.conf` and ran
  `wsl --shutdown`. Without this, `os.chmod()` is a no-op on
  `/mnt/c` and the adopt apply fails with `RESULT_DRIFT` (file
  created at mode 0o511 instead of the expected 0o600).

**Phase 2 — Organize sources.** The original plan was
`mklink /J` junctions from `Market-Analysis-Wiki/inbox/` to
`project_rules/` and `docs/`, but `capture.py` rejects junctions
(`SOURCE_SYMLINK` check — WSL sees Windows reparse points as
symlinks). The decision was to drop junctions and stage physical
copies into `inbox/`. 99 files copied: 9 from `project_rules/`
root, 26 from `archive/sessions/`, 47 from `archive/decisions/`,
17 from `docs/{logs,superpowers}/`. The `.gitignore` line
`Market-Analysis-Wiki/inbox/` was added.

**Phase 3 — Initial ingest.**
- `capture apply` with approval SHA
  `ab30cfa7c64a0e8f2cdb961bd7cee48c8adae6caa4f9dc6d1fbb6d7f7ad53062`
  created 99 content-addressed captures at
  `.raw/captured/<sha>.md`. Idempotency verified: re-running the
  plan produced `would_change: 0, skipped: 99, status: noop`.
- `transaction inspect` then `transaction apply` with approval SHA
  `9e7c2b70b87c5406c471fc019b9f1083bf59da2cc89f9d3b043f1df15de21e4b`
  wrote 102 vault files: 99 source pages at
  `wiki/sources/<slug>.md`, plus updated `wiki/{index,log,hot}.md`.
  `source_manifest_updates` on the bundle populates
  `.raw/.manifest.json` — do NOT write
  `wiki/meta/ledgers/source-ledger.json` directly (the engine
  manages it).
- **Wiki-ingest scope:** 4 parallel background explorer subagents
  read the 99 originals and produced source-page drafts as JSON.
  Groups: docs (17), project_rules root (9), archive/sessions (26),
  archive/decisions (47). Orchestrator aggregated the drafts,
  built the transaction bundle, applied via `transaction apply`.
  No concept/entity pages created — the wiki-ingest
  compilation-value gate filtered them out (most sources are
  point-in-time records, not durable synthesis).
- **Acceptance:** 5 sample SHA-256s matched pre-ingest values;
  HANDOFF wiki page shows the full citation chain
  (original_path + original_sha256 + stored_path); re-capture plan
  shows `would_change: 0` on all 99 items.

**Phase 4 — AGENTS.md Wiki section.** Added `## Wiki` between
`## Skills` and `## See also`, pointing at `wiki-ingest`,
`wiki-query`, `wiki-lint`, and noting the WSL requirement for
vault writes. Added `Wiki knowledge-base sync` bullet to the
hard-rules list.

**Phase 5 — Wiki-centric restructure.** User redirected
mid-phase from "strip Bootstrap/Retrofit" to: inline all Core
rules into AGENTS.md; move `project_rules/` and `docs/` to
`Market-Analysis-Wiki/raw/` preserving structure; remove
`.opencode/skills/project-rules/` entirely.
- `community-plugins.json` is already `[]` — no `karpathywiki`
  entry to remove (no-op).

## Architectural decisions

- **Wiki is canonical, raw/ is the working markdown store.**
  Future edits go to `Market-Analysis-Wiki/raw/<dir>/<file>.md`,
  then `wiki-ingest` folds the changes into
  `wiki/sources/<slug>.md`. Captures in `.raw/captured/<sha>.md`
  are immutable by content address — they only grow (or stay
  constant) as sources change.
- **Hard-rules live in AGENTS.md, not a separate skill.**
  Trade-off: every session reads ~390 lines upfront (vs ~141
  before). Per the Documentation Hygiene rule, this is acceptable
  for a "read in full, every time" file.
- **WSL is the only path that writes to the vault.** Native
  Windows fails closed (`os.name == "nt"` →
  `UNSUPPORTED_PLATFORM`). Read-only queries (capture plan,
  contract verify, doctor) work natively.

## Verification

- `python3.12 doctor --vault ...` → `ok: true`, all checks pass.
- Capture re-plan: `would_change: 0, skipped: 99, status: noop`
  (idempotent on unchanged sources).
- 5/5 sample originals verified SHA-256-unchanged after the entire
  ingest pipeline.

## Files touched (this session)

- **Created (vault):** `Market-Analysis-Wiki/{.claude-obsidian.json,
  .gitignore, .obsidian/snippets/vault-colors.css, .raw/.manifest.json,
  inbox/.gitkeep, wiki/{hot,index,log,overview}.md, wiki/meta/ledgers/
  {claim,source}-ledger.json, wiki/sources/<99 files>, .raw/captured/
  <99 files>, raw/{project_rules,docs}/<all files>}`
- **Modified:** `AGENTS.md` (rewritten, ~141 → ~390 lines,
  hard-rules inlined + paths updated), `.gitignore`
  (`Market-Analysis-Wiki/inbox/` added), `Market-Analysis-Wiki/raw/
  project_rules/HANDOFF.md` (this session's state appended),
  `Market-Analysis-Wiki/raw/project_rules/SESSION_LOG.md`
  (this entry)
- **Removed from repo (now in wiki only):** `project_rules/` (9 + 73
  archive files), `docs/` (18 files),
  `.opencode/skills/project-rules/` (skill + templates)

## Decision pointer

See `Market-Analysis-Wiki/raw/project_rules/DECISIONS.md` →
"Wiki-centric architecture adopted — originals relocated to
`Market-Analysis-Wiki/raw/`, hard-rules inlined in AGENTS.md,
`project-rules` skill removed (2026-09-13)".

## Notes for the next session

- **Don't run `wiki-query` until after wiki-lint passes.**
  wiki-lint is deterministic; wiki-query reads the same graph.
- **`source_manifest_updates` not direct ledger writes.** When
  building transaction bundles for ingest, use the
  `source_manifest_updates` field — the engine writes
  `.raw/.manifest.json` and the wiki/meta/ledgers/{source,claim}-
  ledger.json files from there. Writing the ledger JSON directly
  triggers `INVALID_PROVENANCE_LEDGER` because source IDs must be
  `src-<digest[:20]>` (not raw SHA-256) and each entry needs an
  `origin: {kind, locator}` object.
- **`os.chmod()` is a no-op on `/mnt/c` without `metadata` in
  `/etc/wsl.conf [automount] options`.** Any future WSL-based
  tooling that touches the vault needs this config.
- **The vault is `.gitignore`d by omission, not by an explicit
  rule.** Future agents should keep it that way. The whole
  `Market-Analysis-Wiki/` is local to this machine.

## Archive

Full text in
`archive/sessions/2026-09-13-wiki-centric-architecture-adopted.md`.
