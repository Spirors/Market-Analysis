// Auto-shutdown the local server when the dashboard tab is truly closed.
//
// The desktop launcher (run.py --open-browser) starts a single-user server
// in a cmd window that the user must otherwise close by hand. To avoid
// that, the dashboard fires navigator.sendBeacon('/api/shutdown') on
// pagehide (the most reliable unload signal) and on beforeunload as a
// backup. The beacon returns immediately and survives page navigation,
// so the server usually exits within ~300ms of the tab being closed.
//
// Reload survival: the very next page that loads (F5, link nav, bfcache
// restore) fires ``pageshow`` and we immediately send
// navigator.sendBeacon('/api/cancel-shutdown') to abort the pending exit.
// So F5 refreshing the dashboard does NOT kill the server — only a real
// tab/window close (no follow-up page) reaches os._exit.
//
// We ignore bfcache restore (event.persisted === true) on pagehide so
// flipping to a cached back/forward page does not even schedule a
// shutdown in the first place. On pageshow we still cancel any pending
// shutdown (including one scheduled by a preceding beforeunload on the
// outgoing page) — the server is a single-user resource and a stray
// timer surviving across reloads would be worse than a wasted cancel.
//
// NOTE: We intentionally do NOT listen to visibilitychange. Modern
// browsers fire that event whenever the tab is backgrounded (switching
// to another tab, focusing another window, OS focus changes), and a
// hidden-timeout-based shutdown would kill the server while the user is
// still using the app — every quick "let me check email" tab switch
// would tear down the process.
//
// This script must remain tiny and free of DOM dependencies so it can be
// inlined or preloaded ahead of the dashboard bundle without coupling.
(function () {
  "use strict";
  const SHUTDOWN_URL = "/api/shutdown";
  const CANCEL_URL = "/api/cancel-shutdown";
  let fired = false;

  function beacon(url) {
    try {
      if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
        navigator.sendBeacon(url);
      } else if (typeof fetch === "function") {
        fetch(url, { method: "POST", keepalive: true }).catch(function () {});
      }
    } catch (_e) {
      // best-effort; if the browser blocks it, the user can close the
      // cmd window manually.
    }
  }

  function fireShutdown() {
    if (fired) return;
    fired = true;
    beacon(SHUTDOWN_URL);
  }

  function cancelShutdown() {
    fired = false;
    beacon(CANCEL_URL);
  }

  // pagehide is the canonical signal for tab close / navigation;
  // beforeunload is a fallback for browsers that swallow pagehide.
  window.addEventListener("pagehide", function (ev) {
    if (ev && ev.persisted) return; // bfcache restore — not a real close
    fireShutdown();
  });
  window.addEventListener("beforeunload", fireShutdown);

  // A NEW page has just loaded (F5 reload, post-navigation, bfcache
  // restore). Cancel any pending shutdown so the server survives reloads.
  window.addEventListener("pageshow", function (ev) {
    cancelShutdown();
  });
})();
