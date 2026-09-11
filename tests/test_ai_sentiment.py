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
