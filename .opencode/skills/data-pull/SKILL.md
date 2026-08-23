---
name: data-pull
description: Pull market data (indices, VIX, yields, commodities, sectors, ETF histories) and market events from free no-key sources for the Market Analysis Tool. Use when refreshing, extending, or debugging market data acquisition in this repo.
---

# Data Pull

Acquire market data and market events for the Market Analysis Tool using free
sources (yfinance primary, Stooq fallback, RSS feeds). No API keys required.

## Where the code lives

- `app/market.py` — quotes + bulk histories (`build_market_snapshot`,
  `get_quotes`, `get_histories_bulk`, `get_history`), Stooq fallbacks.
- `app/news.py` — RSS event ingestion with a strict High/Critical filter
  (`fetch_and_store`) + curated seed loader (`seed_events`).
- `app/seed_data.py` — the curated, hand-tagged 2026 event timeline.
- `app/config.py` — the tracked symbols (`INDICES`, `RATES`, `COMMODITIES`,
  `SECTORS`, `CROSS_ASSET`) and `NEWS_FEEDS`. Add a new symbol or feed HERE.

## Conventions

- Every number must trace to a fetched source; never fabricate values.
- Results are cached to `data/cache/` with TTLs in `app/config.py`
  (`QUOTE_TTL`, `HISTORY_TTL`).
- `^TNX`, `^FVX`, `^IRX`, `^TYX` are yield*100 (4.5 = 4.5%).
- Handle Yahoo rate limits / breakages defensively; Stooq CSV is the fallback.
- Events: only High/Critical survive ingest (`IMPORTANCE_THRESHOLD = 6.0` in
  `app/news.py`).

## Commands

```bash
python -c "from app import service; import json; print(json.dumps(service.refresh_market(), default=str))"
python -c "from app import service; service.refresh_news()"
python -c "from app import service; service.backfill_news()"   # curated seed, idempotent
```
