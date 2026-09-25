---
type: source
title: "The serenity chokepoint skill is installed locally, not vendored"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - skills
---

# The serenity chokepoint skill is installed locally, not vendored

The Bottleneck section's methodology comes from
`yan-labs/serenity-aleabitoreddit`, installed into
`.agents/skills/serenity-aleabitoreddit/` and **gitignored**. The previously
vendored `w-y-p/serenity-aleabitoreddit-skill` is deleted, all 10 tracked files
(`8800256`).

## Why

The upstream repo declares `license: null`. Committing its content would be
unlicensed redistribution, so the skill body is never committed. `skills-lock.json`
**is** tracked and records the provenance (`source`, `skillPath`, `computedHash`),
so the repository states what should be installed without redistributing it.
`.gitignore` carries the install command alongside the ignore entry.

## Install and update commands

A plain `npx -y skills add ...` aborts: it needs an agent target and a TTY, and a
webapp has neither. The working non-interactive form is:

```bash
npx -y skills add yan-labs/serenity-aleabitoreddit -a universal --copy -y
npx -y skills update serenity-aleabitoreddit -a universal -y
```

`universal` is the agent name that maps to this repository's `.agents/skills/`
convention; `--copy` avoids a symlink. These run from
`app/topic_agent.refresh_skill()`, the app's **only** child-process spawn site,
which reaps and verifies the child.

## Agent safety boundary

The skill's reference files are treated as **untrusted third-party evidence
text**: quoted as evidence, never executed, never fetched, never followed as
instructions. A scanner rates the repo medium risk; the 6,592-tweet archive and
the X scrapers (`update.py`, `prep.py`) are never used. The agent reads
`references/methodology.md` and `references/theses.md` always, and routes to the
other reference files through the table in `SKILL.md`.

## Caveats to keep visible

- `references/theses.md`'s merged base is **frozen at ~2026-06-08**, with newer
  material appended as dated entries (dated bullets near the top, plus flat
  per-ticker "latest signal" sections). The UI states this so a stale base is not
  read as current.
- `skill_status()["hash"]` is a documented content hash (SHA-256 over sorted
  `<relpath>:<sha256(file)>` lines). It is deliberately **not** equal to the
  `computedHash` in `skills-lock.json`, which is the `skills` CLI's own
  undocumented scheme. Both are content-derived and move together; only one is
  shown in the UI. Reconciling them is an open follow-up.
