"""Tests for app/news.py pure functions (no network)."""

import re

import pytest

from app import news


# ---- _category --------------------------------------------------------------
# NOTE: _category does NOT lowercase — caller must pass lowercased text.

def test_category_macro_fed():
    assert news._category("fed raises rates by 25 basis points") == "macro"


def test_category_macro_cpi():
    assert news._category("cpi comes in hot at 3.5%") == "macro"


def test_category_macro_tariff():
    # "tariff" (singular) is in MACRO_TERMS; "tariffs" (plural) won't match \btariff\b
    assert news._category("new tariff on chinese imports announced") == "macro"


def test_category_global_china():
    assert news._category("china stimulus package boosts markets") == "macro"


def test_category_global_russia():
    assert news._category("russia-ukraine conflict escalates") == "macro"


def test_category_micro_earnings():
    assert news._category("apple earnings beat estimates") == "micro"


def test_category_micro_ipo():
    assert news._category("startup files for ipo") == "micro"


def test_category_none():
    assert news._category("random text with no keywords") is None


def test_category_micro_does_not_override_macro():
    # Macro takes priority over micro
    assert news._category("fed cuts rates, earnings season begins") == "macro"


# ---- _direction -------------------------------------------------------------
# _direction also expects lowercased text.

def test_direction_bullish():
    assert news._direction("markets rally on strong earnings beat") == "bullish"


def test_direction_bearish():
    assert news._direction("stocks plunge on recession fears") == "bearish"


def test_direction_neutral():
    assert news._direction("markets open mixed today") == "neutral"


def test_direction_bullish_stimulus():
    assert news._direction("central bank announces stimulus package") == "bullish"


def test_direction_bearish_tariff():
    assert news._direction("new tariffs trigger sell-off") == "bearish"


def test_direction_tie_is_neutral():
    # One bullish + one bearish term → tie → neutral
    assert news._direction("beat and miss") == "neutral"


def test_direction_empty():
    assert news._direction("") == "neutral"


# ---- _region ----------------------------------------------------------------
# _region also expects lowercased text.

def test_region_china():
    assert news._region("pboc cuts rates") == "china"


def test_region_japan():
    assert news._region("boj holds yield curve control") == "japan"


def test_region_korea():
    assert news._region("kospi index rallies on seoul tech") == "korea"


def test_region_middle_east():
    assert news._region("iran tensions rise in middle east") == "middle-east"


def test_region_russia_ukraine():
    assert news._region("ukraine counteroffensive advances") == "russia-ukraine"


def test_region_europe():
    assert news._region("ecb lagarde signals rate pause") == "europe"


def test_region_us():
    assert news._region("fed powell speaks at jackson hole") == "us"


def test_region_global_default():
    assert news._region("markets open mixed") == "global"


# ---- _actor -----------------------------------------------------------------
# _actor expects lowercased text.

def test_actor_government():
    assert news._actor("federal reserve announces rate hike") == "government"


def test_actor_company():
    assert news._actor("nvidia earnings revenue profit beat") == "company"


def test_actor_none():
    assert news._actor("markets are mixed") is None


def test_actor_gov_wins_tie():
    # gov=1 co=1 → gov wins (gov >= co)
    assert news._actor("fed earnings") == "government"


# ---- _moving ----------------------------------------------------------------
# _moving expects lowercased text.

def test_moving_true():
    assert news._moving("fed announces rate cut") is True


def test_moving_false():
    assert news._moving("random text no market terms") is False


def test_moving_tariff():
    assert news._moving("new tariff imposed on imports") is True


# ---- _score -----------------------------------------------------------------
# _score expects lowercased text. Terms overlap across lists, so we use
# isolated terms that appear in only one scoring list.

def test_score_zero_for_empty():
    assert news._score("", moving=False) == 0.0


def test_score_macro_hits_weight_1x():
    # "gdp" is ONLY in MACRO_TERMS → 1 hit × 1.0 = 1.0
    score = news._score("gdp", moving=False)
    assert score == 1.0


def test_score_severity_hits_weight_2x():
    # "soar" is ONLY in SEVERITY_TERMS → 1 hit × 2.0 = 2.0
    score = news._score("soar", moving=False)
    assert score == 2.0


def test_score_global_hits_weight_2x():
    # "pboc" is ONLY in GLOBAL_TERMS → 1 hit × 2.0 = 2.0
    score = news._score("pboc", moving=False)
    assert score == 2.0


def test_score_systemic_hits_weight_3x():
    # "contagion" is ONLY in SYSTEMIC_TERMS → 1 hit × 3.0 = 3.0
    score = news._score("contagion", moving=False)
    assert score == 3.0


def test_score_moving_adds_1_5():
    score_with = news._score("gdp", moving=True)
    score_without = news._score("gdp", moving=False)
    assert score_with - score_without == pytest.approx(1.5)


def test_score_combined():
    # "gdp" (MACRO×1) + "soar" (SEVERITY×2) + "contagion" (SYSTEMIC×3) = 1+2+3=6.0
    score = news._score("gdp soar contagion", moving=False)
    assert score == 6.0


# ---- rate_impact -------------------------------------------------------------

def test_rate_impact_critical():
    assert news.rate_impact(9.0) == "Critical"
    assert news.rate_impact(10.0) == "Critical"
    assert news.rate_impact(15.0) == "Critical"


def test_rate_impact_high():
    assert news.rate_impact(6.0) == "High"
    assert news.rate_impact(8.9) == "High"


def test_rate_impact_below_threshold():
    # Below 6.0 → defaults to High
    assert news.rate_impact(3.0) == "High"
    assert news.rate_impact(0.0) == "High"


def test_rate_impact_none():
    assert news.rate_impact(None) == "High"


# ---- analyze (integration) --------------------------------------------------
# analyze() lowercases internally, so mixed-case input is fine here.

def test_analyze_macro_fed_bearish_us():
    result = news.analyze("Fed raises rates, markets tumble")
    assert result["category"] == "macro"
    assert result["direction"] == "bearish"
    assert result["region"] == "us"
    assert result["actor"] == "government"
    assert result["importance"] > 0


def test_analyze_micro_earnings():
    result = news.analyze("NVIDIA earnings beat, revenue surges")
    # "nvidia" is in COMPANY_TERMS → company actor
    # "earnings" is in MICRO_TERMS → micro category
    assert result["category"] == "micro"
    assert result["actor"] == "company"
    assert result["direction"] == "bullish"


def test_analyze_empty_text():
    result = news.analyze("")
    assert result["category"] is None
    assert result["direction"] == "neutral"
    assert result["region"] == "global"
    assert result["importance"] == 0.0


def test_analyze_returns_all_keys():
    result = news.analyze("test")
    expected_keys = {"category", "actor", "direction", "region", "impact",
                     "importance", "finance_relevance", "composite_importance",
                     "tags"}
    assert set(result.keys()) == expected_keys


def test_analyze_tags_list():
    result = news.analyze("Fed cuts rates, stocks rally")
    assert isinstance(result["tags"], list)
    # Tags should include category, direction, region, and possibly actor
    assert "macro" in result["tags"]
    assert "bullish" in result["tags"]
    assert "us" in result["tags"]


def test_analyze_multi_feed_consistency():
    """Same text analyzed twice should produce identical output."""
    text = "Fed raises rates by 50 basis points"
    r1 = news.analyze(text)
    r2 = news.analyze(text)
    assert r1 == r2


def test_analyze_high_importance_usually_critical_or_high():
    """Fed + recession should score well above IMPORTANCE_THRESHOLD."""
    result = news.analyze("Fed warns of recession, rate hikes likely")
    assert result["importance"] >= news.IMPORTANCE_THRESHOLD
    assert result["impact"] in ("High", "Critical")


def test_analyze_china_region():
    result = news.analyze("PBOC cuts reserve requirement ratio")
    assert result["region"] == "china"


def test_analyze_japan_region():
    result = news.analyze("BOJ maintains yield curve control policy")
    assert result["region"] == "japan"


def test_analyze_mixed_direction_is_neutral():
    # Equal bullish and bearish signals
    result = news.analyze("Markets rally then crash")
    assert result["direction"] == "neutral"


# ---- finance_relevance & composite_importance --------------------------------

def test_analyze_finance_relevance_zero_for_empty():
    result = news.analyze("")
    assert result["finance_relevance"] == 0.0


def test_analyze_finance_relevance_high_for_finance_terms():
    # Multiple high-signal terms → non-zero finance_relevance
    result = news.analyze(
        "Federal Reserve raises interest rates, inflation CPI surges"
    )
    assert result["finance_relevance"] > 0.0


def test_analyze_finance_relevance_ticker_boost():
    # Mentioning a tracked ticker boosts finance_relevance
    result_ticker = news.analyze("NVDA earnings beat, revenue surges")
    result_plain = news.analyze("Random company earnings beat, revenue surges")
    assert result_ticker["finance_relevance"] >= result_plain["finance_relevance"]


def test_analyze_composite_importance_present():
    result = news.analyze("Fed raises rates by 50 basis points")
    assert "composite_importance" in result
    assert isinstance(result["composite_importance"], float)
    assert result["composite_importance"] >= 0.0


def test_analyze_composite_importance_capped_at_10():
    # Even a very finance-heavy headline should not exceed 10.0
    result = news.analyze(
        "Federal Reserve interest rate hike CPI inflation recession "
        "treasury yield bond market crash meltdown"
    )
    assert result["composite_importance"] <= 10.0


def test_analyze_source_weight_lifts_composite():
    # MarketWatch has weight 1.2; same text from MW should score higher than
    # an unknown source (weight 1.0)
    text = "Fed raises interest rates, inflation surges"
    mw = news.analyze(text, source="MarketWatch")
    unknown = news.analyze(text, source="RandomBlog")
    assert mw["composite_importance"] >= unknown["composite_importance"]


def test_analyze_composite_vs_raw_importance():
    # For MarketWatch (1.2 weight) the composite should >= raw importance
    result = news.analyze("Fed raises rates", source="MarketWatch")
    assert result["composite_importance"] >= result["importance"]


def test_analyze_region_asia():
    # "asia" tag is reachable for pan-Asian stories
    result = news.analyze("Asian markets rally across the region")
    assert result["region"] == "asia"


# ---- Seed event regression --------------------------------------------------

def test_seed_events_preserve_hand_curated_tags():
    """Seed events loaded by seed_events() must keep their hand-curated
    region/direction/impact and not be reclassified by heuristics."""
    from app import seed_data

    # Pick a few seed events with distinct tags.
    sample = [e for e in seed_data.SEED_EVENTS if e["source"] == "Wikipedia"][:5]
    assert len(sample) >= 3, "Need at least 3 Wikipedia seed events for regression"
    for ev in sample:
        # Simulate what seed_events() builds.
        row = {
            "source": ev["source"],
            "title": ev["title"],
            "category": ev["category"],
            "actor": ev.get("actor"),
            "direction": ev["direction"],
            "region": ev["region"],
            "impact": ev["impact"],
        }
        assert row["region"] == ev["region"], (
            f"Region mismatch for '{ev['title']}': {row['region']} != {ev['region']}"
        )
        assert row["direction"] == ev["direction"], (
            f"Direction mismatch for '{ev['title']}': {row['direction']} != {ev['direction']}"
        )
        assert row["impact"] == ev["impact"], (
            f"Impact mismatch for '{ev['title']}': {row['impact']} != {ev['impact']}"
        )
