// Entrypoint: wires the static buttons, boots the layout tools and the
// timeline subsystem, then performs the initial dashboard load.

import { $ } from "./format.js";
import { registerRenderer, load, postFullRefresh, showAppStatus, COOLDOWN_SECONDS } from "./api.js";
import { renderSection, initCardTooltips } from "./cards.js?v=20260927h";
import { initLayoutTools } from "./layout.js";
import { initEvents } from "./events.js";
import { initBottleneck } from "./bottleneck.js?v=20260927f";
import { initMeta } from "./meta.js";
import { attachTooltip } from "./tooltip.js";

registerRenderer(renderSection);

$("#refreshBtn").addEventListener("click", async () => {
  const btn = $("#refreshBtn");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await postFullRefresh();
    await load();
  } catch (e) {
    // The refresh POST itself failed (network / non-2xx). The last good
    // payload is still on screen — a load() failure never got that far — so
    // surface a soft status in the header instead of blanking a card body.
    console.error("Refresh request failed:", e);
    showAppStatus("soft");
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh";
  }
});

// Section-refresh buttons are gone — the global Refresh is the only refresh
// affordance, wired directly above.

initLayoutTools();
initCardTooltips(); // header info buttons — static chrome, safe before data
initEvents();
initBottleneck(); // section delegation + generation-job recovery
await initMeta(); // backend labels before first render; falls back silently
await load();

// No automatic refresh — the dashboard serves the cached payload until the
// user clicks the global Refresh button. Pulling every N minutes while the tab
// was backgrounded was just wasted network and caused "stale data" surprises
// on return.

// ---- Refresh button tooltip: live "Last refresh / next refresh" ----
// The unified tooltip component recomputes the copy at open time, so the same
// freshness string shows on hover AND on keyboard focus (it also handles
// Escape and the aria-describedby wiring). No native title hack.

(function wireRefreshTooltip() {
  const btn = $("#refreshBtn");
  if (!btn) return;
  attachTooltip(btn, {
    text: () => {
      // Access the module-level dashboardData via the api module's getter.
      // We import it indirectly — the global `dashboardData` lives in api.js
      // but isn't exported. Instead, read from the DOM: the header #asof
      // already holds the formatted as_of timestamp.
      const asofEl = $("#asof");
      const asOfIso = asofEl ? asofEl.dataset.iso : null;
      if (!asOfIso) return "Refresh dashboard.";
      const asOfMs = new Date(asOfIso).getTime();
      if (isNaN(asOfMs)) return "Refresh dashboard.";
      const elapsedMin = Math.max(0, Math.floor((Date.now() - asOfMs) / 60000));
      // Next refresh: max remaining cooldown across all cooldown-gated
      // sections. We don't have the cooldown_skip list here, so this is an
      // upper bound — the actual next refresh may be sooner.
      const nextMin = Math.max(
        ...Object.values(COOLDOWN_SECONDS).map((c) =>
          Math.max(0, Math.ceil((c - (Date.now() - asOfMs) / 1000) / 60))
        )
      );
      return `Refresh dashboard. Last refresh: ${elapsedMin} min ago. Next refresh available in up to ${nextMin} min`;
    },
  });
})();
