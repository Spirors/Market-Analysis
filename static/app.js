"use strict";

const $ = (sel) => document.querySelector(sel);

function fmtPrice(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function fmtPct(v) {
  if (v == null) return "";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
}
function pctClass(v) {
  if (v == null) return "";
  return v >= 0 ? "pos" : "neg";
}
function toneCellClass(tone) {
  if (tone === "bullish") return "tone-cell tone-bull";
  if (tone === "bearish") return "tone-cell tone-bear";
  return "tone-cell tone-sub";
}
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Allowlist for hrefs built from external data (RSS links, EDGAR links).
// escapeHtml alone can't stop `javascript:` URIs inside an href attribute,
// so only http/https pass; anything else returns null and callers must
// render a non-anchor fallback instead of an <a>.
function safeUrl(u) {
  const s = String(u ?? "").trim();
  return /^https?:\/\//i.test(s) ? s : null;
}

function renderRisk(risk) {
  // The GREEN/YELLOW/RED wash + border go on the card shell (#riskBanner);
  // ALL dynamic content renders into #riskBody so the card chrome (title,
  // reorder arrows) survives every re-render.
  const el = $("#riskBody");
  const card = $("#riskBanner");
  if (!el) return;
  if (!risk || risk.error) {
    if (card) { card.style.background = ""; card.style.border = ""; }
    el.textContent = "Risk engine unavailable.";
    return;
  }
  if (card) {
    card.style.background = `${risk.color}18`;
    card.style.border = `1px solid ${risk.color}`;
  }
  const counts = risk.counts || {};
  el.innerHTML =
    `<b class="big" style="color:${risk.color}">${risk.risk_level} — ${escapeHtml(risk.verdict)}</b>` +
    `<div>Bull ${counts.bullish} / Bear ${counts.bearish} / Neutral ${counts.neutral} · ` +
    `Division score ${risk.division_score} (0 = unanimous)</div>` +
    `<div class="risk-thesis">${escapeHtml(risk.thesis || "")}</div>`;

  const fEl = $("#fragility");
  const list = $("#fragilityList");
  if (risk.fragility_flags && risk.fragility_flags.length) {
    fEl.classList.remove("hidden");
    list.innerHTML = risk.fragility_flags
      .map((f) => {
        const flagText = typeof f === "string" ? f : f.flag;
        const flipText = typeof f === "string" ? null : f.flip;
        return `
          <li class="flag-row">
            <div class="flag-top"><b>${escapeHtml(flagText)}</b><span class="pill gov">Active</span></div>
            ${flipText ? `<div class="flag-evidence">Flip condition: ${escapeHtml(flipText)}</div>` : ""}
          </li>`;
      })
      .join("");
  } else {
    fEl.classList.add("hidden");
  }
  // Visibility changed → derived section headers and reorder edges follow
  // (a revealed Fragility needs the Stats header moved ahead of it).
  rebuildBandHeads();
  updateReorderStates();

  // Signal detail table appended below the thesis
  if (risk.signals && risk.signals.length) {
    const rows = risk.signals
      .map((s) => {
        return `<tr><td>${escapeHtml(s.name)}</td><td class="${toneCellClass(s.tone)}">${escapeHtml(s.tone || "")}</td><td class="num">${escapeHtml(s.value || "")}</td><td class="td-sub">${escapeHtml(s.note || "")}</td></tr>`;
      })
      .join("");
    el.innerHTML +=
      `<table class="table-gap"><thead><tr><th>Signal</th><th>Tone</th><th class="num">Value</th><th>Read</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
}

const REGIME_PLAIN_ENGLISH = {
  "Concentration": "Big tech / mega-caps are carrying the market. Narrow leadership is fragile because the rally depends on very few names.",
  "Broadening": "The rally is spreading beyond mega-caps. More stocks are participating, which is historically healthier.",
  "Contraction": "Credit is tightening and defensive assets are leading. This is a risk-off, capital-preservation environment.",
  "Inflationary": "Stocks and bonds are moving together, so traditional hedges (bonds, 60/40) are not working as usual.",
  "Transitional": "Signals are mixed and the market is between regimes. This is a 'wait and watch' phase with elevated chop risk.",
};

function _regimeScoreClass(score) {
  if (score == null) return "";
  if (score >= 70) return "pos";
  if (score <= 35) return "neg";
  return "";
}

function renderRegime(regime) {
  const el = $("#regimeBody");
  if (!regime || regime.error) {
    el.innerHTML = `<div class="kv"><span class="k">Status</span>${escapeHtml(regime?.error || "unavailable")}</div>`;
    return;
  }
  const r = regime.regime || {};
  const c = regime.composite || {};
  const tr = r.transition_probability || {};
  const label = r.regime_label || "—";
  const plain = REGIME_PLAIN_ENGLISH[label] || r.regime_description || "";

  let html = "";
  html += `<div class="regime-title">${escapeHtml(label)} regime</div>`;
  if (plain) {
    html += `<div class="regime-desc">${escapeHtml(plain)}</div>`;
  }

  // Component score traffic-light grid
  const compScores = c.component_scores || {};
  const compEntries = Object.values(compScores);
  if (compEntries.length) {
    html += `<div class="regime-grid">`;
    for (const comp of compEntries) {
      const score = comp.score;
      const fillCls = score >= 70 ? "pos" : score <= 35 ? "neg" : "mid";
      html += `
        <div class="regime-tile">
          <div class="regime-tile-label">${escapeHtml(comp.label.split("(")[0].trim())}</div>
          <div class="regime-tile-score">${score}<span class="regime-tile-unit">/100</span></div>
          <div class="regime-bar"><div class="regime-bar-fill ${fillCls}" style="width:${score}%"></div></div>
        </div>`;
    }
    html += `</div>`;
  }

  const add = (k, v) => { html += `<div class="kv"><span class="k">${k}</span><b>${escapeHtml(v)}</b></div>`; };
  add("Composite score", c.composite_score != null ? c.composite_score + "/100" : "—");
  add("Signal zone", c.zone || "—");
  add("Transition prob", tr.probability_range || "—");
  add("Confidence", r.confidence || "—");
  if (r.portfolio_posture) add("Posture", r.portfolio_posture);
  if (c.guidance) html += `<div class="regime-guidance">${escapeHtml(c.guidance)}</div>`;
  el.innerHTML = html;
}

function renderIndicators(ind) {
  const el = $("#indicatorBody");
  if (!ind) { el.textContent = "—"; return; }
  const b = ind.breadth || {};
  const spy = ind.spy || {};
  const vix = ind.vix || {};
  const trend = spy.trend || {};
  let html = "";
  const add = (k, v, cls = "") => { html += `<div class="kv"><span class="k">${k}</span><b class="${cls}">${escapeHtml(v)}</b></div>`; };
  add("Breadth — Sectors & Indices (% > 50DMA)", b.breadth_pct != null ? b.breadth_pct + "%" : "—");
  add("SPY trend", trend.state || "—");
  add("SPY vs 50/200DMA", `${trend.sma_short ?? "—"} / ${trend.sma_long ?? "—"}`);
  add("SPY drawdown", trend.drawdown_pct != null ? fmtPct(trend.drawdown_pct) : "—", pctClass(trend.drawdown_pct));
  add("SPY realized vol (ann.)", spy.realized_vol_annual_pct != null ? spy.realized_vol_annual_pct + "%" : "—");
  add("VIX level", vix.level != null ? vix.level : "—");
  add("VIX signal", vix.signal || "—");
  el.innerHTML = html;
}

function renderAISentiment(ai) {
  const el = $("#aiSentimentBody");
  if (!ai || ai.error) {
    el.textContent = ai?.error || "—";
    return;
  }
  const pct = Math.max(-100, Math.min(100, ai.score ?? 0));
  const left = ((pct + 100) / 2).toFixed(1);
  // Euphoric reads as fragile (bear red); healthy = bull green; balanced = amber.
  const verdictCls = pct >= 60 ? "tone-bear" : pct >= 20 ? "tone-bull" : pct >= -20 ? "tone-amber" : "tone-bear";
  const rows = (ai.cohorts || [])
    .map((c) => {
      return `<tr>
        <td>${escapeHtml(c.name)}</td>
        <td class="num ${pctClass(c.roc_3m_pct)}">${c.roc_3m_pct != null ? fmtPct(c.roc_3m_pct) : "—"}</td>
        <td class="num">${c.breadth_pct != null ? c.breadth_pct + "%" : "—"}</td>
        <td class="${toneCellClass(c.tone)}">${escapeHtml(c.tone)}</td>
        <td class="td-sub">${escapeHtml(c.note || "")}</td>
      </tr>`;
    })
    .join("");
  const flips = (ai.flip_conditions || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
  el.innerHTML = `
    <div class="ai-gauge-wrap">
      <div class="ai-gauge-top">
        <span class="ai-gauge-label">Net AI capex cycle health</span>
        <span class="ai-gauge-verdict ${verdictCls}">${escapeHtml(ai.verdict)}</span>
      </div>
      <div class="ai-gauge-track">
        <div class="ai-gauge-center"></div>
        <div class="ai-gauge-marker" style="left:${left}%" data-pct="${pct.toFixed(1)}"></div>
      </div>
      <div class="ai-gauge-labels"><span>← Broken</span><span>Balanced</span><span>Euphoric →</span></div>
      <div class="ai-gauge-meta">
        <span>Score <b>${ai.score ?? "—"}</b></span>
        <span>Beneficiaries vs Spenders <b>${ai.spread_pct != null ? fmtPct(ai.spread_pct) : "—"}</b></span>
        <span>News <b class="${toneCellClass(ai.news?.tone)}">${escapeHtml(ai.news?.tone || "—")}</b></span>
        <span>Valuation <b>${escapeHtml(ai.valuation?.note || "—")}</b></span>
      </div>
    </div>
    <table class="table-gap"><thead><tr><th>Cohort</th><th class="num">3m ROC</th><th class="num">Breadth</th><th>Tone</th><th>Read</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="flip-block"><b>What would flip it:</b><ul>${flips}</ul></div>
  `;
}

function quotesTable(data, labelMap) {
  let html = `<table><thead><tr><th>Name</th><th class="num">Price</th><th class="num">Chg%</th></tr></thead><tbody>`;
  for (const [sym, q] of Object.entries(data || {})) {
    const name = labelMap[sym] || sym;
    if (!q) continue;
    html += `<tr><td>${escapeHtml(name)}</td><td class="num">${fmtPrice(q.price)}</td><td class="num ${pctClass(q.pct_change)}">${q.pct_change != null ? fmtPct(q.pct_change) : "—"}</td></tr>`;
  }
  return html + `</tbody></table>`;
}

function renderQuotes(container, data, labelMap) {
  container.innerHTML = quotesTable(data, labelMap);
}

// Tiny "as of" stamp for cards that blend two sources (spot + futures).
function asofNote(ts) {
  if (!ts || typeof ts !== "string") return "";
  return `<div class="asof-note">As of ${escapeHtml(ts.replace("T", " ").slice(0, 16))}</div>`;
}

// Spot index ↔ lead future pairing for the merged Indices table.
const INDEX_FUTURE_PAIRS = [
  { spot: "^GSPC", future: "ES=F" },
  { spot: "^IXIC", future: "NQ=F" },
  { spot: "^DJI", future: "YM=F" },
  { spot: "^RUT", future: "RTY=F" },
];

function renderIndices(data) {
  const el = $("#indicesBody");
  if (!el) return;
  const quotes = (data.market || {}).indices || {};
  const futBySym = new Map((((data.futures || {}).index_futures) || [])
    .filter((r) => r && r.symbol).map((r) => [r.symbol, r]));
  let html = `<table><thead><tr><th>Index</th><th class="num">Spot</th><th class="num">Spot %</th><th class="num">Futures</th><th class="num">Fut %</th></tr></thead><tbody>`;
  for (const pair of INDEX_FUTURE_PAIRS) {
    const q = quotes[pair.spot] || null;
    const f = futBySym.get(pair.future) || null;
    html += `<tr>` +
      `<td>${escapeHtml(labelMap[pair.spot] || pair.spot)}</td>` +
      `<td class="num">${q ? fmtPrice(q.price) : "—"}</td>` +
      `<td class="num ${q ? pctClass(q.pct_change) : ""}">${q && q.pct_change != null ? fmtPct(q.pct_change) : "—"}</td>` +
      `<td class="num ${f ? pctClass(f.chg_pct) : ""}">${f ? fmtPrice(f.last) : "—"}</td>` +
      `<td class="num ${f ? pctClass(f.chg_pct) : ""}">${f && f.chg_pct != null ? fmtPct(f.chg_pct) : "—"}</td>` +
      `</tr>`;
  }
  html += `</tbody></table>`;
  html += asofNote((data.futures || {}).as_of || data.as_of);
  el.innerHTML = html;
}

// Category grouping for the merged Commodities card.
const COMMODITY_GROUPS = [
  { name: "Energy", symbols: ["CL=F", "BZ=F"] },
  { name: "Metals", symbols: ["GC=F", "SI=F", "HG=F"] },
  { name: "Agriculture", symbols: ["ZW=F", "ZC=F"] },
  { name: "Other", symbols: ["NG=F", "BTC-USD"] },
];

function renderCommodities(data) {
  const el = $("#commoditiesBody");
  if (!el) return;
  // Spot (market.commodities) and futures (futures.commodities) are merged BY
  // SYMBOL: spot fills the Spot column, futures fills Futures. Day % prefers
  // the futures contract when present, else the spot quote. Nulls stay "—".
  const spot = (data.market || {}).commodities || {};
  const futBySym = new Map((((data.futures || {}).commodities) || [])
    .filter((r) => r && r.symbol).map((r) => [r.symbol, r]));
  let html = "";
  for (const g of COMMODITY_GROUPS) {
    const rows = [];
    for (const sym of g.symbols) {
      const f = futBySym.get(sym) || null;
      const q = spot[sym] || null;
      if (!f && !q) continue; // BTC-USD has no future; rows need at least one side
      const dayPct = f && f.chg_pct != null ? f.chg_pct : q ? q.pct_change : null;
      const name = (f && f.name) || labelMap[sym] || sym;
      rows.push(`<tr>` +
        `<td>${escapeHtml(name)}</td>` +
        `<td class="num">${q ? fmtPrice(q.price) : "—"}</td>` +
        `<td class="num">${f ? fmtPrice(f.last) : "—"}</td>` +
        `<td class="num ${dayPct != null ? pctClass(dayPct) : ""}">${dayPct != null ? fmtPct(dayPct) : "—"}</td>` +
        `</tr>`);
    }
    if (!rows.length) continue;
    html += `<div class="subhead">${escapeHtml(g.name)}</div>`;
    html += `<table><thead><tr><th>Commodity</th><th class="num">Spot</th><th class="num">Futures</th><th class="num">Day %</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
  }
  el.innerHTML = html
    ? html + asofNote((data.futures || {}).as_of || data.as_of)
    : "—";
}

function renderThirteenf(tf) {
  const el = $("#thirteenfBody");
  if (!el) return;
  if (!tf || tf.error) { el.textContent = tf?.error || "—"; return; }
  const holdLabel = (h) => {
    const label = h.ticker || (h.issuer ? h.issuer.slice(0, 18) : null);
    const pct = h.weight_pct != null ? Math.round(h.weight_pct) + "%" : "—";
    return `${escapeHtml(label || "—")} ${pct}`;
  };
  const rows = (tf.funds || []).map((f) => {
    const top = (f.top || []).slice(0, 3).map(holdLabel).join(" · ") || "—";
    const mgrHref = safeUrl(f.link);
    const mgr = f.manager
      ? `<br><span class="td-sub">Managed by ${mgrHref ? `<a href="${escapeHtml(mgrHref)}" target="_blank" rel="noopener">${escapeHtml(f.manager)}</a>` : escapeHtml(f.manager)}</span>`
      : "";
    return `<tr>
      <td><b>${escapeHtml(f.name)}</b>${mgr}</td>
      <td>${escapeHtml(f.quarter || "—")}</td>
      <td class="num">${f.n_positions != null ? f.n_positions : "—"}</td>
      <td class="tf-holdings">${top}</td>
    </tr>`;
  }).join("");
  let html = `<table><thead><tr><th>Fund</th><th>Quarter</th><th class="num">Positions</th><th>Top holdings</th></tr></thead><tbody>`;
  html += rows || `<tr><td colspan="4">No funds loaded.</td></tr>`;
  html += `</tbody></table>`;
  if ((tf.errors || []).length) {
    html += `<div class="bn-note">${tf.errors.map(escapeHtml).join("<br>")}</div>`;
  }
  html += `<div class="bn-note">Source: SEC EDGAR 13F-HR filings · weights are % of each fund's reported portfolio · manual deep-dive reference: <a href="https://www.dataroma.com" target="_blank" rel="noopener">dataroma.com</a></div>`;
  el.innerHTML = html;
}

const STANCE_PILL = { "Risk-On": "bull", "Risk-Off": "bear", "Cautious": "gov", "Neutral": "neutral" };

function renderAnalysis(a) {
  const el = $("#analysisBody");
  if (!el) return;
  if (!a || a.error) { el.textContent = a?.error || "—"; return; }
  const pillCls = STANCE_PILL[a.stance] || "neutral";
  let html = `<div class="ana-head">` +
    `<span class="pill ${pillCls}">${escapeHtml(a.stance || "—")}</span>` +
    `<span class="ana-conf">${a.confidence != null ? a.confidence + "% confidence" : "—"}</span>` +
    `</div>`;
  html += `<div class="ana-headline">${escapeHtml(a.headline || "—")}</div>`;
  if ((a.bullets || []).length) {
    html += `<ul class="ana-list">${a.bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>`;
  }
  if ((a.divergences || []).length) {
    html += `<div class="subhead">Divergences</div><ul class="ana-list">${a.divergences.map((d) => `<li>${escapeHtml(d)}</li>`).join("")}</ul>`;
  }
  if ((a.watch || []).length) {
    html += `<div class="subhead">Watch</div><ul class="ana-list">${a.watch.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`;
  }
  html += `<div class="bn-note">Rule-based synthesis of dashboard sections · no external model · generated after each refresh</div>`;
  html += `<details class="ana-history"><summary id="anaHistSummary">Run history</summary><div id="analysisHistoryBody">—</div></details>`;
  el.innerHTML = html;
  loadAnalysisHistory();
}

async function loadAnalysisHistory() {
  const el = $("#analysisHistoryBody");
  const summary = $("#anaHistSummary");
  if (!el) return;
  try {
    const res = await fetch("/api/analysis/history?limit=20");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const rows = await res.json();
    if (summary) summary.textContent = `Run history (${rows.length})`;
    if (!rows.length) { el.textContent = "No runs logged yet."; return; }
    el.innerHTML = `<table><tbody>` + rows.map((r) =>
      `<tr>` +
      `<td>${escapeHtml((r.ts || "").replace("T", " ").slice(0, 19))}</td>` +
      `<td><span class="pill ${STANCE_PILL[r.stance] || "neutral"}">${escapeHtml(r.stance)}</span></td>` +
      `<td class="num">${r.confidence != null ? r.confidence : "—"}%</td>` +
      `<td>${escapeHtml(r.headline || "—")}</td>` +
      `</tr>`).join("") + `</tbody></table>`;
  } catch (e) {
    el.textContent = "—";
  }
}

const COHORT_PALETTE = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7"];

function _renderLegend(containerId, entries) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = entries
    .map((e) => `<span class="lg-item"><span class="lg-swatch" style="background:${e.color}"></span>${escapeHtml(e.label)}</span>`)
    .join("");
}

function _renderBarChart(canvasId, title, breadth, instanceKey, opts = {}) {
  const canvas = $(`#${canvasId}`);
  if (!canvas) return;
  // Placeholders render into the dedicated .chart-empty slot inside the
  // .chart-box wrapper — never into canvas.parentElement, which is the whole
  // card (wiping it used to destroy the h2/buttons/canvas and brick re-renders).
  const box = canvas.closest(".chart-box");
  const emptyEl = box ? box.querySelector(".chart-empty") : null;
  const showEmpty = (html) => {
    if (opts.legendId) _renderLegend(opts.legendId, []);
    if (window[instanceKey]) { window[instanceKey].destroy(); window[instanceKey] = null; }
    canvas.classList.add("hidden");
    if (emptyEl) {
      emptyEl.innerHTML = html || "—";
      emptyEl.classList.remove("hidden");
    }
  };
  const showCanvas = () => {
    canvas.classList.remove("hidden");
    if (emptyEl) { emptyEl.classList.add("hidden"); emptyEl.innerHTML = ""; }
  };
  if (!breadth || !breadth.detail) {
    showEmpty();
    return;
  }
  showCanvas();
  const detail = breadth.detail;
  const pctOf = (s) => {
    const d = detail[s];
    return d.pct_from_ma != null ? d.pct_from_ma : d.ma ? ((d.close - d.ma) / d.ma) * 100 : 0;
  };
  let symbols = Object.keys(detail);
  let colors = null;
  let cohortBySym = null;
  if (opts.groups && opts.groups.length) {
    const colorBySym = new Map();
    cohortBySym = new Map();
    const legendEntries = [];
    const grouped = [];
    opts.groups.forEach((g, gi) => {
      const color = COHORT_PALETTE[gi % COHORT_PALETTE.length];
      const present = g.symbols.filter((s) => s in detail && !colorBySym.has(s));
      if (!present.length) return;
      present.forEach((s) => {
        colorBySym.set(s, color);
        cohortBySym.set(s, g.name);
      });
      legendEntries.push({ label: g.name, color });
      present.sort((a, b) => pctOf(b) - pctOf(a));
      present.forEach((s) => grouped.push(s));
    });
    symbols = [...grouped, ...symbols.filter((s) => !colorBySym.has(s))];
    colors = symbols.map((s) => colorBySym.get(s) || "#8A8A8A");
    _renderLegend(opts.legendId, legendEntries);
  } else {
    colors = symbols.map((s) => (pctOf(s) >= 0 ? cssVar("--bull") : cssVar("--bear")));
  }
  const labels = symbols.map((s) => labelMap[s] || s.replace("^", ""));
  const values = symbols.map(pctOf);
  let tooltipOpts = null;
  if (cohortBySym) {
    const cohortByLabel = new Map(labels.map((l, i) => [l, cohortBySym.get(symbols[i])]));
    tooltipOpts = { callbacks: { afterLabel: (ctx) => cohortByLabel.get(ctx.label) || "" } };
  }
  if (window.Chart) {
    if (window[instanceKey]) {
      window[instanceKey].destroy();
    }
    window[instanceKey] = new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ label: "% from 50DMA", data: values, backgroundColor: colors }] },
      options: {
        plugins: {
          legend: { display: false },
          title: { display: true, text: title },
          ...(tooltipOpts ? { tooltip: tooltipOpts } : {}),
        },
        scales: { y: { title: { display: true, text: "distance from 50DMA (%)" } } },
        responsive: true,
      },
    });
  } else {
    // Chart.js unavailable (CDN blocked): degrade to the headline number in
    // the empty slot instead of wiping the card.
    showEmpty(`<div class="kv"><span class="k">Breadth</span>${breadth.breadth_pct != null ? breadth.breadth_pct : "—"}% above 50DMA</div>`);
  }
}

// Each breadth card refreshes independently — refreshing one must not
// destroy/recreate the other chart.
function renderBreadthSectorsChart(ind) {
  _renderBarChart("breadthChart", "% from 50DMA", ind?.breadth, "breadthChartInstance");
}

function renderBreadthAIChart(ind) {
  _renderBarChart(
    "breadthAIChart",
    "AI proxies",
    ind?.breadth_ai,
    "breadthAIInstance",
    { groups: ind?.breadth_ai?.cohort_groups || [], legendId: "breadthAILegend" }
  );
}

function renderStreamTable(stream) {
  const layers = stream?.layers || [];
  if (!layers.length) return "<p>—</p>";
  let html = `<table><thead><tr><th>Layer</th><th>Why scarce</th><th>Proxy tickers</th><th class="num">40-day<br>momentum</th></tr></thead><tbody>`;
  for (const cp of layers) {
    const v = cp.proxy_40d_roc_pct;
    const tickers = (cp.proxies || []).map(escapeHtml).join(", ");
    html += `<tr><td><b>${escapeHtml(cp.layer)}</b></td><td class="td-sub">${escapeHtml(cp.why_scarce)}</td><td class="bn-tickers">${tickers}</td><td class="num ${v != null ? pctClass(v) : ""}">${v != null ? fmtPct(v) : "—"}</td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderBottleneck(bn) {
  const el = $("#bottleneckBody");
  if (!bn || bn.error) { el.innerHTML = "—"; return; }
  if (!bn.categories) {
    el.innerHTML = `<div class="bn-note">Bottleneck data format updated. Click the global <b>Refresh</b> button to load the new category view.</div>`;
    return;
  }
  let html = `<div class="bn-thesis">${escapeHtml(bn.thesis || "")}</div>`;
  html += `<div class="bn-note">40-day momentum = how much the proxy tickers moved over the last 40 trading days. It is a rough stress gauge, not a buy/sell signal.</div>`;

  html += `<div class="bn-categories">`;
  for (const cat of bn.categories || []) {
    const score = cat.proxy_40d_roc_pct;
    const upstream = cat.streams?.upstream;
    const downstream = cat.streams?.downstream;
    const upScore = upstream?.proxy_40d_roc_pct;
    const downScore = downstream?.proxy_40d_roc_pct;
    html += `
      <div class="bn-category" data-cat="${escapeHtml(cat.category)}">
        <div class="bn-cat-header">
          <span class="bn-caret">▶</span>
          <span class="bn-cat-title">${escapeHtml(cat.category)}</span>
          <span class="bn-cat-score ${score != null ? pctClass(score) : ""}">${score != null ? fmtPct(score) : "—"}</span>
        </div>
        <div class="bn-cat-body hidden">
          <div class="bn-stream">
            <div class="bn-stream-title subhead">Upstream <span class="bn-stream-score ${upScore != null ? pctClass(upScore) : ""}">${upScore != null ? fmtPct(upScore) : "—"}</span></div>
            ${renderStreamTable(upstream)}
          </div>
          <div class="bn-stream">
            <div class="bn-stream-title subhead">Downstream <span class="bn-stream-score ${downScore != null ? pctClass(downScore) : ""}">${downScore != null ? fmtPct(downScore) : "—"}</span></div>
            ${renderStreamTable(downstream)}
          </div>
        </div>
      </div>`;
  }
  html += `</div>`;

  if (bn.strongest_signal) {
    html += `<div class="bn-strongest"><b>Strongest signal:</b> ${escapeHtml(bn.strongest_signal.layer)} · ${escapeHtml(bn.strongest_signal.why_scarce || "")} (${bn.strongest_signal.proxy_40d_roc_pct != null ? fmtPct(bn.strongest_signal.proxy_40d_roc_pct) : "—"})</div>`;
  }
  el.innerHTML = html;

  // Wire up expand/collapse for each category header.
  el.querySelectorAll(".bn-cat-header").forEach((header) => {
    header.addEventListener("click", () => {
      const category = header.closest(".bn-category");
      const body = category.querySelector(".bn-cat-body");
      const caret = header.querySelector(".bn-caret");
      body.classList.toggle("hidden");
      caret.textContent = body.classList.contains("hidden") ? "▶" : "▼";
    });
  });
}

let earningsData = { companies: [] };
let earnSort = { key: "date", dir: 1 };
let earnValidateTimer = null;
let earnValidated = null;

const EARN_COLUMNS = [
  { key: "symbol", label: "Ticker", default: true, fmt: (r) => `<b>${escapeHtml(r.symbol)}</b>` },
  { key: "date", label: "Next earnings", default: true, fmt: (r) => escapeHtml(r.next_earnings || r.last_earnings || "—") },
  { key: "price", label: "Last price", default: true, num: true, fmt: (r) => fmtPrice(r.price) },
  { key: "pct_daily", label: "Daily %", default: true, num: true, fmt: (r) => fmtPctHtml(r.pct_daily) },
  { key: "pct_7d", label: "7-day %", default: true, num: true, fmt: (r) => fmtPctHtml(r.pct_7d) },
  { key: "high_52w", label: "52W high", default: true, num: true, fmt: (r) => fmtPrice(r.high_52w) },
  { key: "forward_pe", label: "Forward PE", default: true, num: true, fmt: (r) => fmtFloat(r.forward_pe) },
  { key: "forward_peg", label: "Forward PEG", default: false, num: true, fmt: (r) => fmtFloat(r.forward_peg) },
  { key: "market_cap_fmt", label: "Market cap", default: false, num: true, fmt: (r) => escapeHtml(r.market_cap_fmt ?? "—") },
  { key: "sector", label: "Sector", default: false, num: true, fmt: (r) => escapeHtml(r.sector || "—") },
  { key: "rec", label: "AI rec", default: true, fmt: (r) => `<span class="earn-rec" style="background:${r.rec_color}22;color:${r.rec_color};border:1px solid ${r.rec_color}" title="${escapeHtml(r.rec_reason || "")}">${escapeHtml(r.rec_signal || "—")}</span>` },
];

function loadVisibleEarnCols() {
  try {
    const saved = JSON.parse(localStorage.getItem("earnVisibleCols"));
    if (Array.isArray(saved) && saved.length) return new Set(saved);
  } catch (e) { /* ignore */ }
  return new Set(EARN_COLUMNS.filter((c) => c.default).map((c) => c.key));
}

function saveVisibleEarnCols() {
  try {
    localStorage.setItem("earnVisibleCols", JSON.stringify([...visibleEarnCols]));
  } catch (e) { /* ignore */ }
}

let visibleEarnCols = loadVisibleEarnCols();

function fmtFloat(v) {
  if (v == null) return "—";
  return Number(v).toFixed(2);
}
function fmtPctHtml(v) {
  if (v == null) return "—";
  return `<span class="${pctClass(v)}">${fmtPct(v)}</span>`;
}

function renderEarnings(earn) {
  earningsData = earn || { companies: [] };
  drawEarningsControls();
  drawEarnings();
}

function earnKey(r) {
  if (earnSort.key === "symbol") return r.symbol || "";
  if (earnSort.key === "date") return r.next_earnings || r.last_earnings || "";
  const v = r[earnSort.key];
  if (v == null) return -Infinity;
  return Number(v);
}

function drawEarningsControls() {
  const el = $("#earnControls");
  if (!el) return;
  el.innerHTML = `
    <div class="earn-actions">
      <div class="earn-cols">
        <button id="earnColsBtn" class="mini">Columns</button>
        <div id="earnColsMenu" class="earn-cols-menu hidden">
          ${EARN_COLUMNS.map((c) => `
            <label><input type="checkbox" data-col="${c.key}" ${visibleEarnCols.has(c.key) ? "checked" : ""}> ${escapeHtml(c.label)}</label>
          `).join("")}
        </div>
      </div>
    </div>
    <div class="earn-add">
      <input id="earnInput" placeholder="Add ticker (e.g. NVDA)" autocomplete="off">
      <button id="earnAddBtn" disabled>Add</button>
      <span id="earnInputStatus" class="earn-status"></span>
    </div>
  `;

  $("#earnColsBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    $("#earnColsMenu").classList.toggle("hidden");
  });
  $("#earnColsMenu").querySelectorAll("input").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) visibleEarnCols.add(cb.dataset.col); else visibleEarnCols.delete(cb.dataset.col);
      saveVisibleEarnCols();
      drawEarnings();
    });
  });
  // Note: the outside-click close for #earnColsMenu is bound ONCE in
  // initLayoutTools() — binding it here leaked a document listener per render.

  const input = $("#earnInput");
  input.addEventListener("input", () => {
    earnValidated = null;
    setEarnStatus("", "");
    $("#earnAddBtn").disabled = true;
    clearTimeout(earnValidateTimer);
    const sym = input.value.trim().toUpperCase();
    if (!sym) return;
    earnValidateTimer = setTimeout(() => validateEarningsTicker(sym), 400);
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryAddEarningsTicker(); });

  $("#earnAddBtn").addEventListener("click", tryAddEarningsTicker);
}

function setEarnStatus(text, cls) {
  const st = $("#earnInputStatus");
  if (!st) return;
  st.textContent = text;
  st.className = "earn-status " + (cls || "");
}

async function validateEarningsTicker(sym) {
  if (!sym) return;
  setEarnStatus("checking…", "muted");
  try {
    const res = await fetch(`/api/earnings/validate?symbol=${encodeURIComponent(sym)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.valid) {
      earnValidated = data.symbol;
      setEarnStatus(`${data.name}${data.sector ? " · " + data.sector : ""}`, "ok");
      $("#earnAddBtn").disabled = false;
    } else {
      earnValidated = null;
      setEarnStatus("Ticker not found", "bad");
      $("#earnAddBtn").disabled = true;
    }
  } catch (e) {
    earnValidated = null;
    setEarnStatus("Validation failed", "bad");
    $("#earnAddBtn").disabled = true;
  }
}

async function tryAddEarningsTicker() {
  const input = $("#earnInput");
  const sym = (input.value || "").trim().toUpperCase();
  if (!sym) return;
  if (earnValidated !== sym) {
    await validateEarningsTicker(sym);
    if (earnValidated !== sym) return;
  }
  await addEarningsTicker(sym);
}

function drawEarnings() {
  const el = $("#earningsBody");
  const rows = earningsData.companies || [];
  const sorted = [...rows].sort((a, b) => {
    const ka = earnKey(a), kb = earnKey(b);
    if (typeof ka === "string" && typeof kb === "string") {
      if (ka < kb) return -1 * earnSort.dir;
      if (ka > kb) return 1 * earnSort.dir;
      return 0;
    }
    if (ka < kb) return -1 * earnSort.dir;
    if (ka > kb) return 1 * earnSort.dir;
    return 0;
  });

  const cols = EARN_COLUMNS.filter((c) => visibleEarnCols.has(c.key));
  const th = (c) => `<th class="sortable${c.num ? " num" : ""}${earnSort.key === c.key ? (earnSort.dir > 0 ? " asc" : " desc") : ""}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
  let html = `<table><thead><tr>${cols.map(th).join("")}<th></th></tr></thead><tbody>`;
  if (!rows.length) {
    html += `<tr><td colspan="${cols.length + 1}">No tickers yet. Add one above.</td></tr>`;
  } else {
    for (const r of sorted) {
      html += `<tr>${cols.map((c) => `<td${c.num ? " class=\"num\"" : ""}>${c.fmt(r)}</td>`).join("")}<td><button class="mini-del" data-sym="${escapeHtml(r.symbol)}" title="Remove">✕</button></td></tr>`;
    }
  }
  html += `</tbody></table>`;
  el.innerHTML = html;

  el.querySelectorAll("th.sortable").forEach((h) => h.addEventListener("click", () => {
    const k = h.dataset.key;
    if (earnSort.key === k) earnSort.dir *= -1; else { earnSort.key = k; earnSort.dir = 1; }
    drawEarnings();
  }));

  el.querySelectorAll(".mini-del").forEach((b) => b.addEventListener("click", () => removeEarningsTicker(b.dataset.sym)));
}

async function addEarningsTicker(sym) {
  try {
    const res = await fetch(`/api/earnings/watchlist?symbol=${encodeURIComponent(sym)}`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    earnValidated = null;
    const input = $("#earnInput");
    if (input) input.value = "";
    setEarnStatus("", "");
    renderEarnings(await res.json());
  } catch (e) {
    setEarnStatus(`Failed to add ${sym} (${e.message})`, "bad");
  }
}

async function removeEarningsTicker(sym) {
  try {
    const res = await fetch(`/api/earnings/watchlist?symbol=${encodeURIComponent(sym)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderEarnings(await res.json());
  } catch (e) {
    setEarnStatus(`Failed to remove ${sym} (${e.message})`, "bad");
  }
}

let eventsCache = [];
let activeTags = new Set();
const WEEK_KEY = "tlSelectedWeek";
let activeWeekKey = null;

function initWeekSelection() {
  try { activeWeekKey = localStorage.getItem(WEEK_KEY); } catch (e) { activeWeekKey = null; }
}

function saveSelectedWeek(key) {
  try { localStorage.setItem(WEEK_KEY, key); } catch (e) { /* ignore */ }
}

const TAG_ORDER = ["macro", "micro", "government", "company", "bullish", "bearish", "neutral", "us", "japan", "china", "middle-east", "europe", "korea", "russia-ukraine", "global"];

function tagClass(t) {
  if (t === "macro" || t === "micro") return t;
  if (t === "government") return "gov";
  if (t === "company") return "co";
  if (t === "bullish") return "bull";
  if (t === "bearish") return "bear";
  if (t === "neutral") return "neutral";
  return "region";
}

function weekStart(s) {
  const d = new Date(s);
  if (isNaN(d)) return null;
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  d.setHours(0, 0, 0, 0);
  return d;
}

function fmtWeek(d) {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtWeekRange(ws) {
  const end = new Date(ws);
  end.setDate(end.getDate() + 6);
  const a = fmtWeek(ws);
  const b = fmtWeek(end);
  const [monthA, dayA] = a.split(" ");
  const [monthB, dayB] = b.split(" ");
  return monthA === monthB ? `${monthA} ${dayA}–${dayB}` : `${a} – ${b}`;
}

function renderNews(items) {
  eventsCache = items || [];
  activeTags = new Set();
  renderTagFilters();
  applyEventFilter();
}

function renderTagFilters() {
  // Counts reflect the selected week — that's the scope the chips filter.
  const group = buildWeekGroups(eventsCache).find((g) => g.key === activeWeekKey);
  const scope = group ? group.items : [];
  const counts = {};
  scope.forEach((e) => (e.tags || []).forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
  const tags = [...new Set([
    ...TAG_ORDER.filter((t) => counts[t]),
    ...Object.keys(counts).filter((t) => !TAG_ORDER.includes(t)),
  ])];
  const el = $("#tlFilters");
  if (!el) return;
  el.innerHTML = tags.map((t) => {
    const active = activeTags.has(t) ? " active" : "";
    return `<button class="chip${active}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}<span class="cnt">${counts[t]}</span></button>`;
  }).join("");
  el.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    const t = b.dataset.tag;
    if (activeTags.has(t)) activeTags.delete(t); else activeTags.add(t);
    renderTagFilters();
    applyEventFilter();
  }));
}

const UNDATED_KEY = "—";

function buildWeekGroups(items) {
  const groups = [];
  items.forEach((n) => {
    const ws = weekStart(n.published);
    const key = ws ? ws.toISOString().slice(0, 10) : UNDATED_KEY;
    const label = ws ? "Week of " + fmtWeekRange(ws) : "Undated";
    let g = groups.find((x) => x.key === key);
    if (!g) { g = { key, label, items: [] }; groups.push(g); }
    g.items.push(n);
  });
  // Newest first within each week.
  groups.forEach((g) => g.items.sort((a, b) => ((a.published || "") < (b.published || "") ? 1 : -1)));
  // Newest weeks first; undated always last.
  groups.sort((a, b) => {
    if (a.key === UNDATED_KEY) return 1;
    if (b.key === UNDATED_KEY) return -1;
    return a.key < b.key ? 1 : -1;
  });
  return groups;
}

function renderWeekSelector(groups) {
  const sel = $("#weekSelect");
  const badge = $("#weekBadge");
  if (!sel) return;
  if (!groups.length) {
    activeWeekKey = null;
    sel.innerHTML = `<option value="">No weeks</option>`;
    if (badge) { badge.hidden = true; badge.textContent = ""; }
    return;
  }
  // Keep a still-valid selection; otherwise fall back to the newest week
  // that actually contains events.
  if (!activeWeekKey || !groups.some((g) => g.key === activeWeekKey)) {
    activeWeekKey = groups[0].key;
    saveSelectedWeek(activeWeekKey);
  }
  sel.innerHTML = groups.map((g) =>
    `<option value="${escapeHtml(g.key)}"${g.key === activeWeekKey ? " selected" : ""}>${escapeHtml(g.label)} · ${g.items.length} event${g.items.length === 1 ? "" : "s"}</option>`
  ).join("");
  // Glanceable count for the selected week, next to the dropdown.
  const current = groups.find((g) => g.key === activeWeekKey);
  if (badge && current) {
    badge.textContent = `${current.items.length} event${current.items.length === 1 ? "" : "s"}`;
    badge.hidden = false;
  }
}

function applyEventFilter() {
  const el = $("#newsBody");
  const groups = buildWeekGroups(eventsCache);
  renderWeekSelector(groups);

  // Only the selected week renders; tag chips filter within it.
  const group = groups.find((g) => g.key === activeWeekKey) || null;
  let items = group ? group.items : [];
  if (activeTags.size) items = items.filter((e) => (e.tags || []).some((t) => activeTags.has(t)));
  if (!items.length) { el.innerHTML = "<p>No events match the selected filters.</p>"; return; }

  el.innerHTML = `<div class="timeline">` +
    `<div class="subhead accent">${escapeHtml(group.label)}</div>` +
    items.map(renderEventItem).join("") +
    `</div>`;
}

function renderEventItem(n) {
  const pills = (n.tags || []).map((t) => `<span class="pill ${tagClass(t)}">${escapeHtml(t)}</span>`).join(" ");
  // Impact tiers: Critical = loud (red edge + glow + BREAKING badge);
  // High = quiet amber accent. Everything else stays plain so ordinary rows
  // never read like an error state.
  const isCritical = n.impact === "Critical";
  const isHigh = n.impact === "High";
  const impactCls = isCritical ? " tl-critical" : isHigh ? " tl-high" : "";
  const breaking = isCritical ? `<span class="breaking-badge">Breaking</span>` : "";
  const impactPill = isHigh ? `<span class="pill high">High</span> ` : "";
  const date = (n.published || "").slice(0, 10);
  const dateShown = n.date_label ? `${escapeHtml(n.date_label)} · ${date}` : (date || "—");
  // Only http(s) links become anchors (scheme allowlist); seed:// entries and
  // anything with an unexpected scheme render as plain text, never an <a>.
  const linkHref = safeUrl(n.link);
  const titleEl = linkHref
    ? `<a href="${escapeHtml(linkHref)}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a>`
    : `<span class="tl-plain">${escapeHtml(n.title)}</span>`;
  const summary = n.summary ? `<div class="tl-summary">${escapeHtml(n.summary)}</div>` : "";
  return `<div class="tl-item${impactCls}">
    <div class="tl-date">${dateShown}</div>
    <div class="tl-body">
      ${breaking}${titleEl}
      <div class="tl-tags">${impactPill}${pills}</div>
      <div class="meta">${escapeHtml(n.source)}
        <button class="mini-del ev-del" data-link="${escapeHtml(n.link)}" title="Remove this event from the timeline">✕ Remove</button>
        <button class="mini-del ev-hide" data-src="${escapeHtml(n.source)}" title="Hide all events from this source">hide source</button>
      </div>
      ${summary}
    </div>
  </div>`;
}

let dashboardData = null;

function renderSection(section, data) {
  const m = data.market || {};
  switch (section) {
    case "risk": renderRisk(data.risk); break;
    case "analysis": renderAnalysis(data.ai_analysis); break;
    case "regime": renderRegime(data.regime); break;
    case "indicators": renderIndicators(data.indicators); break;
    case "indices": renderIndices(data); break;
    case "rates": renderQuotes($("#ratesBody"), m.rates || {}, labelMap); break;
    case "commodities": renderCommodities(data); break;
    case "ai_sentiment": renderAISentiment(data.ai_sentiment); break;
    case "breadth": renderBreadthSectorsChart(data.indicators); break;
    case "breadth_ai": renderBreadthAIChart(data.indicators); break;
    case "bottleneck": renderBottleneck(data.bottleneck); break;
    case "earnings": renderEarnings(data.earnings); break;
    case "thirteenf": renderThirteenf(data.thirteenf); break;
    case "events": renderNews(data.events); break;
    default:
      renderRisk(data.risk);
      renderAnalysis(data.ai_analysis);
      renderAISentiment(data.ai_sentiment);
      renderRegime(data.regime);
      renderIndicators(data.indicators);
      renderIndices(data);
      renderQuotes($("#ratesBody"), m.rates || {}, labelMap);
      renderCommodities(data);
      renderBreadthSectorsChart(data.indicators);
      renderBreadthAIChart(data.indicators);
      renderBottleneck(data.bottleneck);
      renderEarnings(data.earnings);
      renderThirteenf(data.thirteenf);
      renderNews(data.events);
  }
}

// ---- Fetch orchestration: generation tokens + per-section error routing ----
// Every fetch path captures a token before awaiting and bails instead of
// rendering when a newer request has started, so stale responses can never
// overwrite fresh ones. Global loads bump the global token AND every section
// token; single-section refreshes bump only their own.
const gen = { global: 0 };
const sectionGen = {};

// Section id → body container, so fetch errors render into the card that
// actually failed (same plain-text pattern as the risk engine's error state)
// instead of always landing in #riskBody.
const SECTION_ERROR_TARGETS = {
  risk: "#riskBody",
  analysis: "#analysisBody",
  regime: "#regimeBody",
  indicators: "#indicatorBody",
  indices: "#indicesBody",
  rates: "#ratesBody",
  commodities: "#commoditiesBody",
  ai_sentiment: "#aiSentimentBody",
  bottleneck: "#bottleneckBody",
  earnings: "#earningsBody",
  thirteenf: "#thirteenfBody",
  events: "#newsBody",
};
const SECTION_IDS = [...Object.keys(SECTION_ERROR_TARGETS), "breadth", "breadth_ai"];

function renderSectionError(section, e) {
  let el = null;
  if (section === "breadth" || section === "breadth_ai") {
    // Chart cards have no text body — degrade into their .chart-empty slot,
    // mirroring how _renderBarChart shows placeholder content.
    const canvas = $(section === "breadth" ? "#breadthChart" : "#breadthAIChart");
    const box = canvas ? canvas.closest(".chart-box") : null;
    el = box ? box.querySelector(".chart-empty") : null;
    if (el && canvas) {
      canvas.classList.add("hidden");
      el.classList.remove("hidden");
    }
  } else {
    el = document.querySelector(SECTION_ERROR_TARGETS[section] || "");
  }
  if (el) el.textContent = `Failed to load ${section}: ${e.message}`;
}

async function load() {
  const g = ++gen.global;
  // A full load also supersedes any in-flight single-section refresh.
  for (const s of SECTION_IDS) sectionGen[s] = (sectionGen[s] || 0) + 1;
  try {
    const res = await fetch("/api/dashboard");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (gen.global !== g) return; // a newer full load superseded this one
    dashboardData = data;
    $("#asof").textContent = "As of " + (dashboardData.as_of || "—").replace("T", " ").slice(0, 19);
    renderSection("all", dashboardData);
  } catch (e) {
    if (gen.global !== g) return;
    $("#riskBody").textContent = "Failed to load dashboard: " + e.message;
  }
}

async function refreshSection(section) {
  const btn = document.querySelector(`.section-refresh[data-section="${section}"]`);
  if (btn) { btn.disabled = true; btn.style.opacity = "0.4"; }
  const t = (sectionGen[section] || 0) + 1;
  sectionGen[section] = t;
  try {
    const res = await fetch("/api/dashboard");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (sectionGen[section] !== t) return; // superseded by a newer refresh
    dashboardData = data;
    // Header as_of is intentionally NOT touched here: a single-card refresh
    // must not desync the header timestamp from the rest of the dashboard.
    renderSection(section, data);
  } catch (e) {
    if (sectionGen[section] === t) renderSectionError(section, e);
  }
  if (btn) { btn.disabled = false; btn.style.opacity = ""; }
}

const labelMap = {
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

// ---- Layout: sequence-derived section headers + reorderable cards ----
// Cards sit FLAT inside <main id="bands">; band membership is a per-card
// property below. Section headers (.band-head) are GENERATED by walking the
// visible cards in order and inserting one wherever the band changes — so a
// header can never dangle, and moving a card moves its section header with
// it. Cards themselves move as existing DOM nodes (insertBefore/appendChild)
// — never rebuilt — so Chart.js instances bound to their canvases survive.
const LAYOUT_KEY = "dashLayout";

const CARD_BAND = {
  risk: "sentiment",
  "ai-sentiment": "sentiment",
  analysis: "analysis",
  fragility: "stats",
  regime: "stats",
  indicators: "stats",
  indices: "stats",
  commodities: "stats",
  rates: "stats",
  breadth: "stats",
  "breadth-ai": "stats",
  bottleneck: "stats",
  earnings: "stats",
  thirteenf: "stats",
  events: "news",
};

const BAND_LABELS = { sentiment: "Sentiment", analysis: "Analysis", stats: "Stats", news: "News" };

function loadLayout() {
  try {
    const v = JSON.parse(localStorage.getItem(LAYOUT_KEY));
    return (v && typeof v === "object" && !Array.isArray(v)) ? v : null;
  } catch (e) { return null; }
}

function saveLayout(layout) {
  try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch (e) { /* ignore */ }
}

// Apply a saved order from localStorage BEFORE first data render (no flicker).
// Format v2 = { v: 2, order: [cardId, ...] }. Old-format layouts ({bands,
// cards}) and anything malformed are ignored silently — defaults stay intact.
function applyLayoutOnLoad() {
  const layout = loadLayout();
  const host = $("#bands");
  if (!layout || !host) return;
  if (layout.v !== 2 || !Array.isArray(layout.order)) return;
  const known = new Set(Object.keys(CARD_BAND));
  if (!layout.order.every((id) => typeof id === "string" && known.has(id))) return;
  const byId = new Map(
    [...host.querySelectorAll("[data-card]")].map((c) => [c.dataset.card, c])
  );
  layout.order.forEach((cid) => {
    const card = byId.get(cid);
    if (card) host.appendChild(card); // moves the existing node into saved order
  });
  rebuildBandHeads();
}

// Rebuild the generated section headers. Idempotent: drop every existing head
// first, then walk the VISIBLE cards in order and insert a .band-head before
// each card whose band differs from the previous visible card's band.
// Consecutive same-band cards share one header; hidden cards (e.g. Fragility
// when empty) neither claim nor dangle one.
function rebuildBandHeads() {
  const host = $("#bands");
  if (!host) return;
  host.querySelectorAll(":scope > .band-head").forEach((h) => h.remove());
  let prevBand = null;
  for (const node of [...host.children]) {
    if (!node.matches("[data-card]")) continue;
    if (node.classList.contains("hidden")) continue;
    const band = CARD_BAND[node.dataset.card];
    if (!band || band === prevBand) continue;
    node.before(_makeBandHead(band));
    prevBand = band;
  }
}

// Same inner markup as the old static wrappers: h2.band-title + .band-rule.
function _makeBandHead(band) {
  const head = document.createElement("div");
  head.className = "band-head";
  const title = document.createElement("h2");
  title.className = "band-title";
  title.textContent = BAND_LABELS[band] || band;
  const rule = document.createElement("div");
  rule.className = "band-rule";
  head.append(title, rule);
  return head;
}

// Persist v2 layout from actual DOM order (hidden cards included, so a saved
// order never loses track of them).
function persistLayoutFromDOM() {
  const host = $("#bands");
  if (!host) return;
  const order = [...host.children]
    .filter((c) => c.matches("[data-card]"))
    .map((c) => c.dataset.card);
  saveLayout({ v: 2, order });
}

// Visible cards only: .hidden cards (e.g. Fragility when it has no flags)
// must not count as neighbors, or moving into their slot looks like a no-op.
function _visibleCards(host) {
  return [...host.children].filter(
    (c) => c.matches("[data-card]") && !c.classList.contains("hidden")
  );
}

// dir -1 = swap with the previous VISIBLE card, +1 = the next. Pure DOM node
// moves over the one flat sequence — no band-edge special cases anymore,
// because section headers are derived from the sequence itself
// (rebuildBandHeads regenerates them after every move).
function moveCard(cardEl, dir) {
  const host = $("#bands");
  if (!host) return;
  const visible = _visibleCards(host);
  const i = visible.indexOf(cardEl);
  if (i === -1) return;
  const neighbor = dir < 0 ? visible[i - 1] : visible[i + 1];
  if (!neighbor) return; // very top/bottom of the dashboard — no-op
  if (dir < 0) neighbor.before(cardEl);
  else neighbor.after(cardEl);
  persistLayoutFromDOM();
  rebuildBandHeads();
  updateReorderStates();
}

// Disabled states are GLOBAL: ↑ is disabled only on the very first visible
// card of the whole dashboard, ↓ only on the very last — mirroring moveCard's
// neighbor swaps. Hidden cards don't count as edges.
function updateReorderStates() {
  const host = $("#bands");
  if (!host) return;
  const visible = _visibleCards(host);
  const first = visible[0];
  const last = visible[visible.length - 1];
  host.querySelectorAll("[data-card]").forEach((card) => {
    const up = card.querySelector('.card-mv[data-move="up"]');
    const down = card.querySelector('.card-mv[data-move="down"]');
    if (up) up.disabled = card === first;
    if (down) down.disabled = card === last;
  });
}

// ONE delegated document-level click listener handles every repeated /
// dynamically rendered control (reorder arrows, per-section refresh, layout
// reset, earnings menu outside-click) — rendered content never loses handlers.
function initLayoutTools() {
  applyLayoutOnLoad(); // runs synchronously before load()'s fetch resolves
  rebuildBandHeads();  // covers the no-saved-layout path (idempotent)
  updateReorderStates();

  document.addEventListener("click", (e) => {
    const mv = e.target.closest(".card-mv");
    if (mv) {
      if (mv.disabled) return;
      const card = mv.closest("[data-card]");
      if (card) moveCard(card, mv.dataset.move === "up" ? -1 : 1);
      return;
    }
    const sr = e.target.closest(".section-refresh");
    if (sr) { refreshSection(sr.dataset.section); return; }
    if (e.target.closest("#resetLayoutBtn")) {
      try { localStorage.removeItem(LAYOUT_KEY); } catch (err) { /* ignore */ }
      window.location.reload();
      return;
    }
    // Earnings column menu closes on any outside click (bound once here,
    // not per dashboard render).
    const menu = $("#earnColsMenu");
    if (menu && !menu.contains(e.target) && !e.target.closest("#earnColsBtn")) {
      menu.classList.add("hidden");
    }
  });
}

$("#refreshBtn").addEventListener("click", async () => {
  const btn = $("#refreshBtn");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    const res = await fetch("/api/refresh?full=true", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await load();
  } catch (e) {
    // Whole-dashboard failure — the global error spot stays #riskBody.
    $("#riskBody").textContent = "Refresh failed: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh";
  }
});

// Section-refresh buttons are handled by the delegated document listener in
// initLayoutTools() — no per-button binding needed here.

$("#weekSelect").addEventListener("change", (e) => {
  activeWeekKey = e.target.value || null;
  saveSelectedWeek(activeWeekKey);
  renderTagFilters();
  applyEventFilter();
});

$("#newsBody").addEventListener("click", async (e) => {
  const del = e.target.closest(".ev-del");
  const hide = e.target.closest(".ev-hide");

  // Brief inline failure notice next to the clicked control. Reuses the
  // earnings status styling (the only existing inline status classes).
  const showEventError = (btn, msg) => {
    const meta = btn.closest(".meta");
    if (!meta) return;
    let st = meta.querySelector(".earn-status");
    if (!st) {
      st = document.createElement("span");
      meta.appendChild(st);
    }
    st.textContent = msg;
    st.className = "earn-status bad";
  };

  if (del) {
    if (!confirm("Remove this event from the timeline?")) return;
    try {
      const res = await fetch(`/api/events?link=${encodeURIComponent(del.dataset.link)}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      renderNews(await res.json());
    } catch (err) {
      showEventError(del, `Remove failed (${err.message})`);
    }
  } else if (hide) {
    const src = hide.dataset.src;
    if (confirm(`Hide all events from "${src}" and stop fetching it?`)) {
      try {
        const res = await fetch(`/api/events/suppress?source=${encodeURIComponent(src)}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderNews(await res.json());
      } catch (err) {
        showEventError(hide, `Hide failed (${err.message})`);
      }
    }
  }
});

initLayoutTools();
initWeekSelection();
load();
