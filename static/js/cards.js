// Per-section card renderers + the renderSection dispatch table.
// Pure rendering: every fetch goes through api.js, labels come from meta.js.

import {
  $, escapeHtml, safeUrl, fmtPrice, fmtPct, pctClass, toneCellClass,
  cssVar, fmtPctHtml, asofNote, fmtHmET, fmtTimestampET,
} from "./format.js";
import { labelMap } from "./meta.js";
import { rebuildBandHeads, updateReorderStates } from "./layout.js";
import { fetchAnalysisHistory } from "./api.js";
import { renderEarnings } from "./earnings.js";
import { renderNews } from "./events.js";
import { attachTooltip } from "./tooltip.js";

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
    `<div>Bull ${counts.bullish} / Bear ${counts.bearish} / Neutral ${counts.neutral}</div>` +
    `<div class="risk-thesis">${escapeHtml(risk.thesis || "")}</div>`;

  const fEl = $("#fragility");
  const list = $("#fragilityList");
  if (risk.fragility_flags && risk.fragility_flags.length) {
    fEl.classList.remove("hidden");
    const flagLi = (f) => {
      const flagText = typeof f === "string" ? f : f.flag;
      const flipText = typeof f === "string" ? null : f.flip;
      return `
          <li class="flag-row">
            <div class="flag-top"><b>${escapeHtml(flagText)}</b><span class="pill gov">Active</span></div>
            ${flipText ? `<div class="flag-evidence">Flip condition: ${escapeHtml(flipText)}</div>` : ""}
          </li>`;
    };
    // Group by evidence side: euphoria evidence (fragility OF the consensus
    // trade) vs distress signals (market breakage). Flags without a side
    // (legacy payloads) fall into the euphoria group to preserve old order.
    const groups = [
      ["Euphoria evidence", "optimism"],
      ["Distress signals", "distress"],
    ];
    let html = "";
    for (const [heading, side] of groups) {
      const items = risk.fragility_flags.filter((f) => (typeof f === "object" && f.side ? f.side : "optimism") === side);
      if (!items.length) continue;
      html += `<li class="flag-group-head">${escapeHtml(heading)}</li>`;
      html += items.map(flagLi).join("");
    }
    list.innerHTML = html;
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
  if (regime.stale) {
    const age = regime.age_days != null ? ` (${regime.age_days}d old)` : "";
    html += `<div class="regime-desc" style="color:#B9860B">Stale report${age} — detection has not succeeded recently</div>`;
  }
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

// Spot index ↔ lead future pairing for the merged Indices table.
const INDEX_FUTURE_PAIRS = [
  { spot: "^GSPC", future: "ES=F" },
  { spot: "^NDX", future: "NQ=F" },
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
      `<td class="num ${q ? pctClass(q.pct_change) : ""}">${q ? fmtPrice(q.price) : "—"}</td>` +
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
    const rows = await fetchAnalysisHistory();
    if (summary) summary.textContent = `Run history (${rows.length})`;
    if (!rows.length) { el.textContent = "No runs logged yet."; return; }
    el.innerHTML = `<table><tbody>` + rows.map((r) =>
      `<tr>` +
      `<td>${escapeHtml(fmtTimestampET(r.ts))}</td>` +
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

// Section name → [card element id, payload coverage key]. Cards whose id
// differs from their section/coverage key are called out explicitly.
const SECTION_CARDS = {
  risk: ["risk", "risk"],
  ai_sentiment: ["ai-sentiment", "ai_sentiment"],
  analysis: ["analysis", "ai_analysis"],
  regime: ["regime", "regime"],
  indicators: ["indicators", "indicators"],
  indices: ["indices", "indices"],
  commodities: ["commodities", "commodities"],
  rates: ["rates", "rates"],
  breadth: ["breadth", "breadth"],
  breadth_ai: ["breadth-ai", "breadth_ai"],
  bottleneck: ["bottleneck", "bottleneck"],
  earnings: ["earnings", "earnings"],
  thirteenf: ["thirteenf", "thirteenf"],
  events: ["events", "events"],
};

// Tiny muted "n/m" badge in the card header while a section's sources are
// incomplete ("n of m sources live" tooltip). Removed entirely when coverage
// is complete (or unknown), so a healthy dashboard shows nothing extra.
function applyCoverageBadge(section, data) {
  const entry = SECTION_CARDS[section];
  if (!entry) return;
  const [cardId, covKey] = entry;
  const card = document.querySelector(`[data-card="${cardId}"]`);
  const head = card ? card.querySelector("h2") : null;
  if (!head) return;
  const cov = (data.coverage || {})[covKey];
  const badge = head.querySelector(".cov-badge");
  if (!cov || cov.ok >= cov.total) {
    if (badge) badge.remove();
    return;
  }
  let el = badge;
  if (!el) {
    el = document.createElement("span");
    el.className = "pill neutral cov-badge";
    el.style.cssText = "font-size:9px;font-weight:600;padding:0 5px;";
    head.appendChild(el);
  }
  el.textContent = `${cov.ok}/${cov.total}`;
  el.title = `${cov.ok} of ${cov.total} sources live`;
}

// Card id → payload vintage key: which refresh timestamp this card's data
// actually came from. Indices/commodities are omitted — they already carry
// their own precise as-of note blended from spot + futures sources.
const CARD_VINTAGE_KEY = {
  risk: "risk",
  "ai-sentiment": "ai_sentiment",
  analysis: "ai_analysis",
  regime: "regime",
  indicators: "indicators",
  rates: "market",
  breadth: "indicators",
  "breadth-ai": "indicators",
  bottleneck: "bottleneck",
  earnings: "earnings",
  thirteenf: "thirteenf",
  events: "events",
};

// ---- Card-header info tooltips ---------------------------------------------
// One info icon per card h2, explaining the card's purpose and the other
// dashboard sections it reads from. The copy is grounded in the backend
// contracts (app/config.py knobs, app/risk.py gates, app/news.py thresholds);
// the deps list renders as small pills inside the tooltip.

const INFO_ICON_SVG =
  `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">` +
  `<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v3.4"/><path d="M8 5.1v.1"/></svg>`;

const CARD_TOOLTIPS = {
  risk: {
    text: "Aggregates 9 cross-asset signals. Fragility flags mark consensus optimism OR washout setups. RED fires when 2+ optimism-side flags align, on trend break, or on broad risk-off.",
    deps: ["breadth", "VIX", "credit", "equity trend"],
  },
  "ai-sentiment": {
    text: "Reads AI-tagged events from data/events.json plus per-cohort momentum and breadth (% of constituents above their 50DMA, see Breadth — AI proxies). Coverage depends on news refresh cadence and on how many cohort quotes resolve. Score is −100..100; verdicts: Euphoric / Expansion / Neutral / Caution / Cycle under pressure.",
    deps: ["news events", "cohort quotes", "AI cohort breadth"],
  },
  analysis: {
    text: "Deterministic weighted-vote synthesis of every engine. Capped by input coverage. History is async-loaded from /api/analysis/history.",
    deps: ["all engines"],
  },
  regime: {
    text: "6-component cross-asset regime classification. Reports older than 3 days (REGIME_MAX_AGE_DAYS) are flagged stale.",
    deps: ["cross-asset quotes"],
  },
  indicators: {
    text: "Breadth from sectors + indices. VIX signal uses its own 50-day MA. Coverage drops when histories are missing.",
    deps: ["sector quotes", "SPY", "VIX"],
  },
  indices: {
    text: "Quotes + daily change, derived from close history (yfinance fast_info is broken). Failed fetches show as null.",
    deps: ["index quotes", "index futures"],
  },
  commodities: {
    text: "Quotes + daily change, derived from close history (yfinance fast_info is broken). Failed fetches show as null.",
    deps: ["commodity quotes", "futures"],
  },
  rates: {
    text: "Quotes + daily change, derived from close history (yfinance fast_info is broken). Failed fetches show as null.",
    deps: ["treasury yields"],
  },
  breadth: {
    text: "Share of sector constituents trading above their 50-day moving average.",
    deps: ["sector histories"],
  },
  "breadth-ai": {
    text: "Share of AI-cohort constituents trading above their 50-day moving average.",
    deps: ["AI cohort histories"],
  },
  bottleneck: {
    text: "Ranks proxy tickers by 40-day ROC (BOTTLENECK_LOOKBACK_DAYS). Most-stressed first.",
    deps: ["proxy tickers"],
  },
  earnings: {
    text: "Tracked universe includes default mega-caps. Users can add/remove any ticker via /api/earnings/validate.",
    deps: ["yfinance quotes"],
  },
  thirteenf: {
    text: "SEC EDGAR weight-%. Dollar values intentionally never shown. ~20d cache (THIRTEENF_TTL).",
    deps: ["SEC EDGAR"],
  },
  events: {
    text: "Live RSS feeds: MarketWatch (US finance) + BBC Business (global finance). Seed timeline: curated Wikipedia history (preserved legacy). High/Critical only (IMPORTANCE_THRESHOLD = 6.0). 48h ingest window. Cross-source dedupe merges same-story items (Jaccard ≥ 0.6 or fuzzy ≥ 0.85 within 2 days). Source weights bias MarketWatch 1.2×, BBC 1.0×; finance-relevance lifts composite score above the gate.",
    deps: ["MarketWatch", "BBC Business", "Wikipedia seed"],
  },
  fragility: {
    text: "Sub-card of risk. Fragility flags split by side: optimism-side flags (breadth overheating, leadership narrowing, credit risk-on accelerating, AI theme extending, valuation stretched) drive the consensus-optimism RED gate. Distress-side flags (washed-out breadth, rising stock-bond correlation, SPY drawdown) describe breakage, not euphoria. Each flag carries a flip condition — the metric movement that would resolve it.",
    deps: ["breadth", "concentration", "credit", "AI theme", "valuation"],
  },
};

// Injects one info button into every card h2 and attaches its tooltip.
// Idempotent: re-running (e.g. after a future layout rebuild) never stacks
// buttons. Card h2s are static chrome — renderers only touch card bodies —
// so boot-time injection is enough.
export function initCardTooltips() {
  for (const [cardId, spec] of Object.entries(CARD_TOOLTIPS)) {
    const card = document.querySelector(`[data-card="${cardId}"]`);
    const h2 = card ? card.querySelector("h2") : null;
    if (!h2 || h2.querySelector(".card-info")) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card-info";
    btn.setAttribute("aria-label", `About the ${cardId} card`);
    btn.innerHTML = INFO_ICON_SVG;
    h2.appendChild(btn);
    attachTooltip(btn, { text: spec.text, deps: spec.deps });
  }
}

// Tiny muted "As of YYYY-MM-DD HH:MM" stamp at the foot of each card, from
// that section's own refresh timestamp (rendered in US Eastern time — same
// zone and format as the page-level header "As of").
function applyVintageStamp(section, data) {
  const entry = SECTION_CARDS[section];
  if (!entry) return;
  const [cardId] = entry;
  const key = CARD_VINTAGE_KEY[cardId];
  if (!key) return;
  const card = document.querySelector(`[data-card="${cardId}"]`);
  if (!card) return;
  const el = card.querySelector(":scope > .vintage-note");
  const ts = (data.vintage || {})[key];
  // fmtHmET doubles as the null/parse check ("" for missing); the stamp
  // itself renders the full date via fmtTimestampET, matching the header.
  if (!fmtHmET(ts)) {
    if (el) el.remove();
    return;
  }
  let note = el;
  if (!note) {
    note = document.createElement("div");
    note.className = "asof-note vintage-note";
    card.appendChild(note);
  }
  note.textContent = `As of ${fmtTimestampET(ts)} ET`;
}

export function renderSection(section, data) {
  const m = data.market || {};
  const stamped = section === "all" ? Object.keys(SECTION_CARDS) : [section];
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
  for (const s of stamped) {
    applyCoverageBadge(s, data);
    applyVintageStamp(s, data);
  }
}
