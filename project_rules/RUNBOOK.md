# Runbook

Exact operational procedures and the launch/verify/reap checklist.
The *rule* (why these steps exist) lives in the project-rules skill
(`.opencode/skills/project-rules/SKILL.md` § "Server lifecycle"); this
file holds the *mechanics* — commands, snippet, env vars, and the
copy-pasteable turn-end checklist.

Read this in full before launching anything.

## Run commands (reference)

```
{{SERVER_COMMAND}}                  # serve at http://127.0.0.1:8000
{{SERVER_COMMAND}} --refresh        # run a full refresh once and exit
{{SERVER_COMMAND}} --news-refresh   # fast news-only ingest once and exit
{{SERVER_COMMAND}} --backfill       # seed the curated event timeline once and exit
{{SERVER_COMMAND}} --schedule-install   # install the 3 Windows scheduled tasks
{{SERVER_COMMAND}} --schedule-remove    # remove all scheduled tasks
{{SERVER_COMMAND}} --schedule-status    # check whether the scheduled tasks are installed
{{SERVER_COMMAND}} --install-shortcut   # create the desktop launch.bat + .lnk
{{SERVER_COMMAND}} --remove-shortcut    # remove the desktop launch.bat + .lnk
{{SERVER_COMMAND}} --auto-reap 60       # auto-exit 60s after the launching parent dies
                                          # (use when launching from an agent terminal;
                                          # desktop launches leave this at 0)
```

Equivalent env var (useful when the agent's CLI line is short on space):
`$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60; python run.py`

## Server lifecycle checklist (copy into the PR/turn notes)

Every agent turn that needs a running server follows this cycle, in order.
The full *rule* (why) is in the project-rules skill — this is the
*how*.

- [ ] **Step 1 — try `TestClient` first.** In-process, no port binding, no
      orphan risk. Use it for any verification that doesn't need a real
      browser:
      ```python
      from fastapi.testclient import TestClient
      from app.api import app
      r = TestClient(app).get("/api/dashboard", headers={"Host": "127.0.0.1:8000"})
      ```
      The `Host` header is required — the DNS-rebinding allowlist
      middleware rejects TestClient's default `testserver` host with a 403.
- [ ] **Step 2 — if a real server is genuinely required, launch hidden.**
      Never `Start-Process`, `nohup`, `&`, or `Invoke-Expression`. Never
      `pythonw.exe` (silent abort on console detach — see
      `project_rules/DECISIONS.md`). Use the desktop launcher
      (`launch.vbs` → `launch.bat`) or
      `wscript.exe` + VBS with `shell.Run "python args", 0, False`.
- [ ] **Step 3 — launched from an agent terminal? Add `--auto-reap 60`.**
      The watchdog in `app/lifecycle.py` polls the launching parent every
      10s and exits when the parent has been gone for 60s. Use 0 for
      desktop launches where the parent stays alive for the whole session.
- [ ] **Step 4 — reap before the turn ends (non-negotiable).**
      `Stop-Process -Id <pid> -Force` (or `taskkill /PID <pid> /F`, or
      `POST /api/shutdown`).
- [ ] **Step 5 — verify it's gone.**
      `Get-Process python` empty, `Get-Process pythonw` empty,
      `Test-NetConnection -Port 8000` returns False.
- [ ] **Step 6 — clear any leftover pid file.**
      A pid file at `data/server.pid` records the running pid,
      parent's pid, and start timestamp. `/api/shutdown` and `atexit`
      remove it cleanly; the watchdog's `os._exit` cannot run cleanup
      hooks, so an auto-reaped server may leave it behind:
      ```powershell
      Get-Content data\server.pid        # pid=<x> parent_pid=<y> started=...
      Stop-Process -Id <x> -Force        # reap the orphan
      Remove-Item data\server.pid        # clear the diagnostic record
      ```
- [ ] **Step 7 — never leave a server running "for the user to test."**
      The user runs the server themselves via the desktop launcher. An
      orchestrator-spawned server left running collides on port 8000 and
      leaves stale lockfiles.

## Scheduled tasks (3-task setup)

`app/scheduler.py` installs three Windows Task Scheduler tasks via
`python run.py --schedule-install`. They all launch via the VBS-wrapper
pattern (`wscript.exe scheduler.vbs`, `WindowStyle=0`, `False` = do not
wait) so no console window flashes when the trigger fires. See
`project_rules/DECISIONS.md` "Hidden launchers" for *why* VBS, not
pythonw.

| Task name | Trigger | Command | Log file |
|---|---|---|---|
| `MarketAnalysis-DailyRefresh` | Daily 09:00 **local** | `python run.py --refresh --logfile-prefix data\logs\refresh` | `data\logs\refresh-YYYYMMDD.log` |
| `MarketAnalysis-NewsRefresh` | Every 4 hours (00:00 / 04:00 / ... / 20:00, daily boundary + PT4H repetition) | `python run.py --news-refresh --logfile-prefix data\logs\news-refresh` | `data\logs\news-refresh-YYYYMMDD.log` |
| `MarketAnalysis-EventsCommit` | Daily 17:00 **local** | `python run.py --commit-events --logfile-prefix data\logs\events-commit` | `data\logs\events-commit-YYYYMMDD.log` |

All three pass `--logfile-prefix` so each run appends to a daily-dated
log (`<prefix>-YYYYMMDD.log`); `run.py` prunes siblings older than
`LOG_RETENTION_DAYS` (30) on startup.

All three are installed as **InteractiveToken** (no admin, no
password), which means they silently do NOT run while the user is
logged off — Windows skips the trigger entirely, and `StartWhenAvailable`
only catches up after you log back in. If refreshes must happen while
you are away from the machine, either reinstall with `schtasks /RU <user>
/RP <password>` ("run whether user is logged on or not", requires the
account password) or keep an always-on session. The `data/events.json`
events-commit task is the most likely to be silently skipped during a
long absence — check the daily-dated log if `events.json` looks stale.

`EXECUTION_TIME_LIMIT = "PT4H"` is set in `scheduler.py:71`. A full
refresh (regime detection + slow EDGAR pulls) can exceed one hour, and
being killed mid-write corrupts caches — so the limit is generous
rather than tight. This is enforced by **schtasks itself**, not by
python — see "Anti-patterns" below for why this is distinct from
`--auto-reap`.

**Recovery — "stuck scheduled refresh":** if the 9 AM daily refresh
appears to have hung, check in this order:
1. The latest `data\logs\refresh-YYYYMMDD.log` (last few lines for an
   exception or traceback).
2. `Get-Process python` — if a refresh task is mid-run, there will be a
   `python.exe` whose parent is the orphan-reparented `services.exe` /
   `svchost.exe` (the VBS's `False` flag detaches it immediately).
3. `data\refresh.lock` — if a previous refresh died uncleanly, the
   cross-process lockfile stays held. `app/lockfile.py` breaks it two
   ways: age-based (older than `STALE_LOCK_SECONDS` = 10 min) and
   PID-based (`GetExitCodeProcess` via ctypes — if the holding PID is
   no longer alive, the lock is broken immediately regardless of age).
4. `python run.py --schedule-status` — confirms whether all 3 tasks are
   installed and reports each one's state.

## Anti-patterns — launch paths that bypass the runtime backstop

The stuck-process fix in Phase 0 (see `project_rules/DECISIONS.md`
"Stuck process on test launch") is a **runtime backstop in the launched
python itself** — `app/lifecycle.py`'s auto-reap watchdog polls the
launching parent PID and `os._exit(0)`s when it's gone. The watchdog is
opt-in via `--auto-reap <seconds>` (or
`$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=<s>`); **it defaults to
0 = disabled.** The two well-known "right" launch paths set it
correctly; the wrong paths below don't, and that is the regression that
re-introduces "stuck python on port 8000":

- **WRONG:** `python run.py --refresh` from a notebook / PowerShell
  ISE / VS Code interactive window. No `--auto-reap`, no VBS wrapper,
  no `/api/shutdown` on exit. If the notebook kernel dies or the ISE
  is force-killed, the python child stays bound to port 8000.
  Use `--auto-reap 60` if you really need this; the watchdog turns
  "agent forgot to reap" into "agent reaps itself".
- **WRONG:** `Start-Process python ...`, `nohup python ...`, `python ... &`,
  `Invoke-Expression "python ..."`. Same root cause: the launcher
  exits immediately, leaving a python child with no trackable parent,
  and the watchdog has no parent to watch.
- **WRONG:** `pythonw.exe run.py ...` from any context. pythonw is a
  GUI-subsystem app that detaches from the parent console on startup;
  when that detach leaves OS console-handle state inconsistent,
  pythonw silently aborts before binding. This is the original
  Phase 0 root cause — see `DECISIONS.md` "Hidden launchers".
- **RIGHT (desktop):** the `.lnk` → `wscript.exe //nologo launch.vbs`
  → `python run.py --open-browser` chain installed by
  `--install-shortcut`. Parent stays alive across the session;
  `/api/shutdown` is the documented exit.
- **RIGHT (agent terminal):** `python run.py --auto-reap 60 ...` (or
  the env-var form). Watchdog kills the orphan 60 s after the agent's
  shell exits.
- **RIGHT (scheduled tasks):** `wscript.exe scheduler.vbs ...` from
  Task Scheduler. The watchdog is intentionally disabled here
  (auto-reap defaults to 0) because `EXECUTION_TIME_LIMIT = "PT4H"` is
  enforced by **schtasks** itself — the watchdog and the schtasks
  hard-kill are two different layers of defense and do not overlap.
  Do NOT pass `--auto-reap <n>` to a scheduled refresh — the
  watchdog's "parent gone" trigger would fire within `n` seconds of
  `wscript.exe` exiting (which it does immediately because
  `scheduler.vbs` runs with `False` = do not wait), killing the
  refresh mid-run.

## Commit conventions

- `data/events.json` changes are batched and committed once daily by the
  `MarketAnalysis-EventsCommit` scheduled task (17:00 local). Do not
  commit `events.json` from interactive sessions — let the scheduler
  own it.
- Code, config, `AGENTS.md`, and `project_rules/` changes are committed
  immediately after the change is verified (tests pass, no obvious
  regressions). Use a scope-prefixed message: `feat(scope): ...`,
  `fix(scope): ...`, `chore(scope): ...`, `docs(scope): ...`.
- Never amend an existing commit unless explicitly asked.
- Full commit-hygiene rule: project-rules skill § "Commit hygiene".

## Future browser automation against third-party sites

Playwright is currently used only for frontend tests
(`tests/frontend/playwright.config.mjs`, `tests/frontend/*.spec.mjs`)
against `http://127.0.0.1:8000` with no anti-bot middleware — **no
stealth configuration is needed for those.** The app itself scrapes no
JavaScript-rendered pages today; data sources are yfinance, RSS, and
SEC EDGAR via `curl_cffi` with browser-TLS impersonation
(`app/thirteenf.py`).

If you ever add browser automation that hits a real third-party site
(this is the *only* case "stealth" means anti-bot evasion on this
project — see `AGENTS.md`'s definition), follow this pattern to avoid
bot detection:

- `playwright.chromium.launch(headless=True, channel="chrome")` rather
  than the bundled Chromium when possible — production Chrome's TLS
  fingerprint is less bot-flagged.
- Pass `--disable-blink-features=AutomationControlled` via
  `chromium.launch(args=[...])` to suppress the `navigator.webdriver`
  flag.
- Override the user agent to a real recent Chrome/Firefox string
  (rotating per session if scraping multiple sites).
- Realistic viewport (`{width: 1280, height: 800}` or
  `{width: 1920, height: 1080}`), realistic locale (`en-US`) and
  timezone (`America/New_York`).
- Disable the webdriver flag via `addInitScript`:
  ```js
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  ```
- Avoid detection tells: don't navigate faster than a human could click;
  add small randomized delays between actions; respect `robots.txt` and
  rate-limit headers; never reuse the same session across unrelated
  sites.
