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
