# API

HTTP routes and dashboard payload shape. Read this **on demand** when a task
touches an endpoint or the payload contract — not part of mandatory
session-start reading (see `AGENTS.md`).

## HTTP API

| Method        | Path                              | Purpose                                                                                                                                                                                                  |
| ------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET           | `/api/dashboard`                  | Cached-or-refreshed dashboard payload                                                                                                                                                                    |
| POST          | `/api/refresh?full=`              | Refresh data (+ regime detection when `full=true`)                                                                                                                                                       |
| GET           | `/api/events?limit=`              | List stored market events                                                                                                                                                                                |
| DELETE        | `/api/events?link=` or `?source=` | Delete one event, or all from a source                                                                                                                                                                   |
| POST          | `/api/events/suppress?source=`    | Blocklist a source and purge its events                                                                                                                                                                  |
| GET           | `/api/analysis/history?limit=`    | Logged synthesis runs (newest first)                                                                                                                                                                     |
| GET           | `/api/earnings`                   | Enriched earnings calendar                                                                                                                                                                               |
| GET           | `/api/earnings/validate?symbol=`  | Validate a ticker before adding                                                                                                                                                                          |
| POST / DELETE | `/api/earnings/watchlist?symbol=` | Add / remove a ticker                                                                                                                                                                                    |
| GET           | `/api/regime`                     | Latest regime report                                                                                                                                                                                     |
| POST / GET    | `/api/shutdown`                   | Schedule `os._exit(0)` ~300 ms out (called by the dashboard's `pagehide` / `beforeunload` beacons — keeps the desktop launcher from leaking a lingering cmd window). The next page's `pageshow` beacon to `/api/cancel-shutdown` aborts the exit, so F5 / link-nav / bfcache restore never kill the server. |
| POST / GET    | `/api/cancel-shutdown`            | Cancel a pending `/api/shutdown` exit. Idempotent. Sent by the dashboard on `pageshow` so a page reload survives without taking down the local server.                                                   |

## Dashboard payload sections

`as_of`, `market` (indices / volatility / rates / commodities / sectors),
`indicators`, `risk`, `bottleneck`, `futures`, `spot` (fed into the
Commodities card via `spot.commodities_map`; not its own card), `thirteenf`,
`earnings`, `ai_sentiment`, `news`, `regime`, `ai_analysis`, `events`.
