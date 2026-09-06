# Decisions

Durable, one-way-door(ish) decisions and confirmed root causes. Append new
entries; don't delete old ones even if later superseded — mark them
superseded instead, so the history of *why* stays intact. Newest at the
bottom.

The entries below were pulled out of `AGENTS.md`'s "Key quirks" and "Recent
activity" sections during the `docs/` split-out — they were always true,
just harder to scan in prose form.

---

## Market data: yfinance only, no secondary fallback (2026-08-23)

The former Stooq CSV fallback was removed because Stooq now serves a
JavaScript bot-wall to non-browser clients. There is currently no secondary
source for market data — failed fetches surface as `null` and are never
cached. Do not silently re-add a scraping-based fallback without confirming
it can survive non-browser access long-term; that's the exact failure mode
that killed Stooq.

## Hidden launchers: `wscript.exe` + VBS, not `pythonw.exe`

`pythonw.exe` (the GUI-subsystem Python launcher) tries to detach from the
parent console on startup; when that detach leaves OS console-handle state
inconsistent, `pythonw` silently aborts before binding. The working pattern
is `wscript.exe <vbs-script> python args...` with the VBS setting
`shell.Run "python args", 0, False` (`WindowStyle=0` = `SW_HIDE`, `False` =
don't wait). Used by both `launch.vbs` (desktop shortcut) and
`scheduler.vbs` (Windows Task Scheduler tasks). If a third hidden launcher
is ever needed, copy this pattern — do not reintroduce `pythonw.exe`.

## Commodities spot pricing: FRED + Minted Metal, not Yahoo quotes

Yahoo's `fast_info` is broken in current `yfinance` versions, so real
cash-market spot for the Commodities card comes from FRED public CSV
(energy) and Minted Metal public JSON (precious metals) instead, mapped
back onto the matching Yahoo futures ticker so the renderer doesn't need to
know the source family.

## Risk gauge design: divided signals = healthy, unanimous = fragility

In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed
for layout; the signed `weight` is what moves the needle. `app/risk.py`
encodes the same intuition in code rather than layout: divided signals
across the 9 cross-asset inputs are healthy, unanimous optimism is the
fragility signal (RED fires on consensus optimism, not just bad numbers).
The gauge's ~70 events are also part of the news timeline seed
(`app/seed_data.py`), with direction mapped from its bear/neutral/bull
columns. Keep this framing in mind before "fixing" `app/risk.py` to fire on
raw bearishness — unanimous bearishness is not the RED trigger, unanimous
*optimism* is.

## Frozen reference files are not touched, ever

The four `ai_*.html` files at repo root are frozen reference material from a
prior project (they seeded the analysis framework and design system). Do not
modify them regardless of what else is being refactored.

## Hard-rule propagation: `project-rules` skill, not AGENTS.md alone

`AGENTS.md` auto-injects into the parent orchestrator's system prompt but
**not** into OMO-slim subagent sessions (`@fixer`, `@explorer`, `@oracle`,
`@designer`, etc.). Handing the rules through the dispatch prompt is the
only reliable cross-context path. The pattern:

1. Hard rules live in `.opencode/skills/project-rules/SKILL.md`.
2. `AGENTS.md` "During Work" instructs the orchestrator to invoke that
   skill (`skill` tool) before any subagent dispatch and include the
   output in the subagent's prompt string.
3. Subagents receive the rules as immediate task context, not as static
   background.

Keep the skill and AGENTS.md's "Hard rules" section in sync — they are
deliberately the same content in two places, because the skill survives
subagent dispatch while AGENTS.md survives session restart.

---

---

## OPEN — tickerTable.js shared-component persistence (2026-09-05)

**Status:** under investigation, not yet confirmed.

The `914f406` refactor made Earnings and Portfolio share `tickerTable.js`.
Section position (column order/visibility) is reportedly no longer saving
for at least one of them. Working hypothesis: the shared component lost the
per-section key namespacing that `column_order`/`column_visibility` used to
have when each section had its own implementation.

**Once confirmed, replace this entry with the actual root cause and the
resulting rule**, e.g.: *"Shared UI components must take their persistence
key as a required prop; never let a shared component default or hardcode a
storage key, since that silently merges state across every caller."* Add a
regression test per consuming section so this can't regress unnoticed again
on the next shared-component extraction.

## OPEN — stuck process on test launch (2026-09-05)

**Status:** under investigation, not yet confirmed.

`AGENTS.md` already documents the correct lifecycle (in-process `TestClient`
first; never `Start-Process`/`nohup`; hidden launch via the VBS pattern
above; reap-and-verify before ending a turn), so a recurrence means either
the documented procedure isn't being followed, or there's a path to a hang
not covered by the current rule. Once root-caused, record the specific
trigger here (which command, which launch path) so the runbook in
`docs/RUNBOOK.md` can be tightened accordingly.
