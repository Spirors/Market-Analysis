# Runbook

Exact operational procedures for the project's repetitive workflows
(install, run, refresh, scheduled tasks, install/remove helpers,
etc.) and the launch/verify/reap checklist. The *why* (the rule)
lives in the `project-rules` skill; this file holds the *how* —
commands, snippets, env vars, and the copy-pasteable turn-end
checklist.

Read this in full before launching anything.

> AGENT: replace this stub with the project's actual run commands
> once you know them. A typical structure:

```
## Run commands (reference)

```
{{SERVER_COMMAND}}                # serve at …
{{SERVER_COMMAND}} --refresh      # run a full refresh once and exit
{{SERVER_COMMAND}} --backfill     # seed the curated timeline once and exit
{{SERVER_COMMAND}} --schedule-install   # install scheduled tasks
{{SERVER_COMMAND}} --schedule-remove    # remove scheduled tasks
{{SERVER_COMMAND}} --install-shortcut   # create the desktop launcher
{{SERVER_COMMAND}} --remove-shortcut    # remove the desktop launcher
```

## Operational checklist (copy into the PR/turn notes when you launch anything)

- [ ] (replace with the project's launch/verify/reap steps)
- [ ] (tested on a real launch this session)

## Commit conventions

- Files owned by automated pipelines (scheduled tasks, watchers, CI
  jobs) are not committed from interactive sessions — let the pipeline
  commit them at the next run.
- Code, config, `AGENTS.md`, and `project_rules/` changes commit
  immediately after verification (tests pass, no obvious regressions).
  Use a scope-prefixed message: `feat(scope): …`, `fix(scope): …`,
  `chore(scope): …`, `docs(scope): …`, `refactor(scope): …`.
- Never amend an existing commit unless explicitly asked.
- Full commit-hygiene rule: `project-rules` skill § "Commit hygiene".
