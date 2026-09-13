---
type: source
title: "Hard-rule propagation — project-rules skill, not AGENTS.md alone"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/hard-rule-propagation-project-rules-skill-not-agents-md-alone-undated.md"
original_sha256: "22bae3ee7ee0ccb62ce0dbddff6dd4cb53243bf6fdd3d6181ff9cad8a7ae6f71"
stored_path: ".raw/captured/22bae3ee7ee0ccb62ce0dbddff6dd4cb53243bf6fdd3d6181ff9cad8a7ae6f71.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Hard-rule propagation — project-rules skill, not AGENTS.md alone

AGENTS.md auto-injects into the parent orchestrator but not into subagent sessions; hard rules must live in the project-rules skill and be invoked via the skill tool before subagent dispatch, with output included in the dispatch prompt.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/hard-rule-propagation-project-rules-skill-not-agents-md-alone-undated.md`
  - SHA-256: `22bae3ee7ee0ccb62ce0dbddff6dd4cb53243bf6fdd3d6181ff9cad8a7ae6f71`
- **Captured:** `.raw/captured/22bae3ee7ee0ccb62ce0dbddff6dd4cb53243bf6fdd3d6181ff9cad8a7ae6f71.md`

## Key claims

- Hard rules must live in .opencode/skills/project-rules/SKILL.md and be invoked before any subagent dispatch.
- AGENTS.md and the skill are deliberately kept in sync — the skill survives subagent dispatch, AGENTS.md survives session restart.

## Concepts

- `hard-rules`
- `subagent-dispatch`
- `skill-propagation`

## Entities

- `.opencode/skills/project-rules/SKILL.md`
- `AGENTS.md`
