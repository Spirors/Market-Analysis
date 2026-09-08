# Diagnostic scripts MUST redirect data/portfolios.json to a temp dir (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Diagnostic scripts MUST redirect data/portfolios.json to a temp dir (2026-09-07)

**Status:** confirmed + durable rule (data-loss incident).

**Trigger:** A diagnostic TestClient timing script
(`C:\Users\Spirors\AppData\Local\Temp\opencode\diag_api_timing.py`,
written 2026-09-07 for the audit-2026-09-07 P0 follow-up) wrote
test data to the user's REAL `data/portfolios.json`. The script
called `store.save_json(portfolio.PORTFOLIOS_PATH,
portfolio._default_state())` and then `API.createPortfolio()` +
`API.addPortfolioHolding()` via `TestClient(app)`. The TestClient
runs in-process against the real `app.api` module, which reads +
writes `data/portfolios.json` via the unmodified `app.config.DATA_DIR`.
The user's 5 portfolios (Fidelity Main, Fidelity Roth IRA, Fidelity
HSA, IBKR Cash, Earning Watchlist) were overwritten with
`testmain` / `test` / `test-2` / `test-3` / `test2-*` test data.

**Root cause:** the diagnostic script treated `data/portfolios.json`
as a writable scratch surface without checking that the file is the
user's source-of-truth (not a fixture). Three contributing factors:

1. **gitignored = no safety net.** `data/*` is in `.gitignore` with
   exceptions only for `.gitkeep` and `data/events.json`. There is no
   git history to `git checkout` from, no stash, no reflog. A
   single careless write is permanent unless an external backup
   exists (OneDrive mirror, Windows File History, second device).
   The cross-device sync model in `project_rules/ARCHITECTURE.md`
   confirms `data/portfolios.json` does NOT sync via Git — it lives
   on one device only.
2. **No fixture isolation helper.** `app.portfolio` + `app.config`
   expose `DATA_DIR` and `PORTFOLIOS_PATH` as module-level globals.
   Nothing in the test infrastructure (`tests/conftest.py`,
   `tests/test_portfolio.py`, or anywhere) provides a one-liner
   monkeypatch to redirect those paths to a tmp dir for the
   duration of a diagnostic / test session.
3. **The diagnostic ran before `tests/` was used for the same
   purpose.** The user's TestClient suite (`tests/test_portfolio.py`)
   uses `tmp_path` fixtures correctly; the diagnostic script was a
   one-off that bypassed that pattern.

**Severity:** the user's portfolio holdings are unrecoverable
without an external backup. Per AGENTS.md "Data integrity":
"`data/portfolios.json` belongs to the user; never overwrite
silently." Even a benign test fixture write is forbidden if it
erases user data.

**Recovery performed:** the user provided a CSV export
(`c:\Users\Spirors\Desktop\Financials - Portfolio.csv`) with the
5 portfolios + holdings + cash rows. A one-shot import script
rebuilt `data/portfolios.json` from this CSV. Holdings are
restored to the exact shares/cost values from the CSV. Live
prices (`last_price`, `pct_daily`, sector, fundamentals) are
null and will repopulate on the next full enrichment pass
(`/api/refresh`, the Refresh button, or QUOTE_TTL expiry) — the
UI renders null as `—` per the existing convention. Cash rows
are restored with `kind: "cash"`, `label: "Cash"`, `total_value`
from the CSV value, `total_cost = total_value` (matching the
existing `portfolio.js editCash` symmetry).

**Rule (durable):** ANY script (diagnostic, ad-hoc, or test) that
exercises the portfolio API MUST redirect `data/portfolios.json`
(and `data/dashboard.json`) to a temp directory for the
duration of the session. Two acceptable patterns:

- **`app.config.DATA_DIR` monkeypatch (preferred):**
  ```python
  import tempfile, pathlib
  from app import config, store
  with tempfile.TemporaryDirectory() as td:
      monkeypatch.setattr(config, "DATA_DIR", pathlib.Path(td))
      monkeypatch.setattr(config, "CACHE_DIR", pathlib.Path(td) / "cache")
      monkeypatch.setattr(store, "PORTFOLIOS_PATH", config.DATA_DIR / "portfolios.json")
      # ... use TestClient(app) here ...
  ```
  Note: also override `config.DATA_DIR` before `app.api` is imported
  if the import has cached the path.

- **`tmp_path` pytest fixture (already used by `tests/test_portfolio.py`):
  write a pytest test instead of a standalone script — the test
  infrastructure handles isolation automatically.

**Hard rule:** the diagnostic script's failure mode (writing to the
real `data/portfolios.json`) MUST NOT be repeatable. The script's
source has been deleted from `C:\Users\Spirors\AppData\Local\Temp\opencode\diag_api_timing.py`; future diagnostics MUST follow
the patterns above or they will be rejected at session-end review.

