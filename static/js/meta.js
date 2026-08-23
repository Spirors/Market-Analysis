// Symbol -> display-name map for the dashboard tables/charts.
//
// Single source of truth is the backend (/api/meta, derived from
// app/config.py); this module ships the same map as a built-in fallback so
// rendering works even if the endpoint is unavailable.

export const labelMap = {
  "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow", "^RUT": "Russell 2000",
  "^VIX": "VIX", "^IRX": "13wk T-bill", "^FVX": "5Y Treasury", "^TNX": "10Y Treasury", "^TYX": "30Y Treasury",
  "GC=F": "Gold", "CL=F": "WTI Crude", "NG=F": "Natural Gas", "BTC-USD": "Bitcoin",
  "ES=F": "S&P 500 E-mini", "NQ=F": "Nasdaq 100 E-mini", "YM=F": "Dow E-mini", "RTY=F": "Russell 2000 E-mini",
  "BZ=F": "Brent Crude", "SI=F": "Silver", "HG=F": "Copper", "ZW=F": "Wheat", "ZC=F": "Corn",
  "XLY": "Cons. Discr.", "XLP": "Cons. Staples", "XLE": "Energy", "XLF": "Financials",
  "XLV": "Health Care", "XLI": "Industrials", "XLB": "Materials", "XLK": "Technology",
  "XLU": "Utilities", "XLC": "Communication", "XLRE": "Real Estate", "SMH": "Semis", "SOXX": "Semis (iShares)",
  // Cross-asset ETFs (names from app/config.py CROSS_ASSET)
  "SPY": "S&P 500 ETF", "RSP": "Equal-weight S&P 500", "IWM": "Russell 2000 ETF", "QQQ": "Nasdaq 100 ETF",
  "TLT": "20Y+ Treasury ETF", "SHY": "1-3Y Treasury ETF", "HYG": "High-yield corporate", "LQD": "Investment-grade corporate",
  "GLD": "Gold ETF", "UUP": "US Dollar",
  // AI capex cohort tickers (app/config.py AI_CAPEX_COHORTS)
  "AMZN": "Amazon", "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta Platforms",
  "ORCL": "Oracle", "CRM": "Salesforce", "NOW": "ServiceNow",
  "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC", "QCOM": "Qualcomm", "ARM": "Arm Holdings",
  "CRDO": "Credo Tech", "ALAB": "Astera Labs",
  "MU": "Micron", "WDC": "Western Digital", "STX": "Seagate",
  "LITE": "Lumentum", "COHR": "Coherent", "AAOI": "Applied Optoelectronics",
  "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA",
  "DELL": "Dell", "SMCI": "Super Micro", "ANET": "Arista Networks", "NBIS": "Nebius",
  "VST": "Vistra", "CEG": "Constellation Energy", "NRG": "NRG Energy",
  "PLD": "Prologis", "DLR": "Digital Realty", "EQIX": "Equinix",
  "PLTR": "Palantir", "SHOP": "Shopify", "ADBE": "Adobe",
};
