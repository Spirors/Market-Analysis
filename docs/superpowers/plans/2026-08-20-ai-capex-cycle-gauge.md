# AI Capex Cycle Gauge Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or implement inline. Steps use checkbox syntax for tracking.

**Goal:** Add a new dashboard card below the risk banner that gauges AI capex-cycle health using Capex Spenders vs. Beneficiaries, news flow, and valuation.

**Architecture:** A new backend module `app/ai_sentiment.py` computes cohort ROC, breadth, tone, news sentiment, and valuation flag. `app/config.py`, `app/market.py`, and `app/service.py` wire the data. The frontend adds a card in `static/index.html` and a renderer in `static/app.js`.

**Tech Stack:** Python 3.12 + FastAPI, vanilla JS + Chart.js already loaded, yfinance/Stooq for data.

**Spec:** `docs/superpowers/specs/2026-08-20-ai-capex-cycle-gauge-design.md`

## Global Constraints
- Use only free, no-key data sources already in use (yfinance, Stooq, RSS, earnings cache).
- Never fabricate values; missing data shows as `null`/`—`.
- Follow existing code style in `app/` and `static/`.
- Reuse existing helpers (`indicators._sma`, `market.get_histories_bulk`, `store.load_json`).

---

### Task 1: Add AI cohort configuration

**Files:**
- Modify: `app/config.py`

**Interfaces:**
- Produces: `AI_CAPEX_COHORTS: dict[str, list[str]]`, `AI_NEWS_TAGS: set[str]`

- [ ] **Step 1: Add AI cohort ticker lists**

Insert after `EARNINGS_UNIVERSE`:

```python
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

# News tags that contribute to the AI capex cycle narrative.
AI_NEWS_TAGS = {"ai", "semis", "china", "capex", "cloud", "macro"}
```

- [ ] **Step 2: Verify Python syntax**

Run: `python -m py_compile app/config.py`
Expected: no output / no error.

---

### Task 2: Ensure AI cohort histories are fetched

**Files:**
- Modify: `app/market.py`

**Interfaces:**
- Consumes: `config.AI_CAPEX_COHORTS`
- Produces: histories for all AI cohort tickers available in `snapshot["histories"]["extra"]` or core dicts.

- [ ] **Step 1: Flatten AI cohort tickers into the bulk history fetch**

In `build_market_snapshot`, update the `history_symbols` line to include all AI cohort tickers:

```python
ai_tickers = list({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
history_symbols = _HISTORY_CORE + list(config.SECTORS) + list(config.INDICES) + ai_tickers
```

This guarantees histories exist for `ai_sentiment.py` even when tickers are not in `SECTORS` or `CROSS_ASSET`.

- [ ] **Step 2: Verify Python syntax**

Run: `python -m py_compile app/market.py`

---

### Task 3: Implement AI sentiment engine

**Files:**
- Create: `app/ai_sentiment.py`

**Interfaces:**
- Consumes: `snapshot` from `market.build_market_snapshot`, `events` list, `earnings` dict.
- Produces: `compute_ai_sentiment(snapshot, events, earnings) -> dict`

- [ ] **Step 1: Create `app/ai_sentiment.py`**

```python
"""AI capex cycle sentiment gauge.

Measures the health of the AI trade through Capex Spenders vs. Beneficiaries,
AI-tagged news flow, and forward valuation from the earnings cache.
"""

import math
from typing import Any, Optional

from . import config
from .indicators import _closes, _sma


def _eq_weight_roc(histories: dict[str, list[dict]], tickers: list[str]) -> Optional[float]:
    rocs = []
    for sym in tickers:
        hist = histories.get(sym, [])
        closes = _closes(hist)
        if len(closes) < 63:
            continue
        base = closes[-63]
        if base == 0:
            continue
        rocs.append((closes[-1] / base - 1) * 100)
    if len(rocs) < 2:
        return None
    return round(sum(rocs) / len(rocs), 2)


def _cohort_breadth(histories: dict[str, list[dict]], tickers: list[str], n: int = 50) -> Optional[float]:
    above = total = 0
    for sym in tickers:
        hist = histories.get(sym, [])
        closes = _closes(hist)
        if len(closes) < n:
            continue
        total += 1
        ma = _sma(closes, n)
        if ma is not None and closes[-1] > ma:
            above += 1
    if total == 0:
        return None
    return round(above / total * 100, 1)


def _cohort_tone(roc: Optional[float], breadth: Optional[float]) -> tuple[str, str]:
    if roc is None and breadth is None:
        return "unknown", "insufficient data"
    r = roc or 0
    b = breadth or 50
    if r > 8 and b >= 65:
        return "bullish", "strong momentum + broad participation"
    if r > 5 and b >= 50:
        return "bullish", "momentum intact"
    if r < -8 and b <= 35:
        return "bearish", "negative momentum + weak breadth"
    if r < -5:
        return "bearish", "momentum weakening"
    if r > 15 or b > 80:
        return "bullish", "extended but strong"
    return "neutral", "mixed"


def compute_ai_news_sentiment(events: list[dict]) -> dict[str, Any]:
    """Net signed sentiment from AI-tagged events, scaled to roughly -100..100."""
    weights = []
    for e in events:
        tags = set(e.get("tags") or [])
        if not tags & config.AI_NEWS_TAGS:
            continue
        impact = str(e.get("impact") or "Low")
        tag_weight = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0.5}.get(impact, 0.5)
        direction = "neutral"
        if "bullish" in tags:
            direction = "bullish"
        elif "bearish" in tags:
            direction = "bearish"
        elif "macro" in tags and impact in ("Critical", "High"):
            direction = "bearish"  # high-impact macro/AI news is usually risk-off
        sign = {"bullish": 1, "bearish": -1, "neutral": 0}.get(direction, 0)
        weights.append(sign * tag_weight * 10)
    if not weights:
        return {"score": 0, "event_count": 0, "tone": "neutral", "note": "no AI-tagged events"}
    raw = sum(weights)
    # Soft-cap to avoid one headline dominating
    score = round(math.copysign(min(abs(raw), 100), raw), 1)
    tone = "bullish" if score > 20 else "bearish" if score < -20 else "neutral"
    return {"score": score, "event_count": len(weights), "tone": tone, "note": f"{len(weights)} AI-tagged events"}


def compute_valuation_flag(earnings: dict[str, Any]) -> dict[str, Any]:
    """Median forward PE/PEG across AI cohorts; stretched if top quartile of cached values."""
    companies = earnings.get("companies") or []
    pes = [c.get("forward_pe") for c in companies if c.get("forward_pe")]
    pEGs = [c.get("forward_peg") for c in companies if c.get("forward_peg")]
    if len(pes) < 4:
        return {"forward_pe": None, "forward_peg": None, "stretched": False, "note": "insufficient data"}
    pe_median = round(sorted(pes)[len(pes) // 2], 2)
    peg_median = round(sorted(pEGs)[len(pEGs) // 2], 2) if pEGs else None
    # Top quartile threshold among observed cached values
    sorted_pes = sorted(pes)
    q3_idx = int(len(sorted_pes) * 0.75)
    threshold = sorted_pes[q3_idx]
    stretched = pe_median >= threshold
    note = f"median forward PE {pe_median}" + (" — stretched" if stretched else "")
    return {"forward_pe": pe_median, "forward_peg": peg_median, "stretched": stretched, "note": note}


def compute_ai_sentiment(snapshot: dict[str, Any], events: list[dict], earnings: dict[str, Any]) -> dict[str, Any]:
    """Main entry point."""
    histories = snapshot.get("histories", {})
    extra = histories.get("extra", {})
    all_hist = {**histories, **extra}

    cohorts: list[dict[str, Any]] = []
    spenders_roc: Optional[float] = None
    beneficiary_rocs: list[float] = []

    for name, tickers in config.AI_CAPEX_COHORTS.items():
        roc = _eq_weight_roc(all_hist, tickers)
        breadth = _cohort_breadth(all_hist, tickers)
        tone, note = _cohort_tone(roc, breadth)
        cohorts.append({
            "name": name,
            "roc_3m_pct": roc,
            "breadth_pct": breadth,
            "tone": tone,
            "note": note,
        })
        if name == "Capex Spenders":
            spenders_roc = roc
        else:
            if roc is not None:
                beneficiary_rocs.append(roc)

    beneficiary_roc = round(sum(beneficiary_rocs) / len(beneficiary_rocs), 2) if beneficiary_rocs else None
    spread = None
    if spenders_roc is not None and beneficiary_roc is not None:
        spread = round(beneficiary_roc - spenders_roc, 2)

    news = compute_ai_news_sentiment(events)
    valuation = compute_valuation_flag(earnings)

    # Aggregate gauge score: -100..100
    score = 0.0
    valid_cohorts = [c for c in cohorts if c["roc_3m_pct"] is not None]
    if valid_cohorts:
        score += sum((c["roc_3m_pct"] or 0) for c in valid_cohorts) / len(valid_cohorts) * 2
    if spread is not None:
        score += spread * 1.5
    score += news["score"] * 0.3
    if valuation["stretched"]:
        score -= 15
    score = round(max(-100, min(100, score)), 1)

    if score >= 60:
        verdict = "Euphoric / fragility setup"
    elif score >= 20:
        verdict = "Healthy expansion"
    elif score >= -20:
        verdict = "Balanced / mixed"
    elif score >= -60:
        verdict = "Cooling / divergence"
    else:
        verdict = "Cycle under pressure"

    flip_conditions = [
        "Beneficiaries' 3m ROC flips below spenders' (spread turns negative)",
        "Breadth across beneficiary cohorts drops below 40%",
        "Forward PE median rises further or AI news turns decisively bearish",
    ]

    return {
        "as_of": snapshot.get("as_of"),
        "score": score,
        "verdict": verdict,
        "cohorts": cohorts,
        "spread_pct": spread,
        "news": news,
        "valuation": valuation,
        "flip_conditions": flip_conditions,
    }
```

- [ ] **Step 2: Verify Python syntax**

Run: `python -m py_compile app/ai_sentiment.py`

---

### Task 4: Wire AI sentiment into dashboard aggregation

**Files:**
- Modify: `app/service.py`

**Interfaces:**
- Consumes: `ai_sentiment.compute_ai_sentiment`
- Produces: `result["ai_sentiment"]` key in dashboard payload.

- [ ] **Step 1: Import and attach to refresh_market**

In `app/service.py`:

```python
from . import ai_sentiment, bottleneck, config, earnings, indicators, market, news, regime, risk, store
```

Inside `refresh_market`, after computing `bn`:

```python
    earn = earnings.earnings_calendar()
    ai = ai_sentiment.compute_ai_sentiment(snapshot, store.list_events(limit=500), earn)

    result = {
        ...
        "ai_sentiment": ai,
    }
```

- [ ] **Step 2: Attach to refresh_all**

`refresh_all` already calls `refresh_market` first, so the key is present. Ensure `refresh_all` does not overwrite it: no extra change needed because `refresh_market` returns it and `refresh_all` extends that dict.

- [ ] **Step 3: Verify Python syntax**

Run: `python -m py_compile app/service.py`

---

### Task 5: Add frontend card and gauge renderer

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `dashboardData.ai_sentiment`
- Produces: rendered `#aiSentimentCard`

- [ ] **Step 1: Add card to HTML**

After the `#fragility` section and before `<main class="grid">`:

```html
<section id="aiSentimentCard" class="card wide">
  <h2>AI capex cycle gauge <button class="section-refresh" data-section="ai_sentiment" title="Refresh section">↻</button></h2>
  <div id="aiSentimentBody">—</div>
</section>
```

- [ ] **Step 2: Add renderer to app.js**

Insert before `renderQuotes`:

```javascript
function renderAISentiment(ai) {
  const el = $("#aiSentimentBody");
  if (!ai || ai.error) {
    el.textContent = ai?.error || "—";
    return;
  }
  const pct = Math.max(-100, Math.min(100, ai.score ?? 0));
  const left = ((pct + 100) / 2).toFixed(1);
  const toneColor = pct >= 60 ? "#A32D2D" : pct >= 20 ? "#3B6D11" : pct >= -20 ? "#B9860B" : "#A32D2D";
  const rows = (ai.cohorts || [])
    .map((c) => {
      const color = c.tone === "bullish" ? "var(--bull)" : c.tone === "bearish" ? "var(--bear)" : "var(--sub)";
      return `<tr>
        <td>${escapeHtml(c.name)}</td>
        <td class="num ${pctClass(c.roc_3m_pct)}">${c.roc_3m_pct != null ? fmtPct(c.roc_3m_pct) : "—"}</td>
        <td class="num">${c.breadth_pct != null ? c.breadth_pct + "%" : "—"}</td>
        <td style="color:${color};font-weight:600">${escapeHtml(c.tone)}</td>
        <td style="color:var(--sub)">${escapeHtml(c.note || "")}</td>
      </tr>`;
    })
    .join("");
  const flips = (ai.flip_conditions || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
  el.innerHTML = `
    <div class="ai-gauge-wrap">
      <div class="ai-gauge-top">
        <span class="ai-gauge-label">Net AI capex cycle health</span>
        <span class="ai-gauge-verdict" style="color:${toneColor}">${escapeHtml(ai.verdict)}</span>
      </div>
      <div class="ai-gauge-track">
        <div class="ai-gauge-center"></div>
        <div class="ai-gauge-marker" style="left:${left}%" data-pct="${pct.toFixed(1)}"></div>
      </div>
      <div class="ai-gauge-labels"><span>← Broken</span><span>Balanced</span><span>Euphoric →</span></div>
      <div class="ai-gauge-meta">
        <span>Score <b>${ai.score ?? "—"}</b></span>
        <span>Beneficiaries vs Spenders <b>${ai.spread_pct != null ? fmtPct(ai.spread_pct) : "—"}</b></span>
        <span>News <b style="color:${ai.news?.tone === "bullish" ? "var(--bull)" : ai.news?.tone === "bearish" ? "var(--bear)" : "var(--sub)"}">${escapeHtml(ai.news?.tone || "—")}</b></span>
        <span>Valuation <b>${escapeHtml(ai.valuation?.note || "—")}</b></span>
      </div>
    </div>
    <table style="margin-top:14px"><thead><tr><th>Cohort</th><th class="num">3m ROC</th><th class="num">Breadth</th><th>Tone</th><th>Read</th></tr></thead><tbody>${rows}</tbody></table>
    <div style="margin-top:12px;font-size:12px;color:var(--sub)"><b>What would flip it:</b><ul style="margin:4px 0 0 18px;padding:0">${flips}</ul></div>
  `;
}
```

- [ ] **Step 3: Register section refresh**

In `renderSection`, add:

```javascript
case "ai_sentiment": renderAISentiment(data.ai_sentiment); break;
```

And in the default branch add:

```javascript
renderAISentiment(data.ai_sentiment);
```

- [ ] **Step 4: Add CSS to style.css**

Append:

```css
.ai-gauge-wrap { margin: 8px 0 14px; }
.ai-gauge-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.ai-gauge-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--sub); }
.ai-gauge-verdict { font-size: 17px; font-weight: 700; }
.ai-gauge-track { position: relative; height: 28px; border-radius: 14px; background: linear-gradient(90deg, #C9433F 0%, #E8A5A3 25%, #F1EFE8 50%, #A9CE7F 75%, #4C8A1E 100%); border: 1px solid var(--hair); overflow: visible; }
.ai-gauge-center { position: absolute; left: 50%; top: -3px; bottom: -3px; width: 2px; background: rgba(44,44,42,0.35); transform: translateX(-1px); }
.ai-gauge-marker { position: absolute; top: -6px; width: 4px; height: 40px; background: var(--ink); border-radius: 2px; transform: translateX(-2px); box-shadow: 0 0 0 2px #fff, 0 1px 4px rgba(0,0,0,0.35); }
.ai-gauge-marker::after { content: attr(data-pct); position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 11px; font-weight: 700; white-space: nowrap; background: var(--ink); color: #fff; padding: 2px 6px; border-radius: 4px; }
.ai-gauge-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--sub); margin-top: 6px; font-weight: 600; }
.ai-gauge-meta { display: flex; gap: 18px; margin-top: 12px; flex-wrap: wrap; font-size: 12px; color: var(--sub); }
.ai-gauge-meta b { color: var(--ink); }
```

- [ ] **Step 5: Verify file integrity**

No build step for frontend; syntax checked by loading in Task 6.

---

### Task 6: Test dashboard end-to-end

**Files:**
- None modified.

- [ ] **Step 1: Run a full refresh**

Run: `python run.py --refresh`
Expected: completes without traceback; `data/dashboard.json` contains `ai_sentiment` key.

- [ ] **Step 2: Start server and load dashboard**

Run: `python run.py` (in background or separate shell).
Open: `http://127.0.0.1:8000`
Expected: new "AI capex cycle gauge" card appears below the risk banner, with a gauge needle, cohort table, and flip conditions.

- [ ] **Step 3: Inspect JSON payload**

Run: `python -c "from app import service; import json; d=service.get_dashboard(); print(json.dumps(d['ai_sentiment'], indent=2, default=str))"`
Expected: `score`, `verdict`, `cohorts`, `spread_pct`, `news`, `valuation` all populated; no fabricated values.

---

## Spec Coverage Check
- AI cohort config → Task 1.
- Histories fetched for all tickers → Task 2.
- Cohort ROC/breadth/tone → Task 3.
- News sentiment → Task 3.
- Valuation flag → Task 3.
- Gauge output zones/verdict → Task 3.
- Frontend card/gauge → Task 5.
- Dashboard wiring → Task 4.
- Testing → Task 6.

No gaps.
