// Bottleneck (chokepoint) section.
//
// The section is user-authored: each *topic* names a demand driver, lists the
// upstream layers that physically constrain it, and carries downstream
// per-stock thesis cards. Anchors are the obvious capex spenders (unranked —
// the demand trace); underdogs are filtered by a per-topic market-cap ceiling
// and ranked by 40-day momentum.
//
// Render source is ONE call: GET /api/bottleneck/topics. Nothing here computes
// a figure — every number printed comes from that payload, a null renders as
// "—", and each figure carries its own `as_of` where the payload supplies one.
// Display formatting (dollar magnitude, signed percent, ×) is presentation
// only; no averages, sums or percentages are derived in the browser.

import {
  $, escapeHtml, fmtFloat, fmtPct, pctClass, fmtTimestampET, safeUrl,
} from "./format.js";
import * as API from "./api.js";

const EM = "\u2014"; // em dash — the single representation of "no value"

const EVIDENCE_LABELS = {
  "primary-filing": "Primary filing",
  "company-release": "Company release",
  "sell-side": "Sell-side",
  social: "Social",
};

const CHECKLIST_FLAGS = [
  ["dilution_atm", "Dilution / ATM"],
  ["customer_concentration", "Customer concentration"],
  ["gaap_margin", "GAAP margin"],
  ["financing_quality", "Financing quality"],
];

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "cancelled"]);
const POLL_MS = 1500;

// ---- Module state ------------------------------------------------------------
// Expansion is deliberately in-memory only: this component is used in exactly
// one section, so there is no cross-consumer persistence key to get wrong.

let payload = null;          // {topics: [], bottleneck, generation}
let openTopics = new Set();  // expanded topic ids
let openStocks = new Set();  // expanded stock keys
let panel = null;            // {kind, ...} open form: new|edit|generate|import|export
let editDraft = null;        // working copy for the editor
let genTarget = "__new__";   // retained generate target selection
let importText = "";
let exportText = "";
let notice = null;           // {tone, text}
let skillInfo = null;        // GET /skill/status
let skillBusy = false;
let skillResult = null;      // POST /skill/refresh outcome
let job = null;              // active or most-recent drafting job
let pollTimer = null;
let renderToken = 0;

// ---- Small formatters --------------------------------------------------------
// fmtCapital scales a dollar figure for readability (the backend does the same
// in its own topic note, e.g. "$3B"). It is unit formatting, not arithmetic
// over several fields.

function fmtCapital(value) {
  if (value == null) return EM;
  const n = Number(value);
  if (!isFinite(n)) return EM;
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function parseCeiling(text) {
  const m = String(text == null ? "" : text).trim().match(/^\$?\s*([0-9]*\.?[0-9]+)\s*([tbmk])?$/i);
  if (!m) return null;
  const unit = (m[2] || "").toLowerCase();
  const mult = unit === "t" ? 1e12 : unit === "b" ? 1e9 : unit === "m" ? 1e6 : unit === "k" ? 1e3 : 1;
  return Number(m[1]) * mult;
}

function formatCeilingInput(value) {
  if (value == null) return "";
  const n = Number(value);
  if (!isFinite(n)) return "";
  if (n >= 1e12 && n % 1e12 === 0) return `${n / 1e12}T`;
  if (n >= 1e9 && n % 1e9 === 0) return `${n / 1e9}B`;
  if (n >= 1e6 && n % 1e6 === 0) return `${n / 1e6}M`;
  return String(n);
}

function asOfTitle(ts) {
  return ts ? `as of ${fmtTimestampET(ts)} ET` : "as of \u2014";
}

function shortHash(h) {
  if (!h || typeof h !== "string") return EM;
  return h.slice(0, 10);
}

// ---- Value chips -------------------------------------------------------------

function stancePill(stance) {
  const s = String(stance || "").trim();
  if (!s) return "";
  const low = s.toLowerCase();
  const cls = /(bull|buy|long|own)/.test(low) ? "bull"
    : /(bear|sell|short|avoid|fade)/.test(low) ? "bear"
    : "neutral";
  return `<span class="pill ${cls} bn-stance">${escapeHtml(s)}</span>`;
}

function flagChip(label, value) {
  if (value === true) return `<span class="bn-flag yes" title="${escapeHtml(label)}: yes">${escapeHtml(label)}: yes</span>`;
  if (value === false) return `<span class="bn-flag no" title="${escapeHtml(label)}: no">${escapeHtml(label)}: no</span>`;
  return `<span class="bn-flag na" title="${escapeHtml(label)}: not assessed">${escapeHtml(label)}: not assessed</span>`;
}

function evidenceItem(ev) {
  const tier = EVIDENCE_LABELS[ev.tier] ? ev.tier : "social";
  const label = EVIDENCE_LABELS[tier] || escapeHtml(ev.tier || "unclassified");
  const url = safeUrl(ev.source_url);
  const source = ev.source
    ? (url
      ? `<a class="bn-ev-src" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ev.source)}</a>`
      : `<span class="bn-ev-src">${escapeHtml(ev.source)}</span>`)
    : "";
  return `<li class="bn-ev-item">
      <span class="bn-ev-tier t-${tier}">${escapeHtml(label)}</span>
      <span class="bn-ev-claim">${escapeHtml(ev.claim || "")}</span>
      ${source}
    </li>`;
}

// ---- Stock thesis card -------------------------------------------------------

function stockKey(topicId, kind, index, ticker) {
  return `${topicId}::${kind}::${ticker || index}`;
}

function renderStockCard(card, ctx) {
  // ctx: {topicId, kind: "anchor"|"underdog", rank: number|null}
  const key = stockKey(ctx.topicId, ctx.kind, ctx.index, card.ticker);
  const open = openStocks.has(key);
  const m = card.metrics || {};
  const metrics = [
    ["Market cap", m.market_cap != null ? fmtCapital(m.market_cap) : EM, m.as_of, ""],
    ["40-day momentum", m.roc_40d != null ? `<span class="${pctClass(m.roc_40d)}">${escapeHtml(fmtPct(m.roc_40d))}</span>` : EM, m.as_of, ""],
    ["1-year move", m.move_1y != null ? `<span class="${pctClass(m.move_1y)}">${escapeHtml(fmtPct(m.move_1y))}</span>` : EM, m.as_of, ""],
    ["Forward PE", m.forward_pe != null ? `${escapeHtml(fmtFloat(m.forward_pe))}\u00d7` : EM, m.as_of, ""],
    // Revenue growth is stored as the source's ratio (yfinance revenueGrowth:
    // 0.18 = +18%). It is shown exactly as fetched — never converted to a
    // percentage in the browser — and the label says so.
    ["Revenue growth (ratio)", m.revenue_growth != null ? escapeHtml(fmtFloat(m.revenue_growth)) : EM, m.as_of, "0.18 = +18%, as fetched from the source"],
  ];

  const rank = ctx.rank != null ? `<span class="bn-rank">#${ctx.rank}</span>` : "";
  const head = `
    <button type="button" class="bn-stock-toggle" data-bn-action="toggle-stock"
            data-stock-key="${escapeHtml(key)}" aria-expanded="${open ? "true" : "false"}">
      <span class="bn-caret">${open ? "\u25be" : "\u25b8"}</span>
      ${rank}
      <span class="bn-stock-ticker">${escapeHtml(card.ticker || EM)}</span>
      <span class="bn-stock-name">${escapeHtml(card.name || "")}</span>
      ${stancePill(card.stance)}
      <span class="bn-stock-roc num ${m.roc_40d != null ? pctClass(m.roc_40d) : ""}">
        ${m.roc_40d != null ? escapeHtml(fmtPct(m.roc_40d)) : EM}
      </span>
    </button>`;

  if (!open) {
    return `<div class="bn-stock" data-stock-key="${escapeHtml(key)}">${head}</div>`;
  }

  const meta = [
    ["Layer", card.layer],
    ["Role", card.role],
    ["Stance", card.stance],
  ].filter(([, v]) => v)
    .map(([k, v]) => `<div class="kv"><span class="k">${escapeHtml(k)}</span><span>${escapeHtml(v)}</span></div>`)
    .join("");

  const evidence = Array.isArray(card.evidence) && card.evidence.length
    ? `<div class="bn-subhead">Evidence</div><ul class="bn-evidence">${card.evidence.map(evidenceItem).join("")}</ul>`
    : `<div class="bn-subhead">Evidence</div><div class="bn-muted">${EM}</div>`;

  const invalidation = Array.isArray(card.invalidation) && card.invalidation.length
    ? `<div class="bn-subhead">Invalidation</div><ul class="bn-list">${card.invalidation.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`
    : "";

  const catalyst = (card.catalyst || card.catalyst_window)
    ? `<div class="bn-subhead">Catalyst</div>
       <div class="bn-catalyst">
         <span>${escapeHtml(card.catalyst || EM)}</span>
         ${card.catalyst_window ? `<span class="bn-window">${escapeHtml(card.catalyst_window)}</span>` : ""}
       </div>`
    : "";

  const flags = `<div class="bn-subhead">Checklist</div>
    <div class="bn-flags">${CHECKLIST_FLAGS.map(([k, label]) => flagChip(label, card[k])).join("")}</div>`;

  const prov = card.provenance || {};
  const hasProv = Object.values(prov).some((v) => v);
  const provBlock = hasProv
    ? `<div class="bn-subhead">Provenance</div>
       <div class="bn-prov">
         <div class="kv"><span class="k">Model</span><span>${escapeHtml(prov.model || EM)}</span></div>
         <div class="kv"><span class="k">Skill snapshot</span><span title="${escapeHtml(prov.skill_snapshot || "")}">${escapeHtml(shortHash(prov.skill_snapshot))}</span></div>
         <div class="kv"><span class="k">Prompt hash</span><span title="${escapeHtml(prov.prompt_hash || "")}">${escapeHtml(shortHash(prov.prompt_hash))}</span></div>
         <div class="kv"><span class="k">Run</span><span>${prov.run_ts ? escapeHtml(fmtTimestampET(prov.run_ts)) + " ET" : EM}</span></div>
       </div>`
    : "";

  return `<div class="bn-stock expanded" data-stock-key="${escapeHtml(key)}">
    ${head}
    <div class="bn-stock-body">
      ${card.why_chokepoint ? `<div class="bn-why">${escapeHtml(card.why_chokepoint)}</div>` : ""}
      ${meta}
      <div class="bn-subhead">Metrics <span class="bn-asof-inline">${escapeHtml(asOfTitle(m.as_of))}</span></div>
      <div class="bn-metrics">
        ${metrics.map(([label, value, asOf, hint]) => `
          <div class="bn-metric" title="${escapeHtml(`${label} ${asOfTitle(asOf)}${hint ? ` — ${hint}` : ""}`)}">
            <span class="bn-metric-label">${escapeHtml(label)}</span>
            <span class="bn-metric-value num">${value}</span>
          </div>`).join("")}
      </div>
      ${evidence}
      ${catalyst}
      ${invalidation}
      ${flags}
      ${provBlock}
    </div>
  </div>`;
}

// ---- Topic rendering ---------------------------------------------------------

function renderLayer(layer) {
  const v = layer.roc_40d_pct;
  const tickers = Array.isArray(layer.stocks) && layer.stocks.length
    ? `<span class="bn-tickers">${layer.stocks.map((t) => `<span class="bn-ticker">${escapeHtml(t)}</span>`).join("")}</span>`
    : `<span class="bn-muted">${EM}</span>`;
  return `<div class="bn-layer">
      <div class="bn-layer-top">
        <span class="bn-layer-name">${escapeHtml(layer.name || EM)}</span>
        <span class="bn-layer-roc num ${v != null ? pctClass(v) : ""}"
              title="${escapeHtml(`40-day ROC ${asOfTitle(layer.as_of)}`)}">${v != null ? escapeHtml(fmtPct(v)) : EM}</span>
      </div>
      ${layer.physical_constraint ? `<div class="bn-layer-line"><span class="bk">Constraint</span>${escapeHtml(layer.physical_constraint)}</div>` : ""}
      ${layer.what_to_watch ? `<div class="bn-layer-line"><span class="bk">Watch</span>${escapeHtml(layer.what_to_watch)}</div>` : ""}
      <div class="bn-layer-tickers">${tickers}</div>
    </div>`;
}

function renderStocks(cards, ctxBase) {
  if (!cards.length) return `<div class="bn-muted">${EM}</div>`;
  return cards.map((card, i) => renderStockCard(card, {
    ...ctxBase, index: i,
    rank: ctxBase.ranked ? i + 1 : null,
  })).join("");
}

function renderTopicBody(block) {
  if (panel && panel.kind === "edit" && panel.topicId === block.id && editDraft) {
    return renderEditor(editDraft);
  }
  const upstream = block.upstream || [];
  const anchors = (block.downstream || {}).anchor || [];
  const underdogs = (block.downstream || {}).underdogs || [];
  const ceilingNote = formatCeilingInput(block.underdog_ceiling) || EM;

  return `
    <div class="bn-band">
      <div class="bn-subhead">Upstream layers <span class="bn-subhead-note">ranked by 40-day momentum</span></div>
      ${upstream.length ? upstream.map(renderLayer).join("") : `<div class="bn-muted">No upstream layers defined yet.</div>`}
    </div>

    <div class="bn-band bn-band-anchor">
      <div class="bn-subhead">Demand trace — anchors
        <span class="bn-subhead-note">obvious capex spenders, unranked</span>
      </div>
      <div class="bn-strip">${renderStocks(anchors, { topicId: block.id, kind: "anchor", ranked: false })}</div>
    </div>

    <div class="bn-band bn-band-underdog">
      <div class="bn-subhead">Underdogs
        <span class="bn-subhead-note">below $${escapeHtml(ceilingNote)} market cap · ranked by 40-day momentum</span>
      </div>
      ${underdogs.length
        ? renderStocks(underdogs, { topicId: block.id, kind: "underdog", ranked: true })
        : `<div class="bn-muted">No underdogs within the ceiling.</div>`}
    </div>

    <div class="bn-foot">
      <span class="bn-topic-note">${escapeHtml(block.note || "")}</span>
      <span class="bn-topic-edited">Updated ${block.updated ? escapeHtml(fmtTimestampET(block.updated)) + " ET" : EM}</span>
    </div>`;
}

function renderTopic(block) {
  const open = openTopics.has(block.id);
  const layerCount = (block.upstream || []).length;
  const underdogCount = ((block.downstream || {}).underdogs || []).length;
  const anchorCount = ((block.downstream || {}).anchor || []).length;
  const strongest = block.strongest_signal;
  const ceiling = formatCeilingInput(block.underdog_ceiling) || EM;
  return `<section class="bn-topic${open ? " open" : ""}" data-topic-id="${escapeHtml(block.id)}">
    <div class="bn-topic-head">
      <button type="button" class="bn-topic-toggle" data-bn-action="toggle-topic"
              data-topic-id="${escapeHtml(block.id)}" aria-expanded="${open ? "true" : "false"}">
        <span class="bn-caret">${open ? "\u25be" : "\u25b8"}</span>
        <span class="bn-topic-name">${escapeHtml(block.name || EM)}</span>
        <span class="bn-topic-chips">
          <span class="bn-chip" title="Upstream layers">${layerCount} layer${layerCount === 1 ? "" : "s"}</span>
          <span class="bn-chip" title="Anchors + underdogs">${anchorCount} anchor${anchorCount === 1 ? "" : "s"} · ${underdogCount} underdog${underdogCount === 1 ? "" : "s"}</span>
          <span class="bn-chip ceiling" title="Underdog market-cap ceiling">\u2264 $${escapeHtml(ceiling)}</span>
          ${strongest ? `<span class="bn-chip strongest ${strongest.roc_40d_pct != null ? pctClass(strongest.roc_40d_pct) : ""}" title="Strongest upstream layer">${escapeHtml(strongest.name || EM)} ${strongest.roc_40d_pct != null ? escapeHtml(fmtPct(strongest.roc_40d_pct)) : EM}</span>` : ""}
        </span>
      </button>
      <div class="bn-topic-actions" data-topic-id="${escapeHtml(block.id)}">
        ${panel && panel.kind === "delete" && panel.topicId === block.id
          ? `<button type="button" class="mini bn-danger" data-bn-action="confirm-delete" data-topic-id="${escapeHtml(block.id)}">Delete topic and its cards</button>
             <button type="button" class="mini" data-bn-action="cancel-delete">Cancel</button>`
          : `<button type="button" class="mini" data-bn-action="edit-topic" data-topic-id="${escapeHtml(block.id)}">Edit</button>
             <button type="button" class="mini" data-bn-action="generate-for" data-topic-id="${escapeHtml(block.id)}" title="Draft an update with the agent">Generate</button>
             <button type="button" class="mini bn-danger-ghost" data-bn-action="delete-topic" data-topic-id="${escapeHtml(block.id)}" title="Delete topic">Delete</button>`}
      </div>
    </div>
    ${open ? `<div class="bn-topic-body">${renderTopicBody(block)}</div>` : ""}
  </section>`;
}

function renderTopics() {
  const blocks = (payload.bottleneck || {}).topics || [];
  if (!blocks.length) {
    if (panel) return "";
    return renderEmptyState();
  }
  return `<div class="bn-topics">${blocks.map((b) => renderTopic(b)).join("")}</div>`;
}

// ---- Head (thesis, toolbar, skill caveat) ------------------------------------

function renderHead() {
  const bn = payload.bottleneck || {};
  const gen = payload.generation || { enabled: false, error: null };
  const strongest = bn.strongest_signal;
  const generateDisabled = !gen.enabled;
  return `
    <div class="bn-head">
      <p class="bn-thesis">${escapeHtml(bn.thesis || "")}</p>
      <div class="bn-toolbar">
        <button type="button" class="mini bn-primary" data-bn-action="new-topic">+ New topic</button>
        <button type="button" class="mini" data-bn-action="generate"${generateDisabled ? ` disabled title="${escapeHtml(gen.error || "Topic generation is unavailable.")}"` : ""}>Generate topic\u2026</button>
        <button type="button" class="mini" data-bn-action="import">Import</button>
        <button type="button" class="mini" data-bn-action="export">Export</button>
      </div>
      ${generateDisabled
        ? `<div class="bn-gen-off" role="note"><b>Generation unavailable.</b> ${escapeHtml(gen.error || "")}</div>`
        : ""}
      ${strongest
        ? `<div class="bn-strongest">
             <span class="bn-strongest-label">Strongest upstream layer</span>
             <b>${escapeHtml(strongest.name || EM)}</b>
             <span class="bn-muted">${escapeHtml(strongest.topic_name || "")}</span>
             <span class="num ${strongest.roc_40d_pct != null ? pctClass(strongest.roc_40d_pct) : ""}">${strongest.roc_40d_pct != null ? escapeHtml(fmtPct(strongest.roc_40d_pct)) : EM}</span>
             <span class="bn-asof-inline">${escapeHtml(asOfTitle(strongest.as_of))}</span>
           </div>`
        : ""}
      ${renderSkillBar()}
    </div>`;
}

function renderSkillBar() {
  const bn = payload.bottleneck || {};
  const framework = bn.framework || "serenity-aleabitoreddit";
  let statusLine;
  if (skillInfo) {
    statusLine = skillInfo.installed
      ? `installed · ${skillInfo.file_count || 0} files · hash ${escapeHtml(shortHash(skillInfo.hash))}${skillInfo.mtime ? ` · updated ${escapeHtml(fmtTimestampET(skillInfo.mtime))} ET` : ""}`
      : "not installed";
  } else {
    statusLine = "status unavailable";
  }
  let result = "";
  if (skillBusy) {
    result = `<div class="bn-skill-result busy">Installing or updating the skill\u2026 this can take a minute.</div>`;
  } else if (skillResult) {
    const ok = skillResult.ok === true;
    const tail = String(skillResult.output_tail || "").trim();
    result = `<div class="bn-skill-result ${ok ? "ok" : "bad"}">
        <b>${ok ? "Skill refreshed." : "Skill refresh did not complete."}</b>
        ${skillResult.timed_out ? " It timed out and the process was stopped." : ""}
        ${skillResult.returncode != null ? ` Exit code ${escapeHtml(String(skillResult.returncode))}.` : ""}
        ${skillResult.new_hash ? ` New hash ${escapeHtml(shortHash(skillResult.new_hash))}.` : ""}
        ${tail ? `<pre class="bn-skill-output">${escapeHtml(tail)}</pre>` : ""}
      </div>`;
  }
  return `
    <div class="bn-skillbar">
      <div class="bn-skill-row">
        <span class="bn-skill-name">${escapeHtml(framework)}</span>
        <span class="bn-skill-status">${statusLine}</span>
        <button type="button" class="mini" data-bn-action="refresh-skill"${skillBusy ? " disabled" : ""}>Refresh skill</button>
      </div>
      <div class="bn-skill-caveat">
        The skill's merged thesis base is frozen at ~2026-06-08. Material added since then is
        appended as dated entries — read the newest entries as the current view, and treat the
        older base as history.
      </div>
      ${result}
    </div>`;
}

function renderNotice() {
  if (!notice) return "";
  return `<div class="bn-msg ${notice.tone === "error" ? "error" : "ok"}" role="status">${escapeHtml(notice.text)}</div>`;
}

// ---- Empty state -------------------------------------------------------------

function renderEmptyState() {
  const gen = payload.generation || { enabled: false, error: null };
  return `
    <div class="bn-empty">
      <div class="bn-empty-title">No topics yet</div>
      <p class="bn-empty-body">
        A topic names a demand driver, traces it to the upstream layers that constrain it,
        and carries a thesis card for each stock named. Create one by hand, or have the
        agent draft one from a theme and apply it after review.
      </p>
      <div class="bn-empty-actions">
        <button type="button" class="mini bn-primary" data-bn-action="new-topic">+ Create a topic</button>
        <button type="button" class="mini" data-bn-action="generate"${gen.enabled ? "" : ` disabled title="${escapeHtml(gen.error || "Topic generation is unavailable.")}"`}>Generate one\u2026</button>
      </div>
      ${gen.enabled ? "" : `<p class="bn-gen-off">${escapeHtml(gen.error || "")}</p>`}
    </div>`;
}

// ---- Panels (new / generate / import / export) -------------------------------

function renderPanels() {
  if (!panel) return renderJobPanel();
  switch (panel.kind) {
    case "new": return renderNewPanel() + renderJobPanel();
    case "generate": return renderGeneratePanel() + renderJobPanel();
    case "import": return renderImportPanel();
    case "export": return renderExportPanel();
    default: return renderJobPanel();
  }
}

function renderNewPanel() {
  return `
    <form class="bn-panel" data-bn-form="new-topic">
      <div class="bn-panel-title">New topic</div>
      <label class="bn-field">
        <span>Name (the demand driver)</span>
        <input type="text" name="name" data-field="name" maxlength="120" placeholder="e.g. Grid power for data centers" autocomplete="off" />
      </label>
      <div class="bn-panel-actions">
        <button type="submit" class="mini bn-primary">Create topic</button>
        <button type="button" class="mini" data-bn-action="close-panel">Cancel</button>
        <span class="bn-panel-hint">Starts empty — add layers and stock cards next.</span>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </form>`;
}

function renderGeneratePanel() {
  const topics = payload.topics || [];
  const options = [
    `<option value="__new__"${genTarget === "__new__" ? " selected" : ""}>Create a new topic from the draft</option>`,
    ...topics.map((t) => `<option value="${escapeHtml(t.id)}"${genTarget === t.id ? " selected" : ""}>${escapeHtml(t.name || t.id)}</option>`),
  ].join("");
  return `
    <form class="bn-panel" data-bn-form="generate">
      <div class="bn-panel-title">Draft a topic with the agent</div>
      <label class="bn-field">
        <span>Theme</span>
        <input type="text" name="theme" data-field="theme" maxlength="200" placeholder="e.g. HBM memory supply for AI accelerators" autocomplete="off" />
      </label>
      <label class="bn-field">
        <span>Apply to</span>
        <select name="topic_id" data-field="topic_id">${options}</select>
      </label>
      <p class="bn-panel-hint">The draft is shown for review. Nothing is written to the topic store until you apply it.</p>
      <div class="bn-panel-actions">
        <button type="submit" class="mini bn-primary">Start generation</button>
        <button type="button" class="mini" data-bn-action="close-panel">Cancel</button>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </form>`;
}

function renderImportPanel() {
  return `
    <form class="bn-panel" data-bn-form="import">
      <div class="bn-panel-title">Import topics</div>
      <label class="bn-field">
        <span>Paste a topics document (a bare list, or {"version", "topics"})</span>
        <textarea name="doc" data-field="doc" rows="6" spellcheck="false" placeholder='{"version": 1, "topics": []}'>${escapeHtml(importText)}</textarea>
      </label>
      <p class="bn-panel-hint">Valid topics are merged in; invalid ones are reported and skipped.</p>
      <div class="bn-panel-actions">
        <button type="submit" class="mini bn-primary">Import</button>
        <button type="button" class="mini" data-bn-action="close-panel">Cancel</button>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </form>`;
}

function renderExportPanel() {
  return `
    <div class="bn-panel" data-bn-panel="export">
      <div class="bn-panel-title">Export topics</div>
      <p class="bn-panel-hint">This is the exact document the import endpoint accepts.</p>
      <textarea class="bn-export-text" data-field="export" rows="10" readonly spellcheck="false">${escapeHtml(exportText)}</textarea>
      <div class="bn-panel-actions">
        <button type="button" class="mini bn-primary" data-bn-action="copy-export">Copy JSON</button>
        <button type="button" class="mini" data-bn-action="download-export">Download</button>
        <button type="button" class="mini" data-bn-action="close-panel">Close</button>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </div>`;
}

// ---- Drafting job panel ------------------------------------------------------

// The four named research stages the backend reports while a draft is building.
// `status` alone drives the row; any stage carrying a note prints it, so a
// skipped, failed or merely-annotated step is legible instead of reading as an
// ambiguous hang. The set is frozen server-side — the browser maps status to a
// state, and never invents a stage or a note.
const STAGE_STATUSES = new Set(["pending", "running", "done", "skipped", "failed"]);
const STAGE_GLYPH = {
  pending: "\u25cb", // ○
  running: "\u25cf", // ●
  done: "\u2713",    // ✓
  skipped: "\u2298", // ⊘
  failed: "\u2715",  // ✕
};
const STAGE_WORD = {
  pending: "pending", running: "running", done: "done",
  skipped: "skipped", failed: "failed",
};

function renderStages(stages) {
  // A legacy persisted job carries no stage breakdown; keep the old bar so the
  // panel never regresses to an empty box.
  if (!Array.isArray(stages) || !stages.length) {
    return `<div class="bn-progress"><span></span></div>`;
  }
  return `<ol class="bn-stages">${stages.map((s) => {
    const st = (s && STAGE_STATUSES.has(s.status)) ? s.status : "pending";
    const note = s && s.note
      ? `<span class="bn-stage-note">${escapeHtml(s.note)}</span>`
      : "";
    return `<li class="bn-stage ${st}">
        <span class="bn-stage-marker" aria-hidden="true">${STAGE_GLYPH[st]}</span>
        <span class="bn-stage-label">${escapeHtml((s && (s.label || s.key)) || "")}</span>
        <span class="bn-stage-status">${escapeHtml(STAGE_WORD[st])}</span>
        ${note}
      </li>`;
  }).join("")}</ol>`;
}

function renderJobPanel() {
  if (!job) return "";
  const status = job.status;
  if (status === "queued" || status === "running") {
    return `<div class="bn-job" role="status">
        <div class="bn-job-title">Drafting a topic for \u201c${escapeHtml(job.theme || "")}\u201d\u2026</div>
        <div class="bn-job-status">${escapeHtml(status)}${job.model ? ` \u00b7 ${escapeHtml(job.model)}` : ""}</div>
        ${renderStages(job.stages)}
        <div class="bn-panel-actions">
          <button type="button" class="mini" data-bn-action="cancel-job" data-job-id="${escapeHtml(job.id)}">Cancel</button>
        </div>
      </div>`;
  }
  if (status === "failed") {
    return `<div class="bn-job error" role="alert">
        <div class="bn-job-title">Generation failed</div>
        <div class="bn-job-error">${escapeHtml(job.error || "no error detail returned")}</div>
        <div class="bn-panel-actions"><button type="button" class="mini" data-bn-action="dismiss-job">Dismiss</button></div>
      </div>`;
  }
  if (status === "cancelled") {
    return `<div class="bn-job" role="status">
        <div class="bn-job-title">Generation cancelled</div>
        <p class="bn-panel-hint">Nothing was written to the topic store.</p>
        <div class="bn-panel-actions"><button type="button" class="mini" data-bn-action="dismiss-job">Dismiss</button></div>
      </div>`;
  }
  if (status === "succeeded" && job.draft) {
    return renderReview(job);
  }
  return "";
}

// A short, human label for a researched URL: its hostname without a leading
// "www.". Presentation only — the anchor still carries the full URL in `title`.
// Falls back to the raw string when the URL cannot be parsed.
function researchSourceLabel(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./i, "");
    return host || url;
  } catch (e) {
    return url;
  }
}

function renderReview(j) {
  const draft = j.draft || {};
  const topic = draft.topic || {};
  const prov = draft.provenance || {};
  const upstream = Array.isArray(topic.upstream) ? topic.upstream : [];
  const downstream = topic.downstream || {};
  const anchors = Array.isArray(downstream.anchor) ? downstream.anchor : [];
  const underdogs = Array.isArray(downstream.underdogs) ? downstream.underdogs : [];
  const research = (j.research && typeof j.research === "object") ? j.research : null;
  const sources = research && Array.isArray(research.sources)
    ? research.sources.filter((s) => typeof s === "string" && s.trim())
    : [];
  const adjustments = Array.isArray(j.fill_adjustments)
    ? j.fill_adjustments.filter((a) => typeof a === "string" && a.trim())
    : [];
  const topics = payload.topics || [];
  const targetOptions = [
    ...(topics.length
      ? topics.map((t) => `<option value="${escapeHtml(t.id)}"${j.topic_id === t.id ? " selected" : ""}>${escapeHtml(t.name || t.id)}</option>`)
      : []),
    `<option value="__new__"${topics.length ? "" : " selected"}>Create a new topic: ${escapeHtml(topic.name || j.theme || "")}</option>`,
  ].join("");

  const listStocks = (cards, rank) => cards.map((card, i) => `
      <li>${rank ? `<span class="bn-rank">#${i + 1}</span> ` : ""}<b>${escapeHtml(card.ticker || EM)}</b>
        <span class="bn-stock-name">${escapeHtml(card.name || "")}</span>
        ${card.stance ? stancePill(card.stance) : ""}
      </li>`).join("");

  // "Chain preserved" (Phase 2): a non-empty list means the backend restored
  // parts of the draft chain the refined thesis had dropped or renamed. Grounded
  // copy only — the heading states that fact, the lines are the server's own.
  const fillNote = adjustments.length
    ? `<div class="bn-fill-note">
        <div class="bn-subhead">Chain preserved from the draft</div>
        <ul>${adjustments.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
      </div>`
    : "";

  // Research (Phase 2): sources the agent actually consulted, any degradation
  // note, and the raw findings (collapsed so a long evidence dump never
  // dominates the panel). Absent on a legacy job -> render nothing at all.
  const researchParts = [];
  if (research) {
    if (sources.length) {
      researchParts.push(`<div class="bn-subhead">Research sources (${sources.length})</div>`);
      researchParts.push(`<ul class="bn-draft-sources">${sources.map((s) => {
        // Only http(s) becomes a link; anything else (e.g. a javascript: value)
        // stays inert text so it can never be assigned as an href.
        if (/^https?:\/\//i.test(s)) {
          return `<li><a class="bn-source-link" href="${escapeHtml(s)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(s)}">${escapeHtml(researchSourceLabel(s))}</a></li>`;
        }
        return `<li><span class="bn-source-link">${escapeHtml(s)}</span></li>`;
      }).join("")}</ul>`);
    }
    if ((research.status === "skipped" || research.status === "failed")
      && typeof research.note === "string" && research.note.trim()) {
      researchParts.push(`<div class="bn-research-note">Research: ${escapeHtml(research.note)}</div>`);
    }
    if (typeof research.findings === "string" && research.findings.trim()) {
      researchParts.push(`<details class="bn-findings"><summary>Researched findings (${research.findings.length} chars)</summary><pre class="bn-findings-text">${escapeHtml(research.findings)}</pre></details>`);
    }
  }
  const researchHtml = researchParts.join("");

  return `<div class="bn-job review">
      <div class="bn-job-title">Draft ready for review \u2014 not applied yet</div>
      <div class="bn-draft">
        <div class="bn-draft-name">${escapeHtml(topic.name || j.theme || EM)}</div>
        ${topic.underdog_ceiling != null ? `<div class="bn-draft-ceiling">Underdog ceiling: $${escapeHtml(formatCeilingInput(topic.underdog_ceiling) || EM)}</div>` : ""}
        ${fillNote}

        <div class="bn-subhead">Upstream layers (${upstream.length})</div>
        ${upstream.length
          ? `<ul class="bn-draft-layers">${upstream.map((l) => `<li><b>${escapeHtml(l.name || EM)}</b>${l.physical_constraint ? ` \u2014 ${escapeHtml(l.physical_constraint)}` : ""}</li>`).join("")}</ul>`
          : `<div class="bn-muted">${EM}</div>`}

        <div class="bn-subhead">Demand trace \u2014 anchors (${anchors.length}, unranked)</div>
        ${anchors.length ? `<ul class="bn-draft-stocks">${listStocks(anchors, false)}</ul>` : `<div class="bn-muted">${EM}</div>`}

        <div class="bn-subhead">Underdogs (${underdogs.length}, ranked)</div>
        ${underdogs.length ? `<ul class="bn-draft-stocks">${listStocks(underdogs, true)}</ul>` : `<div class="bn-muted">${EM}</div>`}

        ${researchHtml}

        <div class="bn-subhead">Provenance</div>
        <div class="bn-prov">
          <div class="kv"><span class="k">Model</span><span>${escapeHtml(prov.model || EM)}</span></div>
          <div class="kv"><span class="k">Skill snapshot</span><span title="${escapeHtml(prov.skill_snapshot || "")}">${escapeHtml(shortHash(prov.skill_snapshot))}</span></div>
          <div class="kv"><span class="k">Prompt hash</span><span title="${escapeHtml(prov.prompt_hash || "")}">${escapeHtml(shortHash(prov.prompt_hash))}</span></div>
          <div class="kv"><span class="k">Run</span><span>${prov.run_ts ? escapeHtml(fmtTimestampET(prov.run_ts)) + " ET" : EM}</span></div>
        </div>
      </div>
      <label class="bn-field">
        <span>Apply to</span>
        <select data-field="apply-target">${targetOptions}</select>
      </label>
      <div class="bn-panel-actions">
        <button type="button" class="mini bn-primary" data-bn-action="apply-draft" data-job-id="${escapeHtml(j.id)}">Apply draft</button>
        <button type="button" class="mini" data-bn-action="dismiss-job">Discard</button>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </div>`;
}

// ---- Editor ------------------------------------------------------------------
// A structured form over one topic. System-owned fields (metrics, provenance)
// are preserved from the stored topic verbatim and are not editable here.

// Editor group key for a card kind. The UI names the kinds "anchor" and
// "underdog"; the stored payload keys them "anchor" and "underdogs".
function groupKey(kind) {
  return kind === "underdog" ? "underdogs" : "anchor";
}

function blankStock(role, tier) {
  return {
    ticker: "", name: "", stance: "", why_chokepoint: "",
    layer: "", role, tier, evidence: [], catalyst: "", catalyst_window: "",
    invalidation: [], dilution_atm: null, customer_concentration: null,
    gaap_margin: null, financing_quality: null,
    metrics: { market_cap: null, roc_40d: null, move_1y: null, forward_pe: null, revenue_growth: null, as_of: null },
    provenance: { model: "", skill_snapshot: "", prompt_hash: "", run_ts: "" },
  };
}

function cloneTopic(raw) {
  const t = JSON.parse(JSON.stringify(raw || {}));
  if (!Array.isArray(t.upstream)) t.upstream = [];
  const d = t.downstream && typeof t.downstream === "object" ? t.downstream : {};
  t.downstream = {
    anchor: Array.isArray(d.anchor) ? d.anchor : [],
    underdogs: Array.isArray(d.underdogs) ? d.underdogs : [],
  };
  return t;
}

function layerFieldsHtml(layer, i) {
  return `
    <div class="bn-ed-layer" data-layer-index="${i}">
      <div class="bn-ed-layer-top">
        <input type="text" data-field="name" value="${escapeHtml(layer.name || "")}" placeholder="Layer name" />
        <button type="button" class="mini bn-danger-ghost" data-bn-action="remove-layer" data-layer-index="${i}" aria-label="Remove layer">Remove</button>
      </div>
      <label class="bn-field"><span>Physical constraint</span><input type="text" data-field="physical_constraint" value="${escapeHtml(layer.physical_constraint || "")}" /></label>
      <label class="bn-field"><span>What to watch</span><input type="text" data-field="what_to_watch" value="${escapeHtml(layer.what_to_watch || "")}" /></label>
      <label class="bn-field"><span>Stocks (comma separated tickers)</span><input type="text" data-field="stocks" value="${escapeHtml((layer.stocks || []).join(", "))}" /></label>
    </div>`;
}

function stockFieldsHtml(card, kind, i) {
  const evRows = (card.evidence || []).map((ev, j) => `
      <div class="bn-ed-ev" data-ev-index="${j}">
        <input type="text" data-field="ev_claim" value="${escapeHtml(ev.claim || "")}" placeholder="Claim" />
        <input type="text" data-field="ev_source" value="${escapeHtml(ev.source || "")}" placeholder="Source name" />
        <input type="text" data-field="ev_url" value="${escapeHtml(ev.source_url || "")}" placeholder="Source URL" />
        <select data-field="ev_tier">
          ${Object.entries(EVIDENCE_LABELS).map(([k, label]) => `<option value="${k}"${(ev.tier || "social") === k ? " selected" : ""}>${escapeHtml(label)}</option>`).join("")}
        </select>
        <button type="button" class="mini bn-danger-ghost" data-bn-action="remove-evidence" data-kind="${kind}" data-stock-index="${i}" data-ev-index="${j}" aria-label="Remove evidence">\u2715</button>
      </div>`).join("");
  const flagSelects = CHECKLIST_FLAGS.map(([k, label]) => {
    const v = card[k];
    return `<label class="bn-ed-flag"><span>${escapeHtml(label)}</span>
        <select data-field="flag_${k}">
          <option value=""${v == null ? " selected" : ""}>Not assessed</option>
          <option value="true"${v === true ? " selected" : ""}>Yes</option>
          <option value="false"${v === false ? " selected" : ""}>No</option>
        </select></label>`;
  }).join("");
  return `
    <div class="bn-ed-stock" data-kind="${kind}" data-stock-index="${i}">
      <div class="bn-ed-stock-top">
        <input type="text" data-field="ticker" value="${escapeHtml(card.ticker || "")}" placeholder="Ticker" class="bn-ed-ticker" />
        <input type="text" data-field="name" value="${escapeHtml(card.name || "")}" placeholder="Company name" />
        <button type="button" class="mini bn-danger-ghost" data-bn-action="remove-stock" data-kind="${kind}" data-stock-index="${i}" aria-label="Remove stock">Remove</button>
      </div>
      <div class="bn-ed-grid">
        <label class="bn-field"><span>Stance</span><input type="text" data-field="stance" value="${escapeHtml(card.stance || "")}" /></label>
        <label class="bn-field"><span>Layer</span><input type="text" data-field="layer" value="${escapeHtml(card.layer || "")}" /></label>
        <label class="bn-field"><span>Catalyst</span><input type="text" data-field="catalyst" value="${escapeHtml(card.catalyst || "")}" /></label>
        <label class="bn-field"><span>Catalyst window</span><input type="text" data-field="catalyst_window" value="${escapeHtml(card.catalyst_window || "")}" /></label>
      </div>
      <label class="bn-field"><span>Why it is a chokepoint</span><textarea data-field="why_chokepoint" rows="2">${escapeHtml(card.why_chokepoint || "")}</textarea></label>
      <label class="bn-field"><span>Invalidation (one per line)</span><textarea data-field="invalidation" rows="2">${escapeHtml((card.invalidation || []).join("\n"))}</textarea></label>
      <div class="bn-ed-flags">${flagSelects}</div>
      <div class="bn-ed-ev-head"><span>Evidence</span>
        <button type="button" class="mini" data-bn-action="add-evidence" data-kind="${kind}" data-stock-index="${i}">+ Evidence</button>
      </div>
      ${evRows || `<div class="bn-muted">${EM}</div>`}
    </div>`;
}

function renderEditor(topic) {
  const anchors = topic.downstream.anchor || [];
  const underdogs = topic.downstream.underdogs || [];
  return `
    <form class="bn-editor" data-bn-form="edit-topic" data-topic-id="${escapeHtml(topic.id)}">
      <div class="bn-panel-title">Edit topic</div>
      <div class="bn-ed-grid">
        <label class="bn-field"><span>Name</span><input type="text" data-field="name" value="${escapeHtml(topic.name || "")}" /></label>
        <label class="bn-field"><span>Underdog ceiling ($, accepts 3B / 500M)</span><input type="text" data-field="underdog_ceiling" value="${escapeHtml(formatCeilingInput(topic.underdog_ceiling))}" /></label>
      </div>

      <div class="bn-ed-section">
        <div class="bn-ed-section-head"><span>Upstream layers</span>
          <button type="button" class="mini" data-bn-action="add-layer">+ Layer</button>
        </div>
        ${(topic.upstream || []).map(layerFieldsHtml).join("") || `<div class="bn-muted">${EM}</div>`}
      </div>

      <div class="bn-ed-section">
        <div class="bn-ed-section-head"><span>Downstream — anchors (unranked)</span>
          <button type="button" class="mini" data-bn-action="add-stock" data-kind="anchor">+ Anchor</button>
        </div>
        ${anchors.map((c, i) => stockFieldsHtml(c, "anchor", i)).join("") || `<div class="bn-muted">${EM}</div>`}
      </div>

      <div class="bn-ed-section">
        <div class="bn-ed-section-head"><span>Downstream — underdogs (ranked)</span>
          <button type="button" class="mini" data-bn-action="add-stock" data-kind="underdog">+ Underdog</button>
        </div>
        ${underdogs.map((c, i) => stockFieldsHtml(c, "underdog", i)).join("") || `<div class="bn-muted">${EM}</div>`}
      </div>

      <p class="bn-panel-hint">Metrics and provenance are fetched and stamped by the system; they are preserved but not editable here.</p>
      <div class="bn-panel-actions">
        <button type="submit" class="mini bn-primary">Save topic</button>
        <button type="button" class="mini" data-bn-action="cancel-edit">Cancel</button>
      </div>
      <div class="bn-panel-msg" data-bn-msg></div>
    </form>`;
}

// ---- Editor read/sync --------------------------------------------------------

function readField(root, field) {
  const el = root.querySelector(`[data-field="${field}"]`);
  return el ? el.value : "";
}

function syncEditEditor() {
  const form = document.querySelector(".bn-editor");
  if (!form || !editDraft) return;
  editDraft.name = readField(form, "name").trim();
  const parsedCeiling = parseCeiling(readField(form, "underdog_ceiling"));
  if (parsedCeiling != null) editDraft.underdog_ceiling = parsedCeiling;

  // Scope by the row container class, not the index attribute — the remove
  // buttons carry the same data-index attributes and would otherwise be read
  // back as extra rows.
  editDraft.upstream = [...form.querySelectorAll(".bn-ed-layer")].map((el) => ({
    name: readField(el, "name").trim(),
    physical_constraint: readField(el, "physical_constraint").trim(),
    what_to_watch: readField(el, "what_to_watch").trim(),
    stocks: readField(el, "stocks").split(",").map((s) => s.trim()).filter(Boolean),
  }));

  for (const kind of ["anchor", "underdog"]) {
    const key = groupKey(kind);
    const cards = [...form.querySelectorAll(`.bn-ed-stock[data-kind="${kind}"]`)].map((el, i) => {
      const prev = editDraft.downstream[key][i] || blankStock("downstream", kind);
      const card = { ...prev };
      card.ticker = readField(el, "ticker").trim();
      card.name = readField(el, "name").trim();
      card.stance = readField(el, "stance").trim();
      card.layer = readField(el, "layer").trim();
      card.catalyst = readField(el, "catalyst").trim();
      card.catalyst_window = readField(el, "catalyst_window").trim();
      card.why_chokepoint = el.querySelector('[data-field="why_chokepoint"]').value.trim();
      card.invalidation = el.querySelector('[data-field="invalidation"]').value
        .split("\n").map((s) => s.trim()).filter(Boolean);
      for (const [flag] of CHECKLIST_FLAGS) {
        const raw = readField(el, `flag_${flag}`);
        card[flag] = raw === "" ? null : raw === "true";
      }
      card.evidence = [...el.querySelectorAll(".bn-ed-ev")].map((evEl) => ({
        claim: readField(evEl, "ev_claim").trim(),
        source: readField(evEl, "ev_source").trim(),
        source_url: readField(evEl, "ev_url").trim(),
        tier: readField(evEl, "ev_tier") || "social",
      })).filter((ev) => ev.claim || ev.source);
      return card;
    });
    editDraft.downstream[key] = cards;
  }
}

// ---- Rendering entry ---------------------------------------------------------

// Coverage badge in the card header, derived from THIS section's render payload
// alone. Same visual contract as applyCoverageBadge in cards.js (identical
// `pill neutral cov-badge` class, inline size, `n/m` text, removal when the
// section is complete or empty) — but the count comes from the same
// `bottleneck.topics` the body renders, never from the dashboard's coverage
// map, which refreshes on its own schedule and would disagree with the body.
//
// Definition mirrors the backend's (app/service.py `_coverage_counts`):
// `ok` = upstream layers carrying a momentum reading (roc_40d_pct not null),
// `total` = every upstream layer across every topic. A structural completeness
// count, not a financial figure.
function syncCoverageBadge(topics) {
  const card = document.querySelector('[data-card="bottleneck"]');
  const head = card ? card.querySelector("h2") : null;
  if (!head) return;
  let ok = 0;
  let total = 0;
  for (const topic of topics || []) {
    for (const layer of (topic.upstream || [])) {
      total += 1;
      if (layer && layer.roc_40d_pct != null) ok += 1;
    }
  }
  const badge = head.querySelector(".cov-badge");
  if (total === 0 || ok >= total) {
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
  el.textContent = `${ok}/${total}`;
  el.title = `${ok} of ${total} upstream layers have momentum`;
}

function render() {
  const el = $("#bottleneckBody");
  if (!el) return;
  if (!payload) {
    el.innerHTML = `<div class="bn-loading">Loading\u2026</div>`;
    syncCoverageBadge([]);
    return;
  }
  el.innerHTML = [
    renderHead(),
    renderNotice(),
    renderPanels(),
    renderTopics(),
    renderFooter(),
  ].join("");
  syncCoverageBadge((payload.bottleneck || {}).topics || []);
}

function renderFooter() {
  const bn = payload.bottleneck || {};
  const topics = bn.topics || [];
  if (!topics.length) return "";
  return `<div class="bn-section-foot">
      <span class="bn-asof-inline">Topic momentum ${escapeHtml(asOfTitle(bn.as_of))}</span>
      <span class="bn-muted">${escapeHtml(bn.note || "")}</span>
    </div>`;
}

export async function renderBottleneckSection() {
  const token = ++renderToken;
  const el = $("#bottleneckBody");
  if (el && !payload) el.innerHTML = `<div class="bn-loading">Loading\u2026</div>`;
  let next;
  try {
    next = await API.fetchBottleneckTopics();
  } catch (e) {
    if (token !== renderToken) return;
    if (el) el.innerHTML = `<div class="bn-msg error" role="alert">Failed to load bottleneck topics: ${escapeHtml(e.message)}</div>`;
    // Coverage is unknown when the section payload failed to load — don't leave
    // a stale badge describing a body that is no longer shown.
    syncCoverageBadge([]);
    return;
  }
  if (token !== renderToken) return;
  payload = next;
  render();
}

// ---- Job polling -------------------------------------------------------------

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

function applyJobUpdate(j) {
  job = j;
  if (TERMINAL_STATUSES.has(j.status)) stopPolling();
  render();
}

async function pollJob(id) {
  try {
    const j = await API.fetchBottleneckJob(id);
    applyJobUpdate(j);
  } catch (e) {
    stopPolling();
    notice = { tone: "error", text: `Could not read generation job ${id}: ${e.message}` };
    render();
  }
}

function startPolling(id) {
  stopPolling();
  pollJob(id); // immediate first poll, then steady interval
  pollTimer = setInterval(() => pollJob(id), POLL_MS);
}

// ---- Init / delegation -------------------------------------------------------

async function refreshPayload() {
  try {
    payload = await API.fetchBottleneckTopics();
  } catch (e) {
    notice = { tone: "error", text: `Refresh failed: ${e.message}` };
  }
  render();
}

async function recoverJobState() {
  try {
    const jobs = await API.fetchBottleneckJobs();
    const active = jobs.find((j) => j.status === "queued" || j.status === "running");
    if (active) {
      startPolling(active.id);
      applyJobUpdate(active);
      return;
    }
    const draft = jobs.find((j) => j.status === "succeeded" && j.draft);
    if (draft) { job = draft; render(); }
  } catch (e) {
    // The section still renders; job recovery is best-effort.
  }
}

async function loadSkillStatus() {
  try {
    skillInfo = await API.fetchBottleneckSkillStatus();
    render();
  } catch (e) { /* status line stays "unavailable" */ }
}

function setPanelMsg(text, tone = "error") {
  const box = document.querySelector(".bn-panel [data-bn-msg], .bn-editor [data-bn-msg]");
  if (box) { box.textContent = text; box.className = `bn-panel-msg ${tone}`; }
}

function openPanel(kind, extra = {}) {
  notice = null;
  panel = { kind, ...extra };
  if (kind === "edit") {
    const raw = (payload.topics || []).find((t) => t.id === extra.topicId);
    editDraft = raw ? cloneTopic(raw) : null;
    if (editDraft) openTopics.add(extra.topicId);
  }
  render();
}

async function submitNewTopic(form) {
  const name = readField(form, "name").trim();
  if (!name) { setPanelMsg("A topic name is required."); return; }
  try {
    const created = await API.createBottleneckTopic(name);
    panel = null;
    openTopics.add(created.id);
    await refreshPayload();
    openPanel("edit", { topicId: created.id });
  } catch (e) {
    setPanelMsg(e.message);
  }
}

async function submitEditTopic(form) {
  if (!editDraft) return;
  syncEditEditor();
  if (!editDraft.name) { setPanelMsg("A topic name is required."); return; }
  const invalid = [...editDraft.downstream.anchor, ...editDraft.downstream.underdogs]
    .filter((c) => !c.ticker);
  if (invalid.length) { setPanelMsg("Every stock card needs a ticker."); return; }
  const patch = {
    name: editDraft.name,
    underdog_ceiling: editDraft.underdog_ceiling,
    upstream: editDraft.upstream,
    downstream: editDraft.downstream,
  };
  try {
    await API.updateBottleneckTopic(editDraft.id, patch);
    panel = null;
    editDraft = null;
    await refreshPayload();
  } catch (e) {
    setPanelMsg(e.message);
  }
}

async function submitGenerate(form) {
  const theme = readField(form, "theme").trim();
  const target = readField(form, "topic_id") || "__new__";
  genTarget = target;
  if (!theme) { setPanelMsg("A theme is required."); return; }
  try {
    const started = await API.generateBottleneckTopic({
      theme,
      topic_id: target === "__new__" ? null : target,
    });
    panel = null;
    startPolling(started.id);
    applyJobUpdate(started);
  } catch (e) {
    // 409: the detail is the exact user-facing message — show it verbatim.
    setPanelMsg(e.message);
  }
}

async function submitImport(form) {
  const text = readField(form, "doc").trim();
  if (!text) { setPanelMsg("Paste a topics document first."); return; }
  let doc;
  try {
    doc = JSON.parse(text);
  } catch (e) {
    setPanelMsg(`That is not valid JSON: ${e.message}`);
    return;
  }
  try {
    const res = await API.importBottleneckTopics(doc);
    const errors = Array.isArray(res.errors) ? res.errors : [];
    panel = null;
    notice = errors.length
      ? { tone: "error", text: `Imported ${res.imported} topic(s). ${errors.length} were skipped: ${errors.join("; ")}` }
      : { tone: "ok", text: `Imported ${res.imported} topic(s).` };
    await refreshPayload();
  } catch (e) {
    setPanelMsg(e.message);
  }
}

async function applyDraft(jobId) {
  const select = document.querySelector('[data-field="apply-target"]');
  let targetId = select ? select.value : "__new__";
  try {
    if (targetId === "__new__") {
      const created = await API.createBottleneckTopic((job.draft.topic && job.draft.topic.name) || job.theme || "New topic");
      targetId = created.id;
    }
    await API.applyBottleneckJob(jobId, {
      topic_id: targetId,
      summary: `Applied agent draft for theme: ${job.theme || ""}`,
    });
    job = null;
    stopPolling();
    openTopics.add(targetId);
    await refreshPayload();
  } catch (e) {
    setPanelMsg(e.message);
  }
}

async function doRefreshSkill() {
  skillBusy = true;
  skillResult = null;
  render();
  try {
    skillResult = await API.refreshBottleneckSkill();
  } catch (e) {
    skillResult = { ok: false, output_tail: e.message };
  }
  skillBusy = false;
  await loadSkillStatus();
  render();
}

function onEditorStructuralAction(action, target) {
  syncEditEditor();
  if (action === "add-layer") {
    editDraft.upstream.push({ name: "", physical_constraint: "", what_to_watch: "", stocks: [] });
  } else if (action === "remove-layer") {
    editDraft.upstream.splice(Number(target.dataset.layerIndex), 1);
  } else if (action === "add-stock") {
    const kind = target.dataset.kind;
    editDraft.downstream[groupKey(kind)].push(blankStock("downstream", kind));
  } else if (action === "remove-stock") {
    const kind = target.dataset.kind;
    editDraft.downstream[groupKey(kind)].splice(Number(target.dataset.stockIndex), 1);
  } else if (action === "add-evidence") {
    const kind = target.dataset.kind;
    const card = editDraft.downstream[groupKey(kind)][Number(target.dataset.stockIndex)];
    if (card) card.evidence.push({ claim: "", source: "", source_url: "", tier: "primary-filing" });
  } else if (action === "remove-evidence") {
    const kind = target.dataset.kind;
    const card = editDraft.downstream[groupKey(kind)][Number(target.dataset.stockIndex)];
    if (card) card.evidence.splice(Number(target.dataset.evIndex), 1);
  }
  render();
}

function onClick(e) {
  const target = e.target.closest("[data-bn-action]");
  if (!target) return;
  const action = target.dataset.bnAction;
  switch (action) {
    case "toggle-topic": {
      const id = target.dataset.topicId;
      if (openTopics.has(id)) openTopics.delete(id); else openTopics.add(id);
      render();
      return;
    }
    case "toggle-stock": {
      const key = target.dataset.stockKey;
      if (openStocks.has(key)) openStocks.delete(key); else openStocks.add(key);
      render();
      return;
    }
    case "new-topic": openPanel("new"); return;
    case "generate": openPanel("generate"); return;
    case "generate-for": genTarget = target.dataset.topicId; openPanel("generate"); return;
    case "import": openPanel("import"); return;
    case "export": {
      API.exportBottleneckTopics().then((doc) => {
        exportText = JSON.stringify(doc, null, 2);
        openPanel("export");
      }).catch((err) => {
        notice = { tone: "error", text: `Export failed: ${err.message}` };
        render();
      });
      return;
    }
    case "close-panel": panel = null; render(); return;
    case "copy-export": {
      if (navigator.clipboard) navigator.clipboard.writeText(exportText).then(
        () => setPanelMsg("Copied to clipboard.", "ok"),
        () => setPanelMsg("Copy failed — select the text and copy manually.")
      );
      return;
    }
    case "download-export": {
      const blob = new Blob([exportText], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "bottleneck-topics.json";
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    case "edit-topic": openPanel("edit", { topicId: target.dataset.topicId }); return;
    case "cancel-edit": panel = null; editDraft = null; render(); return;
    case "delete-topic": panel = { kind: "delete", topicId: target.dataset.topicId }; render(); return;
    case "cancel-delete": panel = null; render(); return;
    case "confirm-delete": {
      const id = target.dataset.topicId;
      API.deleteBottleneckTopic(id).then(async () => {
        openTopics.delete(id);
        panel = null;
        notice = { tone: "ok", text: "Topic deleted." };
        await refreshPayload();
      }).catch((err) => { notice = { tone: "error", text: `Delete failed: ${err.message}` }; render(); });
      return;
    }
    case "cancel-job": {
      API.cancelBottleneckJob(target.dataset.jobId).then(applyJobUpdate)
        .catch((err) => { notice = { tone: "error", text: `Cancel failed: ${err.message}` }; render(); });
      return;
    }
    case "dismiss-job": job = null; stopPolling(); render(); return;
    case "apply-draft": applyDraft(target.dataset.jobId); return;
    case "refresh-skill": doRefreshSkill(); return;
    case "add-layer":
    case "remove-layer":
    case "add-stock":
    case "remove-stock":
    case "add-evidence":
    case "remove-evidence":
      if (editDraft) onEditorStructuralAction(action, target);
      return;
    default: return;
  }
}

function onSubmit(e) {
  const form = e.target.closest("[data-bn-form]");
  if (!form) return;
  e.preventDefault();
  const kind = form.dataset.bnForm;
  if (kind === "new-topic") submitNewTopic(form);
  else if (kind === "edit-topic") submitEditTopic(form);
  else if (kind === "generate") submitGenerate(form);
  else if (kind === "import") submitImport(form);
}

let _bound = false;

export function initBottleneck() {
  const body = $("#bottleneckBody");
  if (!body || _bound) return;
  _bound = true;
  body.addEventListener("click", onClick);
  body.addEventListener("submit", onSubmit);
  recoverJobState();
  loadSkillStatus();
}
