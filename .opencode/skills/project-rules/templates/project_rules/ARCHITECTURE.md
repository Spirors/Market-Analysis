# Architecture

> AGENT: replace this stub with a description of the project's
> architecture. The structure below is a generic template that
> works for any webapp / CLI / library — adapt the headings to
> your project type, delete sections that don't apply, add
> sections that do.

## Stack

> AGENT: 1-3 sentences naming the primary language, framework(s),
> storage layer, and any non-obvious infrastructure. Example:
> "Python 3.11 + FastAPI for the backend, vanilla JS + a thin
> WebSocket layer for the live dashboard, JSON files for local
> persistence, yfinance / RSS / curl_cffi for data acquisition."

## Module map

> AGENT: list every significant module in the project. One line per
> module: path → what it does, who calls it. Skip trivial files
> (single-function utilities, type-only modules, etc.).

| Module | Role | Called by |
|--------|------|-----------|
| `{{MODULE_PATH}}` | {{ROLE}} | {{CALLERS}} |
| ... | ... | ... |

## Section-to-code map

> AGENT: if the project has UI sections / routes / CLI commands /
> API endpoints that span multiple modules, list them here so a
> reader can trace "what code backs this feature" without
> grepping the whole tree.

| Surface | Module(s) |
|---------|-----------|
| {{SURFACE}} | {{MODULE(S)}} |
| ... | ... |

## Known quirks

> AGENT: anything a future session must not silently re-discover.
> Usually phrased as "the obvious approach doesn't work because
> X" or "we intentionally did Y even though Z is the standard
> pattern". One bullet per quirk. Reference the matching
> `project_rules/DECISIONS.md` entry so the rationale stays
> discoverable.

- ...
