"""CI dry-run helper for ``.github/workflows/pipeline-dry-run.yml``.

Three subcommands, every one parameterized by a data directory (and, where it
writes, an explicit report/before/after path) so a rehearsal or a test can
point them at a scratch location and never touch the user's real ``data/``:

* ``seed``              — write one synthetic portfolio (public tickers only).
* ``validate``          — check a run's ``dashboard.json`` + ``portfolio_history.json``.
* ``check-idempotency`` — compare ``portfolio_history.json`` across two refreshes.

Synthetic data only. Nothing here reads or writes outside the given data dir
and the explicit report/before/after paths. Exit code 0 == all checks passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Sections the dashboard must carry after a full ``--refresh`` (see
# ``app/service.refresh_all``). ``news`` and ``regime`` are added by
# ``refresh_all`` on top of the ``refresh_market`` payload.
CORE_SECTIONS = ("market", "indicators", "risk", "portfolios", "news", "vintage")

# A dashboard ``as_of`` older than this is treated as "not recent". Generous:
# the pipeline itself runs in ~1 min; this only catches a stale/absent write.
AS_OF_MAX_AGE_S = 60 * 60

SYNTHETIC_PORTFOLIO_ID = "dry-run"
# (symbol, shares, total_cost) — fixed so the fixture is deterministic. Public
# tickers with long yfinance history so the settle-date logic always finds an
# eligible bar.
SYNTHETIC_HOLDINGS = (
    ("SPY", 10.0, 4000.0),
    ("AAPL", 20.0, 3500.0),
    ("MSFT", 5.0, 1800.0),
)


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #

def load_json_with_dups(path: Path) -> tuple[object, list[str]]:
    """Load JSON and report any duplicate object keys.

    ``json.loads`` silently keeps the last of duplicate keys, which would hide
    a duplicate ``close_date`` in ``portfolio_history.json``. The pairs hook
    records every repeated key so the caller can flag it.
    """
    duplicates: list[str] = []

    def _hook(pairs):
        seen: set[str] = set()
        for key, _value in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text, object_pairs_hook=_hook), duplicates


def _parse_ts(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp (with or without trailing ``Z``)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# seed
# --------------------------------------------------------------------------- #

def seed(data_dir: Path, force: bool = False) -> dict:
    """Write a synthetic ``portfolios.json`` (one portfolio, public tickers).

    Refuses to overwrite an existing file unless ``force`` — a safety rail so a
    stray ``--data-dir`` pointing at the real ``data/`` cannot clobber the
    user's holdings.
    """
    path = Path(data_dir) / "portfolios.json"
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists; refusing to overwrite (pass --force)"
        )
    state = {
        "version": 1,
        "portfolios": {
            SYNTHETIC_PORTFOLIO_ID: {
                "id": SYNTHETIC_PORTFOLIO_ID,
                "name": "CI Dry Run",
                "holdings": [
                    {"symbol": sym, "shares": shares, "total_cost": cost}
                    for sym, shares, cost in SYNTHETIC_HOLDINGS
                ],
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "portfolio": SYNTHETIC_PORTFOLIO_ID,
        "tickers": [sym for sym, _, _ in SYNTHETIC_HOLDINGS],
    }


# --------------------------------------------------------------------------- #
# validation (pure)
# --------------------------------------------------------------------------- #

def validate_dashboard(data: object, now: datetime | None = None) -> list[str]:
    """Return the list of problems with a dashboard payload (empty == OK)."""
    if not isinstance(data, dict):
        return ["dashboard.json is not a JSON object"]
    problems: list[str] = []
    now = now or datetime.now(timezone.utc)

    as_of = _parse_ts(data.get("as_of"))
    if as_of is None:
        problems.append("dashboard.as_of missing or unparseable")
    else:
        age = (now - as_of).total_seconds()
        if age > AS_OF_MAX_AGE_S:
            problems.append(f"dashboard.as_of is stale ({age:.0f}s old)")
        elif age < -300:
            problems.append("dashboard.as_of is in the future")

    missing = [section for section in CORE_SECTIONS if section not in data]
    if missing:
        problems.append("dashboard missing sections: " + ", ".join(missing))

    portfolios = data.get("portfolios")
    if not isinstance(portfolios, dict) or not portfolios:
        problems.append("dashboard.portfolios is empty (synthetic seed not enriched?)")
    return problems


def validate_history(data: object, now: datetime | None = None) -> tuple[list[str], dict]:
    """Return (problems, info) for a ``portfolio_history.json`` payload."""
    if not isinstance(data, dict):
        return ["portfolio_history.json is not a JSON object"], {}
    snapshots = data.get("snapshots")
    if not isinstance(snapshots, dict):
        return ["portfolio_history.snapshots missing or not an object"], {}

    dates = list(snapshots.keys())
    info = {"entries": len(dates), "close_dates": sorted(dates)}
    problems: list[str] = []
    if not dates:
        problems.append("portfolio_history has no snapshots")
        return problems, info

    now = now or datetime.now(timezone.utc)
    limit = now.date() + timedelta(days=1)  # +1 day slack for ET vs UTC
    for key in dates:
        parsed = _parse_date(key)
        if parsed is None:
            problems.append(f"portfolio_history invalid close_date: {key!r}")
        elif parsed > limit:
            problems.append(f"portfolio_history close_date in the future: {key}")
    return problems, info


def check_idempotency(
    before: object, after: object, duplicates: list[str] | None = None
) -> tuple[list[str], dict]:
    """Return (problems, info) comparing two history payloads.

    Rules (run 2 must not disturb run 1's settled history):

    * no duplicate snapshot dates,
    * every date present in ``before`` is still present in ``after``,
    * every surviving date's entry is deep-equal (no rewrite),
    * at most one new date may appear (a settle boundary crossed mid-run).
    """
    problems: list[str] = []
    if duplicates:
        problems.append("duplicate snapshot dates: " + ", ".join(sorted(set(duplicates))))

    before_snaps = before.get("snapshots") if isinstance(before, dict) else None
    after_snaps = after.get("snapshots") if isinstance(after, dict) else None
    if not isinstance(before_snaps, dict) or not isinstance(after_snaps, dict):
        return ["snapshots missing in before/after history"], {}

    before_keys, after_keys = set(before_snaps), set(after_snaps)

    missing = sorted(before_keys - after_keys)
    if missing:
        problems.append("dates lost between runs: " + ", ".join(missing))

    rewritten = sorted(
        key for key in before_keys & after_keys if before_snaps[key] != after_snaps[key]
    )
    if rewritten:
        problems.append("dates rewritten between runs: " + ", ".join(rewritten))

    added = sorted(after_keys - before_keys)
    if len(added) > 1:
        problems.append("more than one new date added: " + ", ".join(added))

    info = {
        "before": len(before_keys),
        "after": len(after_keys),
        "added": added,
        "rewritten": rewritten,
        "missing": missing,
    }
    return problems, info


# --------------------------------------------------------------------------- #
# report + CLI
# --------------------------------------------------------------------------- #

def _write_report(path: str | None, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _append_report(path: str | None, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(text)


def _cmd_validate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    lines = ["== CI dry-run validation =="]
    problems: list[str] = []

    dash_path = data_dir / "dashboard.json"
    if not dash_path.exists():
        problems.append(f"missing {dash_path}")
        lines.append(f"dashboard: MISSING ({dash_path})")
    else:
        data, _dups = load_json_with_dups(dash_path)
        problems += validate_dashboard(data)
        lines.append(f"dashboard: {dash_path}")
        lines.append(f"  as_of: {data.get('as_of') if isinstance(data, dict) else None}")
        present = [s for s in CORE_SECTIONS if isinstance(data, dict) and s in data]
        lines.append(f"  sections present: {', '.join(present) or '(none)'}")
        count = len(data.get("portfolios") or {}) if isinstance(data, dict) else 0
        lines.append(f"  portfolios: {count}")

    hist_path = data_dir / "portfolio_history.json"
    if not hist_path.exists():
        problems.append(f"missing {hist_path}")
        lines.append(f"portfolio_history: MISSING ({hist_path})")
    else:
        data, _dups = load_json_with_dups(hist_path)
        hist_problems, info = validate_history(data)
        problems += hist_problems
        lines.append(f"portfolio_history: {hist_path}")
        lines.append(f"  entries: {info.get('entries')}")
        lines.append(f"  close_dates: {', '.join(info.get('close_dates', [])) or '(none)'}")

    if problems:
        lines.append("RESULT: FAIL")
        lines.extend(f"  - {problem}" for problem in problems)
    else:
        lines.append("RESULT: OK")

    report = "\n".join(lines) + "\n"
    print(report, end="")
    _write_report(args.report, report)
    return 1 if problems else 0


def _cmd_check_idempotency(args: argparse.Namespace) -> int:
    before, _before_dups = load_json_with_dups(Path(args.before))
    after, after_dups = load_json_with_dups(Path(args.after))
    problems, info = check_idempotency(before, after, after_dups)

    lines = ["", "== idempotency check (refresh #2) =="]
    lines.append(f"  snapshots before: {info.get('before')}")
    lines.append(f"  snapshots after:  {info.get('after')}")
    lines.append(f"  new dates: {', '.join(info.get('added', [])) or '(none)'}")
    if problems:
        lines.append("RESULT: FAIL")
        lines.extend(f"  - {problem}" for problem in problems)
    else:
        lines.append("RESULT: OK (no rewrites, no lost dates)")

    report = "\n".join(lines) + "\n"
    print(report, end="")
    _append_report(args.report, report)
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CI dry-run helper (synthetic data only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="write a synthetic data/portfolios.json")
    p_seed.add_argument("--data-dir", default="data")
    p_seed.add_argument("--force", action="store_true", help="overwrite an existing file")

    p_validate = sub.add_parser("validate", help="validate a run's dashboard + history")
    p_validate.add_argument("--data-dir", default="data")
    p_validate.add_argument("--report", default=None, help="write the report here")

    p_check = sub.add_parser("check-idempotency", help="compare history across two refreshes")
    p_check.add_argument("--before", required=True, help="history JSON from run 1")
    p_check.add_argument("--after", required=True, help="history JSON from run 2")
    p_check.add_argument("--report", default=None, help="append the report here")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "seed":
        try:
            info = seed(Path(args.data_dir), force=args.force)
        except FileExistsError as exc:
            print(f"seed refused: {exc}", file=sys.stderr)
            return 1
        print(
            f"seeded {info['path']} with portfolio '{info['portfolio']}' "
            f"({', '.join(info['tickers'])})"
        )
        return 0
    if args.command == "validate":
        return _cmd_validate(args)
    return _cmd_check_idempotency(args)


if __name__ == "__main__":
    sys.exit(main())
