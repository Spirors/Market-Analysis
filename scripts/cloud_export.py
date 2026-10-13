"""Cloud capture CLI for the off-PC data transport (used by capture.yml).

Subcommands, all parameterized by paths so a rehearsal can target scratch dirs:

* ``export``     — post-refresh data dir + data-repo checkout → captures + state.
* ``validate``   — parse + shape-check every capture and state file in a checkout.
* ``pull-state`` — validate ``<repo>/state/*`` then copy into the data dir.
* ``fold``       — validate + apply captures into the data dir (the local fold);
                   ``--expect-noop`` fails when a fold would change anything.

Output is sanitized: counts, dates, ok flags and file names only — never
holdings, shares, values or costs. Exit code 0 == success.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow ``python scripts/cloud_export.py`` from the repo root: the script dir
# (``scripts/``) is sys.path[0], not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import sync as sync_mod  # noqa: E402


def _parse_steps(raw: list[str]) -> list[dict]:
    """``--step NAME[:ok|fail][:detail]`` → ``[{"name","ok"[,"detail"]}]``."""
    steps: list[dict] = []
    for item in raw or []:
        parts = item.split(":", 2)
        name = parts[0].strip()
        if not name:
            continue
        ok = True
        detail = None
        if len(parts) > 1:
            ok = parts[1].strip().lower() not in ("fail", "false", "0", "no")
        if len(parts) > 2:
            detail = parts[2]
        step: dict = {"name": name, "ok": ok}
        if detail:
            step["detail"] = detail
        steps.append(step)
    return steps


def _print_export(result: dict) -> None:
    print(f"export: ok={result['ok']}")
    print(f"  written: {len(result['written'])} file(s)")
    print(f"  skipped (existing captures): {len(result['skipped'])}")
    print(f"  new history dates: {', '.join(result['new_history_dates']) or '(none)'}")
    print(f"  new events: {result['new_events']}")
    print(f"  latest close date: {result['latest_close_date']}")
    if result["problems"]:
        print("  problems:")
        for problem in result["problems"]:
            print(f"    - {problem}")


def _print_fold(result: dict) -> None:
    print("fold:")
    print(f"  history added: {', '.join(result['history_added']) or '(none)'}")
    print(f"  history existing: {len(result['history_existing'])}")
    print(f"  events considered: {result['events_considered']}")
    print(f"  events inserted: {result['events_inserted']}")
    status = result.get("latest_status")
    if status:
        print(
            "  latest status: "
            f"runid={status.get('runid')} ok={status.get('ok')} "
            f"finished={status.get('finished_at')}"
        )
    else:
        print("  latest status: (none)")
    if result.get("status_stale"):
        print("  WARNING: latest status is stale or failed")


def _cmd_export(args: argparse.Namespace) -> int:
    result = sync_mod.export_captures(
        data_dir=Path(args.data_dir),
        repo_dir=Path(args.repo_dir),
        runid=args.runid,
        mode=args.mode,
        started_at=args.started_at,
        finished_at=args.finished_at,
        steps=_parse_steps(args.step),
        events_before_path=Path(args.events_before) if args.events_before else None,
        error=args.error,
    )
    _print_export(result)
    return 0 if result["ok"] else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    caps = sync_mod.validate_captures(Path(args.repo_dir))
    state_problems = sync_mod.validate_state_dir(Path(args.repo_dir))
    ok = caps["ok"] and not state_problems
    print(f"validate: ok={ok} ({caps['count']} capture file(s))")
    for problem in caps["problems"] + state_problems:
        print(f"  - {problem}")
    return 0 if ok else 1


def _cmd_pull_state(args: argparse.Namespace) -> int:
    try:
        result = sync_mod.copy_state_from_repo(Path(args.repo_dir), Path(args.data_dir))
    except sync_mod.SyncValidationError as exc:
        print(f"pull-state failed:\n{exc}", file=sys.stderr)
        return 1
    print(f"pull-state: copied {len(result['copied'])} file(s)")
    return 0


def _cmd_fold(args: argparse.Namespace) -> int:
    try:
        result = sync_mod.fold_captures(
            repo_dir=Path(args.repo_dir),
            data_dir=Path(args.data_dir),
            max_status_age_hours=args.max_status_age_hours,
        )
    except sync_mod.SyncValidationError as exc:
        print(f"fold failed:\n{exc}", file=sys.stderr)
        return 1
    _print_fold(result)
    if args.expect_noop and (result["history_added"] or result["events_inserted"]):
        print("fold: NOT a no-op (expected no changes)", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cloud capture CLI (sanitized output)")
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser("export", help="write captures + state into a data-repo checkout")
    e.add_argument("--data-dir", required=True)
    e.add_argument("--repo-dir", required=True)
    e.add_argument("--runid", required=True)
    e.add_argument("--mode", required=True, choices=["local", "private"])
    e.add_argument("--started-at", required=True)
    e.add_argument("--finished-at", required=True)
    e.add_argument("--step", action="append", default=[], help="NAME[:ok|fail][:detail]")
    e.add_argument("--events-before", default=None)
    e.add_argument("--error", default=None)

    v = sub.add_parser("validate", help="validate every capture + state file")
    v.add_argument("--repo-dir", required=True)

    ps = sub.add_parser("pull-state", help="copy <repo>/state/* into the data dir")
    ps.add_argument("--repo-dir", required=True)
    ps.add_argument("--data-dir", required=True)

    f = sub.add_parser("fold", help="validate + apply captures into the data dir")
    f.add_argument("--repo-dir", required=True)
    f.add_argument("--data-dir", required=True)
    f.add_argument("--max-status-age-hours", type=float, default=48.0)
    f.add_argument("--expect-noop", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export":
        return _cmd_export(args)
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "pull-state":
        return _cmd_pull_state(args)
    return _cmd_fold(args)


if __name__ == "__main__":
    sys.exit(main())
