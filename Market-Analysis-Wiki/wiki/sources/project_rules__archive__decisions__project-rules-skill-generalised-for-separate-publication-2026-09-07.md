---
type: source
title: "project-rules skill generalised for separate publication"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/project-rules-skill-generalised-for-separate-publication-2026-09-07.md"
original_sha256: "c1fbad4d94883ac9392a0419a1105ba337c86e8feff8dd574382b37d5c1d79bd"
stored_path: ".raw/captured/c1fbad4d94883ac9392a0419a1105ba337c86e8feff8dd574382b37d5c1d79bd.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# project-rules skill generalised for separate publication

The project-rules skill was stripped of project-specific sections (Card behavior, Risk gauge, Commodities) and repo-specific anchors, making it portable and project-agnostic. Project-specific rules now live in DECISIONS.md only; the skill encodes universal principles.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/project-rules-skill-generalised-for-separate-publication-2026-09-07.md`
  - SHA-256: `c1fbad4d94883ac9392a0419a1105ba337c86e8feff8dd574382b37d5c1d79bd`
- **Captured:** `.raw/captured/c1fbad4d94883ac9392a0419a1105ba337c86e8feff8dd574382b37d5c1d79bd.md`

## Key claims

- When adding a rule to the skill, ask: does this apply to ANY project? If only to this feature, document it in DECISIONS.md instead.
- The skill's Bootstrap section teaches the agent to read templates/ and write AGENTS.md + seed files in a fresh repo.

## Concepts

- `skill-generalisation`
- `portable-rules`
- `separation-of-concerns`

## Entities

- `.opencode/skills/project-rules/SKILL.md`
- `templates/`
- `DECISIONS.md`
