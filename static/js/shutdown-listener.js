// Auto-shutdown the local server when the dashboard tab closes.
//
// The desktop launcher (run.py --open-browser) starts a single-user server
// in a cmd window that the user must otherwise close by hand. To avoid
// that, the dashboard fires navigator.sendBeacon('/api/shutdown') on
// pagehide (the most reliable unload signal) and on beforeunload as a
// backup. The beacon returns immediately and survives page navigation,
// so the server usually exits within ~300ms of the tab being closed.
//
// We ignore bfcache restore (event.persisted === true) so flipping to a
// cached back/forward page does not kill the server; the listener is
// gone for good once the page is reloaded, which is fine because the
// user explicitly reloaded.
//
// This script must remain tiny and free of DOM dependencies so it can be
// inlined or preloaded ahead of the dashboard bundle without coupling.
(function () {
  "use strict";
  const URL_ = "/api/shutdown";
  let fired = false;

  function fire() {
    if (fired) return;
    fired = true;
    try {
      // sendBeacon queues a POST and returns immediately; size and method
      // are fixed by the API. Falls back to fetch with keepalive on the
      // rare browser where sendBeacon is unavailable (none we target).
      if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
        navigator.sendBeacon(URL_);
      } else if (typeof fetch === "function") {
        fetch(URL_, { method: "POST", keepalive: true }).catch(function () {});
      }
    } catch (_e) {
      // best-effort; if the browser blocks it, the user can close the
      // cmd window manually.
    }
  }

  // pagehide is the canonical signal for tab close / navigation;
  // beforeunload is a fallback for browsers that swallow pagehide.
  window.addEventListener("pagehide", function (ev) {
    if (ev && ev.persisted) return; // bfcache restore — not a real close
    fire();
  });
  window.addEventListener("beforeunload", fire);

  // Belt-and-suspenders: if the tab enters a hibernated state for a while
  // we treat it as effectively closed. The server-side /api/shutdown
  // endpoint is idempotent, so duplicate fires are harmless.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      // 3s of continuous hidden page is treated as abandonment.
      // Hidden fires are debounced to avoid killing on a quick tab switch.
      setTimeout(function () {
        if (document.visibilityState === "hidden") fire();
      }, 3000);
    }
  });
})();
