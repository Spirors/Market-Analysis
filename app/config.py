"""Central configuration: tracked symbols, news feeds, and paths."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
REGIME_DIR = DATA_DIR / "regime"
DB_PATH = DATA_DIR / "news.db"
STATIC_DIR = BASE_DIR / "static"

# How long (seconds) a cached price snapshot is considered fresh.
QUOTE_TTL = 30 * 60          # 30 min
HISTORY_TTL = 24 * 60 * 60   # 24 hours
THIRTEENF_TTL = 20 * 24 * 60 * 60   # ~20 days (13F filings are quarterly)

# ---- Market data symbols (free, no-key via yfinance / Stooq fallback) ----

INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
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
    "SOXX": "Semiconductors (iShares)",
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

# ---- Live news feed (free, no keys) ----

# Single reliable source (one publisher => no cross-source dupes). Reuters'
# public RSS is dead; Yahoo is noisy; Google News re-dupes across outlets.
NEWS_FEEDS = [
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
]

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


def ensure_dirs() -> None:
    for d in (DATA_DIR, CACHE_DIR, REGIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
