# News Section Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the news firehose + GDELT/Wikipedia backfill with a curated, tagged market-events timeline (2026-01-01 → now, seeded once) plus a strict High/Critical-only live RSS flow.

**Architecture:** Single `events` table with explicit tag columns (category/actor/direction/region/impact/date_label). Curated seed (`app/seed_data.py`) loaded idempotently; live RSS classified by retuned keyword heuristics with threshold 6.0. Frontend filter chips unchanged in mechanics.

**Tech Stack:** Python 3.12, FastAPI, SQLite (stdlib), feedparser, vanilla JS.

**Spec:** `docs/superpowers/specs/2026-08-18-news-section-overhaul-design.md`

## Global Constraints

- Free, no-key sources only. No new pip dependencies.
- Never fabricate market data — every seed entry traces to the frozen gauge file, a Wikipedia article, or the researched sources listed in Task 1.
- Only High/Critical events are stored (importance threshold 6.0; bands `[(9.0, "Critical"), (6.0, "High")]`).
- Actor tag nullable; every other dimension always present.
- No test framework and no git repo: verification = deterministic `python -c` smoke checks + running the server. Skip all commit steps.
- Do not modify the 4 frozen `ai_*.html` files.
- PowerShell 7 shell; run commands with `workdir` = repo root.

---

### Task 1: Curated seed data (`app/seed_data.py`)

**Files:**
- Modify: `app/seed_data.py` (full rewrite)

**Interfaces:**
- Produces: `SEED_EVENTS: list[dict]` where each dict has exactly: `date` (ISO `YYYY-MM-DD`), `date_label` (str, optional — original fuzzy label), `title` (str), `summary` (str, optional), `link` (str), `source` (str), `category` (`macro`|`micro`), `actor` (`government`|`company`|None), `direction` (`bullish`|`bearish`|`neutral`), `region` (`us`|`japan`|`china`|`middle-east`|`europe`|`korea`|`russia-ukraine`|`global`), `impact` (`Critical`|`High`).

- [ ] **Step 1: Rewrite the file**

Compose `SEED_EVENTS` from three sources, in this order of precedence (later duplicate entries are dropped during curation, not in code):

**A. Existing Wikipedia seed** (all 35 rows currently in `app/seed_data.py`, keep their links; source `"Wikipedia"`): keep every row, converted to the new schema. Tag each by these rules:
- category: government shutdowns, tariffs, Fed, inflation, OPEC, war, elections, trade deals, central banks → `macro`; company/IPO/M&A/CEO news → `micro`.
- actor: governments/central banks/courts/military → `government`; companies (Nvidia, Meta, Apple, WBD, SpaceX, Spirit, EA) → `company`.
- direction: war escalation, tariffs, shutdown, Fed probe, delisting → `bearish`; peace deal, trade deal, IPO → `bullish`; court rulings/structural → `neutral` where neither case dominates.
- region: from the obvious country each event concerns (Bulgaria euro → `europe`; US airstrikes Venezuela → `global` (US acting abroad, no dedicated region → use `us` if the market impact is on US assets; otherwise global); Iran war events → `middle-east`; Japan election → `japan`; India–EU FTA → `global`).
- impact: `Critical` for: wars/blockades, Fed chair replacement, shutdowns, Iran war, Hormuz closure, tariff walls, inflation record, Nvidia -17%; `High` for the rest.
- date: exact date from the row.

**B. Gauge events** (from the frozen `ai_market_sentiment_gauge.html` `EVENTS` array; source `"Curated (gauge)"`):
- SKIP the 4 pure-2025 rows: "Nov 18, 2025" (Microsoft+Nvidia→Anthropic), "2025" (Nvidia→OpenAI $100B), "Oct 2025" (SK Hynix sold out), "Dec 2025" (CoWoS 600-850K wafers).
- SKIP duplicates already covered by A: the gauge "Nvidia shares plunge 17%" is already in A (keep A's row).
- Map each remaining row: `title` = condensed card text (first clause, ≤ ~90 chars); `summary` = full card text; `direction` ← col (`bear`→`bearish`, `bull`→`bullish`, `neutral`→`neutral`); `category` ← `type`; `actor` ← `government` if the event is Fed/CPI/tariffs/war/policy/courts/regulators, else `company`; `region` by affected market (CPI/Fed/FOMC/treasury → `us`; KOSPI/Samsung/SK Hynix/Korea exports → `korea`; China export bans on Japan → `japan`; China five-year plan/Moonshot/Huawei → `china`; EU compute package → `europe`; Iran/OPEC/Strait → `middle-east`; cross-region structural themes (GPU debt, circular financing, AI capex) → `global`).
- `impact` ← `Critical` when `|weight| >= 5`, else `High`.
- `date_label` = original `dateLabel`; `date` normalized: "Jan 14–15, 2026"→`2026-01-14`; "Jan 2026"→`2026-01-15`; "Jan/Feb/Jun 2026"→`2026-01-15`; "Feb 2026"→`2026-02-15`; "Feb–Apr 2026"→`2026-02-15`; "Q1 2026"→`2026-02-15`; "Apr 2026"→`2026-04-15`; "May 2026"→`2026-05-15`; "May–Jun 2026"→`2026-05-15`; "Jun 2026"→`2026-06-15`; "Jun–Jul 2026"→`2026-06-15`; "Jul 2026"→`2026-07-15`; "Jul–Aug 2026"→`2026-07-15`; "2026"→`2026-06-30`; "2025–26"→`2026-01-01`; "Ongoing 2025–26"→`2026-01-01`; "2026 est."→`2026-06-30`; "Mid-2026"→`2026-06-30`; "YTD May 2026"→`2026-05-15`; "Q2 2026"→`2026-05-15`; exact dates ("Apr 30, 2026"→`2026-04-30`, "Jun 12, 2026"→`2026-06-12`, "Jul 1, 2026"→`2026-07-01`, "Jul 14, 2026"→`2026-07-14`, "Jul 16, 2026"→`2026-07-16`, "Jul 17, 2026"→`2026-07-17`, "Jun 1 & 8, 2026"→`2026-06-01`, "Mar 2, 2026"→`2026-03-02`, "May 6, 2026"→`2026-05-06`, "Apr 8, 2026"→`2026-04-08`) → use the exact date, no `date_label`.
- `link`: real Wikipedia article when confident (Nvidia→`https://en.wikipedia.org/wiki/Nvidia`, OpenAI→`.../wiki/OpenAI`, Anthropic→`.../wiki/Anthropic`, TSMC→`.../wiki/TSMC`, Samsung→`.../wiki/Samsung_Electronics`, KOSPI→`.../wiki/KOSPI`, Jerome Powell→`.../wiki/Jerome_Powell`, FOMC→`.../wiki/Federal_Open_Market_Committee`, SpaceX→`.../wiki/SpaceX`, CoreWeave→`.../wiki/CoreWeave`, Palantir→`.../wiki/Palantir_Technologies`, Salesforce→`.../wiki/Salesforce`, ServiceNow→`.../wiki/ServiceNow`, Micron→`.../wiki/Micron_Technology`, SanDisk→`.../wiki/SanDisk`, SK Hynix→`.../wiki/SK_Hynix`, Huawei→`.../wiki/Huawei`, CPI→`.../wiki/United_States_Consumer_Price_Index`, Burry→`.../wiki/Michael_Burry`, Amazon→`.../wiki/Amazon_(company)`, Meta→`.../wiki/Meta_Platforms`, Google Cloud→`.../wiki/Google_Cloud`, Stratos of Hormuz → `https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis`, OpenAI IPO → `https://en.wikipedia.org/wiki/OpenAI`); otherwise `seed://<YYYYMMDD>-<slug>` (slug = lowercase-hyphen title, no punctuation).

**C. Researched gap-fill** (source `"Wikipedia (current events)"` for wiki links, `"News (researched)"` for news links): add these researched events with real links, tagged by the same rules (all `region` `middle-east`/`russia-ukraine`/`korea`/`us`/`global` as noted, `impact` `Critical` except where noted `High`):

- 2026-07-18 — Iran suspends Islamabad Memorandum commitments, accusing the US of breaching the deal — https://en.wikipedia.org/wiki/2025%E2%80%932026_Iran%E2%80%93United_States_negotiations — macro/government/bearish/middle-east/Critical
- 2026-07-20 — Brent crude tops $90 and US gasoline passes $4/gal as Iran escalation resumes — https://www.cnbc.com/2026/07/20/oil-prices-today-brent-wti-crude-us-iran-centcom-hormuz.html — macro/government/bearish/middle-east/Critical
- 2026-07-20 — Trump signs executive order imposing 50% tariffs on many Canadian goods including USMCA products — https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_trade_war_with_Canada_and_Mexico — macro/government/bearish/us/Critical
- 2026-07-21 — OpenAI says AI models "went rogue" during testing, triggering an "unprecedented" breach at Hugging Face — https://www.reuters.com/technology/openai-says-ai-models-went-rogue-during-testing-triggering-unprecedented-breach-2026-07-21/ — micro/company/bearish/us/High
- 2026-07-21 — Russia halts bond auctions after recent sales failed to find buyers — https://www.bloomberg.com/news/articles/2026-07-21/russia-halts-bond-auctions-with-more-monetary-easing-in-question — macro/government/bearish/russia-ukraine/High
- 2026-07-23 — US imposes 10–12.5% tariffs on 60 trading partners over forced labor — https://en.wikipedia.org/wiki/Tariffs_in_the_second_Trump_administration — macro/government/bearish/us/Critical
- 2026-07-23 — Brent tops $101, WTI near $93 after Red Sea escalation — https://www.nbcnews.com/business/markets/oil-prices-rise-red-sea-attacks-houthis-saudi-trump-iran-war-rcna588851 — macro/government/bearish/middle-east/Critical
- 2026-07-27 — Houthi drone attack damages the Abqaiq oil field in eastern Saudi Arabia — https://en.wikipedia.org/wiki/Abqaiq_oil_field — macro/government/bearish/middle-east/Critical
- 2026-07-27 — Singapore's MAS tightens monetary policy for the second time in three months citing Iran-war inflation risks — https://en.wikipedia.org/wiki/Monetary_Authority_of_Singapore — macro/government/bearish/global/High
- 2026-07-28 — Taiwan detains an Nvidia employee in an AI-chip smuggling probe to China — https://www.france24.com/en/live-news/20260728-taiwan-detains-nvidia-worker-in-chip-smuggling-probe-source-familiar-with-case — micro/company/neutral/china/High
- 2026-07-28 — Mw 7.1 earthquake strikes Kumamoto, Japan; tsunami alert; toll later rises to 35 dead — https://en.wikipedia.org/wiki/2026_Kumamoto_earthquake — macro/None/bearish/japan/High
- 2026-07-30 — US awards Lockheed Martin a record $58.6B Patriot interceptor contract — https://en.wikipedia.org/wiki/Lockheed_Martin — micro/company/bullish/us/High
- 2026-07-31 — KOSPI surges 18%, its largest single-day gain in history, on AI investment surge — https://en.wikipedia.org/wiki/KOSPI — macro/company/bullish/korea/Critical
- 2026-08-04 — Bulk carrier Minoan Pioneer struck by projectile, reported missing in the Strait of Hormuz — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bearish/middle-east/Critical
- 2026-08-05 — Iran and Oman reach agreement on shipping-route coordinates through the Strait of Hormuz — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bullish/middle-east/High
- 2026-08-07 — US Senate passes (86–11) Russia energy-sanctions bill with 100% tariffs on buyers of Russian oil/gas — https://en.wikipedia.org/wiki/Sanctioning_Russia_Act — macro/government/bearish/russia-ukraine/Critical
- 2026-08-08 — Iran says it will reopen the Strait of Hormuz if the US lifts sanctions and ends its naval blockade — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bullish/middle-east/High
- 2026-08-10 — Ukrainian drone attack on the Nizhnekamsk oil refinery in Tatarstan kills 13 — https://en.wikipedia.org/wiki/Attacks_in_Russia_during_the_Russo-Ukrainian_war_(2022%E2%80%93present) — macro/government/bearish/russia-ukraine/High
- 2026-08-13 — UAE says two more ADNOC vessels attacked in the Strait of Hormuz, accuses Iran — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bearish/middle-east/Critical
- 2026-08-14 — Trump says US will declare the Strait of Hormuz a US territory "pretty soon" — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bearish/middle-east/Critical
- 2026-08-15 — Third ADNOC vessel attacked by Iran in the Strait of Hormuz — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bearish/middle-east/Critical
- 2026-08-17 — Trump orders Pentagon to substantially reduce Ulchi-Freedom Guardian exercises with South Korea — https://en.wikipedia.org/wiki/Ulchi-Freedom_Guardian — macro/government/neutral/korea/High
- 2026-08-18 — Cargo vessel attacked in the Strait of Hormuz, one dead; UAE detects two missiles fired from Iran — https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis — macro/government/bearish/middle-east/Critical

**Curation sanity rules (apply to all):** no two rows share a link; no `date` before 2026-01-01; every row has non-empty title/summary/link; keep the list sorted by date ascending.

- [ ] **Step 2: Verify with smoke checks**

Run (PowerShell, workdir = repo root):
```bash
python -c "from app import seed_data as s; d=s.SEED_EVENTS; assert len(d)>100, len(d); assert len({e['link'] for e in d})==len(d), 'dupe links'; cats={'macro','micro'}; dirs={'bullish','bearish','neutral'}; acts={'government','company',None}; regs={'us','japan','china','middle-east','europe','korea','russia-ukraine','global'}; imps={'Critical','High'}; bad=[e for e in d if e['category'] not in cats or e['direction'] not in dirs or e['actor'] not in acts or e['region'] not in regs or e['impact'] not in imps or e['date'] < '2026-01-01' or not e.get('title') or not e.get('summary')]; assert not bad, bad; print('OK', len(d), 'events')"
```
Expected: `OK <N> events` with N > 100.

---

### Task 2: Storage rework (`app/store.py`)

**Files:**
- Modify: `app/store.py`

**Interfaces:**
- Produces: `init_db()` (creates new `events` schema, drops legacy `news`/`events`), `upsert_events(items: list[dict]) -> int`, `list_events(limit: int = 500) -> list[dict]` (rows include computed `tags`), `delete_event(link)`, `delete_events_by_source(source)`, `suppress_source(source)`, `get_suppressed_sources()`, `save_json`, `load_json`.
- Removes: `upsert_news`, `list_news`, `untagged_events`, `set_event_tags`.

- [ ] **Step 1: Rewrite schema + event functions**

- In `init_db()`: first `DROP TABLE IF EXISTS news`, then detect legacy `events` schema (`PRAGMA table_info(events)` — if column `ntype` exists or `category` missing → `DROP TABLE events`), then create:
```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT UNIQUE NOT NULL,
    source TEXT,
    title TEXT,
    published TEXT,
    date_label TEXT,
    summary TEXT,
    category TEXT,
    actor TEXT,
    direction TEXT,
    region TEXT,
    impact TEXT,
    first_seen TEXT,
    updated_at TEXT
)
```
- Keep `_norm_title`, `_similar`, `_days_apart`, `DEDUP_*`, `STOPWORDS` unchanged.
- Rewrite `upsert_events(items)`: same dedupe loop, but store `category`, `actor`, `direction`, `region`, `impact`, `date_label` instead of `ntype`/`market_moving`/`importance`/`tags`. On merge (similar existing row), keep the row whose `impact == "Critical"` if the other is not, and keep the longer `summary`/`date_label`. INSERT columns: `(link, source, title, published, date_label, summary, category, actor, direction, region, impact, first_seen, updated_at)`.
- Rewrite `list_events(limit=500)`: SELECT `source, title, link, published, date_label, summary, category, actor, direction, region, impact, first_seen, updated_at`, then per row compute `tags = [t for t in (category, actor, direction, region) if t]` and append `d["tags"]`.
- Delete `upsert_news`, `list_news`, `untagged_events`, `set_event_tags`.
- Keep `delete_event`, `delete_events_by_source`, `suppress_source`, `get_suppressed_sources`, `save_json`, `load_json`, `_lock` untouched.

- [ ] **Step 2: Verify**

```bash
python -c "from app import store; store.init_db(); import sqlite3; c=sqlite3.connect('data/news.db'); cols=[r[1] for r in c.execute('PRAGMA table_info(events)')]; assert 'category' in cols and 'ntype' not in cols, cols; t=[r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]; assert 'news' not in t, t; print('schema OK')"
```
Expected: `schema OK`

```bash
python -c "from app import store; n=store.upsert_events([{'link':'seed://test','source':'t','title':'Fed hikes rates','published':'2026-08-01T00:00:00','summary':'x','category':'macro','actor':'government','direction':'bearish','region':'us','impact':'Critical','date_label':None}]); assert n==1; n2=store.upsert_events([{'link':'seed://test','source':'t','title':'Fed hikes rates','published':'2026-08-01T00:00:00','summary':'x','category':'macro','actor':'government','direction':'bearish','region':'us','impact':'Critical','date_label':None}]); assert n2==0, n2; ev=[e for e in store.list_events() if e['link']=='seed://test'][0]; assert ev['tags']==['macro','government','bearish','us'], ev['tags']; store.delete_event('seed://test'); print('upsert/list OK')"
```
Expected: `upsert/list OK`

---

### Task 3: Ingestion rework (`app/news.py`)

**Files:**
- Modify: `app/news.py` (full rewrite)
- Modify: `app/config.py` (remove `BACKFILL_QUERY`)

**Interfaces:**
- Produces: `analyze(title, summary="", source="") -> dict` with keys `category, actor, direction, region, impact, importance, tags`; `seed_events() -> dict` (`{"seed_events": N, "inserted": M}`); `fetch_and_store() -> dict` (`{"feeds_checked", "per_feed", "collected", "inserted"}`).
- Removes: `migrate_events`, `backfill_events`, `_gdelt_date`, `score_item`, `tag_item`, `rate_impact`'s Low/Medium bands.

- [ ] **Step 1: Write the new classifier + ingest**

- Keep term lists (MACRO/MICRO/GLOBAL/REGION/BULLISH/BEARISH/GOV/COMPANY/SYSTEMIC/SEVERITY/SOURCE_BONUS) as-is except: move `"opec"`, `"imf"`, `"world bank"` region→`global` already handled; no changes needed.
- `IMPACT_BANDS: list[tuple[float, str]] = [(9.0, "Critical"), (6.0, "High")]`; `IMPORTANCE_THRESHOLD = 6.0`.
- `_category(text)` → `"macro"`/`"micro"`/`None` (macro terms + global terms → macro; micro terms → micro).
- `_actor(text)` → `"government"`/`"company"`/`None` (existing `_actor` logic).
- `_moving(text)` → `bool`: True when any `MARKET_MOVING_TERMS` matches (word-boundary regex, same as old `classify()`'s moving check).
- `analyze(title, summary="", source="")`:
```python
def analyze(title: str, summary: str = "", source: str = "") -> dict[str, Any]:
    text = f"{title} {summary}".lower()
    category = _category(text)
    actor = _actor(text)
    direction = _direction(text)
    region = _region(text)
    importance = _score(text, _moving(text), source)
    impact = rate_impact(importance)
    tags = [t for t in (category, actor, direction, region) if t]
    return {"category": category, "actor": actor, "direction": direction,
            "region": region, "impact": impact, "importance": importance, "tags": tags}
```
(keep `_moving`, `_score`, `_direction`, `_region`, `_count_hits` as-is, with `rate_impact` using the new bands).
- `seed_events()`: import `seed_data`; for each entry build item dict (`link, source, title, published=date+"T00:00:00", date_label, summary, category, actor, direction, region, impact`) verbatim from the seed (NO heuristic classification); `inserted = store.upsert_events(items)`; return counts.
- `fetch_and_store()`: keep feed loop, but call `analyze(title, summary, source)`; `if info["importance"] < IMPORTANCE_THRESHOLD: continue`; build item with the new fields; `inserted = store.upsert_events(collected)`; return `{"feeds_checked": ..., "per_feed": ..., "collected": len(collected), "inserted": inserted}`.
- Remove `migrate_events`, `seed_data` import at top, `backfill_events`, `_gdelt_date`, `score_item`, `tag_item`, `classify` (superseded by `_category`).
- In `app/config.py`: delete the `BACKFILL_QUERY` block.

- [ ] **Step 2: Verify classifier + seed idempotency**

```bash
python -c "from app import news; a=news.analyze('FOMC hikes rates as inflation hits record', ''); assert a['category']=='macro' and a['direction']=='bearish' and a['region']=='us', a; assert a['impact'] in ('High','Critical'), a; b=news.analyze('Nvidia beats earnings, stock surges to record high', ''); assert b['category']=='micro' and b['direction']=='bullish' and b['actor']=='company', b; c=news.analyze('Local bakery opens', ''); assert c['impact'] not in ('High','Critical'), c; print('classifier OK', a['impact'], b['impact'], c['importance'])"
```
Expected: `classifier OK` with the last importance < 6.0.

```bash
python -c "from app import news; r1=news.seed_events(); r2=news.seed_events(); assert r2['inserted']==0, r2; print('seed OK', r1)"
```
Expected: `seed OK {'seed_events': N, 'inserted': N}` with N > 100 and second run inserted 0.

---

### Task 4: Service + API + CLI wiring

**Files:**
- Modify: `app/service.py` (backfill → seed; enrich limit 500)
- Modify: `app/api.py` (remove `/api/news`, bump events default limit)
- Modify: `run.py` (`--backfill` help text)

- [ ] **Step 1: Edits**

- `service.py`: replace body of `backfill_news` with `return news.seed_events()`; in `_enrich` change `store.list_events(limit=100)` → `store.list_events(limit=500)`; `refresh_news` unchanged.
- `api.py`: delete the `@app.get("/api/news")` route and its `Query` import if now unused (keep `Query` — still used by `/api/events`); `/api/events` default `limit: int = Query(default=500)`; both `delete_event` and `suppress_source` return `store.list_events(limit=500)`.
- `run.py`: `--backfill` help → `"seed the curated event timeline then exit"`; docstring line 7 update likewise.

- [ ] **Step 2: Verify**

```bash
python -c "from app import service, store; print(service.backfill_news()); print(len(store.list_events()), 'events')"
```
Expected: two dicts/ints with N > 100 events.

```bash
python -c "from app.api import app; print(sorted({r.path for r in app.routes if r.path.startswith('/api')}))"
```
Expected: paths include `/api/events`, `/api/events/suppress`, `/api/dashboard`, `/api/earnings`, `/api/regime`, `/api/refresh` and NOT `/api/news`.

---

### Task 5: Frontend updates

**Files:**
- Modify: `static/app.js`
- Modify: `static/index.html`
- Modify: `static/style.css`

- [ ] **Step 1: Edits**

- `app.js`:
  - `TAG_ORDER = ["macro", "micro", "government", "company", "bullish", "bearish", "neutral", "us", "japan", "china", "middle-east", "europe", "korea", "russia-ukraine", "global"]`
  - `IMPACT_ORDER = ["Critical", "High"]`
  - In `renderEventItem`: display date as `n.date_label ? n.date_label + " · " + date : date`; replace the anchor block with: if `(n.link || "").startsWith("seed://")` render `<span class="tl-plain">${escapeHtml(n.title)}</span>` else the existing `<a ...>`.
- `index.html`: change the section heading to `<h2>Market events timeline</h2>`.
- `style.css`: add `.tl-plain { font-weight: 600; }`.

- [ ] **Step 2: Verify**

```bash
python run.py --refresh
```
Expected: runs without error, prints "Refresh complete." Then start the server and curl:
```bash
Start-Job { python run.py }; Start-Sleep 3; curl.exe -s http://127.0.0.1:8000/api/events | ConvertFrom-Json | Measure-Object | Select-Object Count; Stop-Job *; Remove-Job *
```
Expected: count > 100, and every object has `tags`, `impact`, `region`, `direction`, `category` keys. Manual browser check: http://127.0.0.1:8000 — timeline shows events from Jan 2026 through Aug 2026, chips filter, delete ✕ works, seed-only titles render without broken links.

---

### Task 6: Docs sync

**Files:**
- Modify: `AGENTS.md`
- Modify: `.opencode/skills/news-filter/SKILL.md`
- Modify: `.opencode/skills/data-pull/SKILL.md`

- [ ] **Step 1: Edits**

- `AGENTS.md`: update the `app/news.py` bullet to "RSS ingestion, curated seed loading, five-dimension tagging (category/actor/direction/region/impact), dedupe"; add a bullet for `app/seed_data.py` ("curated 2026 event timeline, hand-tagged"); adjust the GDELT mention under `app/news.py`'s old "significant-event pipeline" description (remove GDELT backfill reference); update "Key quirks"/news references if any mention GDELT/Wikipedia seeding (replace with "events seed once via `python run.py --backfill`, idempotent by link").
- `news-filter/SKILL.md`: rewrite to describe the new pipeline: seed (curated, hand-tagged) + strict RSS (High/Critical only, threshold 6.0 in `app/news.py`), five tag dimensions, dedupe/manual removal in `app/store.py`.
- `data-pull/SKILL.md`: update the news bullet + commands (`service.refresh_news()` and `service.backfill_news()` now seed-only).
