"""Market-event ingestion: curated seed + strict High/Critical RSS flow.

The events timeline is populated once from the curated seed
(``app/seed_data.py``, hand-tagged) and then kept current by RSS ingestion
with a strict importance threshold — only High/Critical events are stored.

Every event carries five tag dimensions: category (macro/micro),
actor (government/company, optional), direction (bullish/bearish/neutral),
region (us/japan/china/middle-east/europe/korea/russia-ukraine/global),
and impact (High/Critical). Seed events are tagged by hand; RSS events go
through the deterministic keyword heuristics below.
"""

import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config, store

# Keyword heuristics for classifying headline/summary text. Deliberately
# directional, not authoritative — the tags are a filter aid, not a model.
MACRO_TERMS = [
    "fed", "fomc", "inflation", "cpi", "pce", "gdp", "unemployment", "jobs",
    "payroll", "nonfarm", "treasury", "yield", "yields", "bond", "bonds",
    "rate", "rates", "debt", "auction", "recession", "ecb",
    "boj", "congress", "tariff", "deficit", "debt ceiling", "election", "fiscal",
    "monetary", "warsh", "powell", "trade", "oil", "energy", "sanction",
    "stock market", "equities", "chip", "chips", "semiconductor", "semiconductors",
    "ai", "artificial intelligence", "mortgage", "mortgages", "housing",
    "home buyers", "wall street",
]
MICRO_TERMS = [
    "earnings", "revenue", "guidance", "profit", "buyback", "merger", "acqui",
    "ipo", "stock", "shares", "ceo", "outlook", "dividend", "split", "downgrade",
    "upgrade", "target", "quarterly",
]
MARKET_MOVING_TERMS = [
    "fed", "fomc", "rate hike", "rate cut", "cpi", "inflation", "recession",
    "earnings miss", "earnings beat", "guidance", "tariff", "war", "strike",
    "default", "meltdown", "rout", "surge", "plunge", "crash", "record",
    "selloff", "pullback", "record high",
]

# Severity words that raise a story's importance regardless of category.
SEVERITY_TERMS = [
    "crash", "rout", "plunge", "surge", "meltdown", "recession", "default",
    "war", "strike", "record", "fomc", "cpi", "inflation", "earnings miss",
    "earnings beat", "guidance", "tariff", "layoff", "bankruptcy", "halt",
    "collapse", "soar", "tumble", "slump", "rate hike", "rate cut",
    "rate hikes", "rate cuts", "hikes rates", "cuts rates",
    "selloff", "sell-offs", "pullback", "pulling back", "deepens", "deepening",
    "blow",
]

# Global / geopolitical developments that can ripple into US markets. These
# also count as "macro" for classification purposes.
GLOBAL_TERMS = [
    "pboc", "china", "stimulus", "yuan", "renminbi", "ukraine", "russia",
    "iran", "israel", "gaza", "nato", "kospi", "south korea", "seoul", "korea",
    "yen", "boj", "bank of japan", "carry trade", "ecb", "lagarde", "opec",
    "middle east", "sanction", "embargo", "geopolitic", "export controls",
    "chip ban", "taiwan", "north korea", "wto",
]

# Region tags. Ordered most-specific-first so "China vs US" resolves to China.
# "asia" sits after china/japan/korea but before global so stories that
# mention pan-Asian developments without naming a specific country still get
# a regional tag.
REGION_TERMS: dict[str, list[str]] = {
    "china": ["china", "chinese", "pboc", "yuan", "renminbi", "taiwan", "beijing", "hong kong"],
    "japan": ["japan", "japanese", "boj", "bank of japan", "yen", "nikkei", "tokyo"],
    "korea": ["south korea", "kospi", "seoul", "korea", "korean", "north korea", "pyongyang"],
    "middle-east": ["middle east", "iran", "iranian", "israel", "israeli", "gaza", "opec", "saudi"],
    "russia-ukraine": ["russia", "russian", "ukraine", "nato", "kyiv", "moscow", "putin", "zelensky"],
    "europe": ["europe", "european", "eurozone", "ecb", "lagarde", "germany", "france", "britain", "united kingdom", "bank of england", "euro"],
    "us": ["federal reserve", "fed", "fomc", "congress", "white house", "treasury", "wall street", "powell", "united states", "u.s.", "dow", "nasdaq", "s&p 500", "trump", "biden"],
    "asia": ["asia", "asian", "asean", "southeast asia", "asia-pacific", "apac"],
}

# Direction heuristics — every event carries exactly one direction tag.
BULLISH_TERMS = [
    "beat", "beats", "surge", "surges", "rally", "rallies", "upgrade", "upgrades",
    "stimulus", "easing", "eases", "rate cut", "rate cuts", "cut rates",
    "cuts rates", "dovish", "buyback", "recovery", "recovers", "expansion",
    "soar", "soars", "record high", "all-time high", "strong growth",
    "boost", "boosts", "outperform", "outperforms", "outlook raised",
]
BEARISH_TERMS = [
    "miss", "misses", "rout", "routs", "plunge", "plunges", "crash", "crashes",
    "recession", "war", "hike", "hikes", "rate hike", "rate hikes", "hikes rates",
    "hawkish", "downgrade", "downgrades", "default", "defaults", "layoff",
    "layoffs", "bankruptcy", "meltdown", "slump", "slumps", "tumble", "tumbles",
    "collapse", "collapses", "tariff", "tariffs", "sanction", "sanctions",
    "strike", "strikes", "deficit", "selloff", "selloffs", "sell-off",
    "downturn", "bear market", "risk-off", "outlook cut", "warning", "warnings",
    "pulling back", "pullback", "deepens", "deepening",
]

# Who/what is causing the event: government/central bank/policy vs a company.
GOV_TERMS = [
    "fed", "fomc", "federal reserve", "central bank", "congress", "senate",
    "white house", "president", "trump", "biden", "powell", "administration",
    "government", "treasury", "ecb", "boj", "pboc", "lagarde", "nato", "kremlin",
    "putin", "zelensky", "opec", "wto", "imf", "world bank", "sec", "fdic",
    "regulator", "tariff", "sanction", "embargo", "election", "fiscal",
    "military", "war", "ministry", "parliament", "prime minister",
    "bank of japan", "bank of korea", "bank of england",
]
COMPANY_TERMS = [
    "earnings", "revenue", "profit", "guidance", "buyback", "merger", "acqui",
    "ipo", "dividend", "split", "layoff", "bankruptcy", "ceo", "cfo", "chairman",
    "board", "downgrade", "upgrade", "outlook", "quarterly", "shareholder",
    "company", "startup", "nvidia", "apple", "microsoft", "amazon", "alphabet",
    "google", "meta", "tesla", "openai", "anthropic",
]

# Whole-market / systemic events: these alone justify Critical impact.
SYSTEMIC_TERMS = [
    "fomc", "federal reserve", "fed", "rate hike", "rate hikes", "hikes rates",
    "rate cut", "rate cuts", "cuts rates", "recession", "meltdown", "crash",
    "war", "default", "debt ceiling", "systemic", "contagion",
    "banking crisis", "cpi", "inflation", "stock market", "equities",
]

# Items scoring at/above this are stored on the timeline (High/Critical only).
IMPORTANCE_THRESHOLD = 6.0

# Impact bands: (minimum score, label). Highest match wins.
IMPACT_BANDS: list[tuple[float, str]] = [
    (9.0, "Critical"),
    (6.0, "High"),
]


def _count_hits(text: str, terms: list[str]) -> int:
    return sum(1 for k in terms if re.search(rf"\b{re.escape(k)}\b", text))


def _category(text: str) -> str | None:
    is_macro = any(re.search(rf"\b{re.escape(k)}\b", text) for k in MACRO_TERMS)
    is_global = any(re.search(rf"\b{re.escape(k)}\b", text) for k in GLOBAL_TERMS)
    is_micro = any(re.search(rf"\b{re.escape(k)}\b", text) for k in MICRO_TERMS)
    if is_macro or is_global:
        return "macro"
    if is_micro:
        return "micro"
    return None


def _moving(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in MARKET_MOVING_TERMS)


def _score(text: str, moving: bool) -> float:
    score = 0.0
    score += _count_hits(text, MACRO_TERMS) * 1.0
    score += _count_hits(text, MICRO_TERMS) * 1.0
    score += _count_hits(text, SEVERITY_TERMS) * 2.0
    score += _count_hits(text, GLOBAL_TERMS) * 2.0
    score += _count_hits(text, SYSTEMIC_TERMS) * 3.0
    if moving:
        score += 1.5
    return round(score, 2)


def rate_impact(importance: float | None) -> str:
    """Band an importance score into High / Critical."""
    if importance is None:
        return "High"
    for threshold, label in IMPACT_BANDS:
        if importance >= threshold:
            return label
    return "High"


def _region(text: str) -> str:
    for region, terms in REGION_TERMS.items():
        if any(re.search(rf"\b{re.escape(k)}\b", text) for k in terms):
            return region
    return "global"


def _direction(text: str) -> str:
    bull = _count_hits(text, BULLISH_TERMS)
    bear = _count_hits(text, BEARISH_TERMS)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def _actor(text: str) -> str | None:
    """Return 'government', 'company', or None depending on the event's cause."""
    gov = _count_hits(text, GOV_TERMS)
    co = _count_hits(text, COMPANY_TERMS)
    if gov and gov >= co:
        return "government"
    if co:
        return "company"
    return None


def _finance_relevance(text: str, original: str = "") -> float:
    """Score 0..10 measuring how finance-specific a story is.

    Counts hits in ``config.FINANCE_KEYWORDS`` and tracked-ticker mentions
    from ``config.EARNINGS_UNIVERSE`` + all values in
    ``config.AI_CAPEX_COHORTS``.  Normalised to a 0-10 scale.

    Ticker matching requires an uppercase appearance in *original* (the
    pre-lowercase text) to avoid false positives on common English words
    like NOW, SHOP, ARM, META, LITE, MU.
    """
    keyword_hits = _count_hits(text, config.FINANCE_KEYWORDS)
    # Build a flat set of tracked tickers (unique).
    tickers: list[str] = list(config.EARNINGS_UNIVERSE)
    for cohort_tickers in config.AI_CAPEX_COHORTS.values():
        tickers.extend(cohort_tickers)
    # Require the ticker to appear uppercase in the original text.
    # ``text`` is already lowered; ``original`` preserves the raw casing.
    ticker_hits = 0
    seen_tickers: set[str] = set()
    for t in set(tickers):
        if t in seen_tickers:
            continue
        seen_tickers.add(t)
        # Match the lowercase ticker as a word boundary in the lowered text.
        if re.search(rf"\b{re.escape(t.lower())}\b", text):
            # Confirm the ticker actually appears UPPERCASE in the original.
            # Only matches when the ticker is written as e.g. "NVDA", "AMD",
            # "TSM" — not when a common word like "now" happens to match.
            if original and re.search(rf"\b{re.escape(t)}\b", original):
                ticker_hits += 1
            elif not original:
                # Fallback: no original provided, accept lowercase match
                # (backward compat for callers that don't supply original).
                ticker_hits += 1
    raw = keyword_hits * 1.0 + ticker_hits * 2.0
    # Cap at 10.0 — 6 keyword hits alone (6 × 1 = 6) would saturate most stories.
    return min(round(raw, 1), 10.0)


def analyze(title: str, summary: str = "", source: str = "") -> dict[str, Any]:
    """Full analysis for one item: five tag dimensions + importance + composite score.

    Returns a dict with:
      - Five tag dimensions: category, actor, direction, region, impact
      - ``importance``: raw keyword/heuristic score
      - ``finance_relevance``: 0..10 score for finance specificity
      - ``composite_importance``: importance × source_weight ×
        (1 + FINANCE_RELEVANCE_BOOST × finance_relevance/10), capped at 10.0
      - ``impact``: band derived from composite_importance
      - ``tags``: flat list of non-None tags
    """
    original_text = f"{title} {summary}"
    text = original_text.lower()
    category = _category(text)
    actor = _actor(text)
    direction = _direction(text)
    region = _region(text)
    importance = _score(text, _moving(text))
    fin_rel = _finance_relevance(text, original=original_text)
    # Composite: importance × source_weight × finance lift, capped at 10.0.
    source_weight = config.NEWS_SOURCE_WEIGHTS.get(source, 1.0)
    finance_lift = 1.0 + config.FINANCE_RELEVANCE_BOOST * (fin_rel / 10.0)
    composite = min(round(importance * source_weight * finance_lift, 2), 10.0)
    impact = rate_impact(composite)
    tags = [t for t in (category, actor, direction, region) if t]
    return {
        "category": category,
        "actor": actor,
        "direction": direction,
        "region": region,
        "impact": impact,
        "importance": importance,
        "finance_relevance": fin_rel,
        "composite_importance": composite,
        "tags": tags,
    }


def seed_events() -> dict[str, Any]:
    """Load the curated seed verbatim (hand-tagged, no heuristics).

    Deterministic and idempotent: re-running inserts nothing new.
    """
    from . import seed_data

    items: list[dict[str, Any]] = []
    for ev in seed_data.SEED_EVENTS:
        items.append(
            {
                "source": ev["source"],
                "title": ev["title"],
                "link": ev["link"],
                "published": ev["date"] + "T00:00:00",
                "date_label": ev.get("date_label"),
                "summary": ev.get("summary", ""),
                "category": ev["category"],
                "actor": ev.get("actor"),
                "direction": ev["direction"],
                "region": ev["region"],
                "impact": ev["impact"],
            }
        )
    inserted = store.upsert_events(items)
    return {"seed_events": len(items), "inserted": inserted}


def _to_iso(entry: Any) -> str:
    try:
        d = entry.get("published_parsed") or entry.get("updated_parsed")
        if d:
            return datetime(*d[:6]).isoformat()
    except Exception:
        pass
    return ""


def _entry_timestamp(entry: Any) -> float | None:
    """Unix timestamp of an entry's publish time, or None if unknown."""
    d = entry.get("published_parsed") or entry.get("updated_parsed")
    if not d:
        return None
    try:
        return float(calendar.timegm(d))
    except Exception:
        return None


def fetch_and_store() -> dict[str, Any]:
    """Fetch the live feed and store only High/Critical events published
    within the ingest window (no backlog backfill)."""
    import socket
    import urllib.error
    import urllib.request

    import feedparser

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=config.NEWS_INGEST_WINDOW_HOURS)).timestamp()

    collected: list[dict[str, Any]] = []
    per_feed: dict[str, int] = {}
    feed_errors: dict[str, str] = {}
    suppressed = set(config.SUPPRESSED_SOURCES) | set(store.get_suppressed_sources())
    feeds = list(config.NEWS_FEEDS)
    for source, url in feeds:
        if source in suppressed:
            per_feed[source] = 0
            continue
        try:
            # Fetch bytes ourselves so the read cannot hang forever;
            # feedparser only parses the payload. A browser-style
            # User-Agent (config.NEWS_USER_AGENT) is required — several
            # publishers 403 the default Python-urllib UA.
            req = urllib.request.Request(
                url, headers={"User-Agent": config.NEWS_USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
            feed = feedparser.parse(raw)
            entries = feed.entries[:30]
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            # Record the failure instead of silently returning no entries.
            feed_errors[source] = f"{type(e).__name__}: {e}"
            entries = []
        count = 0
        for e in entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            if not title or not link:
                continue
            ts = _entry_timestamp(e)
            # Strict 48h window: entries without a parseable publish time are
            # dropped, not waved through.
            if ts is None or ts < cutoff:
                continue
            summary = html.unescape(
                re.sub(r"<[^>]+>", "", e.get("summary") or e.get("description") or "")
            ).strip()[:500]
            info = analyze(title, summary, source)
            if info["composite_importance"] < IMPORTANCE_THRESHOLD:
                continue
            collected.append(
                {
                    "source": source,
                    "title": title,
                    "link": link,
                    # Undated entries never reach this point, so _to_iso is
                    # always populated here (no fabricated "now" fallback).
                    "published": _to_iso(e),
                    "date_label": None,
                    "summary": summary,
                    "category": info["category"],
                    "actor": info["actor"],
                    "direction": info["direction"],
                    "region": info["region"],
                    "impact": info["impact"],
                    "importance": info["importance"],
                    "finance_relevance": info["finance_relevance"],
                    "composite_importance": info["composite_importance"],
                    "source_weight": config.NEWS_SOURCE_WEIGHTS.get(source, 1.0),
                }
            )
            count += 1
        per_feed[source] = count

    inserted = store.upsert_events(collected)
    return {
        "feeds_checked": len(feeds),
        "per_feed": per_feed,
        "errors": feed_errors,
        "collected": len(collected),
        "inserted": inserted,
    }
