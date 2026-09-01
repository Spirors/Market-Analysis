"""Tests for the serenity-style bottleneck section."""

from app import bottleneck


EXPECTED_CATEGORIES = [
    "Agentic AI",
    "Autonomous Driving",
    "AI gadgets",
    "Power / data-center infrastructure",
    "Robots",
]

REQUIRED_LAYER_KEYS = {"layer", "proxies", "gauge", "why_scarce"}


def test_bottleneck_has_categories_structure():
    """The bottleneck module exposes a hierarchical category structure."""
    assert hasattr(bottleneck, "BOTTLENECK_CATEGORIES")
    cats = bottleneck.BOTTLENECK_CATEGORIES
    assert len(cats) == len(EXPECTED_CATEGORIES)
    assert [c["category"] for c in cats] == EXPECTED_CATEGORIES


def test_each_category_has_upstream_and_downstream_streams():
    """Every category contains upstream and downstream layer lists."""
    for cat in bottleneck.BOTTLENECK_CATEGORIES:
        assert "streams" in cat
        streams = cat["streams"]
        assert "upstream" in streams
        assert "downstream" in streams
        assert isinstance(streams["upstream"], list)
        assert isinstance(streams["downstream"], list)
        assert len(streams["upstream"]) > 0
        assert len(streams["downstream"]) > 0


def test_each_layer_has_required_fields():
    """Every chokepoint layer specifies proxies, gauge, and scarcity logic."""
    for cat in bottleneck.BOTTLENECK_CATEGORIES:
        for stream_name in ("upstream", "downstream"):
            for layer in cat["streams"][stream_name]:
                missing = REQUIRED_LAYER_KEYS - set(layer.keys())
                assert not missing, f"Missing keys {missing} in {cat['category']} {stream_name} layer"
                assert isinstance(layer["proxies"], list)
                assert len(layer["proxies"]) > 0
                assert isinstance(layer["layer"], str)
                assert isinstance(layer["gauge"], str)
                assert isinstance(layer["why_scarce"], str)
