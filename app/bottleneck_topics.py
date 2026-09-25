"""Bottleneck topic store: topic-driven, per-stock thesis persistence.

Replaces the old category-preference model (``bottleneck_prefs.py``) with a
list of user-authored *topics*.  Each topic names a demand driver, lists the
upstream layers that constrain it, and carries downstream stock thesis cards
(anchors = obvious capex spenders, underdogs = filtered/ranked later).

Persistence lives in ``data/bottleneck_topics.json``.  State shape::

    {
        "version": 1,
        "topics": [ topic, ... ]
    }

A ``topic`` is::

    {
        "id": <short uuid4 hex>,
        "name": <demand driver>,
        "created": <ISO-8601 UTC>,
        "updated": <ISO-8601 UTC>,
        "upstream": [ layer, ... ],
        "downstream": {"anchor": [stock, ...], "underdogs": [stock, ...]},
        "underdog_ceiling": 10_000_000_000,
        "revisions": [ revision, ... ]   # newest first, bounded
    }

Every mutating call is atomic (``store.save_json``) and every read degrades
gracefully: a missing file, an empty file, a corrupt file, or an unexpected
root type all yield an empty store rather than raising.  This module is pure
local persistence — it imports nothing network-related and never invents a
figure.  ``metrics`` values are stored verbatim; nothing is computed here.
"""

from __future__ import annotations

import copy
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from . import config, store


_TOPICS_PATH = config.DATA_DIR / "bottleneck_topics.json"

# ---- Constants (public; consumers and tests rely on these) -------------------

UNDERDOG_CEILING_DEFAULT = 10_000_000_000
CORE_TIER_MAX = 3_000_000_000
MAX_REVISIONS = 20

EVIDENCE_TIERS = ("primary-filing", "company-release", "sell-side", "social")

# Checklist flags. ``None`` means "not assessed" — never guessed.
CHECKLIST_FLAGS = (
    "dilution_atm",
    "customer_concentration",
    "gaap_margin",
    "financing_quality",
)

# Full thesis-card field set (order matches the persisted shape).
STOCK_CARD_FIELDS = (
    "ticker",
    "name",
    "stance",
    "conviction_tier",
    "why_chokepoint",
    "layer",
    "role",
    "tier",
    "evidence",
    "catalyst",
    "catalyst_window",
    "invalidation",
    "dilution_atm",
    "customer_concentration",
    "gaap_margin",
    "financing_quality",
    "metrics",
    "provenance",
)

# ``as_of`` is the stamped provenance time for the metrics block; the rest are
# numbers and are validated as such.
METRIC_FIELDS = (
    "market_cap",
    "roc_40d",
    "move_1y",
    "forward_pe",
    "revenue_growth",
    "as_of",
)

_ALLOWED_ROLES = ("upstream", "downstream")
_ALLOWED_TIERS = ("anchor", "underdog")
_NUMERIC_METRIC_FIELDS = tuple(f for f in METRIC_FIELDS if f != "as_of")

# Only a market cap has a meaningful floor at zero. Every other numeric metric
# is legitimately signed: ``roc_40d`` and ``move_1y`` are returns, so a laggard
# is negative; ``revenue_growth`` is a delta, so a shrinking business is
# negative; ``forward_pe`` is negative for a loss-making company. Rejecting a
# signed value there would reject ordinary fetched market data and would make
# the agent's own output unvalidatable.
_NON_NEGATIVE_METRIC_FIELDS = ("market_cap",)

_TOPIC_FIELDS = (
    "id",
    "name",
    "created",
    "updated",
    "upstream",
    "downstream",
    "underdog_ceiling",
    "revisions",
)


# ---- Small helpers -----------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _is_number(value: Any) -> bool:
    """True for a finite int/float; ``bool`` is explicitly not a number."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _new_stock(ticker: str = "", role: str = "upstream", tier: str = "anchor") -> dict[str, Any]:
    """A fully-defaulted thesis card. Every field present, every default empty/null."""
    return {
        "ticker": ticker,
        "name": "",
        "stance": "",
        "conviction_tier": "",
        "why_chokepoint": "",
        "layer": "",
        "role": role,
        "tier": tier,
        "evidence": [],
        "catalyst": "",
        "catalyst_window": "",
        "invalidation": [],
        "dilution_atm": None,
        "customer_concentration": None,
        "gaap_margin": None,
        "financing_quality": None,
        "metrics": {field: None for field in METRIC_FIELDS},
        "provenance": {"model": "", "skill_snapshot": "", "prompt_hash": "", "run_ts": ""},
    }


# ---- Load / save -------------------------------------------------------------


def load_topics() -> list[dict[str, Any]]:
    """Return all stored topics, degrading to ``[]`` on any unusable file.

    Handles missing file, empty file, corrupt JSON, wrong root type, and a
    stray bare list (accepted for resilience — ``import_topics`` also accepts
    one).  Never raises on user data.
    """
    data = store.load_json(_TOPICS_PATH)
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("topics")
    else:
        return []
    if not isinstance(raw, list):
        return []
    return [t for t in raw if isinstance(t, dict)]


def save_topics(topics: list[dict[str, Any]]) -> None:
    """Atomically persist the topic list as a versioned document."""
    store.save_json(_TOPICS_PATH, {"version": 1, "topics": list(topics or [])})


def get_topic(topic_id: str) -> dict[str, Any] | None:
    """Return the topic with ``topic_id``, or ``None`` when unknown."""
    for topic in load_topics():
        if topic.get("id") == topic_id:
            return topic
    return None


def new_topic(name: str) -> dict[str, Any]:
    """A fully-defaulted empty topic. Not persisted — caller decides when."""
    now = _now_iso()
    return {
        "id": _new_id(),
        "name": (name or "").strip(),
        "created": now,
        "updated": now,
        "upstream": [],
        "downstream": {"anchor": [], "underdogs": []},
        "underdog_ceiling": UNDERDOG_CEILING_DEFAULT,
        "revisions": [],
    }


def create_topic(name: str) -> dict[str, Any]:
    """Create ``new_topic(name)``, persist it, and return it."""
    topic = new_topic(name)
    topics = load_topics()
    topics.append(topic)
    save_topics(topics)
    return topic


def update_topic(topic_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    """Shallow-merge ``patch`` over the topic, refresh ``updated``, persist.

    ``id`` is immutable (identity is not editable via a patch).  Returns the
    updated topic, or ``None`` when the id is unknown.
    """
    topics = load_topics()
    for topic in topics:
        if topic.get("id") != topic_id:
            continue
        for key, value in (patch or {}).items():
            if key == "id":
                continue
            topic[key] = value
        topic["updated"] = _now_iso()
        save_topics(topics)
        return topic
    return None


def delete_topic(topic_id: str) -> bool:
    """Delete the topic. Returns ``True`` when one was removed."""
    topics = load_topics()
    remaining = [t for t in topics if t.get("id") != topic_id]
    if len(remaining) == len(topics):
        return False
    save_topics(remaining)
    return True


def append_revision(
    topic_id: str, snapshot: dict[str, Any], source: str, summary: str
) -> dict[str, Any] | None:
    """Apply ``snapshot`` body to the topic and record a numbered revision.

    The revision number is 1-based and monotonically increasing per topic;
    revisions are stored newest-first and truncated to ``MAX_REVISIONS``.
    Returns the updated topic, or ``None`` when the id is unknown.
    """
    topics = load_topics()
    for topic in topics:
        if topic.get("id") != topic_id:
            continue

        for key, value in (snapshot or {}).items():
            if key == "revisions":
                continue
            topic[key] = copy.deepcopy(value)
        topic["id"] = topic_id  # identity is never rewritten by a snapshot

        now = _now_iso()
        topic["updated"] = now

        revisions = topic.get("revisions")
        if not isinstance(revisions, list):
            revisions = []
        last_n = 0
        for rev in revisions:
            if isinstance(rev, dict) and _is_positive_int(rev.get("n")):
                last_n = max(last_n, rev["n"])

        # What actually got applied (the topic body, minus history).
        applied = {k: copy.deepcopy(v) for k, v in topic.items() if k != "revisions"}
        revision = {
            "n": last_n + 1,
            "created": now,
            "source": source,
            "summary": summary,
            "snapshot": applied,
        }
        topic["revisions"] = [revision, *revisions][:MAX_REVISIONS]
        save_topics(topics)
        return topic
    return None


def export_topics() -> dict[str, Any]:
    """The persisted document, sanitised for JSON export.

    ``store.json_safe`` guarantees no ``NaN``/``Infinity`` leaks into a JSON
    response, matching the project's boundary contract.
    """
    return store.json_safe({"version": 1, "topics": load_topics()})


def import_topics(payload: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse+validate topics from a bare list or ``{"version", "topics"}`` doc.

    Returns ``(imported_topics, errors)``.  Invalid topics are skipped with a
    human-readable error each — never raised, never silently coerced.  This
    function does not persist; the caller decides whether to ``save_topics``.
    """
    if isinstance(payload, list):
        raw: Any = payload
    elif isinstance(payload, dict):
        raw = payload.get("topics")
    else:
        return [], ['payload must be a list of topics or a {"version", "topics"} document']

    if not isinstance(raw, list):
        return [], ["payload does not contain a 'topics' list"]

    imported: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, topic in enumerate(raw):
        if not isinstance(topic, dict):
            errors.append(f"topic[{index}]: not an object")
            continue
        found = validate_topic(topic)
        if found:
            label = topic.get("name") or topic.get("id") or f"index {index}"
            for message in found:
                errors.append(f"topic[{label}]: {message}")
            continue
        imported.append(topic)
    return imported, errors


# ---- Validation --------------------------------------------------------------


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_stock(stock: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(stock, dict):
        return [f"{path}: stock must be an object"]

    ticker = stock.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        errors.append(f"{path}: ticker is required")

    role = stock.get("role")
    if role not in _ALLOWED_ROLES:
        errors.append(f"{path}: role must be one of {_ALLOWED_ROLES}, got {role!r}")

    tier = stock.get("tier")
    if tier not in _ALLOWED_TIERS:
        errors.append(f"{path}: tier must be one of {_ALLOWED_TIERS}, got {tier!r}")

    evidence = stock.get("evidence")
    if evidence is not None:
        if not isinstance(evidence, list):
            errors.append(f"{path}: evidence must be a list")
        else:
            for i, item in enumerate(evidence):
                if not isinstance(item, dict):
                    errors.append(f"{path}.evidence[{i}]: must be an object")
                    continue
                item_tier = item.get("tier")
                if item_tier not in EVIDENCE_TIERS:
                    errors.append(
                        f"{path}.evidence[{i}]: tier must be one of {EVIDENCE_TIERS}, got {item_tier!r}"
                    )

    invalidation = stock.get("invalidation")
    if invalidation is not None and not isinstance(invalidation, list):
        errors.append(f"{path}: invalidation must be a list")

    for flag in CHECKLIST_FLAGS:
        if flag not in stock:
            continue
        if stock[flag] is not None and not isinstance(stock[flag], bool):
            errors.append(f"{path}: {flag} must be true, false, or null, got {stock[flag]!r}")

    metrics = stock.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            errors.append(f"{path}: metrics must be an object")
        else:
            for field in _NUMERIC_METRIC_FIELDS:
                if field not in metrics:
                    continue
                value = metrics[field]
                if value is None:
                    continue
                if not _is_number(value):
                    errors.append(
                        f"{path}.metrics.{field}: must be null or a finite number, got {value!r}"
                    )
                elif field in _NON_NEGATIVE_METRIC_FIELDS and value < 0:
                    errors.append(
                        f"{path}.metrics.{field}: must be null or a non-negative number, got {value!r}"
                    )
            as_of = metrics.get("as_of")
            if as_of is not None and not isinstance(as_of, str):
                errors.append(f"{path}.metrics.as_of: must be null or a string, got {as_of!r}")

    return errors


def _validate_layer(layer: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(layer, dict):
        return [f"{path}: layer must be an object"]
    stocks = layer.get("stocks")
    if stocks is not None:
        if not isinstance(stocks, list):
            errors.append(f"{path}: stocks must be a list of tickers")
        else:
            for i, ticker in enumerate(stocks):
                if not isinstance(ticker, str) or not ticker.strip():
                    errors.append(f"{path}.stocks[{i}]: must be a non-empty ticker string")
    return errors


def validate_topic(topic: Any) -> list[str]:
    """Return human-readable validation errors; ``[]`` when valid.

    Strict on the fields that carry meaning, tolerant of *missing* optional
    fields.  Rejects: a missing/blank ``name``, a bad ``role``, a bad ``tier``,
    an ``evidence.tier`` outside ``EVIDENCE_TIERS``, a non-numeric metric that is
    not ``None`` (and a *negative* one where the metric has a zero floor — see
    ``_NON_NEGATIVE_METRIC_FIELDS``), a revision ``n`` that is not a positive
    int, and any checklist flag that is not ``True``/``False``/``None``.
    """
    if not isinstance(topic, dict):
        return ["topic must be an object/dict"]

    errors: list[str] = []

    name = topic.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required and must be a non-empty string")

    upstream = topic.get("upstream")
    if upstream is not None:
        if not isinstance(upstream, list):
            errors.append("upstream must be a list of layers")
        else:
            for i, layer in enumerate(upstream):
                errors.extend(_validate_layer(layer, f"upstream[{i}]"))

    downstream = topic.get("downstream")
    if downstream is not None:
        if not isinstance(downstream, dict):
            errors.append("downstream must be an object with anchor/underdogs")
        else:
            for group in ("anchor", "underdogs"):
                group_value = downstream.get(group)
                if group_value is None:
                    continue
                if not isinstance(group_value, list):
                    errors.append(f"downstream.{group} must be a list of stocks")
                    continue
                for i, stock in enumerate(group_value):
                    errors.extend(_validate_stock(stock, f"downstream.{group}[{i}]"))

    ceiling = topic.get("underdog_ceiling")
    if ceiling is not None and not _is_number(ceiling):
        errors.append(f"underdog_ceiling must be a number, got {ceiling!r}")

    revisions = topic.get("revisions")
    if revisions is not None:
        if not isinstance(revisions, list):
            errors.append("revisions must be a list")
        else:
            for i, revision in enumerate(revisions):
                if not isinstance(revision, dict):
                    errors.append(f"revisions[{i}]: must be an object")
                    continue
                if not _is_positive_int(revision.get("n")):
                    errors.append(
                        f"revisions[{i}].n: must be a positive integer, got {revision.get('n')!r}"
                    )

    return errors


def tier_for_market_cap(market_cap: Any, ceiling: Any) -> str | None:
    """Classify a market cap into a conviction tier.

    ``None`` when ``market_cap`` is unavailable — never guessed.  ``"core"``
    below ``CORE_TIER_MAX``; ``"extended"`` from there up to ``ceiling``;
    ``None`` above the ceiling.
    """
    if not _is_number(market_cap):
        return None
    if not _is_number(ceiling):
        ceiling = UNDERDOG_CEILING_DEFAULT
    if market_cap < CORE_TIER_MAX:
        return "core"
    if market_cap <= ceiling:
        return "extended"
    return None
