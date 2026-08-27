"""Central configuration: tracked symbols, news feeds, and paths."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
REGIME_DIR = DATA_DIR / "regime"
# News events live in a GitHub-synced JSON file (one pretty-printed object,
# events sorted newest-first). Legacy ``data/news.db`` (events + analysis_runs
# in one SQLite file) is migrated on first load and renamed to
# ``news.db.migrated``; ``analysis.db`` carries the synthesis-run log only.
EVENTS_PATH = DATA_DIR / "events.json"
ANALYSIS_DB_PATH = DATA_DIR / "analysis.db"
STATIC_DIR = BASE_DIR / "static"

# How long (seconds) a cached price snapshot is considered fresh.
QUOTE_TTL = 30 * 60          # 30 min
HISTORY_TTL = 24 * 60 * 60   # 24 hours
THIRTEENF_TTL = 20 * 24 * 60 * 60   # ~20 days (13F filings are quarterly)
EARNINGS_TTL = 30 * 60       # 30 minutes (earnings calendar cache)

# Hostnames the API accepts requests for (Host header allowlist). The server
# is localhost-bound; the check blocks DNS-rebinding, where a malicious page
# re-resolves its own hostname to 127.0.0.1 and reaches the API from a
# browser. Extend only if you change run.py's --host/--port.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]

# ---- Market data symbols (free, no-key via yfinance) ----

INDICES = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "^DJI": "Dow Jones",
    "^RUT": "Russell 2000",
}

VOLATILITY = {"^VIX": "VIX"}

# Yahoo tickers are yield*100 (e.g. 4.5 = 4.5%).
RATES = {
    "^IRX": "13-week T-bill",
    "^FVX": "5Y Treasury",
    "^TNX": "10Y Treasury",
    "^TYX": "30Y Treasury",
}

COMMODITIES = {
    "GC=F": "Gold",
    "CL=F": "WTI Crude",
    "NG=F": "Natural Gas",
    "BTC-USD": "Bitcoin",
}

# Index futures (E-minis) for the Futures card.
INDEX_FUTURES = {
    "ES=F": "S&P 500 E-mini",
    "NQ=F": "Nasdaq 100 E-mini",
    "YM=F": "Dow E-mini",
    "RTY=F": "Russell 2000 E-mini",
}

# Commodity futures for the Futures card.
COMMODITY_FUTURES = {
    "CL=F": "WTI Crude",
    "BZ=F": "Brent Crude",
    "GC=F": "Gold",
    "SI=F": "Silver",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
}

# Sector SPDRs + key cross-asset ETFs used for breadth and regime signals.
SECTORS = {
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLK": "Technology",
    "XLU": "Utilities",
    "XLC": "Communication",
    "XLRE": "Real Estate",
    "SMH": "Semiconductors",
}

# Cross-asset ETFs powering regime / risk-divergence signals.
CROSS_ASSET = {
    "SPY": "S&P 500 ETF",
    "RSP": "Equal-weight S&P 500",
    "IWM": "Russell 2000 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "TLT": "20Y+ Treasury ETF",
    "SHY": "1-3Y Treasury ETF",
    "HYG": "High-yield corporate",
    "LQD": "Investment-grade corporate",
    "GLD": "Gold ETF",
    "UUP": "US Dollar",
}

# Core cross-asset histories fetched on every snapshot build (app/market.py).
HISTORY_CORE_SYMBOLS = ["SPY", "RSP", "IWM", "QQQ", "TLT", "SHY", "HYG", "LQD", "^VIX"]

# Mega-caps tracked for the earnings calendar (macro concentration lens).
EARNINGS_UNIVERSE = [
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "TSLA",
    "AVGO", "AMD", "TSM", "PLTR", "CRM", "NOW", "ORCL", "MU",
]

# AI capex cycle cohorts: demand side (spenders) vs. supply-side beneficiaries.
AI_CAPEX_COHORTS = {
    "Capex Spenders": ["AMZN", "MSFT", "GOOGL", "META", "ORCL", "CRM", "NOW"],
    "Compute / Accelerators": ["NVDA", "AMD", "AVGO", "TSM", "QCOM", "ARM", "CRDO", "ALAB"],
    "Memory": ["MU", "WDC", "STX"],
    "Photonics / Optics": ["LITE", "COHR", "AAOI"],
    "Equipment / Packaging": ["AMAT", "LRCX", "KLAC", "TSM"],
    "Neocloud / Infrastructure": ["DELL", "SMCI", "ANET", "NBIS"],
    "Power / Data Center": ["VST", "CEG", "NRG", "XLU", "PLD", "DLR", "EQIX"],
    "Applications": ["PLTR", "CRM", "NOW", "SHOP", "ADBE"],
}

# Keywords for identifying AI/capex-cycle-relevant news events.
AI_NEWS_KEYWORDS = [
    "ai", "artificial intelligence", "nvidia", "amd", "semiconductor", "semiconductors",
    "chip", "chips", "datacenter", "data center", "hyperscaler",
    "tsmc", "memory", "hbm", "dram", "photonics", "optic", "optics",
    "foundry", "accelerator", "gpu", "compute",
]

# ---- Engine knobs ----
# Values preserved verbatim from the engines that consumed them; engines read
# these instead of hardcoding. Derived values (anything computed from other
# constants) stay inside their engine modules.

# Risk-divergence engine (app/risk.py).
RISK_LOOKBACK_BARS = -10                # "is it getting worse" reference bar (negative = bars from end)
RISK_BREADTH_TIERS = (75, 55, 40, 25)   # % > 50DMA tiers: overheating / healthy / narrowing / poor
RISK_CONCENTRATION_BAND = 3             # ± RSP/SPY 3m ROC band (%)
RISK_SMALLCAP_BAND = 3                  # ± IWM/SPY 3m ROC band (%)
RISK_CREDIT_BAND = 1                    # ± HYG/LQD 3m ROC band (%)
RISK_CORRELATION_BAND = 0.3             # ± SPY/TLT return-correlation band
RISK_AI_EXTENSION_ROC = 25              # AI-theme 3m ROC above this counts as extended (%)
RISK_DRAWDOWN_SHALLOW = -5              # drawdown bound for the shallow-drawdown AI flag (%)
RISK_DRAWDOWN_RISK_OFF = -8             # drawdown turning a bearish lean RED (%)
RISK_DRAWDOWN_WASHOUT = -10             # washout/capitulation drawdown (%)
RISK_TONE_GATE_MIN = 3                  # floor for the tone-supermajority gate
RISK_TONE_GATE_RATIO = 0.6              # gate = max(min, ceil(ratio * tone-bearing signals))
RISK_SIGNAL_TOTAL = 9                   # signals the engine evaluates; some drop out when data is missing

# Absolute forward-PE band for the AI mega-cap stretch flag; replaces the broken
# same-sample quartile comparison (median vs Q3 of the same sorted sample).
VALUATION_STRETCH_PE = 30.0

# AI capex-cycle gauge (app/ai_sentiment.py).
AI_SENTIMENT_ROC_WEIGHT = 2             # cohort ROC multiplier in the composite score
AI_SENTIMENT_SPREAD_WEIGHT = 1.5        # beneficiaries-minus-spenders spread multiplier
AI_SENTIMENT_NEWS_WEIGHT = 0.3          # AI news score multiplier
AI_SENTIMENT_VALUATION_PENALTY = 15     # subtracted when forward PE is stretched
AI_SENTIMENT_VERDICT_CUTOFFS = (60, 20) # euphoric/expansion bounds (mirrored below zero)

# Bottleneck ranking (app/bottleneck.py).
BOTTLENECK_LOOKBACK_DAYS = 40           # proxy momentum window for layer ranking

# ---- Superinvestor 13F filers (SEC EDGAR, free, no key) ----

# CIKs validated against EDGAR submissions (13F-HR presence confirmed 2026-08-22).
SUPERINVESTORS = [
    {"name": "Berkshire Hathaway", "cik": 1067983, "manager": "Warren Buffett",
     "link": "https://en.wikipedia.org/wiki/Berkshire_Hathaway"},
    {"name": "Pershing Square", "cik": 1336528, "manager": "Bill Ackman",
     "link": "https://en.wikipedia.org/wiki/Pershing_Square_Capital_Management"},
    {"name": "Scion Asset", "cik": 1649339, "manager": "Michael Burry",
     "link": "https://en.wikipedia.org/wiki/Michael_Burry"},
    {"name": "Appaloosa Management", "cik": 1656456, "manager": "David Tepper",
     "link": "https://en.wikipedia.org/wiki/David_Tepper"},
    {"name": "Bridgewater Associates", "cik": 1350694, "manager": "Ray Dalio",
     "link": "https://en.wikipedia.org/wiki/Bridgewater_Associates"},
    {"name": "Tiger Global", "cik": 1166559, "manager": "Chase Coleman",
     "link": "https://en.wikipedia.org/wiki/Tiger_Global_Management"},
    {"name": "Viking Global", "cik": 1103804, "manager": "Andreas Halvorsen",
     "link": "https://en.wikipedia.org/wiki/Viking_Global_Investors"},
    {"name": "Lone Pine Capital", "cik": 1061165, "manager": "Stephen Mandel",
     "link": "https://en.wikipedia.org/wiki/Lone_Pine_Capital"},
    {"name": "Coatue Management", "cik": 1135730, "manager": "Philippe Laffont",
     "link": "https://en.wikipedia.org/wiki/Coatue_Management"},
    {"name": "Baupost Group", "cik": 1061768, "manager": "Seth Klarman",
     "link": "https://en.wikipedia.org/wiki/Seth_Klarman"},
    {"name": "Duquesne Family Office", "cik": 1536411, "manager": "Stanley Druckenmiller",
     "link": "https://en.wikipedia.org/wiki/Stanley_Druckenmiller"},
    {"name": "Third Point", "cik": 1040273, "manager": "Dan Loeb",
     "link": "https://en.wikipedia.org/wiki/Third_Point_LLC"},
    {"name": "Greenlight Capital", "cik": 1079114, "manager": "David Einhorn",
     "link": "https://en.wikipedia.org/wiki/David_Einhorn_(hedge_fund_manager)"},
]

# ---- Live news feeds (free, no keys) ----

# Multi-feed English editions (US + pan-Asia). Cross-source dedupe in
# app/store.py merges same-story items across publishers (Jaccard >= 0.6 or
# fuzzy ratio >= 0.85 within DEDUP_WINDOW_DAYS = 2). Non-English feeds are
# excluded on purpose: the tokenizer and importance scorer are English-only.
# Nikkei Asia was dropped 2026-08-24: its only official English feed
# (asia.nikkei.com/rss/feed/nar) is a dateless RDF list — no published_parsed,
# so every entry would be dropped by the strict ingest window.
NEWS_FEEDS = [
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("SCMP China", "https://www.scmp.com/rss/4/feed"),
    ("SCMP Business", "https://www.scmp.com/rss/92/feed"),
    ("Korea Herald", "https://www.koreaherald.com/rss/newsAll"),
]

# User-Agent for RSS fetches. SCMP and Korea Herald return HTTP 403 to the
# default Python-urllib UA; a browser-style UA is required to read their
# public feeds.
NEWS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Ingest window (hours): only feed entries published within this window are
# stored, so the live stream starts "today" and never backfills old backlog.
NEWS_INGEST_WINDOW_HOURS = 48

# How often the lightweight news-only scheduled task runs (`run.py
# --news-refresh`, see app/scheduler.py). Hours between runs.
NEWS_REFRESH_INTERVAL_HOURS = 4

# Sources to skip during ingest (add a feed name here to suppress it).
SUPPRESSED_SOURCES: list[str] = []

# Regime detector skill location (reused, not vendored).
REGIME_DETECTOR_SCRIPT = (
    BASE_DIR / ".agents" / "skills" / "macro-regime-detector"
    / "scripts" / "macro_regime_detector.py"
)

REGIME_SUBPROCESS_TIMEOUT_S = 300   # kill the detector CLI after this many seconds
REGIME_DETECT_DAYS = 600            # history window passed to the detector (--days)
REGIME_MAX_AGE_DAYS = 3             # reports older than this are served flagged stale


def ensure_dirs() -> None:
    for d in (DATA_DIR, CACHE_DIR, REGIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
