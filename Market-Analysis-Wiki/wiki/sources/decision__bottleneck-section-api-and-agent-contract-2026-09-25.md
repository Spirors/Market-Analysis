---
type: source
title: "Bottleneck section API and agent contract"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - bottleneck
  - api
---

# Bottleneck section API and agent contract

The reference for the topic-driven Bottleneck section's HTTP surface and its
drafting agent. The vault's imported
[[sources/project_rules__API|API page]] predates this and still lists the
deleted category routes.

## Routes

| Method | Path | Notes |
|---|---|---|
| GET | `/api/bottleneck/topics` | the front-end's **single** render call |
| POST | `/api/bottleneck/topics` | `{name}` -> 201 topic |
| GET | `/api/bottleneck/topics/export` | the export document |
| POST | `/api/bottleneck/topics/import` | a list or `{version, topics}` |
| POST | `/api/bottleneck/topics/generate` | `{theme, model?, topic_id?}` -> 201 job |
| PUT | `/api/bottleneck/topics/{topic_id}` | the raw topic patch |
| DELETE | `/api/bottleneck/topics/{topic_id}` | 204 |
| GET | `/api/bottleneck/jobs` | bare JSON list, newest first |
| GET | `/api/bottleneck/jobs/{job_id}` | one job |
| POST | `/api/bottleneck/jobs/{job_id}/cancel` | cooperative |
| POST | `/api/bottleneck/jobs/{job_id}/apply` | `{topic_id, summary?}` -> topic |
| GET | `/api/bottleneck/skill/status` | skill status **plus** `generation` |
| POST | `/api/bottleneck/skill/refresh` | runs the installer CLI, reaped |

`GET /topics` returns `{topics, bottleneck, generation}`: the raw stored topics
for the edit forms, the computed payload for rendering, and
`{enabled, error}` so the UI can disable generation **before** a click rather
than discovering the failure on one. The computed half is cheap because
`bottleneck_read` is a pure, cache-only read, and it is what lets a freshly
created topic render its ranked layers and tiered underdogs without a full market
refresh.

## Error mapping

- **404** unknown topic or job id.
- **400** a blank `name`; a `PUT` patch that would persist an invalid topic
  (carrying the validator's own messages); a malformed import payload.
- **409** `generate` precondition failure — missing key, missing skill, or a run
  already in progress — with the exact user-facing message in `detail`, surfaced
  verbatim rather than replaced by a generic toast.
- **204** delete, empty body.
- `skill/refresh` returns **200 even when the CLI fails**, with `ok: false` and the
  output tail in the body; only an unexpected exception is a 500.

## Jobs

Serial (an overlapping start is **refused**, not queued), cooperatively
cancellable, persisted to `data/bottleneck_jobs.json` with `MAX_JOBS = 50`
(newest kept), and process-local locking. A job left `queued`/`running` by a crash
is marked **interrupted** on the next start rather than holding the serial lock
forever. Applying a draft is explicit and appends one numbered `source="agent"`
revision; nothing reaches the topic store before that.

**Import persists the valid subset**, merged into the existing store (a matching
`id` replaces, no `id` appends); invalid topics are never written and come back in
`errors`, so `imported` always equals what was actually persisted.

## The agent

- Endpoint `POST https://opencode.ai/zen/go/v1/chat/completions` — note `/zen/go/v1/...`,
  a different endpoint family from Zen's `/zen/v1/...`.
- Required headers: `Authorization: Bearer <key>`, `Content-Type: application/json`,
  a stable `x-opencode-session` per job, and a **custom, non-generic `User-Agent`**.
- Default model `deepseek-v4.1-flash`. A per-run override is whitelisted to the live
  chat/completions family and rejected before any transport call.
- Output handling: prompt for JSON, extract defensively (the model may wrap it in
  prose or a fence), validate with `bottleneck_topics.validate_topic`, then retry
  **at most twice** feeding the validator's own error strings back. No
  structured-output API dependency.
- An **empty `content` is a retryable failure, not a valid draft**: the model can
  spend its whole `max_tokens` budget on `reasoning_tokens` and return
  `content: null` with `finish_reason != stop`. The response carries a
  `reasoning_content` sibling to `content`.
- Cost envelope at the time of writing: off-peak $0.15/$0.60 per M tokens, peak
  $0.30/$1.20, $60/month bucket, ~26k requests/month.

The key is `OPENCODE_GO_API_KEY` in a gitignored `.env` (process env wins over the
file). Absent, it disables generation only — manual CRUD and metrics are unaffected.

## Why the underdog ceiling tiers instead of filtering

`AAOI` reports a market cap of ~$8.69B and `AXTI` ~$5.19B. A flat $3B cap would
have excluded both, which is why the ceiling has a `core` (< ~$3B) and
`extended` ($3-10B) tier per topic rather than a single cutoff, and why a stock
whose market cap is unavailable is kept with a dash tier instead of being dropped.

## Metric units

`market_cap` is USD; `roc_40d` and `move_1y` are percent; `forward_pe` is a
multiple and is negative for a loss-maker; `revenue_growth` is a **ratio, not a
percent** (`0.18` = +18%). Units are stated in `bottleneck_topics.METRIC_FIELDS`
so no consumer guesses and none converts in the UI.
