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

2026-09-14T20:00:00Z - Project skills consolidated: all 19 skills now
live in .agents/skills/ (15 claude-obsidian + 4 domain); .opencode/skills
removed; .slim cleaned and gitignored.

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis. Free, no-key data sources (yfinance + English-edition
  RSS); runs locally on Windows. Vault managed by claude-obsidian; the
  product root is the durable sibling checkout
  C:\Users\Spirors\Documents\Main\GitHub\Spirors\claude-obsidian
  (32ac5a0, v2.2.0). WSL writes go through `wsl -d Ubuntu-22.04`; the
  vault's .claude-obsidian.json is unreadable by the WSL identity
  (root-owned ACL), so always pass explicit --vault.
- All 19 project skills live in .agents/skills/: the 15 claude-obsidian
  skills (wiki*, save, think, autoresearch, defuddle, obsidian-*, canvas;
  byte-identical to the sibling checkout, redundant global copies deleted)
  plus the 4 project-authored domain skills (data-pull,
  financial-deep-research, news-filter, risk-divergence; moved from
  .opencode/skills/, which is now gone). Freebuff and OpenCode both scan
  .agents/skills/. skills-lock.json is the GitHub-installer manifest and
  tracks only the 8 third-party skills there. oh-my-opencode-slim (8
  managed skills, plugins, MCP grants) is global and OpenCode-only;
  context7/gh_grep are slim preset grants in
  ~/.config/opencode/oh-my-opencode-slim.json, not opencode.jsonc.
- 95 live source pages; 47 durable decisions under
  `### decision (47)` in [[wiki/index.md]].

## Recent Changes

- maint(skills) 55d4080 - moved the 4 project domain skills from
  .opencode/skills/ into .agents/skills/ (git mv, verified via opencode
  debug skill); removed empty .slim/ and broadened .gitignore to .slim/.
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
