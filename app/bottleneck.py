"""Bottleneck identification (topic-driven, per the installed
`serenity-aleabitoreddit` skill).

Each stored *topic* names a demand driver, lists the scarce upstream layers
that constrain it, and carries downstream stock thesis cards (``anchor`` =
obvious capex spenders, ``underdogs`` = filtered + ranked small/mid caps).
This module is the *read* engine: it consumes the topic store
(:mod:`app.bottleneck_topics`), the shared valuation cache
(:mod:`app.ai_valuation`) and price history, and assembles the dashboard
payload.

It is deliberately **pure and read-only** — it reads caches and assembles the
payload, and never triggers a fetch.  The network belongs to the refresh path:
``all_proxy_symbols()`` feeds the bulk history download and
``ensure_metrics()`` (called from the create/generate/apply flows) warms the
valuation cache.  Missing data degrades to ``None`` (rendered ``—``), never to
an invented value.
"""

from __future__ import annotations

import math
from typing import Any

from . import ai_valuation, bottleneck_topics, config, market
from .bottleneck_topics import METRIC_FIELDS, STOCK_CARD_FIELDS, tier_for_market_cap
from .indicators import roc_at


# The installed skill this section encodes.  Referenced by the module docstring
# and by the ``framework`` payload string; keep the two in sync.
FRAMEWORK = "serenity-aleabitoreddit"

_THESIS = (
    "Do not start with the obvious winner. Each topic names a demand driver; "
    "trace it down to the scarce physical layer the whole build cannot bypass, "
    "then check whether that layer's price momentum confirms the squeeze."
)

_NOTE = (
    "Layer and underdog momentum is a rough stress gauge, not a thesis. Each "
    "chokepoint still requires primary-source validation (filings, purchase "
    "orders, qualification evidence) before it becomes an actionable "
    "bottleneck."
)

_EMPTY_NOTE = (
    "The bottleneck section is empty. Create a topic or generate one from a "
    "theme to start tracking a demand driver and its chokepoint layers."
)


# ---- Small helpers -----------------------------------------------------------


def _clean_ticker(value: Any) -> str:
    """A trimmed ticker string, or ``""`` for anything unusable."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _num(value: Any) -> float | int | None:
    """A finite int/float, or ``None``.  ``bool`` is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _closes(hist: Any) -> list[float]:
    """Valid closes from a history list; drop missing/NaN (keep 0.0)."""
    if not isinstance(hist, list):
        return []
    out: list[float] = []
    for row in hist:
        if not isinstance(row, dict):
            continue
        close = row.get("close")
        if close is None:
            continue
        if isinstance(close, float) and math.isnan(close):
            continue
        out.append(close)
    return out


# ---- History access (snapshot first, then the shared per-symbol cache) -------


def _extra_histories(snapshot: dict[str, Any]) -> dict[str, Any]:
    histories = snapshot.get("histories")
    if not isinstance(histories, dict):
        return {}
    extra = histories.get("extra")
    return extra if isinstance(extra, dict) else {}


def _history_for(symbol: str, histories: dict[str, Any]) -> list[dict[str, Any]]:
    """History for one symbol: the warm snapshot first, then the shared
    per-symbol 24h cache (``market.get_history``).

    A cold cache yields an empty list, which downstream becomes ``None``
    momentum rather than an invented number.  ``all_proxy_symbols()`` feeds the
    refresh's bulk download, so topic symbols are normally already warm here.
    """
    hist = histories.get(symbol)
    if hist:
        return hist
    return market.get_history(symbol, days=250, ttl=config.HISTORY_TTL) or []


def _roc_40d(symbol: str, histories: dict[str, Any]) -> float | None:
    """40-day ROC for one symbol, rounded to 1dp (old ``_rank_layer`` math)."""
    roc = roc_at(_closes(_history_for(symbol, histories)), config.BOTTLENECK_LOOKBACK_DAYS)
    return round(roc, 1) if roc is not None else None


# ---- Valuation cache (shared; never fetched here) ----------------------------


def _load_metrics(symbol: str, cache: dict[str, dict], stored: Any) -> dict[str, Any]:
    """Assemble one card's metrics block from the shared caches.

    The valuation cache is authoritative: a symbol present there uses its
    values verbatim (including ``None`` where a field is genuinely missing), so
    the card can never disagree with ``breadth_ai``.  A symbol absent from the
    cache falls back to its own persisted metrics (which the store already
    stamps) — never to a guessed value.  ``roc_40d`` / ``move_1y`` come from
    price history.  Every field is always present; unavailable is ``None``.
    """
    metrics: dict[str, Any] = {field: None for field in METRIC_FIELDS}

    entry = cache.get(symbol)
    stored_metrics = stored if isinstance(stored, dict) else {}
    if isinstance(entry, dict):
        metrics["market_cap"] = _num(entry.get("market_cap"))
        metrics["revenue_growth"] = _num(entry.get("revenue_growth"))
        metrics["forward_pe"] = _num(entry.get("forward_pe"))
        as_of = entry.get("as_of")
    else:
        metrics["market_cap"] = _num(stored_metrics.get("market_cap"))
        metrics["revenue_growth"] = _num(stored_metrics.get("revenue_growth"))
        metrics["forward_pe"] = _num(stored_metrics.get("forward_pe"))
        as_of = stored_metrics.get("as_of")

    metrics["as_of"] = as_of if isinstance(as_of, str) and as_of else None
    return metrics


def _market_cap_for(symbol: str, cache: dict[str, dict], stored: Any) -> float | int | None:
    """The market cap used for underdog filtering/tiering, cache-first."""
    entry = cache.get(symbol)
    if isinstance(entry, dict):
        return _num(entry.get("market_cap"))
    stored_metrics = stored if isinstance(stored, dict) else {}
    return _num(stored_metrics.get("market_cap"))


# ---- Cards -------------------------------------------------------------------


def _stock_card(
    raw: dict[str, Any],
    role: str,
    tier: str,
    histories: dict[str, Any],
    cache: dict[str, dict],
    read_as_of: Any,
    *,
    ceiling: Any = None,
) -> dict[str, Any]:
    """One card in the full ``STOCK_CARD_FIELDS`` schema, metrics recomputed."""
    symbol = _clean_ticker(raw.get("ticker"))
    card: dict[str, Any] = {field: raw.get(field) for field in STOCK_CARD_FIELDS}
    card["ticker"] = symbol
    card["role"] = role
    card["tier"] = tier
    # Structural defaults for a card that predates a field (never for the
    # checklist flags — ``None`` there means "not assessed").
    if card.get("evidence") is None:
        card["evidence"] = []
    if card.get("invalidation") is None:
        card["invalidation"] = []
    if card.get("provenance") is None:
        card["provenance"] = {}

    metrics = _load_metrics(symbol, cache, raw.get("metrics"))
    metrics["roc_40d"] = _roc_40d(symbol, histories) if symbol else None
    metrics["move_1y"] = _move_1y(symbol, histories) if symbol else None
    if not metrics["as_of"]:
        metrics["as_of"] = read_as_of if isinstance(read_as_of, str) and read_as_of else None
    card["metrics"] = metrics

    if tier == "underdog":
        # Label the market-cap tier.  ``None`` means unavailable market cap —
        # kept in the list and rendered ``—``, never guessed.
        card["conviction_tier"] = tier_for_market_cap(metrics.get("market_cap"), ceiling)
    return card


def _move_1y(symbol: str, histories: dict[str, Any]) -> float | None:
    roc = roc_at(_closes(_history_for(symbol, histories)), 252)
    return round(roc, 1) if roc is not None else None


def _underdog_cards(
    raw_list: list[dict[str, Any]],
    ceiling: Any,
    histories: dict[str, Any],
    cache: dict[str, dict],
    read_as_of: Any,
) -> list[dict[str, Any]]:
    """Filter, tier and rank ``downstream.underdogs``.

    A stock with a *known* market cap above ``ceiling`` is dropped.  A stock
    whose market cap is unavailable is kept (rendered ``—``) — the two cases
    are deliberately distinct and never conflated.  Survivors rank by 40-day
    ROC descending; ``None`` momentum sinks.
    """
    kept: list[dict[str, Any]] = []
    for raw in raw_list:
        symbol = _clean_ticker(raw.get("ticker"))
        market_cap = _market_cap_for(symbol, cache, raw.get("metrics")) if symbol else None
        if market_cap is not None and tier_for_market_cap(market_cap, ceiling) is None:
            continue  # above ceiling -> filtered out
        kept.append(raw)

    cards = [
        _stock_card(raw, "downstream", "underdog", histories, cache, read_as_of, ceiling=ceiling)
        for raw in kept
    ]
    cards.sort(key=lambda c: (c["metrics"]["roc_40d"] is None, -(c["metrics"]["roc_40d"] or 0.0)))
    return cards


# ---- Layers / topics ---------------------------------------------------------


def _layer_tickers(layer: Any) -> list[str]:
    """The distinct, order-stable tickers of one upstream layer."""
    if not isinstance(layer, dict):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in layer.get("stocks") or []:
        if isinstance(entry, dict):
            symbol = _clean_ticker(entry.get("ticker"))
        else:
            symbol = _clean_ticker(entry)
        if symbol and symbol not in seen:
            seen.add(symbol)
            out.append(symbol)
    return out


def _rank_key(layer: dict[str, Any]) -> tuple[bool, float]:
    value = layer.get("roc_40d_pct")
    return (value is None, -(value or 0.0))


def _layer_block(layer: dict[str, Any], histories: dict[str, Any], read_as_of: Any) -> dict[str, Any]:
    """Rank-ready view of one upstream layer.

    The old ``gauge`` is folded into ``what_to_watch`` (the topic store already
    models it); a legacy ``gauge`` field is honoured as a fallback but never
    re-emitted.
    """
    tickers = _layer_tickers(layer)
    rocs = [r for r in (_roc_40d(sym, histories) for sym in tickers) if r is not None]
    aggregate = round(sum(rocs) / len(rocs), 1) if rocs else None
    what_to_watch = layer.get("what_to_watch") or layer.get("gauge") or ""
    return {
        "name": layer.get("name") or "",
        "physical_constraint": layer.get("physical_constraint") or "",
        "what_to_watch": what_to_watch,
        "stocks": tickers,
        "roc_40d_pct": aggregate,
        "as_of": read_as_of if isinstance(read_as_of, str) and read_as_of else None,
    }


def _topic_block(
    topic: dict[str, Any],
    histories: dict[str, Any],
    cache: dict[str, dict],
    read_as_of: Any,
) -> dict[str, Any]:
    ceiling = _num(topic.get("underdog_ceiling"))
    if ceiling is None:
        ceiling = bottleneck_topics.UNDERDOG_CEILING_DEFAULT

    layers = [
        _layer_block(layer, histories, read_as_of)
        for layer in _list_of_dicts(topic.get("upstream"))
    ]
    layers.sort(key=_rank_key)

    downstream = topic.get("downstream") if isinstance(topic.get("downstream"), dict) else {}
    anchors = [
        _stock_card(raw, "downstream", "anchor", histories, cache, read_as_of)
        for raw in _list_of_dicts(downstream.get("anchor"))
    ]
    underdogs = _underdog_cards(
        _list_of_dicts(downstream.get("underdogs")), ceiling, histories, cache, read_as_of
    )

    return {
        "id": topic.get("id") or "",
        "name": topic.get("name") or "",
        "created": topic.get("created"),
        "updated": topic.get("updated"),
        "underdog_ceiling": ceiling,
        "upstream": layers,
        "downstream": {"anchor": anchors, "underdogs": underdogs},
        "note": _topic_note(ceiling),
    }


def _topic_note(ceiling: Any) -> str:
    return (
        f"Upstream layers rank by {config.BOTTLENECK_LOOKBACK_DAYS}-day ROC. "
        f"Underdogs are capped at ${float(ceiling) / 1e9:g}B and rank by the same "
        "measure; momentum is a stress gauge, not a thesis."
    )


# ---- Public surface ----------------------------------------------------------


def all_proxy_symbols() -> list[str]:
    """Every ticker named by the topic store, deduped in definition order.

    Derived dynamically from the topics' upstream layer stocks and downstream
    cards (anchors + underdogs).  On a fresh install with no topics this is
    ``[]`` — the bulk history download then shrinks to just the non-bottleneck
    symbols, which is expected and correct.  There is no fallback universe.
    """
    seen: dict[str, None] = {}
    for topic in _list_of_dicts(bottleneck_topics.load_topics()):
        for layer in _list_of_dicts(topic.get("upstream")):
            for symbol in _layer_tickers(layer):
                seen.setdefault(symbol)
        downstream = topic.get("downstream") if isinstance(topic.get("downstream"), dict) else {}
        for group in ("anchor", "underdogs"):
            for raw in _list_of_dicts(downstream.get(group)):
                symbol = _clean_ticker(raw.get("ticker"))
                if symbol:
                    seen.setdefault(symbol)
    return list(seen)


def ensure_metrics(tickers: list[str]) -> dict[str, dict]:
    """Warm the shared valuation cache for ``tickers``.

    Refresh-path helper for the create/generate/apply flows; it is never called
    from :func:`bottleneck_read` (which stays pure).  No tickers -> no fetch.
    """
    symbols = [symbol for symbol in dict.fromkeys(tickers) if symbol]
    if not symbols:
        return {}
    return ai_valuation.fetch_ticker_metrics(symbols)


def bottleneck_read(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Assemble the bottleneck payload from caches.  Pure — no network."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    read_as_of = snapshot.get("as_of")
    histories = _extra_histories(snapshot)
    cache = ai_valuation.load_ticker_metrics()

    blocks = [
        _topic_block(topic, histories, cache, read_as_of)
        for topic in _list_of_dicts(bottleneck_topics.load_topics())
    ]

    return {
        "as_of": read_as_of,
        "framework": FRAMEWORK,
        "thesis": _THESIS,
        "topics": blocks,
        "strongest_signal": _strongest_signal(blocks),
        "note": _NOTE if blocks else _EMPTY_NOTE,
    }


def _strongest_signal(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The strongest upstream layer across all topics, or ``None``.

    ``None`` when no layer produced a scored momentum — never a fake winner.
    """
    best: dict[str, Any] | None = None
    for block in blocks:
        for layer in block.get("upstream") or []:
            value = layer.get("roc_40d_pct")
            if value is None:
                continue
            if best is None or value > best["roc_40d_pct"]:
                best = {**layer, "topic_id": block.get("id"), "topic_name": block.get("name")}
    return best
