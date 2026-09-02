// Entrypoint: wires the static buttons, boots the layout tools and the
// timeline subsystem, then performs the initial dashboard load.

import { $ } from "./format.js";
import { registerRenderer, load, postFullRefresh } from "./api.js";
import { renderSection, initCardTooltips } from "./cards.js?v=20260901b";
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
