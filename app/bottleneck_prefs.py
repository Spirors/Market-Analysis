"""Bottleneck category user preferences: reorder + rename.

Persistence lives in ``data/bottleneck_prefs.json``.  The canonical
category list (``bottleneck.BOTTLENECK_CATEGORIES``) is never mutated —
it is the source of truth for the set and definition-order of categories.
User prefs override display order and display names at serve time via
``bottleneck_read()``.

State shape::

    {
        "version": 1,
        "order": ["Agentic AI", ...],       # permutation of canonical names
        "renames": {"Agentic AI": "My AI"}   # canonical → display name
    }

Empty ``order`` means "use definition order".  Empty ``renames`` means
"use canonical names".  Both degrade gracefully: if a category is added
or removed upstream, an invalid ``order`` is silently ignored and falls
back to canonical order.
"""

from __future__ import annotations

from typing import Any

from . import config, store


_PREFS_PATH = config.DATA_DIR / "bottleneck_prefs.json"

_DEFAULT: dict[str, Any] = {
    "version": 1,
    "order": [],
    "renames": {},
}


def _canonical_names() -> list[str]:
    """Canonical category names from the module constant (read-only)."""
    from . import bottleneck
    return [c["category"] for c in bottleneck.BOTTLENECK_CATEGORIES]


def load_prefs() -> dict[str, Any]:
    """Return stored prefs, or a default if the file is missing/corrupt."""
    data = store.load_json(_PREFS_PATH)
    if not isinstance(data, dict) or data.get("version") != 1:
        return dict(_DEFAULT)
    data.setdefault("order", [])
    data.setdefault("renames", {})
    return data


def save_prefs(prefs: dict[str, Any]) -> None:
    """Atomically persist prefs."""
    store.save_json(_PREFS_PATH, prefs)


def reorder_categories(new_order: list[str]) -> dict[str, Any]:
    """Validate ``new_order`` is a permutation of canonical names and persist.

    Returns the updated prefs dict.

    Raises ``ValueError`` on bad input (non-list, missing category,
    duplicate, extra unknown).
    """
    canonical = _canonical_names()
    canonical_set = set(canonical)

    if not isinstance(new_order, list):
        raise ValueError("order must be a list of category names")

    if not new_order:
        raise ValueError("order must not be empty")

    order_set = set(new_order)
    if order_set != canonical_set or len(new_order) != len(canonical):
        missing = canonical_set - order_set
        extra = order_set - canonical_set
        parts = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if extra:
            parts.append(f"unknown: {sorted(extra)}")
        raise ValueError(f"order must be a permutation of canonical categories ({'; '.join(parts)})")

    prefs = load_prefs()
    prefs["order"] = list(new_order)
    save_prefs(prefs)
    _patch_dashboard_cache(prefs)
    return prefs


def rename_category(original: str, new_name: str) -> dict[str, str] | None:
    """Rename a category's display name.

    ``original`` must be a canonical category name.  ``new_name`` must
    be a non-empty trimmed string (else ``ValueError``).

    Returns ``{"original": ..., "display": ...}`` on success, or
    ``None`` if ``original`` is unknown.
    """
    canonical = _canonical_names()
    if original not in canonical:
        return None

    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("new_name must not be empty")

    prefs = load_prefs()
    prefs.setdefault("renames", {})[original] = new_name
    save_prefs(prefs)
    _patch_dashboard_cache(prefs)
    return {"original": original, "display": new_name}


def _patch_dashboard_cache(prefs: dict[str, Any]) -> None:
    """Patch the cached dashboard payload's bottleneck section after a mutation.

    The bottleneck data is recomputed from upstream; we only need to
    apply the user prefs (order + renames) on top of the cached
    bottleneck data, then bump the vintage stamp.  If the cache is
    missing or stale, we skip silently — a full refresh will rebuild it.
    """
    from datetime import datetime, timezone

    cache_path = config.DATA_DIR / "dashboard.json"
    try:
        cached = store.load_json(cache_path)
    except Exception:
        return
    if not isinstance(cached, dict):
        return

    bn = cached.get("bottleneck")
    if not isinstance(bn, dict) or not bn.get("categories"):
        return

    try:
        _apply_prefs_to_cache(bn, prefs)
        vintage = cached.setdefault("vintage", {})
        vintage["bottleneck"] = datetime.now(timezone.utc).isoformat()
        store.save_json(cache_path, cached)
    except Exception:
        pass


def _apply_prefs_to_cache(bn: dict[str, Any], prefs: dict[str, Any]) -> None:
    """Apply order + renames to a cached bottleneck dict in-place."""
    canonical = _canonical_names()
    canonical_set = set(canonical)
    categories = bn.get("categories")
    if not isinstance(categories, list):
        return

    # Build a lookup from canonical name → category dict (by position).
    by_canonical: dict[str, dict[str, Any]] = {}
    for i, cat in enumerate(categories):
        if i < len(canonical):
            by_canonical[canonical[i]] = cat

    # Apply renames.
    renames = prefs.get("renames") or {}
    for canon, cat in by_canonical.items():
        if canon in renames:
            cat["category"] = renames[canon]

    # Apply order (only if it's a valid permutation).
    order = prefs.get("order") or []
    if order and set(order) == canonical_set and len(order) == len(canonical):
        reordered = [by_canonical[name] for name in order if name in by_canonical]
        bn["categories"] = reordered
