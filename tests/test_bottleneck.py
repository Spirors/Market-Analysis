"""Tests for the topic-driven bottleneck engine (app/bottleneck.py).

The engine is pure: it reads the topic store, the shared valuation cache and
price history, and assembles a payload.  These tests mock all three so no
network is ever reached: ``yfinance`` is never touched, the valuation cache is
a controlled in-memory box, and the per-symbol history cache defaults to a
miss.  The autouse ``_isolate_data_files`` fixture in ``tests/conftest.py``
already redirects ``bottleneck_topics._TOPICS_PATH`` into ``tmp_path``.
"""

import pytest

from app import ai_valuation, bottleneck, bottleneck_topics


@pytest.fixture(autouse=True)
def _isolate_engine(monkeypatch):
    """Fake valuation cache + a default cold per-symbol history cache.

    Returns the metrics box so a test can seed it.  ``load_ticker_metrics`` is
    patched on the real module; the real function is TTL-free here, which keeps
    tests deterministic.
    """
    box = {"metrics": {}}
    monkeypatch.setattr(ai_valuation, "load_ticker_metrics", lambda: dict(box["metrics"]))
    # Cold per-symbol cache: no network, empty history -> None momentum.
    monkeypatch.setattr(
        bottleneck.market, "get_history",
        lambda symbol, days=250, ttl=None: [],
    )
    return box


# ---- Fixtures / builders -----------------------------------------------------


def _ramp(base: float, current: float, n: int = 41) -> list[dict]:
    """A close series whose 40-day ROC is ``(current/base - 1) * 100``.

    ``n - 1`` flat bases then one current close, so ``roc_at(closes, 40)``
    reads the base at index 0.
    """
    rows = [{"date": "2026-01-01", "close": float(base)} for _ in range(n - 1)]
    rows.append({"date": "2026-02-20", "close": float(current)})
    return rows


def _layer(name: str, stocks, **overrides) -> dict:
    layer = {
        "name": name,
        "physical_constraint": "capacity",
        "what_to_watch": "lead times",
        "stocks": list(stocks),
    }
    layer.update(overrides)
    return layer


def _card(ticker: str, **overrides) -> dict:
    card = {field: None for field in bottleneck_topics.STOCK_CARD_FIELDS}
    card.update({
        "ticker": ticker,
        "name": ticker,
        "stance": "long",
        "conviction_tier": "",
        "why_chokepoint": "",
        "layer": "",
        "role": "downstream",
        "tier": "underdog",
        "evidence": [],
        "catalyst": "",
        "catalyst_window": "",
        "invalidation": [],
        "dilution_atm": None,
        "customer_concentration": None,
        "gaap_margin": None,
        "financing_quality": None,
        "metrics": {field: None for field in bottleneck_topics.METRIC_FIELDS},
        "provenance": {},
    })
    card.update(overrides)
    return card


def _topic(
    name: str = "AI power",
    *,
    upstream=(),
    anchor=(),
    underdogs=(),
    ceiling: float | None = 10_000_000_000,
    **overrides,
) -> dict:
    topic = bottleneck_topics.new_topic(name)
    topic["upstream"] = list(upstream)
    topic["downstream"] = {"anchor": list(anchor), "underdogs": list(underdogs)}
    if ceiling is not None:
        topic["underdog_ceiling"] = ceiling
    topic.update(overrides)
    return topic


def _snapshot(histories: dict | None = None, as_of: str = "2026-09-25T00:00:00+00:00") -> dict:
    return {"as_of": as_of, "histories": {"extra": histories or {}}}


def _store(topics: list[dict]) -> None:
    bottleneck_topics.save_topics(topics)


def _all_keys(value) -> set:
    """Every dict key anywhere in a nested payload (for key-absence checks)."""
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys |= _all_keys(nested)
        return keys
    if isinstance(value, list):
        keys: set = set()
        for nested in value:
            keys |= _all_keys(nested)
        return keys
    return set()


# ---- Empty state (decision #19) ---------------------------------------------


def test_empty_store_renders_coherent_empty_payload():
    """The default fresh-install state: no topics, no raise, honest note."""
    result = bottleneck.bottleneck_read(_snapshot())

    assert result["topics"] == []
    assert result["framework"] == "serenity-aleabitoreddit"
    assert result["strongest_signal"] is None
    assert isinstance(result["note"], str) and result["note"]
    assert "create" in result["note"].lower() or "generate" in result["note"].lower()
    assert "categories" not in result
    assert set(result) == {"as_of", "framework", "thesis", "topics", "strongest_signal", "note"}


def test_empty_store_against_missing_file_does_not_raise(tmp_path):
    """No topics file at all is the same as an empty store."""
    result = bottleneck.bottleneck_read(_snapshot())
    assert result["topics"] == []


# ---- Ranking -----------------------------------------------------------------


def test_layers_ranked_by_40d_roc_descending_none_sinks():
    _store([_topic(upstream=[
        _layer("weak", ["WEAK"]),
        _layer("strong", ["STRONG"]),
        _layer("nodata", ["NODATA"]),
    ])])
    histories = {"STRONG": _ramp(100, 150), "WEAK": _ramp(100, 90)}

    layers = bottleneck.bottleneck_read(_snapshot(histories))["topics"][0]["upstream"]

    assert [layer["name"] for layer in layers] == ["strong", "weak", "nodata"]
    assert layers[0]["roc_40d_pct"] == 50.0
    assert layers[1]["roc_40d_pct"] == -10.0
    assert layers[2]["roc_40d_pct"] is None  # no data -> sinks, never 0


def test_layer_aggregate_is_the_mean_of_its_stocks_40d_roc():
    _store([_topic(upstream=[_layer("mixed", ["A", "B", "MISSING"])])])
    histories = {"A": _ramp(100, 150), "B": _ramp(100, 90)}

    layer = bottleneck.bottleneck_read(_snapshot(histories))["topics"][0]["upstream"][0]

    # (50.0 + -10.0) / 2 -- the missing stock is skipped, not treated as 0.
    assert layer["roc_40d_pct"] == 20.0
    assert layer["stocks"] == ["A", "B", "MISSING"]


# ---- gauge folding -----------------------------------------------------------


def test_gauge_is_gone_and_what_to_watch_carries_the_content():
    _store([_topic(upstream=[_layer(
        "foundry", ["TSM"],
        what_to_watch="EUV tool lead times, advanced-node pricing",
        physical_constraint="3nm/2nm wafer capacity",
    )])])

    layer = bottleneck.bottleneck_read(_snapshot())["topics"][0]["upstream"][0]

    assert "gauge" not in layer
    assert layer["what_to_watch"] == "EUV tool lead times, advanced-node pricing"
    assert layer["physical_constraint"] == "3nm/2nm wafer capacity"
    assert "gauge" not in _all_keys(bottleneck.bottleneck_read(_snapshot()))


def test_legacy_gauge_field_folds_into_what_to_watch():
    """A topic carrying the old ``gauge`` key degrades into ``what_to_watch``."""
    _store([_topic(upstream=[{"name": "legacy", "stocks": ["X"], "gauge": "old gauge text"}])])

    layer = bottleneck.bottleneck_read(_snapshot())["topics"][0]["upstream"][0]

    assert layer["what_to_watch"] == "old gauge text"
    assert "gauge" not in _all_keys(layer)


# ---- Anchors / underdogs -----------------------------------------------------


def test_anchors_are_unranked_and_order_stable():
    _store([_topic(anchor=[
        _card("WEAK", role="downstream", tier="anchor"),
        _card("STRONG", role="downstream", tier="anchor"),
    ])])
    histories = {"STRONG": _ramp(100, 200), "WEAK": _ramp(100, 80)}

    anchors = bottleneck.bottleneck_read(_snapshot(histories))["topics"][0]["downstream"]["anchor"]

    assert [card["ticker"] for card in anchors] == ["WEAK", "STRONG"]
    assert anchors[0]["tier"] == "anchor"


def test_underdogs_ranked_by_40d_roc_descending_none_sinks():
    _store([_topic(underdogs=[_card("WEAK"), _card("STRONG"), _card("NODATA")])])
    histories = {"STRONG": _ramp(100, 150), "WEAK": _ramp(100, 90)}

    underdogs = bottleneck.bottleneck_read(_snapshot(histories))["topics"][0]["downstream"]["underdogs"]

    assert [card["ticker"] for card in underdogs] == ["STRONG", "WEAK", "NODATA"]
    assert underdogs[0]["tier"] == "underdog"


def test_underdog_filtering_and_tier_labelling(_isolate_engine):
    _isolate_engine["metrics"] = {
        "CORE": {"market_cap": 1_000_000_000, "revenue_growth": None,
                 "forward_pe": None, "as_of": "2026-09-24T00:00:00+00:00"},
        "EXTENDED": {"market_cap": 5_000_000_000, "revenue_growth": None,
                     "forward_pe": None, "as_of": "2026-09-24T00:00:00+00:00"},
        "TOO_BIG": {"market_cap": 20_000_000_000, "revenue_growth": None,
                    "forward_pe": None, "as_of": "2026-09-24T00:00:00+00:00"},
        # "UNKNOWN" deliberately absent -> unavailable market cap.
    }
    _store([_topic(underdogs=[
        _card("TOO_BIG"), _card("CORE"), _card("EXTENDED"), _card("UNKNOWN"),
    ])])

    underdogs = bottleneck.bottleneck_read(_snapshot())["topics"][0]["downstream"]["underdogs"]
    by_ticker = {card["ticker"]: card for card in underdogs}

    # Above-ceiling is dropped; unavailable market cap stays.
    assert "TOO_BIG" not in by_ticker
    assert set(by_ticker) == {"CORE", "EXTENDED", "UNKNOWN"}
    assert by_ticker["CORE"]["conviction_tier"] == "core"
    assert by_ticker["EXTENDED"]["conviction_tier"] == "extended"
    # Unavailable market cap -> `None` tier (rendered —), NOT dropped and NOT guessed.
    assert by_ticker["UNKNOWN"]["conviction_tier"] is None
    assert by_ticker["UNKNOWN"]["metrics"]["market_cap"] is None


def test_underdog_ceiling_is_per_topic(_isolate_engine):
    _isolate_engine["metrics"] = {
        "MID": {"market_cap": 5_000_000_000, "revenue_growth": None,
                "forward_pe": None, "as_of": "2026-09-24T00:00:00+00:00"},
    }
    _store([
        _topic("tight", underdogs=[_card("MID")], ceiling=3_000_000_000),
        _topic("loose", underdogs=[_card("MID")], ceiling=10_000_000_000),
    ])

    topics = bottleneck.bottleneck_read(_snapshot())["topics"]

    assert topics[0]["downstream"]["underdogs"] == []  # $5B > $3B ceiling
    assert [c["ticker"] for c in topics[1]["downstream"]["underdogs"]] == ["MID"]


# ---- all_proxy_symbols -------------------------------------------------------


def test_all_proxy_symbols_empty_store():
    assert bottleneck.all_proxy_symbols() == []


def test_all_proxy_symbols_dynamic_deduped_order_stable():
    _store([_topic(
        upstream=[_layer("l1", ["AAA", "BBB"]), _layer("l2", ["BBB", "CCC"])],
        anchor=[_card("CCC"), _card("DDD")],
        underdogs=[_card("EEE")],
    )])

    assert bottleneck.all_proxy_symbols() == ["AAA", "BBB", "CCC", "DDD", "EEE"]


def test_all_proxy_symbols_ignores_blank_tickers():
    _store([_topic(upstream=[_layer("l1", ["AAA", "", "  "])], anchor=[_card("")])])

    assert bottleneck.all_proxy_symbols() == ["AAA"]


# ---- Purity ------------------------------------------------------------------


def test_bottleneck_read_makes_no_network_call(monkeypatch):
    """Pure read: a warm snapshot means neither yfinance nor get_history fires."""
    _store([_topic(upstream=[_layer("l1", ["AAA"])], anchor=[_card("AAA")])])
    histories = {"AAA": _ramp(100, 110)}

    def _tripwire(*args, **kwargs):
        raise AssertionError("bottleneck_read reached the market history path")

    class _NoYF:
        def __getattr__(self, name):
            raise AssertionError(f"bottleneck_read reached yfinance: {name}")

    monkeypatch.setattr(bottleneck.market, "get_history", _tripwire)
    monkeypatch.setattr(bottleneck.market, "_get_yf", lambda: _NoYF())

    result = bottleneck.bottleneck_read(_snapshot(histories))

    assert result["topics"][0]["upstream"][0]["roc_40d_pct"] == 10.0


def test_bottleneck_read_never_calls_ensure_metrics(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        bottleneck, "ensure_metrics",
        lambda tickers: called.__setitem__("n", called["n"] + 1),
    )
    bottleneck.bottleneck_read(_snapshot())
    assert called["n"] == 0


# ---- History fallback --------------------------------------------------------


def test_topic_ticker_missing_from_extra_uses_market_get_history(monkeypatch):
    _store([_topic(upstream=[_layer("l1", ["MISSING"])])])
    calls: list[tuple] = []

    def _fake_get_history(symbol, days=250, ttl=None):
        calls.append((symbol, days, ttl))
        return _ramp(100, 120)

    monkeypatch.setattr(bottleneck.market, "get_history", _fake_get_history)

    layer = bottleneck.bottleneck_read(_snapshot({}))["topics"][0]["upstream"][0]

    assert layer["roc_40d_pct"] == 20.0
    assert calls == [("MISSING", 250, bottleneck.config.HISTORY_TTL)]


def test_cache_miss_yields_none_momentum_not_an_invented_number():
    _store([_topic(underdogs=[_card("GONE")], anchor=[_card("GONE")])])
    # Default cold history cache (autouse fixture) -> [].
    result = bottleneck.bottleneck_read(_snapshot({}))

    assert result["topics"][0]["upstream"] == []
    anchor = result["topics"][0]["downstream"]["anchor"][0]
    underdog = result["topics"][0]["downstream"]["underdogs"][0]
    assert anchor["metrics"]["roc_40d"] is None
    assert underdog["metrics"]["roc_40d"] is None


# ---- Metrics / as_of ---------------------------------------------------------


def test_metrics_block_is_fully_shaped_with_per_ticker_as_of(_isolate_engine):
    as_of = "2026-09-24T00:00:00+00:00"
    _isolate_engine["metrics"] = {
        "AAA": {"market_cap": 1_000_000_000, "revenue_growth": 0.5,
                "forward_pe": -7.4, "as_of": as_of},
    }
    _store([_topic(anchor=[_card("AAA"), _card("ZZZ")])])

    anchors = bottleneck.bottleneck_read(_snapshot())["topics"][0]["downstream"]["anchor"]
    aaa, zzz = anchors

    assert set(aaa["metrics"]) == set(bottleneck_topics.METRIC_FIELDS)
    assert aaa["metrics"]["market_cap"] == 1_000_000_000
    assert aaa["metrics"]["forward_pe"] == -7.4  # signed is legitimate (loss-maker)
    assert aaa["metrics"]["revenue_growth"] == 0.5
    assert aaa["metrics"]["as_of"] == as_of

    # Ticker absent from the cache -> every value None, never fabricated.
    assert zzz["metrics"]["market_cap"] is None
    assert zzz["metrics"]["forward_pe"] is None
    assert zzz["metrics"]["revenue_growth"] is None
    assert zzz["metrics"]["as_of"] == "2026-09-25T00:00:00+00:00"  # read stamp


def test_forward_pe_matches_the_shared_valuation_cache_exactly(_isolate_engine):
    """Cross-view: the card cannot disagree with breadth_ai's cached PE."""
    _isolate_engine["metrics"] = {
        "AAA": {"market_cap": None, "revenue_growth": None,
                "forward_pe": 48.2, "as_of": "2026-09-24T00:00:00+00:00"},
    }
    # The stored card disagrees; the shared cache must win.
    _store([_topic(anchor=[_card("AAA", metrics={
        **{f: None for f in bottleneck_topics.METRIC_FIELDS}, "forward_pe": 99.9,
    })])])

    card = bottleneck.bottleneck_read(_snapshot())["topics"][0]["downstream"]["anchor"][0]

    assert card["metrics"]["forward_pe"] == 48.2


def test_one_year_move_metric_from_price_history():
    _store([_topic(anchor=[_card("AAA")])])

    card = bottleneck.bottleneck_read(_snapshot({"AAA": _ramp(100, 200, n=253)}))[
        "topics"
    ][0]["downstream"]["anchor"][0]

    assert card["metrics"]["move_1y"] == 100.0
    assert card["metrics"]["roc_40d"] == 100.0


# ---- strongest_signal --------------------------------------------------------


def test_strongest_signal_none_when_nothing_scored():
    _store([_topic(upstream=[_layer("l1", ["NODATA"])])])

    assert bottleneck.bottleneck_read(_snapshot())["strongest_signal"] is None


def test_strongest_signal_picks_the_top_upstream_layer_across_topics():
    _store([
        _topic("t1", upstream=[_layer("mid", ["MID"])]),
        _topic("t2", upstream=[_layer("top", ["TOP"])]),
    ])
    histories = {"MID": _ramp(100, 120), "TOP": _ramp(100, 175)}

    strongest = bottleneck.bottleneck_read(_snapshot(histories))["strongest_signal"]

    assert strongest["name"] == "top"
    assert strongest["roc_40d_pct"] == 75.0
    assert strongest["topic_name"] == "t2"


def test_strongest_signal_ignores_downstream_only_topics():
    _store([_topic(anchor=[_card("AAA")])])

    assert bottleneck.bottleneck_read(_snapshot({"AAA": _ramp(100, 200)}))["strongest_signal"] is None


# ---- ensure_metrics (refresh-path helper, never called by the read) ---------


def test_ensure_metrics_populates_via_fetch_ticker_metrics(monkeypatch):
    calls: list[list[str]] = []

    def _fake_fetch(symbols, *, force=False):
        calls.append(list(symbols))
        return {symbol: {"market_cap": None} for symbol in symbols}

    monkeypatch.setattr(ai_valuation, "fetch_ticker_metrics", _fake_fetch)

    assert bottleneck.ensure_metrics(["A", "A", "B", ""]) == {"A": {"market_cap": None},
                                                             "B": {"market_cap": None}}
    assert calls == [["A", "B"]]
    # Empty input must not touch the fetcher at all.
    assert bottleneck.ensure_metrics([]) == {}
    assert calls == [["A", "B"]]
