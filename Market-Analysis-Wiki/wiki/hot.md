---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-14
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-14T19:00:00Z - All 15 claude-obsidian skills project-local in
.agents/skills/; redundant global copies deleted; OpenCode + Freebuff
discovery verified.

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis. Free, no-key data sources (yfinance + English-edition
  RSS); runs locally on Windows. Vault managed by claude-obsidian; the
  product root is the durable sibling checkout
  C:\Users\Spirors\Documents\Main\GitHub\Spirors\claude-obsidian
  (32ac5a0, v2.2.0). WSL writes go through `wsl -d Ubuntu-22.04`; the
  vault's .claude-obsidian.json is unreadable by the WSL identity
  (root-owned ACL), so always pass explicit --vault.
- All 15 claude-obsidian skills (wiki*, save, think, autoresearch,
  defuddle, obsidian-*, canvas) live project-locally in .agents/skills/
  (byte-identical to the checkout); the redundant global copies under
  ~/.config/opencode/skills/ are deleted, so OpenCode resolves them
  locally. Freebuff reads .agents/skills/ natively. oh-my-opencode-slim
  (8 managed skills, plugins, MCP grants) is global and OpenCode-only,
  untouched. context7/gh_grep MCPs are slim preset grants
  (~/.config/opencode/oh-my-opencode-slim.json), not opencode.jsonc.
- 95 live source pages; 47 durable decisions under
  `### decision (47)` in [[wiki/index.md]].

## Recent Changes

- maint(skills) 233568b/9355c72/8e28412 - migrated think (15th skill) into
  .agents/skills/, deleted the 15 redundant global skill copies, updated
  AGENTS.md (full set + product root, 200-line threshold held) and README
  (bundled project-local skills). Verified via opencode debug skill: all
  15 resolve locally with globals gone; read-only wiki-lint green.
- fix(ai-valuation) 1ba5288 - Fwd PE data re-wired outside indicator
  compute time; test suite repairs 47e5a7f; backend green, frontend 7/7.

## Active Threads

- Watch item: the 9 ETF-type tickers that have no forward PE (verify the
  hover reads acceptably).
