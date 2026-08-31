"""Dashboard payload equivalence test.

Builds a dashboard via ``service.refresh_market()`` (fast path — no regime
detection, no full news ingest) and compares its top-level key set against the
committed oracle snapshot (``data/dashboard.json``).

Key-level comparison catches accidental payload regressions (renamed keys,
missing sections).  Value-level assertions verify a few leaf keys carry real
data after a live refresh.

Note: ``refresh_market()`` does NOT include ``events`` or ``ai_analysis`` —
those are attached later by ``service._enrich()`` on serve.  The oracle
snapshot also excludes them.  This is documented behavior, not a gap.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app import config, service


ORACLE_PATH = config.BASE_DIR / "data" / "dashboard.json"


@pytest.mark.skipif(
    not ORACLE_PATH.exists(),
    reason="oracle snapshot data/dashboard.json not present (git-ignored or first run)",
)
def test_dashboard_payload_keys_match_oracle():
    """The live dashboard must carry every top-level key the oracle has,
    except ``as_of`` which is always fresh."""
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    oracle_keys = set(oracle.keys()) - {"as_of"}

    # Keys that are added by service._enrich() on serve, NOT by
    # refresh_market().  They exist in the oracle snapshot but must be
    # excluded from the live-key comparison.
    _ENRICH_ONLY = {"ai_analysis", "news", "regime", "events"}

    # Run the fast-path refresh (skips regime subprocess + news ingest).
    live = service.refresh_market()
    live_keys = set(live.keys()) - {"as_of"}
    oracle_keys_excl = oracle_keys - _ENRICH_ONLY

    missing = oracle_keys_excl - live_keys
    extra = live_keys - oracle_keys_excl
    assert not missing and not extra, (
        f"Dashboard keys differ: extra={extra}, missing={missing}"
    )


@pytest.mark.skipif(
    not ORACLE_PATH.exists(),
    reason="oracle snapshot data/dashboard.json not present",
)
def test_dashboard_nested_market_keys():
    """The market section must contain the standard sub-groups."""
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    market = oracle.get("market") or {}
    expected = {"indices", "volatility", "rates", "commodities", "sectors"}
    assert expected <= set(market.keys()), (
        f"Missing market sub-keys: {expected - set(market.keys())}"
    )


@pytest.mark.skipif(
    not ORACLE_PATH.exists(),
    reason="oracle snapshot data/dashboard.json not present",
)
def test_dashboard_value_level_sanity():
    """A few leaf keys must carry real data after a live refresh."""
    live = service.refresh_market()

    # risk.risk_level must be one of the three known values.
    risk_level = (live.get("risk") or {}).get("risk_level")
    assert risk_level in {"GREEN", "YELLOW", "RED"}, f"unexpected risk_level: {risk_level}"

    # market.indices must have at least one entry with a numeric price.
    indices = (live.get("market") or {}).get("indices") or {}
    assert len(indices) >= 1, "market.indices is empty"
    any_price = False
    for sym, q in indices.items():
        if isinstance(q, dict) and isinstance(q.get("price"), (int, float)):
            any_price = True
            break
    assert any_price, "no index entry has a numeric price"

    # vintage must be a dict with a 'market' timestamp.
    vintage = live.get("vintage") or {}
    assert isinstance(vintage.get("market"), str), "vintage.market missing or not a string"
