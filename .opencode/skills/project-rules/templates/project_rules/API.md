# API

> AGENT: replace this stub with the HTTP API reference for the
> project. If the project has no HTTP API, delete this file (and
> remove it from the AGENTS.md See also list). If the project has
> both an HTTP API and a CLI or library entry-point, keep this
> file for HTTP and add separate docs for the others.

## Base URL

`{{BASE_URL}}` (e.g. `http://127.0.0.1:8000` for local dev,
`https://api.example.com` for prod)

## Routes

> AGENT: one row per route. Keep the columns narrow — link the
> payload-shape detail to a separate doc if any route has a large
> request or response. Don't list every internal endpoint if the
> API has hundreds — summarise by group, then drill in.

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| {{METHOD}} | {{PATH}} | {{PURPOSE}} | {{REQUEST_LINK_OR_NONE}} | {{RESPONSE_LINK_OR_NONE}} |
| ... | ... | ... | ... | ... |

## Payload shape

> AGENT: if any route has a large or shared response shape (e.g.
> a "dashboard" payload that aggregates many sub-views), document
> it here. Otherwise omit this section.

## Error contract

> AGENT: list the error response shape and the canonical error
> codes the API returns. Most projects standardise on one of:
>
> - `{"error": "...", "code": "..."}` JSON body with HTTP status
> - HTTP status code only, plain-text body
> - A problem-details RFC 7807 envelope (`{"type": "...", "title": "...", ...}`)
>
> Pick one, document the shape, and reference the standard.
