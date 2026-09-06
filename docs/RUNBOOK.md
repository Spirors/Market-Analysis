# Runbook

Exact operational procedures. This file exists so the server-lifecycle rule
is a checklist an agent follows, not a paragraph an agent has to remember
mid-document. Read this in full before launching anything.

## Run commands (reference)

```
python -m pip install -r requirements.txt
python run.py                      # serve at http://127.0.0.1:8000
python run.py --refresh            # run a full refresh once and exit
python run.py --news-refresh       # fast news-only ingest once and exit
python run.py --backfill           # seed the curated event timeline once and exit
python run.py --schedule-install   # install the 3 Windows scheduled tasks
python run.py --schedule-remove    # remove all scheduled tasks
python run.py --schedule-status    # check whether the scheduled tasks are installed
python run.py --install-shortcut   # create the desktop launch.bat + .lnk
python run.py --remove-shortcut    # remove the desktop launch.bat + .lnk
```

## Local server lifecycle — launch / verify / shutdown

Every agent turn that needs a running server follows this cycle, in order:

### Step 1 — Do you actually need a real server?

Default to **no**. Use FastAPI's `TestClient` for in-process verification —
no port binding, no orphan risk:

```python
from fastapi.testclient import TestClient
from app.api import app
r = TestClient(app).get("/api/dashboard", headers={"Host": "127.0.0.1:8000"})
```

The `Host` header is required — the DNS-rebinding allowlist middleware
(`config.ALLOWED_HOSTS`) rejects TestClient's default `testserver` host with
a 403.

Only proceed to Step 2 if in-process verification is genuinely insufficient
(e.g. Playwright against the live rendered UI, an end-to-end smoke test of
the desktop launcher itself).

### Step 2 — If a real server is required, launch it hidden

**Never** use `Start-Process`, `nohup`, `&`, or `Invoke-Expression`-based
detached launches — these have repeatedly hung the orchestrator and leaked
zombie Python processes on port 8000. Use the desktop launcher or
`python run.py` directly in a way you can track the PID of, and see
`docs/DECISIONS.md` for why `pythonw.exe` specifically is banned (silent
abort on console detach) in favor of the `wscript.exe` + VBS `SW_HIDE`
pattern.

### Step 3 — Reap before the turn ends (non-negotiable)

Any server started during the turn — via `python run.py`,
`python run.py --refresh`, `python run.py --news-refresh`, or any other
invocation that spawns a python/pythonw process — must be killed before you
end the turn:

```powershell
Stop-Process -Id <pid> -Force
# or
taskkill /PID <pid> /F
# or, if the app supports it:
# POST/GET /api/shutdown
```

Then **verify** it's actually gone before ending the turn:

```powershell
Get-Process python        # should return nothing
Get-Process pythonw       # should return nothing
Test-NetConnection -Port 8000   # should return False
```

### Step 4 — Never "leave it running for the user to test"

The user runs the server themselves via the desktop launcher
(`launch.vbs` → `launch.bat`). An orchestrator-spawned server left running
collides on port 8000 with the user's own launch and leaves stale lockfiles
that force the user to abort interactively. This is the single most common
cause of the stuck-process complaint — check this step first when
diagnosing a recurrence.

## Checklist (copy this into the PR/turn notes when you launch anything)

- [ ] Confirmed `TestClient` wasn't sufficient before launching a real server
- [ ] Used the hidden-launch pattern (VBS/`SW_HIDE`), not `pythonw.exe` or
      `Start-Process`
- [ ] Process killed before ending the turn
- [ ] `Get-Process python` / `Get-Process pythonw` confirmed empty
- [ ] `Test-NetConnection -Port 8000` confirmed `False`
- [ ] No stale lockfile left in `data/` that would block the user's next
      launch

## Commit conventions

- `data/events.json` changes are batched and committed once daily by the
  `MarketAnalysis-EventsCommit` scheduled task (17:00 local). Do not commit
  `events.json` from interactive sessions — let the scheduler own it.
- Code, config, `AGENTS.md`, and `docs/` changes are committed immediately
  after the change is verified (tests pass, no obvious regressions). Use a
  scope-prefixed message: `feat(scope): ...`, `fix(scope): ...`,
  `chore(scope): ...`, `docs(scope): ...`.
- Never amend an existing commit unless explicitly asked.

## If you ever add browser automation against third-party sites

Playwright is currently used only for frontend tests
(`tests/frontend/playwright.config.mjs`, `tests/frontend/*.spec.mjs`)
against `http://127.0.0.1:8000` with no anti-bot middleware — **no stealth
configuration is needed for those.** The app itself scrapes no
JavaScript-rendered pages today; data sources are yfinance, RSS, and SEC
EDGAR via `curl_cffi` with browser-TLS impersonation (`app/thirteenf.py`).

If you ever add browser automation that hits a real third-party site
(this is the *only* case "stealth" means anti-bot evasion on this
project — see `AGENTS.md`'s definition), follow this pattern to avoid bot
detection:

- Use `playwright.chromium.launch(headless=True, channel="chrome")` rather
  than the bundled Chromium when possible — production Chrome's TLS
  fingerprint is less bot-flagged.
- Pass `--disable-blink-features=AutomationControlled` via
  `chromium.launch(args=[...])` to suppress the `navigator.webdriver` flag.
- Override the user agent to a real recent Chrome/Firefox string (rotating
  per session if scraping multiple sites).
- Realistic viewport (`{width: 1280, height: 800}` or
  `{width: 1920, height: 1080}`), realistic locale (`en-US`) and timezone
  (`America/New_York`).
- Disable the webdriver flag via `addInitScript`:
  ```js
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  ```
- Avoid detection tells: don't navigate faster than a human could click;
  add small randomized delays between actions; respect `robots.txt` and
  rate-limit headers; never reuse the same session across unrelated sites.
