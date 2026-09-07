# Testing

> AGENT: replace this stub with the project's test-suite overview.
> The structure below works for any project type. Delete sections
> that don't apply (e.g. the frontend block if there's no frontend).

## Quick start

```bash
# Run the full suite
{{TEST_COMMAND}}

# Run a single test file
{{TEST_COMMAND}} {{TEST_PATH}}

# Run a single test by name
{{TEST_COMMAND}} -k {{TEST_NAME}}
```

> AGENT: add any project-specific flags here (e.g. network-marker
> gating, coverage flags, race detection).

## Suite layout

> AGENT: one line per test file or test category. Skip trivial
> smoke tests. If the suite is small enough to fit on screen, an
> indented bullet list works better than the table.

| Path | Covers |
|------|--------|
| `{{TEST_PATH}}` | {{WHAT_IT_COVERS}} |
| ... | ... |

## Conventions

> AGENT: project-specific test conventions. The kind of things
> that prevent regression-test rot:
>
> - "Every new mutation function MUST extend the regression suite
>   before it ships" — see `project_rules/RUNBOOK.md` for the
>   procedural reminder.
> - "All network-heavy tests are gated behind a marker so they
>   don't run in the default CI lane."
> - "Frontend tests need a static server on port X — pytest's
>   harness auto-starts it but interactive runs need it started
>   manually."
>
> Bullet list, one per convention.

## Known gaps

> AGENT: list the modules / functions that are currently under-
> tested or untested. These are candidates for the next test-
> coverage pass. If there is a ROADMAP.md item for "close test
> gaps", link it.
