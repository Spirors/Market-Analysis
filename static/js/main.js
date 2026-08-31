// Entrypoint: wires the static buttons, boots the layout tools and the
// timeline subsystem, then performs the initial dashboard load.

import { $ } from "./format.js";
import { registerRenderer, load, postFullRefresh } from "./api.js";
import { renderSection, initCardTooltips } from "./cards.js";
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
startAutoRefresh();

// --- auto-refresh (30 min) ---

const REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes
let autoRefreshTimer = null;
let autoRefreshInFlight = false;

async function autoRefreshTick() {
  if (autoRefreshInFlight) return;
  if (document.visibilityState !== "visible") return;
  autoRefreshInFlight = true;
  try {
    await load();
  } catch (e) {
    // silent — don't disrupt the UI on background refresh errors
    console.warn("auto-refresh failed", e);
  } finally {
    autoRefreshInFlight = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh(); // clear any existing timer
  autoRefreshTimer = setInterval(autoRefreshTick, REFRESH_INTERVAL_MS);
  document.addEventListener("visibilitychange", onVisibilityChange);
}

function stopAutoRefresh() {
  if (autoRefreshTimer !== null) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  document.removeEventListener("visibilitychange", onVisibilityChange);
}

function onVisibilityChange() {
  if (document.visibilityState === "visible") {
    autoRefreshTick();
  }
}
