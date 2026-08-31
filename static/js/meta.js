// Symbol -> display-name map for the dashboard tables/charts.
//
// Single source of truth is the backend (/api/meta, derived from
// app/config.py). initMeta() loads it once at boot and replaces the entries
// below; if the endpoint fails, the built-in defaults — historically the
// frontend's own copy of that map — keep rendering identical.

const DEFAULT_LABELS = {
  "^GSPC": "S&P 500", "^NDX": "Nasdaq 100", "^DJI": "Dow", "^RUT": "Russell 2000",
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
  "000660.KS": "SK Hynix", "005930.KS": "Samsung Electronics",
  "LITE": "Lumentum", "COHR": "Coherent", "AAOI": "Applied Optoelectronics",
  "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA",
  "DELL": "Dell", "SMCI": "Super Micro", "ANET": "Arista Networks", "NBIS": "Nebius",
  "VST": "Vistra", "CEG": "Constellation Energy", "NRG": "NRG Energy",
  "PLD": "Prologis", "DLR": "Digital Realty", "EQIX": "Equinix",
  "PLTR": "Palantir", "SHOP": "Shopify", "ADBE": "Adobe",
};

// Stable object identity: renderers read labelMap[sym] at call time, so
// replacing its contents (not rebinding) is what makes meta loading work.
export const labelMap = { ...DEFAULT_LABELS };

function applyLabels(labels) {
  for (const key of Object.keys(labelMap)) delete labelMap[key];
  Object.assign(labelMap, labels);
}

// Loads /api/meta once at boot and swaps in the backend-derived labels.
// Never throws: on any failure the built-in defaults stay in place.
export async function initMeta() {
  try {
    const res = await fetch("/api/meta");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const meta = await res.json();
    if (meta && meta.labels && typeof meta.labels === "object" && !Array.isArray(meta.labels)) {
      applyLabels(meta.labels);
    }
  } catch (e) {
    /* endpoint unavailable -> keep built-in defaults */
  }
}
