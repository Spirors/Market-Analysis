// Entrypoint: wires the static buttons, boots the layout tools and the
// timeline subsystem, then performs the initial dashboard load.

import { $ } from "./format.js";
import { registerRenderer, load, postFullRefresh } from "./api.js";
import { renderSection } from "./cards.js";
import { initLayoutTools } from "./layout.js";
import { initEvents } from "./events.js";

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
initEvents();
load();
