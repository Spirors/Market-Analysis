#!/usr/bin/env python3
"""Audit news sources stored in the events timeline.

Groups events by source, computes median importance, hit rate, and count,
then prints a recommendation table (keep / de-emphasize / drop).

Usage::

    python tools/news_source_audit.py [--events data/events.json] [--days 60]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a standalone script (no package context).
_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent / "app"
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# Import the threshold directly — we want the canonical value, not a copy.
from app.news import IMPORTANCE_THRESHOLD


def _load_events(path: Path) -> list[dict]:
    """Load events from a JSON timeline file."""
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("events", [])


def _filter_window(events: list[dict], days: int) -> list[dict]:
    """Keep only events published within the last *days* days."""
    if days <= 0:
        return events
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [e for e in events if e.get("published", "") >= cutoff]


def audit(
    events: list[dict],
) -> dict[str, dict]:
    """Compute per-source statistics.

    Returns a dict keyed by source name with:
      - n: event count
      - median_importance: median raw importance score
      - hit_rate: fraction of events whose composite >= threshold
      - recommendation: keep / de-emphasize / drop

    Events lacking an ``importance`` field (older hand-tagged seeds) are
    re-analyzed on the fly via ``app.news.analyze``.
    """
    from collections import defaultdict

    from app import news

    by_source: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        by_source[ev.get("source", "unknown")].append(ev)

    result: dict[str, dict] = {}
    for source, evts in sorted(by_source.items()):
        n = len(evts)
        importances: list[float] = []
        composites: list[float] = []
        for e in evts:
            imp = e.get("importance")
            comp = e.get("composite_importance")
            if imp is None or comp is None:
                # Re-analyze from title + summary.
                info = news.analyze(
                    e.get("title", ""),
                    e.get("summary", ""),
                    e.get("source", ""),
                )
                imp = imp if imp is not None else info["importance"]
                comp = comp if comp is not None else info["composite_importance"]
            importances.append(float(imp))
            composites.append(float(comp))

        median_imp = (
            round(statistics.median(importances), 2) if importances else 0.0
        )
        median_comp = (
            round(statistics.median(composites), 2) if composites else 0.0
        )
        hits = sum(1 for c in composites if c >= IMPORTANCE_THRESHOLD)
        hit_rate = round(hits / n, 3) if n else 0.0

        # Recommendation logic: based on composite score median (which
        # already accounts for source weight and finance relevance), not
        # raw importance.  The storage gate is composite >= 6.0, so the
        # recommendation must be derived from the same metric.
        comp_floor_low = IMPORTANCE_THRESHOLD - 3.0
        comp_floor_high = IMPORTANCE_THRESHOLD - 1.5
        if median_comp >= comp_floor_high:
            rec = "keep"
        elif median_comp >= comp_floor_low:
            rec = "de-emphasize"
        else:
            rec = "drop"

        result[source] = {
            "n": n,
            "median_importance": median_imp,
            "median_composite": median_comp,
            "hit_rate": hit_rate,
            "recommendation": rec,
        }
    return result


def _print_table(stats: dict[str, dict]) -> None:
    """Pretty-print the audit table."""
    hdr = f"{'source':<25} {'n':>5} {'med_imp':>8} {'med_comp':>8} {'hit_rate':>8} {'recommendation':<15}"
    print(hdr)
    print("-" * len(hdr))
    for source, s in stats.items():
        print(
            f"{source:<25} {s['n']:>5} {s['median_importance']:>8.2f} "
            f"{s['median_composite']:>8.2f} "
            f"{s['hit_rate']:>8.3f} {s['recommendation']:<15}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit news source quality from the events timeline."
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("data/events.json"),
        help="Path to events.json (default: data/events.json)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="Look-back window in days (default: 60; 0 = all events)",
    )
    args = parser.parse_args()

    if not args.events.exists():
        print(f"Error: {args.events} not found", file=sys.stderr)
        sys.exit(1)

    events = _load_events(args.events)
    events = _filter_window(events, args.days)
    if not events:
        print("No events in the specified window.", file=sys.stderr)
        sys.exit(0)

    stats = audit(events)
    _print_table(stats)
    print(f"\nThreshold: {IMPORTANCE_THRESHOLD}  |  Window: {args.days}d  |  Events: {len(events)}")


if __name__ == "__main__":
    main()
