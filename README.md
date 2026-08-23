# Market Analysis Tool

A local webapp for macro-trend market analysis. Monitors market conditions and
trend, tracks key earnings, analyzes indicators (breadth, margin-proxies, vol),
filters macro/micro news, finds bottlenecks (serenity-style chokepoint
investing), and — most importantly — flags **trend shifts and the fragility
setup that forms when market sentiment stops being divided.**

## Quick start

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000 in your browser.

- **Dashboard** loads the latest cached snapshot (auto-refreshes on a TTL).
- **Refresh** button runs a full refresh (data + news + earnings + regime).
- First load / full refresh pulls data from free sources and can take ~1 minute.

## What it shows

| Panel | What it tracks |
|---|---|
| Risk banner | GREEN / YELLOW / RED divergence read with the specific evidence and flip conditions |
| Fragility flags | Consensus-optimism / capitulation markers (the "structure for disaster" signal) |
| Macro regime | Reused `macro-regime-detector` 6-component classification |
| Indicators | Breadth, SPY trend, realized vol, VIX signal |
| Indices / Rates | S&P 500, Nasdaq, Dow, Russell, VIX, Treasury yields, commodities |
| Breadth chart | % of sectors/indices above their 50-day MA |
| Bottleneck | Serenity-style chokepoint layers mapped to proxy tickers |
| Earnings | Upcoming earnings calendar for the mega-cap universe |
| Events timeline | Curated, tagged market events (2026 → now) + strict High/Critical live RSS |

## Data sources (free, no keys)

- **yfinance** — indices, VIX, yields, commodities, sector/cross-asset ETFs.
- **Stooq** — CSV fallback when yfinance fails.
- **MarketWatch RSS** — the single live news feed (High/Critical events, 48h window only).
- **Curated seed** — hand-tagged 2026 event timeline from the frozen gauge file, Wikipedia, and researched news.

## Architecture

Python (FastAPI) backend + vanilla JS frontend. See `AGENTS.md` for the full
module map, skills, and hard rules.

## The archived files

`ai_market_cycle_diagram_v4.html`, `ai_market_sentiment_gauge.html`,
`ai_market_positioning.html`, and `ai_thesis_timeline.html` are **frozen
reference material** from a prior project. They seeded the analysis framework
and design system used here. Do not modify them.

> Not investment advice. Data is directional and sourced but unaudited.
