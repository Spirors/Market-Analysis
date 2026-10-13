"""Daily portfolio closing-value snapshots + retrospective series.

Persistence: one JSON file (``data/portfolio_history.json``) holding one
snapshot entry per *close date* — the latest settled US trading bar date the
bulk history data carries. Entries are **write-if-absent**: a past close date
is never rewritten, so history is append-only.

Two responsibilities:

* :func:`record_snapshot` — the single read-modify-write writer. Called once
  per refresh (manual Refresh button and the scheduled daily task both go
  through ``service.refresh_all``).
* :func:`build_history_payload` — the read side for ``GET
  /api/portfolios/history``: the stored snapshots plus a live retrospective
  series computed from *current* holdings applied backwards over the same
  bulk daily-close series the writer used.

Never fabricate: a holding with no close for the reference date has a null
close/value, and the portfolio ``total_value`` is null (never a partial sum).
Missing data degrades to null; nothing raises.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import config, market, portfolio as _portfolio, store

logger = logging.getLogger(__name__)

# User-data path. Module-level constant bound at import time — tests must
# redirect *this* name (see tests/conftest.py), not config.DATA_DIR alone.
HISTORY_PATH = config.DATA_DIR / "portfolio_history.json"

# The history window/days argument shared with ``enrich_portfolios`` so the
# bulk cache key (``bulkhist_<sorted-symbols-hash>_260``) is identical — one
# download, no second fetch path.
BULK_DAYS = 260

# US equities settle their daily close at 16:00 ET; 16:15 gives the data
# source a margin to publish the final bar. A bar dated today is only
# eligible (settled) once the ET clock is at/after this time — otherwise it
# is a partial in-session bar and must never be recorded as a close.
_ET = ZoneInfo("America/New_York")
_SETTLE_TIME = time(16, 15)


def _now_z() -> str:
    """UTC ISO timestamp with a trailing ``Z`` (seconds precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_state() -> dict[str, Any]:
    return {"version": 1, "snapshots": {}}


def load_history() -> dict[str, Any]:
    """Load the snapshot store, or a default when missing/corrupt."""
    data = store.load_json(HISTORY_PATH)
    if not isinstance(data, dict) or data.get("version") != 1:
        return _default_state()
    if not isinstance(data.get("snapshots"), dict):
        data["snapshots"] = {}
    return data


def save_history(state: dict[str, Any]) -> None:
    store.save_json(HISTORY_PATH, state)


def merge_snapshots(
    entries: dict[str, dict[str, Any]], path: Path | None = None
) -> dict[str, list[str]]:
    """Write captured entries into the history store, write-if-absent.

    ``entries`` is ``{close_date: entry}`` (e.g. folded cloud captures).
    Existing dates are NEVER rewritten — this is the same write-if-absent
    contract as ``record_snapshot``, so a re-fold is a no-op. Returns
    ``{"added": [...], "existing": [...]}``. Atomic via ``store.save_json``;
    writes only when something is actually added.
    """
    target = Path(path) if path is not None else HISTORY_PATH
    state = store.load_json(target, None)
    if not isinstance(state, dict) or state.get("version") != 1:
        state = _default_state()
    if not isinstance(state.get("snapshots"), dict):
        state["snapshots"] = {}
    snaps = state["snapshots"]
    added: list[str] = []
    existing: list[str] = []
    for key in sorted(entries):
        if key in snaps:
            existing.append(key)
            continue
        snaps[key] = entries[key]
        added.append(key)
    if added:
        store.save_json(target, state)
    return {"added": added, "existing": existing}


def _parse_bar_date(value: Any) -> date | None:
    """Coerce a bulk-history ``date`` field (``YYYY-MM-DD`` str or date) to a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _is_eligible_session_date(bar_date: date, now: datetime | None = None) -> bool:
    """True when ``bar_date`` is a *settled* US session close, not a partial bar.

    Eligible: strictly before today's US/Eastern session date, or today's
    session date once the ET clock is at/after ~16:15. Applied identically to
    the writer and the retrospective so the two can never disagree.
    """
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    et = now_utc.astimezone(_ET)
    today = et.date()
    if bar_date < today:
        return True
    if bar_date == today:
        return et.time() >= _SETTLE_TIME
    return False


def _latest_eligible_date(
    histories: dict[str, list[dict[str, Any]]], now: datetime | None = None
) -> date | None:
    latest: date | None = None
    for rows in histories.values():
        for row in rows or []:
            d = _parse_bar_date((row or {}).get("date"))
            if d is None or not _is_eligible_session_date(d, now):
                continue
            if latest is None or d > latest:
                latest = d
    return latest


def _collect_symbols(portfolios: dict[str, Any]) -> list[str]:
    """The non-cash symbol union, in first-seen order (same set as enrichment)."""
    symbols: list[str] = []
    for p in portfolios.values():
        for h in (p or {}).get("holdings", []) or []:
            sym = h.get("symbol")
            if sym and h.get("kind") != "cash" and sym not in symbols:
                symbols.append(sym)
    return symbols


def _close_on(rows: list[dict[str, Any]] | None, close_date: date) -> float | None:
    """The settled close for ``close_date`` from one symbol's daily rows, or None."""
    target = close_date.isoformat()
    for row in rows or []:
        if (row or {}).get("date") == target:
            c = row.get("close")
            if c is None:
                return None
            try:
                return round(float(c), 4)
            except (TypeError, ValueError):
                return None
    return None


def _build_portfolio_snapshot(
    p: dict[str, Any], histories: dict[str, list[dict[str, Any]]], close_date: date
) -> dict[str, Any]:
    """One portfolio's point for ``close_date``.

    Mirrors the table's client-side totals (``static/js/portfolio.js``
    ``portfolioTotals``): value = Σ shares×close + cash value, cost = Σ every
    row's ``total_cost`` (cash cost included). Deviation by contract: a
    missing close makes that holding's value null AND the portfolio
    ``total_value`` null — never a partial sum. ``coverage.ok`` counts symbols
    with a close, ``.total`` the symbol count.
    """
    holdings_out: dict[str, Any] = {}
    total_value: float | None = 0.0
    total_cost = 0.0
    cash_value = 0.0
    ok = 0
    total = 0

    for h in p.get("holdings", []) or []:
        if h.get("kind") == "cash":
            total_cost += float(h.get("total_cost") or 0.0)
            cv = float(h.get("total_value") or 0.0)
            cash_value += cv
            total_value = (total_value + cv) if total_value is not None else None
            continue
        sym = h.get("symbol")
        if not sym:
            continue
        total += 1
        shares = float(h.get("shares") or 0.0)
        close = _close_on(histories.get(sym), close_date)
        value = round(shares * close, 3) if close is not None else None
        if close is not None:
            ok += 1
        holdings_out[sym] = {"shares": shares, "close": close, "value": value}
        total_cost += float(h.get("total_cost") or 0.0)
        if total_value is not None:
            total_value = (total_value + value) if value is not None else None

    return {
        "total_value": round(total_value, 3) if total_value is not None else None,
        "total_cost": round(total_cost, 3),
        "cash": round(cash_value, 3),
        "coverage": {"ok": ok, "total": total},
        "holdings": holdings_out,
    }


# Float tolerance for the backfill accuracy check. Shares are compared tightly;
# cash/cost are rounded to 3 dp by ``_build_portfolio_snapshot``, so a 1e-3
# tolerance absorbs that rounding without masking a real book change.
_SHARE_EPS = 1e-6
_VALUE_EPS = 1e-3


def _make_entry(
    portfolios: dict[str, Any],
    histories: dict[str, list[dict[str, Any]]],
    close_date: date,
    *,
    backfilled: bool,
    recorded_at: str,
) -> dict[str, Any]:
    """One snapshot entry for ``close_date`` (the shared writer shape)."""
    entry: dict[str, Any] = {
        "close_date": close_date.isoformat(),
        "recorded_at": recorded_at,
        "portfolios": {
            pid: _build_portfolio_snapshot(p, histories, close_date)
            for pid, p in portfolios.items()
        },
    }
    if backfilled:
        entry["backfilled"] = True
    return entry


def _current_book(p: dict[str, Any]) -> dict[str, Any]:
    """The current portfolio's book: non-cash {symbol: shares}, cash value, total cost."""
    shares: dict[str, float] = {}
    cash = 0.0
    total_cost = 0.0
    for h in p.get("holdings") or []:
        total_cost += float(h.get("total_cost") or 0.0)
        if h.get("kind") == "cash":
            cash += float(h.get("total_value") or 0.0)
            continue
        sym = h.get("symbol")
        if sym:
            shares[sym] = float(h.get("shares") or 0.0)
    return {"shares": shares, "cash": cash, "total_cost": total_cost}


def _book_matches(ref_pf: dict[str, Any], current_p: dict[str, Any]) -> bool:
    """True when the current book provably equals a recorded reference book.

    Compares the non-cash symbol set + shares (tight epsilon), the cash value,
    and the total cost. Any difference means the book changed somewhere in the
    backfill window, so reconstruction would be fabrication — the caller omits
    the portfolio and the gap is preserved.
    """
    if not isinstance(ref_pf, dict):
        return False
    ref_holdings = ref_pf.get("holdings")
    if not isinstance(ref_holdings, dict):
        return False
    current = _current_book(current_p)
    if set(ref_holdings) != set(current["shares"]):
        return False
    for sym, h in ref_holdings.items():
        if abs(float((h or {}).get("shares") or 0.0) - current["shares"][sym]) > _SHARE_EPS:
            return False
    if abs(float(ref_pf.get("cash") or 0.0) - current["cash"]) > _VALUE_EPS:
        return False
    if abs(float(ref_pf.get("total_cost") or 0.0) - current["total_cost"]) > _VALUE_EPS:
        return False
    return True


def _reconstruct_snapshot(
    ref_pf: dict[str, Any],
    histories: dict[str, list[dict[str, Any]]],
    close_date: date,
) -> dict[str, Any]:
    """Rebuild one portfolio's point for ``close_date`` from a recorded book.

    Only valid once ``_book_matches`` proved the book unchanged: the recorded
    shares/cash/cost are carried verbatim and only the close prices are read
    from the bulk-history series. Missing closes still yield null (never a
    partial sum), exactly like the live writer.
    """
    cash_value = float(ref_pf.get("cash") or 0.0)
    holdings_out: dict[str, Any] = {}
    total_value: float | None = cash_value
    ok = 0
    total = 0
    for sym, h in (ref_pf.get("holdings") or {}).items():
        total += 1
        shares = float((h or {}).get("shares") or 0.0)
        close = _close_on(histories.get(sym), close_date)
        value = round(shares * close, 3) if close is not None else None
        if close is not None:
            ok += 1
        holdings_out[sym] = {"shares": shares, "close": close, "value": value}
        if total_value is not None:
            total_value = (total_value + value) if value is not None else None
    return {
        "total_value": round(total_value, 3) if total_value is not None else None,
        "total_cost": round(float(ref_pf.get("total_cost") or 0.0), 3),
        "cash": round(cash_value, 3),
        "coverage": {"ok": ok, "total": total},
        "holdings": holdings_out,
    }


def _backfill_entries(
    prior_snapshots: dict[str, Any],
    portfolios: dict[str, Any],
    histories: dict[str, list[dict[str, Any]]],
    latest_close: date,
    now: datetime | None,
) -> dict[str, dict[str, Any]]:
    """Reconstruct missing settled dates between the last stored date and latest.

    The reference is the LAST STORED entry *before* this run: if the current
    book is provably identical to the book it recorded, the book did not change
    in the window, so a gap inside the window is reconstructable from those
    recorded holdings + bulk-history prices + recorded cash. Portfolios failing
    the check are omitted (their gap remains); if none qualify, no date is
    written. Returns ``{close_date: entry}`` — write-if-absent, never a rewrite.
    """
    if not prior_snapshots:
        return {}
    try:
        last_stored = date.fromisoformat(max(prior_snapshots))
    except (TypeError, ValueError):
        return {}
    ref_entry = prior_snapshots.get(last_stored.isoformat())
    if not isinstance(ref_entry, dict):
        return {}
    ref_portfolios = ref_entry.get("portfolios")
    if not isinstance(ref_portfolios, dict) or not ref_portfolios:
        return {}

    missing = [d for d in _eligible_dates(histories, now) if last_stored < d < latest_close]
    if not missing:
        return {}

    reconstructable = {
        pid: ref_portfolios[pid]
        for pid, p in portfolios.items()
        if pid in ref_portfolios and _book_matches(ref_portfolios[pid], p)
    }
    if not reconstructable:
        logger.info(
            "portfolio history: no portfolio's book matches the last stored entry; gaps preserved"
        )
        return {}

    recorded_at = _now_z()
    out: dict[str, dict[str, Any]] = {}
    for d in missing:
        key = d.isoformat()
        if key in prior_snapshots:
            continue
        out[key] = {
            "close_date": key,
            "recorded_at": recorded_at,
            "backfilled": True,
            "portfolios": {
                pid: _reconstruct_snapshot(ref_pf, histories, d)
                for pid, ref_pf in reconstructable.items()
            },
        }
    return out


def record_snapshot(now: datetime | None = None) -> dict[str, Any] | None:
    """Record the latest eligible close, backfilling reconstructable gaps. The ONE writer.

    Single read-modify-write: load the store, build the latest point, and
    backfill any missed settled dates that are provably reconstructable (see
    ``_backfill_entries``). Every write is write-if-absent — a stored date is
    never rewritten. Returns the latest entry (existing or newly written), or
    ``None`` when there is nothing to record (no symbols, bulk fetch empty, or
    no eligible bar). Never raises for an empty/failed bulk fetch — a failed
    fetch is not cached (``market.get_histories_bulk`` already leaves failures
    uncached).
    """
    state = load_history()
    portfolios = _portfolio.load_portfolios().get("portfolios", {})
    symbols = _collect_symbols(portfolios)
    if not symbols:
        logger.info("portfolio history: no holdings to snapshot; skipping")
        return None

    histories = market.get_histories_bulk(symbols, days=BULK_DAYS)
    if not histories:
        logger.warning("portfolio history: bulk history fetch returned nothing; skipping snapshot")
        return None

    close_date = _latest_eligible_date(histories, now)
    if close_date is None:
        logger.info("portfolio history: no settled bar eligible yet; skipping snapshot")
        return None

    # The pre-run store drives both the backfill reference and the gap window.
    prior_snapshots = dict(state["snapshots"])
    changed = False

    latest_key = close_date.isoformat()
    latest_entry = prior_snapshots.get(latest_key)
    if latest_entry is None:
        latest_entry = _make_entry(
            portfolios, histories, close_date, backfilled=False, recorded_at=_now_z()
        )
        state["snapshots"][latest_key] = latest_entry
        changed = True

    for key, entry in _backfill_entries(
        prior_snapshots, portfolios, histories, close_date, now
    ).items():
        if key not in state["snapshots"]:
            state["snapshots"][key] = entry
            changed = True

    if changed:
        save_history(state)
    return latest_entry


def _point(date_str: str, snap: dict[str, Any]) -> dict[str, Any]:
    """Shape a stored/computed portfolio snapshot into a chart point."""
    value = snap.get("total_value")
    cost = snap.get("total_cost")
    gain = (value - cost) if (value is not None and cost is not None) else None
    return {
        "date": date_str,
        "value": value,
        "cost": cost,
        "gain": gain,
        "coverage": snap.get("coverage") or {"ok": 0, "total": 0},
    }


def _eligible_dates(
    histories: dict[str, list[dict[str, Any]]], now: datetime | None = None
) -> list[date]:
    """Sorted union of settled session dates across every symbol's daily rows."""
    dates: set[date] = set()
    for rows in histories.values():
        for row in rows or []:
            d = _parse_bar_date((row or {}).get("date"))
            if d is not None and _is_eligible_session_date(d, now):
                dates.add(d)
    return sorted(dates)


def _retro_series(
    p: dict[str, Any], histories: dict[str, list[dict[str, Any]]], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Current holdings & cash applied backwards over the settled daily series."""
    return [
        _point(d.isoformat(), _build_portfolio_snapshot(p, histories, d))
        for d in _eligible_dates(histories, now)
    ]


def build_history_payload(now: datetime | None = None) -> dict[str, Any]:
    """The ``GET /api/portfolios/history`` payload.

    Only current portfolios appear. ``snapshots`` is the stored history mapped
    to chart points; ``retrospective`` is computed live from current holdings
    (never stored) over the same bulk series/call shape as enrichment, with
    the same settled-bar cap. An empty/missing store yields ``snapshots: {}``.
    """
    state = load_history()
    portfolios = _portfolio.load_portfolios().get("portfolios", {})

    symbols = _collect_symbols(portfolios)
    histories = market.get_histories_bulk(symbols, days=BULK_DAYS) if symbols else {}
    if not isinstance(histories, dict):
        histories = {}

    stored = state.get("snapshots") or {}
    snapshots: dict[str, list[dict[str, Any]]] = {}
    if stored:
        for pid in portfolios:
            points: list[dict[str, Any]] = []
            for key in sorted(stored):
                entry = stored.get(key) or {}
                pf = (entry.get("portfolios") or {}).get(pid)
                if pf is None:
                    continue
                date_str = entry.get("close_date") or key
                points.append(_point(date_str, pf))
            snapshots[pid] = points

    retrospective = {
        pid: _retro_series(p, histories, now) for pid, p in portfolios.items()
    }

    return {
        "portfolios": [
            {"id": pid, "name": p.get("name")} for pid, p in portfolios.items()
        ],
        "snapshots": snapshots,
        "retrospective": retrospective,
        "meta": {"as_of": _now_z()},
    }
