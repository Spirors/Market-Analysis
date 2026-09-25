---
type: source
title: "A poisoned agent-model binding is inherited by child sessions"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - workflow
---

# A poisoned agent-model binding is inherited by child sessions

A session whose agent-model binding is poisoned cannot delegate **at all**:
every `subagent(...)` dispatch fails with
`Variant unavailable for opencode-go/mimo-v2.5: high`, regardless of agent type.
Child sessions inherit the parent's resolved binding, so retrying inside the
poisoned session can never succeed. **Open a fresh session and dispatch from
there.** No config change is needed.

## Why the obvious fixes are wrong

The stale binding exists in exactly one place on disk — a
`oh-my-opencode-slim.json.council-setup.bak` backup, where explorer and librarian
were `opencode-go/mimo-v2.5` with `"variant": "high"`, an exact match for the
error string. That makes deleting the `.bak` or editing the config look like the
fix. It is not:

- The plugin's `findConfigPath` reads only `<base>.jsonc` then `<base>.json` and
  **never globs**, so the `.bak` is never loaded.
- The live config binds those agents to `mimo-v2.6-flash` with **no** variant.
- The runtime bundle contains zero occurrences of `mimo` and zero of `v2.5`; the
  only `mimo-v2.5` in the package is in the CLI *installer* template (observer
  only), and the plugin log for the session contains no `mimo-v2` string at all.
- No `mimo` reference exists anywhere in the repository working tree.

So the stale `.bak` is a red herring: the binding is resolved **per session
context and cached in memory**. Editing config or deleting the `.bak` changes
nothing and destroys a file for no reason.

## How to tell, and what to do

1. The error names a model/variant pair that appears nowhere in the live config.
2. Confirm by reading the live config and grepping the runtime bundle, rather than
   by trusting the error string.
3. **Start a fresh session** and make one cheap dispatch. If it succeeds, the
   binding is clean and the diagnosis is confirmed — which is how this was
   proven.
4. Only if a fresh session also fails should the model cache be suspected:
   `~/.cache/opencode/models.json` can be stale relative to the provider's current
   model list.

## Consequence for planning

Delegation-heavy work should not be restarted inside a poisoned session, and a
session that has been poisoned should hand off through a written plan rather than
trying to work around the failure. That written-plan handoff is what made this
session possible.
