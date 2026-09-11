// Entrypoint: wires the static buttons, boots the layout tools and the
// timeline subsystem, then performs the initial dashboard load.

import { $ } from "./format.js";
import { registerRenderer, load, postFullRefresh } from "./api.js";
import { renderSection, initCardTooltips } from "./cards.js?v=20260905c";
import { initLayoutTools } from "./layout.js";
import { initEvents } from "./events.js";
import { initMeta } from "./meta.js";

registerRenderer(renderSection);

$("#refreshBtn").addEventListener("click", async () => {
  const btn = $("#refreshBtn");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await postFullRefresh();
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

initLayoutTools();
initCardTooltips(); // header info buttons — static chrome, safe before data
initEvents();
await initMeta(); // backend labels before first render; falls back silently
await load();

// No automatic refresh — the dashboard serves the cached payload until the
// user clicks the global Refresh button (or any per-section ↻). Pulling
// every N minutes while the tab is backgrounded was just wasted network and
// caused "stale data" surprises on return.

// ---- Refresh button hover tooltip: live "Last refresh / next refresh" ----
// The static tooltip says "Refresh"; hovering replaces it with a live-
// computed string showing dashboard age and cooldown status. Unhover
// restores the static text so screen readers always see "Refresh".
const COOLDOWN_SECONDS = { portfolio: 900, breadth_ai: 1800 };

(function wireRefreshTooltip() {
  const btn = $("#refreshBtn");
  if (!btn) return;
  const staticTitle = btn.getAttribute("title") || "Refresh";
  btn.addEventListener("mouseenter", () => {
    // Access the module-level dashboardData via the api module's getter.
    // We import it indirectly — the global `dashboardData` lives in api.js
    // but isn't exported. Instead, read from the DOM: the header #asof
    // already holds the formatted as_of timestamp.
    const asofEl = $("#asof");
    if (!asofEl) return;
    // Parse "As of YYYY-MM-DD HH:MM ET" back to a Date.  The as_of is
    // stored as an ISO string on the last fetched payload; we read it
    // from a data attribute set by the load/refresh path.
    const asOfIso = asofEl.dataset.iso;
    if (!asOfIso) return;
    const asOfMs = new Date(asOfIso).getTime();
    if (isNaN(asOfMs)) return;
    const elapsedMin = Math.max(0, Math.floor((Date.now() - asOfMs) / 60000));
    // Next refresh: max remaining cooldown across all cooldowed sections.
    // We don't have the cooldown_skip list here, so show the max possible.
    const nextMin = Math.max(
      ...Object.values(COOLDOWN_SECONDS).map((c) =>
        Math.max(0, Math.ceil((c - (Date.now() - asOfMs) / 1000) / 60))
      )
    );
    btn.title = `Refresh dashboard. Last refresh: ${elapsedMin} min ago. Next refresh available in: ${nextMin} min`;
  });
  btn.addEventListener("mouseleave", () => {
    btn.title = staticTitle;
  });
})();
