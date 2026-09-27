"""Tests for the AI capex cycle sentiment gauge."""

from app import ai_sentiment, config


def test_ai_news_sentiment_empty():
    result = ai_sentiment.compute_ai_news_sentiment([])
    assert result["score"] == 0
    assert result["tone"] == "neutral"
    assert result["event_count"] == 0


def test_ai_news_sentiment_bullish_event():
    events = [
        {"title": "Nvidia posts record AI revenue", "summary": "", "direction": "bullish", "impact": "Critical"},
    ]
    result = ai_sentiment.compute_ai_news_sentiment(events)
    assert result["score"] > 20
    assert result["tone"] == "bullish"
    assert result["event_count"] == 1


def test_ai_news_sentiment_ignores_non_ai():
    events = [
        {"title": "Fed holds rates steady", "summary": "", "direction": "bearish", "impact": "Critical"},
    ]
    result = ai_sentiment.compute_ai_news_sentiment(events)
    assert result["score"] == 0
    assert result["event_count"] == 0


def test_cohort_tone_bullish():
    tone, note = ai_sentiment._cohort_tone(10.0, 60.0)
    assert tone == "bullish"


def test_cohort_tone_bearish_poor_breadth():
    tone, note = ai_sentiment._cohort_tone(5.0, 0.0)
    assert tone == "bearish"


def test_cohort_tone_missing_either_input_is_unknown():
    """Missing data must read 'unknown', never a fabricated neutral."""
    assert ai_sentiment._cohort_tone(None, 60.0)[0] == "unknown"
    assert ai_sentiment._cohort_tone(10.0, None)[0] == "unknown"
    assert ai_sentiment._cohort_tone(None, None)[0] == "unknown"


def test_ai_capex_cohorts_defined():
    assert "Capex Spenders" in config.AI_CAPEX_COHORTS
    assert "Compute / Accelerators" in config.AI_CAPEX_COHORTS
    for tickers in config.AI_CAPEX_COHORTS.values():
        assert len(tickers) > 0


# ---- AI keyword coverage ----------------------------------------------------
# These exercise the keyword list behind both the gauge's event filter
# (compute_ai_news_sentiment) and the timeline's auto "ai" tag (app/store.py).

import re


def _is_ai(text: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(k)}\b", text.lower())
        for k in config.AI_NEWS_KEYWORDS
    )


def test_ai_keyword_coverage_model_families():
    assert _is_ai("OpenAI unveils new GPT model")
    assert _is_ai("Anthropic releases Claude update")
    assert _is_ai("Google ships Gemini for enterprise")
    assert _is_ai("Mistral and DeepSeek race for cheaper LLMs")


def test_ai_keyword_coverage_hardware_vendors():
    assert _is_ai("Nvidia Blackwell GPU ramps at TSMC")
    assert _is_ai("AMD MI300 accelerator wins hyperscaler deal")
    assert _is_ai("ASML books orders as foundry capacity expands")
    assert _is_ai("Micron HBM3E memory sells out")
    assert _is_ai("Intel arm asml chip foundry buildout")


def test_ai_keyword_coverage_cloud_hyperscale():
    assert _is_ai("Microsoft Azure capacity expansion announced")
    assert _is_ai("AWS invests in new data center buildout")
    assert _is_ai("Oracle Cloud hyperscaler spend accelerates")


def test_ai_keyword_coverage_training_concepts():
    assert _is_ai("neural network training costs surge")
    assert _is_ai("inference workload shifts data center demand")
    assert _is_ai("foundation model developer raises funding")
    assert _is_ai("agentic copilot agents launch in beta")


def test_ai_keyword_coverage_power_grid():
    assert _is_ai("data center power demand strains grid")
    assert _is_ai("nuclear and SMR deals signed for AI campuses")


def test_ai_keyword_coverage_omits_unrelated_finance():
    # Pure macro / non-AI headlines must NOT trip the keyword filter.
    assert not _is_ai("Fed holds rates steady, treasury yields fall")
    assert not _is_ai("oil surge fuels inflation fears")
    assert not _is_ai("recession concerns weigh on wall street")


def test_ai_sentiment_uses_model_family_keyword():
    """The gauge must count model-lab headlines as AI events, not just
    hardware names. Previously the list only covered hardware vendors."""
    events = [
        {
            "title": "OpenAI GPT-5 release drives datacenter capex",
            "summary": "",
            "direction": "bullish",
            "impact": "Critical",
        },
    ]
    result = ai_sentiment.compute_ai_news_sentiment(events)
    assert result["event_count"] == 1
    assert result["tone"] == "bullish"


# ---- AI valuation integration ------------------------------------------------

def _minimal_snapshot():
    """Snapshot with empty histories so compute_ai_sentiment gets score ~0.

    The cohort ROC/breadth legs require >=2 tickers with >=63 history
    entries each; empty lists produce None ROCs, leaving score near zero.
    This isolates the valuation score-shift logic.
    """
    all_hist: dict[str, list] = {}
    for tickers in config.AI_CAPEX_COHORTS.values():
        for t in tickers:
            all_hist[t] = []
    return {"histories": {"extra": all_hist}}


def test_compute_ai_sentiment_valuation_stretched_adds_score_shift():
    """When valuation.stretched is True, score += AI_VALUATION_SCORE_SHIFT."""
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    with_stretch = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 35.0, "stretched": True, "note": "x"},
    )
    assert with_stretch["score"] == round(base["score"] + config.AI_VALUATION_SCORE_SHIFT, 1)


def test_compute_ai_sentiment_valuation_not_stretched_no_shift():
    """valuation.stretched=False -> score unchanged."""
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    with_valuation = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 22.0, "stretched": False, "note": "ok"},
    )
    assert with_valuation["score"] == base["score"]


def test_compute_ai_sentiment_valuation_missing_no_shift():
    """valuation=None (or omitted) -> score unchanged."""
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    explicit_none = ai_sentiment.compute_ai_sentiment(snap, events, valuation=None)
    assert explicit_none["score"] == base["score"]


def test_compute_ai_sentiment_output_includes_valuation_dict():
    """The returned dict always carries the valuation summary, even when no shift applies."""
    snap = _minimal_snapshot()
    events = []
    out = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 25.0, "stretched": False, "note": "ok"},
    )
    assert "valuation" in out
    assert out["valuation"]["median_pe"] == 25.0
    assert out["valuation"]["stretched"] is False


# ---- 02-M: valuation cache age reaches the wire -----------------------------

def test_compute_ai_sentiment_threads_valuation_cache_age():
    """The valuation summary must carry the PE cache age keys the frontend
    reads (frozen contract: ``ai.valuation.fetched_at`` and
    ``ai.valuation.cache_ttl_hours``). The gauge previously copied only
    median_pe/stretched/note, so the age was unreachable."""
    out = ai_sentiment.compute_ai_sentiment(
        _minimal_snapshot(),
        [],
        valuation={
            "median_pe": 25.0,
            "stretched": False,
            "note": "ok",
            "fetched_at": "2026-09-25T12:00:00",
            "cache_ttl_hours": 12,
        },
    )
    assert out["valuation"]["fetched_at"] == "2026-09-25T12:00:00"
    assert out["valuation"]["cache_ttl_hours"] == 12


def test_compute_ai_sentiment_valuation_age_keys_nullable():
    """Both age keys are present and null when the valuation is absent or
    carries no age — the frozen contract is nullable, never key-absent."""
    no_valuation = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [], valuation=None)
    assert no_valuation["valuation"]["fetched_at"] is None
    assert no_valuation["valuation"]["cache_ttl_hours"] is None

    age_less = ai_sentiment.compute_ai_sentiment(
        _minimal_snapshot(), [], valuation={"median_pe": 20.0, "note": "x"}
    )
    assert age_less["valuation"]["fetched_at"] is None
    assert age_less["valuation"]["cache_ttl_hours"] is None


# ---- 02-R: verdict cutoff contract ------------------------------------------
# The verdict bands (config.AI_SENTIMENT_VERDICT_CUTOFFS = (60, 20)) are the
# gauge's user-facing classification, but had no boundary coverage. The helper
# below isolates the band logic deterministically: stubbing every cohort's
# equal-weight ROC at one value R makes the composite collapse to
# score = R * AI_SENTIMENT_ROC_WEIGHT (spread is R - R = 0, news score is 0),
# so exact band edges can be asserted without reverse-engineering histories.


def _verdict_for_constant_roc(monkeypatch, roc_value: float):
    """Return (score, verdict) for a snapshot whose every cohort ROC == roc_value."""
    monkeypatch.setattr(ai_sentiment, "_eq_weight_roc",
                        lambda histories, tickers: roc_value)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    return out["score"], out["verdict"]


def test_verdict_bands_exact_cutoffs(monkeypatch):
    """Exactly +60 / +20 / -20 / -60 land IN the band they open (>=)."""
    assert _verdict_for_constant_roc(monkeypatch, 30.0) == (60.0, "Euphoric / fragility setup")
    assert _verdict_for_constant_roc(monkeypatch, 10.0) == (20.0, "Healthy expansion")
    assert _verdict_for_constant_roc(monkeypatch, 0.0) == (0.0, "Balanced / mixed")
    assert _verdict_for_constant_roc(monkeypatch, -10.0) == (-20.0, "Balanced / mixed")
    assert _verdict_for_constant_roc(monkeypatch, -30.0) == (-60.0, "Cooling / divergence")


def test_verdict_bands_just_inside_each_edge(monkeypatch):
    """One tick inside every cutoff stays in the lower band."""
    assert _verdict_for_constant_roc(monkeypatch, 29.95) == (59.9, "Healthy expansion")
    assert _verdict_for_constant_roc(monkeypatch, 9.95) == (19.9, "Balanced / mixed")
    assert _verdict_for_constant_roc(monkeypatch, -9.95) == (-19.9, "Balanced / mixed")
    assert _verdict_for_constant_roc(monkeypatch, -29.95) == (-59.9, "Cooling / divergence")


def test_verdict_bands_just_outside_each_edge(monkeypatch):
    """One tick past a cutoff promotes to the next band."""
    assert _verdict_for_constant_roc(monkeypatch, 30.05) == (60.1, "Euphoric / fragility setup")
    assert _verdict_for_constant_roc(monkeypatch, 10.05) == (20.1, "Healthy expansion")
    assert _verdict_for_constant_roc(monkeypatch, -10.05) == (-20.1, "Cooling / divergence")
    assert _verdict_for_constant_roc(monkeypatch, -30.05) == (-60.1, "Cycle under pressure")


def test_verdict_score_clamps_to_pm_100(monkeypatch):
    """Extreme ROC cannot push the score past ±100, and the verdict follows
    the clamped score."""
    assert _verdict_for_constant_roc(monkeypatch, 500.0) == (100.0, "Euphoric / fragility setup")
    assert _verdict_for_constant_roc(monkeypatch, -500.0) == (-100.0, "Cycle under pressure")


def test_verdict_reclassified_after_valuation_shift(monkeypatch):
    """The band is applied to the FINAL score, after the valuation +25 shift —
    a Balanced reading can become Healthy, and a Healthy reading Euphoric."""
    monkeypatch.setattr(ai_sentiment, "_eq_weight_roc", lambda histories, tickers: 0.0)
    base = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert (base["score"], base["verdict"]) == (0.0, "Balanced / mixed")

    stretched = {"median_pe": 35.0, "stretched": True, "note": "x"}
    shifted = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [], valuation=stretched)
    assert (shifted["score"], shifted["verdict"]) == (25.0, "Healthy expansion")

    monkeypatch.setattr(ai_sentiment, "_eq_weight_roc", lambda histories, tickers: 29.95)
    near_edge = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [], valuation=stretched)
    assert (near_edge["score"], near_edge["verdict"]) == (84.9, "Euphoric / fragility setup")


# ---- 02-R: spread_pct contract ----------------------------------------------

def _cohort_roc_map(monkeypatch, mapping: dict):
    """Stub per-cohort ROC by the cohort's exact ticker tuple (absent -> None)."""
    monkeypatch.setattr(ai_sentiment, "_eq_weight_roc",
                        lambda histories, tickers: mapping.get(tuple(tickers)))


def _cohort_key(name: str) -> tuple:
    return tuple(config.AI_CAPEX_COHORTS[name])


def test_spread_pct_is_beneficiary_mean_minus_spenders(monkeypatch):
    mapping = {_cohort_key(n): 10.0 for n in config.AI_CAPEX_COHORTS}
    mapping[_cohort_key("Capex Spenders")] = 30.0
    _cohort_roc_map(monkeypatch, mapping)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert out["spread_pct"] == -20.0


def test_spread_pct_ignores_missing_beneficiary_cohorts(monkeypatch):
    """A beneficiary cohort without data is skipped, not counted as 0."""
    mapping = {_cohort_key(n): 10.0 for n in config.AI_CAPEX_COHORTS}
    mapping[_cohort_key("Capex Spenders")] = 30.0
    mapping[_cohort_key("Memory")] = None
    _cohort_roc_map(monkeypatch, mapping)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert out["spread_pct"] == -20.0


def test_spread_pct_none_when_spenders_missing(monkeypatch):
    mapping = {_cohort_key(n): 10.0 for n in config.AI_CAPEX_COHORTS}
    mapping[_cohort_key("Capex Spenders")] = None
    _cohort_roc_map(monkeypatch, mapping)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert out["spread_pct"] is None


def test_spread_pct_none_when_all_beneficiaries_missing(monkeypatch):
    mapping = {_cohort_key("Capex Spenders"): 30.0}
    _cohort_roc_map(monkeypatch, mapping)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert out["spread_pct"] is None


# ---- 02-R: cohort + top-level payload shape ---------------------------------

def test_cohort_payload_shape_and_order():
    """One dict per config cohort, in config order, with the frozen keys; on
    a data-less cohort every leg is null/unknown, never a fabricated neutral."""
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert [c["name"] for c in out["cohorts"]] == list(config.AI_CAPEX_COHORTS.keys())
    for c in out["cohorts"]:
        assert set(c) == {"name", "roc_3m_pct", "breadth_pct", "tone", "note"}
        assert c["roc_3m_pct"] is None
        assert c["breadth_pct"] is None
        assert c["tone"] == "unknown"
        assert c["note"] == "insufficient data"


def test_cohort_payload_carries_tone_and_note(monkeypatch):
    """When data is present the payload carries the _cohort_tone verdict and
    its human note."""
    monkeypatch.setattr(ai_sentiment, "_eq_weight_roc", lambda h, t: 10.0)
    monkeypatch.setattr(ai_sentiment, "breadth_pct_above_ma",
                        lambda h, w, symbols=None: 60.0)
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    for c in out["cohorts"]:
        assert c["roc_3m_pct"] == 10.0
        assert c["breadth_pct"] == 60.0
        assert c["tone"] == "bullish"
        assert c["note"] == "strong momentum + broad participation"


def test_top_level_payload_shape():
    out = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])
    assert set(out) == {
        "as_of", "score", "verdict", "cohorts",
        "spread_pct", "news", "valuation", "flip_conditions",
    }


def test_flip_conditions_contract():
    """The three canned flip conditions are stable and non-empty."""
    conds = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])["flip_conditions"]
    assert isinstance(conds, list)
    assert conds == [
        "Beneficiaries' 3m ROC flips below spenders' (spread turns negative)",
        "Breadth across beneficiary cohorts drops below 40%",
        "AI news tone turns decisively bearish",
    ]
    assert all(isinstance(c, str) and c.strip() for c in conds)


# ---- 02-R: news note / event_count contract ---------------------------------

def test_news_shape_and_empty_note():
    news = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), [])["news"]
    assert set(news) == {"score", "event_count", "tone", "note"}
    assert news["score"] == 0
    assert news["event_count"] == 0
    assert news["tone"] == "neutral"
    assert news["note"] == "no AI-relevant events"


def test_news_event_count_and_note_count_only_ai_events():
    """Non-AI events are excluded from both event_count and the note's count."""
    events = [
        {"title": "Nvidia AI chip demand surges", "summary": "", "direction": "bullish", "impact": "High"},
        {"title": "Fed holds rates steady", "summary": "", "direction": "bearish", "impact": "Critical"},
        {"title": "OpenAI ships new model", "summary": "", "direction": "neutral", "impact": "Low"},
    ]
    news = ai_sentiment.compute_ai_sentiment(_minimal_snapshot(), events)["news"]
    assert news["event_count"] == 2
    assert news["note"] == "2 AI-relevant events"


def test_news_tone_boundary_at_20_is_neutral():
    """A net score of exactly ±20 is still neutral (tone needs > 20)."""
    bull = ai_sentiment.compute_ai_news_sentiment(
        [{"title": "Nvidia AI demand", "summary": "", "direction": "bullish", "impact": "High"}]
    )
    assert (bull["score"], bull["tone"]) == (20.0, "neutral")

    bear = ai_sentiment.compute_ai_news_sentiment(
        [{"title": "Nvidia AI demand", "summary": "", "direction": "bearish", "impact": "High"}]
    )
    assert (bear["score"], bear["tone"]) == (-20.0, "neutral")
